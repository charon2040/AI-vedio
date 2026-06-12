from __future__ import annotations

from typing import Any, Dict, Iterable, List

from app.services.media_audio_service import media_audio_service
from app.services.media_export_service import media_export_service
from app.services.media_probe_service import media_probe_service
from app.services.media_video_service import media_video_service


class MediaService:
    def probe_duration_ms(self, media_path: str) -> int:
        return media_probe_service.probe_duration_ms(media_path)

    def has_audio_stream(self, media_path: str) -> bool:
        return media_probe_service.has_audio_stream(media_path)

    def probe_video_size(self, media_path: str) -> tuple[int, int]:
        return media_probe_service.probe_video_size(media_path)

    def normalize_reference_audio(self, input_media: str, output_audio: str) -> bool:
        return media_audio_service.normalize_reference_audio(input_media, output_audio)

    def normalize_voiceover_audio(self, input_media: str, output_audio: str) -> bool:
        return media_audio_service.normalize_voiceover_audio(input_media, output_audio)

    def trim_audio_segment(
        self,
        input_audio: str,
        output_audio: str,
        *,
        start_ms: int,
        duration_ms: int,
    ) -> bool:
        return media_audio_service.trim_audio_segment(
            input_audio,
            output_audio,
            start_ms=start_ms,
            duration_ms=duration_ms,
        )

    def fit_audio_to_duration(self, input_audio: str, output_audio: str, target_ms: int) -> bool:
        return media_audio_service.fit_audio_to_duration(input_audio, output_audio, target_ms)

    def pad_audio_to_duration(self, input_audio: str, output_audio: str, target_ms: int) -> bool:
        return media_audio_service.pad_audio_to_duration(input_audio, output_audio, target_ms)

    def concat_audio_tracks(self, input_files: List[str], output_audio: str) -> bool:
        return media_audio_service.concat_audio_tracks(input_files, output_audio)

    def build_voiceover_track(
        self,
        synthesized_segments: List[Dict[str, Any]],
        output_audio: str,
    ) -> bool:
        return media_audio_service.build_voiceover_track(synthesized_segments, output_audio)

    def mux_voiceover_video(
        self,
        input_video: str,
        voiceover_audio: str,
        output_video: str,
        *,
        keep_original_audio: bool,
    ) -> bool:
        return media_video_service.mux_voiceover_video(
            input_video,
            voiceover_audio,
            output_video,
            keep_original_audio=keep_original_audio,
        )

    def cut_and_concat_video(self, input_video: str, output_video: str, segments: List[Dict[str, Any]]) -> bool:
        return media_video_service.cut_and_concat_video(input_video, output_video, segments)

    def burn_ass_subtitles(self, input_video: str, ass_path: str, output_video: str) -> bool:
        return media_video_service.burn_ass_subtitles(input_video, ass_path, output_video)

    def build_timeline_segments(self, segments: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return media_export_service.build_timeline_segments(segments)

    def remap_subtitles_to_cut(self, subtitles: List[Dict[str, Any]], segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return media_export_service.remap_subtitles_to_cut(subtitles, segments)

    def build_single_line_subtitles_from_beats(
        self,
        beats: List[Dict[str, Any]],
        *,
        total_duration_ms: int = 0,
    ) -> List[Dict[str, Any]]:
        return media_export_service.build_single_line_subtitles_from_beats(
            beats,
            total_duration_ms=total_duration_ms,
        )

    def build_single_line_subtitles_from_voice_timeline(
        self,
        beats: List[Dict[str, Any]],
        timeline_items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        return media_export_service.build_single_line_subtitles_from_voice_timeline(
            beats,
            timeline_items,
        )

    def normalize_single_line_subtitles(self, subtitles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return media_export_service.normalize_single_line_subtitles(subtitles)

    def export_srt(self, subtitles: List[Dict[str, Any]], output_path: str) -> bool:
        return media_export_service.export_srt(subtitles, output_path)

    def export_ass(
        self,
        subtitles: List[Dict[str, Any]],
        output_path: str,
        *,
        video_width: int = 1920,
        video_height: int = 1080,
    ) -> bool:
        return media_export_service.export_ass(
            subtitles,
            output_path,
            video_width=video_width,
            video_height=video_height,
        )

    def export_edl(self, segments: List[Dict[str, Any]], original_video_name: str, output_path: str, fps: float = 25.0) -> bool:
        return media_export_service.export_edl(segments, original_video_name, output_path, fps=fps)

    def _format_srt_time(self, ms: int) -> str:
        return media_export_service._format_srt_time(ms)

    def _ms_to_smpte(self, ms: int, fps: float = 25.0) -> str:
        return media_export_service._ms_to_smpte(ms, fps=fps)


media_service = MediaService()
