from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List

from app.services.media_service import media_service


logger = logging.getLogger(__name__)

UpdateTaskCallback = Callable[..., Dict[str, Any]]
RecordTaskEventCallback = Callable[..., None]


@dataclass(frozen=True)
class RenderWorkflowResult:
    actual_duration_ms: int
    voiceover_duration_ms: int
    voiceover_count: int
    artifacts: Dict[str, str]


class RenderWorkflowService:
    def build_timeline_segments(self, source_segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return media_service.build_timeline_segments(source_segments)

    def render_final_output(
        self,
        *,
        task_id: str,
        source_path: Path,
        original_filename: str,
        source_segments: List[Dict[str, Any]],
        subtitles: List[Dict[str, Any]],
        reviewed_beats: List[Dict[str, Any]],
        synthesized_beats: List[Dict[str, Any]],
        enable_dubbing: bool,
        keep_original_audio: bool,
        total_duration_ms: int,
        output_path: Path,
        subtitle_work_path: Path,
        raw_output_path: Path,
        srt_path: Path,
        ass_path: Path,
        edl_path: Path,
        voiceover_path: Path,
        update_task: UpdateTaskCallback,
        record_task_event: RecordTaskEventCallback,
    ) -> RenderWorkflowResult:
        render_target = raw_output_path if enable_dubbing else subtitle_work_path
        if not media_service.cut_and_concat_video(str(source_path), str(render_target), source_segments):
            raise RuntimeError("FFmpeg 粗剪失败，请检查源视频编码或片段时间戳。")
        logger.info("Task %s render completed: %s", task_id, render_target.name)
        record_task_event(
            task_id,
            event_type="render_completed",
            detail={
                "output": render_target.name,
                "segment_count": len(source_segments),
                "total_duration_ms": total_duration_ms,
            },
        )

        voiceover_count = 0
        voiceover_duration_ms = 0
        voice_timeline_items: List[Dict[str, Any]] = []
        if enable_dubbing:
            final_synthesized_segments: List[Dict[str, Any]] = []
            timeline_cursor_ms = 0
            for segment, beat, synthesized in zip(source_segments, reviewed_beats, synthesized_beats):
                segment_duration_ms = max(
                    0,
                    int(segment.get("end", 0) or 0) - int(segment.get("start", 0) or 0),
                )
                voice_duration_ms = max(0, int(beat.get("voice_duration_ms", 0) or 0))
                track_duration_ms = max(segment_duration_ms, voice_duration_ms)
                final_synthesized_segments.append(
                    {
                        "audio_path": synthesized["audio_path"],
                        "duration_ms": track_duration_ms,
                    }
                )
                voice_timeline_items.append(
                    {
                        "start_ms": timeline_cursor_ms,
                        "voice_duration_ms": voice_duration_ms,
                        "segment_duration_ms": segment_duration_ms,
                        "track_duration_ms": track_duration_ms,
                    }
                )
                timeline_cursor_ms += track_duration_ms

            voiceover_count = len(final_synthesized_segments)
            if not media_service.build_voiceover_track(
                final_synthesized_segments,
                str(voiceover_path),
            ):
                raise RuntimeError("配音音轨拼接失败，请检查配音时长与选片匹配关系。")
            voiceover_duration_ms = media_service.probe_duration_ms(str(voiceover_path))
            logger.info(
                "Task %s voiceover synthesized: segments=%s audio=%s duration_ms=%s",
                task_id,
                voiceover_count,
                voiceover_path.name,
                voiceover_duration_ms,
            )
            record_task_event(
                task_id,
                event_type="voiceover_track_completed",
                detail={
                    "segment_count": voiceover_count,
                    "duration_ms": voiceover_duration_ms,
                    "audio": voiceover_path.name,
                },
            )

            raw_video_duration_ms = media_service.probe_duration_ms(str(raw_output_path))
            if raw_video_duration_ms + 80 < voiceover_duration_ms:
                raise RuntimeError(
                    "当前选片总画面短于配音，已停止渲染，避免片尾冻结补帧或配音串到无画面区域。"
                    f" 选片约 {raw_video_duration_ms / 1000:.1f}s，配音约 {voiceover_duration_ms / 1000:.1f}s。"
                    "请从配音完成后重新选片。"
                )

            update_task(
                task_id,
                stage="mixing_audio",
                progress=96,
                message="正在混合原声与配音",
                artifacts={"voiceover_audio_url": f"/outputs/voiceovers/{voiceover_path.name}"},
                result={
                    "voiceover_segment_count": voiceover_count,
                    "voiceover_duration_ms": voiceover_duration_ms,
                },
            )
            if not media_service.mux_voiceover_video(
                str(raw_output_path),
                str(voiceover_path),
                str(subtitle_work_path),
                keep_original_audio=keep_original_audio,
            ):
                raise RuntimeError("视频与配音混音失败，请检查音频轨道或重新选片。")
            logger.info("Task %s mix completed: %s", task_id, subtitle_work_path.name)
            record_task_event(
                task_id,
                event_type="mix_completed",
                detail={
                    "output": subtitle_work_path.name,
                    "keep_original_audio": keep_original_audio,
                },
            )

        cut_subtitles = media_service.remap_subtitles_to_cut(subtitles, source_segments)
        single_line_subtitles = (
            media_service.build_single_line_subtitles_from_voice_timeline(
                reviewed_beats,
                voice_timeline_items,
            )
            if enable_dubbing
            else media_service.normalize_single_line_subtitles(cut_subtitles)
        )
        if not single_line_subtitles:
            single_line_subtitles = media_service.normalize_single_line_subtitles(cut_subtitles)

        media_service.export_srt(single_line_subtitles, str(srt_path))
        video_width, video_height = media_service.probe_video_size(str(subtitle_work_path))
        if not media_service.export_ass(
            single_line_subtitles,
            str(ass_path),
            video_width=video_width,
            video_height=video_height,
        ):
            raise RuntimeError("ASS 字幕生成失败，请检查字幕文本或输出目录权限。")
        update_task(
            task_id,
            stage="burning_subtitles",
            progress=98,
            message="正在烧录单行字幕",
        )
        if not media_service.burn_ass_subtitles(
            str(subtitle_work_path),
            str(ass_path),
            str(output_path),
        ):
            raise RuntimeError("字幕烧录失败，请检查 FFmpeg 是否支持 ass/libass 字幕滤镜。")

        media_service.export_edl(source_segments, original_filename, str(edl_path))
        logger.info(
            "Task %s exports completed: ass=%s srt=%s edl=%s",
            task_id,
            ass_path.name,
            srt_path.name,
            edl_path.name,
        )
        record_task_event(
            task_id,
            event_type="exports_completed",
            detail={
                "ass": ass_path.name,
                "srt": srt_path.name,
                "edl": edl_path.name,
                "subtitle_cue_count": len(single_line_subtitles),
            },
        )

        final_output_path = output_path
        actual_duration_ms = media_service.probe_duration_ms(str(final_output_path))
        return RenderWorkflowResult(
            actual_duration_ms=actual_duration_ms,
            voiceover_duration_ms=voiceover_duration_ms,
            voiceover_count=voiceover_count,
            artifacts={
                "output_video_url": f"/outputs/{output_path.name}",
                "srt_url": f"/outputs/{srt_path.name}",
                "edl_url": f"/outputs/{edl_path.name}",
            },
        )


render_workflow_service = RenderWorkflowService()
