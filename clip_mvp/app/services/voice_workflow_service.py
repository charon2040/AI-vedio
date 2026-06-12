from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, List

from app.core.config import settings
from app.services.asr_service import asr_service
from app.services.llm_service import llm_service
from app.services.media_service import media_service
from app.services.tts_cache_service import tts_cache_service
from app.services.tts_service import tts_service


logger = logging.getLogger(__name__)

UpdateTaskCallback = Callable[..., Dict[str, Any]]


class VoiceWorkflowService:
    def _beat_text_weight(self, text: str) -> int:
        return max(1, len("".join(str(text or "").split())))

    def _allocate_durations(self, *, beats: List[Dict[str, Any]], total_duration_ms: int) -> List[int]:
        total_ms = max(1, int(total_duration_ms or 0))
        weights = [
            self._beat_text_weight(str(beat.get("text", "") or ""))
            for beat in beats
            if str(beat.get("text", "") or "").strip()
        ]
        if not weights:
            return []

        weight_total = max(1, sum(weights))
        durations: List[int] = []
        remaining_ms = total_ms
        for index, weight in enumerate(weights):
            remaining_count = len(weights) - index
            if remaining_count == 1:
                duration_ms = max(1, remaining_ms)
            else:
                raw_ms = max(1, int(total_ms * (weight / weight_total)))
                max_for_this = max(1, remaining_ms - (remaining_count - 1))
                duration_ms = min(raw_ms, max_for_this)
            durations.append(duration_ms)
            remaining_ms = max(0, remaining_ms - duration_ms)
        return durations

    def _valid_beat_items(self, beats: List[Dict[str, Any]]) -> List[tuple[int, Dict[str, Any], str]]:
        return [
            (index, beat, str(beat.get("text", "") or "").strip())
            for index, beat in enumerate(beats)
            if str(beat.get("text", "") or "").strip()
        ]

    def _build_proportional_voiceover_ranges(
        self,
        *,
        valid_beats: List[tuple[int, Dict[str, Any], str]],
        total_duration_ms: int,
    ) -> List[Dict[str, Any]]:
        durations = self._allocate_durations(
            beats=[beat for _, beat, _ in valid_beats],
            total_duration_ms=total_duration_ms,
        )
        ranges: List[Dict[str, Any]] = []
        start_ms = 0
        for (index, beat, text), duration_ms in zip(valid_beats, durations):
            ranges.append(
                {
                    "index": index,
                    "beat": beat,
                    "text": text,
                    "start_ms": start_ms,
                    "duration_ms": max(1, int(duration_ms or 0)),
                    "content": "",
                }
            )
            start_ms += max(1, int(duration_ms or 0))
        return ranges

    def _build_asr_llm_voiceover_ranges(
        self,
        *,
        task_id: str,
        uploaded_voiceover_path: Path,
        uploaded_voiceover_duration_ms: int,
        valid_beats: List[tuple[int, Dict[str, Any], str]],
        update_task: UpdateTaskCallback,
    ) -> List[Dict[str, Any]]:
        update_task(
            task_id,
            stage="synthesizing_voice",
            progress=80,
            message="正在识别上传配音，用真实语音时间戳切分段落",
            result={
                "voice_source": "uploaded_voiceover",
                "voiceover_split_strategy": "voiceover_asr_pending",
            },
        )
        try:
            task_dir = settings.voiceover_dir / task_id
            task_dir.mkdir(parents=True, exist_ok=True)
            asr_audio_path = task_dir / "uploaded_voiceover_asr.wav"
            if not asr_service.extract_audio_from_video(str(uploaded_voiceover_path), str(asr_audio_path)):
                asr_audio_path = uploaded_voiceover_path
            voiceover_subtitles = asr_service.process_audio(str(asr_audio_path))
        except Exception as exc:
            logger.warning("Task %s uploaded voiceover ASR failed: %s", task_id, exc)
            return []
        if not voiceover_subtitles:
            logger.warning("Task %s uploaded voiceover ASR returned no subtitles.", task_id)
            return []

        update_task(
            task_id,
            stage="synthesizing_voice",
            progress=82,
            message="正在将确认文案对齐到上传配音字幕",
            result={
                "voiceover_asr_subtitle_count": len(voiceover_subtitles),
                "voiceover_split_strategy": "voiceover_asr_aligning",
            },
        )
        aligned_items = llm_service.align_voiceover_beats_with_subtitles(
            [beat for _, beat, _ in valid_beats],
            voiceover_subtitles,
        )
        if len(aligned_items) != len(valid_beats):
            logger.warning(
                "Task %s uploaded voiceover LLM segmentation mismatch: beats=%s aligned=%s",
                task_id,
                len(valid_beats),
                len(aligned_items),
            )
            return []

        aligned_by_id = {
            str(item.get("beat_id", "") or "").strip(): item
            for item in aligned_items
            if str(item.get("beat_id", "") or "").strip()
        }
        ranges: List[Dict[str, Any]] = []
        previous_end = 0
        audio_limit = max(1, int(uploaded_voiceover_duration_ms or 0))
        for order, (index, beat, text) in enumerate(valid_beats):
            beat_id = str(beat.get("id", "") or f"beat_{index + 1}").strip()
            aligned = aligned_by_id.get(beat_id) or aligned_items[order]
            try:
                start_ms = int(aligned.get("start", 0) or 0)
                end_ms = int(aligned.get("end", 0) or 0)
            except Exception:
                return []
            start_ms = max(0, min(start_ms, audio_limit))
            end_ms = max(0, min(end_ms, audio_limit))
            if start_ms < previous_end:
                start_ms = previous_end
            if end_ms <= start_ms:
                logger.warning(
                    "Task %s uploaded voiceover segmentation invalid range: beat=%s start=%s end=%s",
                    task_id,
                    beat_id,
                    start_ms,
                    end_ms,
                )
                return []
            ranges.append(
                {
                    "index": index,
                    "beat": beat,
                    "text": text,
                    "start_ms": start_ms,
                    "duration_ms": end_ms - start_ms,
                    "content": str(aligned.get("content", "") or "").strip(),
                }
            )
            previous_end = end_ms

        return ranges

    def _split_voiceover_by_ranges(
        self,
        *,
        task_id: str,
        uploaded_voiceover_path: Path,
        ranges: List[Dict[str, Any]],
        split_strategy: str,
        update_task: UpdateTaskCallback,
    ) -> List[Dict[str, Any]]:
        task_dir = settings.voiceover_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        outputs: List[Dict[str, Any]] = []
        total = len(ranges)
        for completed, item in enumerate(ranges, start=1):
            index = int(item["index"])
            beat = dict(item["beat"])
            text = str(item["text"]).strip()
            start_ms = int(item["start_ms"])
            duration_ms = max(1, int(item["duration_ms"]))
            update_task(
                task_id,
                stage="synthesizing_voice",
                progress=min(85, 82 + int((completed - 1) * 3 / max(1, total))),
                message=f"正在切分上传配音 第 {completed}/{total} 段",
                result={
                    "voice_source": "uploaded_voiceover",
                    "voiceover_split_strategy": split_strategy,
                    "voiceover_segment_count": total,
                    "voiceover_current_index": completed,
                },
            )
            output_path = task_dir / f"uploaded_beat_{index:02d}.wav"
            if not media_service.trim_audio_segment(
                str(uploaded_voiceover_path),
                str(output_path),
                start_ms=start_ms,
                duration_ms=duration_ms,
            ):
                raise RuntimeError("上传配音切分失败，请确认音频文件可被 FFmpeg 处理。")
            voice_duration_ms = media_service.probe_duration_ms(str(output_path)) or duration_ms
            outputs.append(
                {
                    "id": str(beat.get("id", "") or f"beat_{index + 1}"),
                    "title": str(beat.get("title", "") or f"第 {index + 1} 段"),
                    "text": text,
                    "order": int(beat.get("order", index + 1) or index + 1),
                    "voice_duration_ms": voice_duration_ms,
                    "audio_path": output_path,
                }
            )
            update_task(
                task_id,
                stage="synthesizing_voice",
                progress=min(85, 82 + int(completed * 3 / max(1, total))),
                message=f"上传配音已切分 第 {completed}/{total} 段",
                result={
                    "voice_source": "uploaded_voiceover",
                    "voiceover_split_strategy": split_strategy,
                    "voiceover_current_index": completed,
                },
            )
        return outputs

    def split_uploaded_voiceover_beats(
        self,
        *,
        task_id: str,
        uploaded_voiceover_path: Path,
        uploaded_voiceover_duration_ms: int,
        beats: List[Dict[str, Any]],
        update_task: UpdateTaskCallback,
    ) -> List[Dict[str, Any]]:
        if not uploaded_voiceover_path or not uploaded_voiceover_path.is_file():
            raise RuntimeError("上传配音文件不存在，请重新上传完整配音。")

        valid_beats = self._valid_beat_items(beats)
        if not valid_beats:
            return []

        ranges = self._build_asr_llm_voiceover_ranges(
            task_id=task_id,
            uploaded_voiceover_path=uploaded_voiceover_path,
            uploaded_voiceover_duration_ms=uploaded_voiceover_duration_ms,
            valid_beats=valid_beats,
            update_task=update_task,
        )
        split_strategy = "voiceover_asr_llm"
        if not ranges:
            update_task(
                task_id,
                stage="synthesizing_voice",
                progress=82,
                message="上传配音 ASR 对齐失败，正在使用比例切分兜底",
                result={
                    "voice_source": "uploaded_voiceover",
                    "voiceover_split_strategy": "proportional_fallback",
                },
            )
            ranges = self._build_proportional_voiceover_ranges(
                valid_beats=valid_beats,
                total_duration_ms=uploaded_voiceover_duration_ms,
            )
            split_strategy = "proportional_fallback"
        if not ranges:
            return []

        outputs = self._split_voiceover_by_ranges(
            task_id=task_id,
            uploaded_voiceover_path=uploaded_voiceover_path,
            ranges=ranges,
            split_strategy=split_strategy,
            update_task=update_task,
        )

        logger.info(
            "Task %s uploaded voiceover split: beats=%s duration_ms=%s strategy=%s",
            task_id,
            len(outputs),
            uploaded_voiceover_duration_ms,
            split_strategy,
        )
        return outputs

    def synthesize_reviewed_beats(
        self,
        *,
        task_id: str,
        voice_mode: str,
        voice: str,
        beats: List[Dict[str, Any]],
        speed: float,
        update_task: UpdateTaskCallback,
        user_id: str = "",
    ) -> List[Dict[str, Any]]:
        task_dir = settings.voiceover_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        outputs: List[Dict[str, Any]] = []
        total = sum(1 for beat in beats if str(beat.get("text", "") or "").strip())
        completed = 0
        for index, beat in enumerate(beats):
            text = str(beat.get("text", "") or "").strip()
            if not text:
                continue
            completed += 1
            update_task(
                task_id,
                stage="synthesizing_voice",
                progress=min(85, 80 + int((completed - 1) * 5 / max(1, total))),
                message=f"正在生成配音 第 {completed}/{total} 段",
                result={
                    "voiceover_segment_count": total,
                    "voiceover_current_index": completed,
                },
            )
            output_path = task_dir / f"draft_beat_{index:02d}.wav"
            cache_path = tts_cache_service.cache_path(
                voice,
                text,
                speed=speed,
                voice_mode=voice_mode,
                user_id=user_id,
            )
            if cache_path.exists():
                shutil.copyfile(str(cache_path), str(output_path))
                logger.info(
                    "Task %s TTS cache hit: beat=%s voice=%s mode=%s speed=%.2fx cache=%s",
                    task_id,
                    index + 1,
                    voice,
                    voice_mode,
                    float(speed or settings.tts_speed_default),
                    cache_path.name,
                )
            else:
                tts_service.synthesize_to_file(
                    text=text,
                    voice=voice,
                    output_path=output_path,
                    speed=speed,
                    voice_mode=voice_mode,
                    user_id=user_id,
                )
                shutil.copyfile(str(output_path), str(cache_path))
            voice_duration_ms = media_service.probe_duration_ms(str(output_path))
            update_task(
                task_id,
                stage="synthesizing_voice",
                progress=min(85, 80 + int(completed * 5 / max(1, total))),
                message=f"配音已生成 第 {completed}/{total} 段",
                result={
                    "voiceover_current_index": completed,
                },
            )
            outputs.append(
                {
                    "id": str(beat.get("id", "") or f"beat_{index + 1}"),
                    "title": str(beat.get("title", "") or f"第 {index + 1} 段"),
                    "text": text,
                    "order": int(beat.get("order", index + 1) or index + 1),
                    "voice_duration_ms": voice_duration_ms,
                    "audio_path": output_path,
                }
            )
        return outputs


voice_workflow_service = VoiceWorkflowService()
