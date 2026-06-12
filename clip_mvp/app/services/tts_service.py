from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from app.core.config import settings
from app.services.media_service import media_service
from app.services.tts_provider_service import tts_provider_service
from app.services.tts_text_chunker import tts_text_chunker


logger = logging.getLogger(__name__)


class TTSService:
    def _get_provider(self) -> str:
        return tts_provider_service.get_provider()

    def normalize_voice_mode(self, voice_mode: str | None) -> str:
        return tts_provider_service.normalize_voice_mode(voice_mode)

    def _provider_for_mode(self, voice_mode: str | None) -> str:
        return tts_provider_service.provider_for_mode(voice_mode)

    def _normalize_speed(self, speed: float | int | str | None) -> float:
        return tts_provider_service.normalize_speed(speed)

    def _native_sft_supported(self) -> bool:
        return tts_provider_service.native_sft_supported()

    def _default_voice_ref(self, *, user_id: str = "") -> str:
        return tts_provider_service.default_voice_ref(user_id=user_id)

    def _is_managed_local_cosyvoice(self, provider: str) -> bool:
        return tts_provider_service.is_managed_local_cosyvoice(provider)

    def _is_subprocess_local_cosyvoice(self, provider: str) -> bool:
        return tts_provider_service.is_subprocess_local_cosyvoice(provider)

    def _provider_supports_native_speed(self, provider: str) -> bool:
        return tts_provider_service.supports_native_speed(provider)

    def prepare_voiceover_segments(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        prepared: List[Dict[str, Any]] = []
        for index, segment in enumerate(segments or []):
            try:
                start = int(segment.get("start", 0) or 0)
                end = int(segment.get("end", 0) or 0)
            except Exception:
                continue

            text = str(segment.get("dubbing", "") or segment.get("content", "") or "").strip()
            if not text or end <= start:
                continue

            prepared.append(
                {
                    "index": index,
                    "start": start,
                    "end": end,
                    "duration_ms": end - start,
                    "text": text,
                }
            )
        return prepared

    def _effective_chunk_limits(self, voice_mode: str | None = None) -> tuple[int, int]:
        soft_limit = max(20, int(settings.tts_chunk_soft_chars or 60))
        hard_limit = max(soft_limit, int(settings.tts_chunk_hard_chars or soft_limit))

        # Local CosyVoice zero-shot is much more sensitive to long text spans than
        # EdgeTTS or native fixed-speaker routes. Keep internal chunks shorter so
        # one oversized request does not stall the whole beat.
        provider = self._provider_for_mode(voice_mode)
        if self._is_managed_local_cosyvoice(provider) and not self._native_sft_supported():
            soft_limit = min(soft_limit, 42)
            hard_limit = min(hard_limit, 58)
            hard_limit = max(soft_limit, hard_limit)

        return soft_limit, hard_limit

    def _split_text_for_tts(self, text: str, voice_mode: str | None = None) -> List[str]:
        raw_text = str(text or "").strip()
        if not raw_text:
            return []

        soft_limit, hard_limit = self._effective_chunk_limits(voice_mode)
        return tts_text_chunker.split(
            raw_text,
            soft_limit=soft_limit,
            hard_limit=hard_limit,
        )

    def _synthesize_provider_to_file(
        self,
        *,
        text: str,
        voice: str,
        output_path: Path,
        voice_mode: str | None = None,
        speed: float = 1.0,
        user_id: str = "",
    ) -> Path:
        return tts_provider_service.synthesize_to_file(
            text=text,
            voice=voice,
            output_path=output_path,
            voice_mode=voice_mode,
            speed=speed,
            user_id=user_id,
        )

    def synthesize_segments(
        self,
        *,
        task_id: str,
        voice: str,
        segments: List[Dict[str, Any]],
        speed: float = 1.0,
        voice_mode: str | None = None,
        user_id: str = "",
    ) -> List[Dict[str, Any]]:
        prepared = self.prepare_voiceover_segments(segments)
        if not prepared:
            return []

        task_dir = settings.voiceover_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        voice_name = str(voice or self._default_voice_ref(user_id=user_id)).strip()

        outputs: List[Dict[str, Any]] = []
        for item in prepared:
            output_path = task_dir / f"segment_{item['index']:02d}.wav"
            self.synthesize_to_file(
                text=item["text"],
                voice=voice_name,
                output_path=output_path,
                speed=speed,
                voice_mode=voice_mode,
                user_id=user_id,
            )
            outputs.append({**item, "audio_path": output_path})
        return outputs

    def synthesize_to_file(
        self,
        *,
        text: str,
        voice: str,
        output_path: Path,
        speed: float = 1.0,
        voice_mode: str | None = None,
        user_id: str = "",
    ) -> Path:
        clean_text = str(text or "").strip()
        normalized_speed = self._normalize_speed(speed)
        normalized_mode = self.normalize_voice_mode(voice_mode)
        provider = self._provider_for_mode(normalized_mode)
        native_speed = normalized_speed if self._provider_supports_native_speed(provider) else 1.0
        chunks = self._split_text_for_tts(clean_text, normalized_mode)
        if not chunks:
            raise RuntimeError("TTS 文案为空，无法生成音频。")
        if len(chunks) == 1:
            synthesized = self._synthesize_provider_to_file(
                text=chunks[0],
                voice=voice,
                output_path=output_path,
                voice_mode=normalized_mode,
                speed=native_speed,
                user_id=user_id,
            )
            if abs(native_speed - normalized_speed) < 0.001:
                return synthesized
            return self._apply_speed_to_audio(synthesized, normalized_speed)

        logger.info(
            "TTS internal chunking: voice=%s chars=%s chunks=%s chunk_chars=%s",
            voice,
            len(re.sub(r"\s+", "", clean_text)),
            len(chunks),
            [len(re.sub(r"\s+", "", chunk)) for chunk in chunks],
        )

        chunk_dir = output_path.parent / f"{output_path.stem}_chunks"
        chunk_dir.mkdir(parents=True, exist_ok=True)
        chunk_files: List[str] = []
        for index, chunk in enumerate(chunks):
            chunk_path = chunk_dir / f"{output_path.stem}_chunk_{index:02d}.wav"
            self._synthesize_provider_to_file(
                text=chunk,
                voice=voice,
                output_path=chunk_path,
                voice_mode=normalized_mode,
                speed=native_speed,
                user_id=user_id,
            )
            chunk_files.append(str(chunk_path))

        if not media_service.concat_audio_tracks(chunk_files, str(output_path)):
            raise RuntimeError("TTS 分块音频合并失败，请检查 FFmpeg。")

        logger.info(
            "TTS chunked synthesis completed: voice=%s chars=%s chunks=%s output=%s",
            voice,
            len(re.sub(r"\s+", "", clean_text)),
            len(chunks),
            output_path.name,
        )
        if abs(native_speed - normalized_speed) < 0.001:
            return output_path
        return self._apply_speed_to_audio(output_path, normalized_speed)

    def _apply_speed_to_audio(self, output_path: Path, speed: float) -> Path:
        normalized_speed = self._normalize_speed(speed)
        if abs(normalized_speed - 1.0) < 0.001:
            return output_path

        adjusted_path = output_path.with_name(f"{output_path.stem}.tempo{output_path.suffix}")
        command = [
            settings.ffmpeg_bin,
            "-y",
            "-i",
            str(output_path),
            "-vn",
            "-filter:a",
            f"atempo={normalized_speed:.3f}",
            str(adjusted_path),
        ]
        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip()
            raise RuntimeError(f"TTS 语速调整失败: {detail[:300]}") from exc

        adjusted_path.replace(output_path)
        logger.info(
            "TTS playback speed adjusted: speed=%.2fx output=%s",
            normalized_speed,
            output_path.name,
        )
        return output_path


tts_service = TTSService()
