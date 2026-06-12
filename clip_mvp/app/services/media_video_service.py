from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Dict, List

from app.core.config import settings
from app.services.media_probe_service import media_probe_service


class MediaVideoService:
    def _run(self, command: List[str]) -> None:
        subprocess.run(command, check=True, capture_output=True)

    def burn_ass_subtitles(
        self,
        input_video: str,
        ass_path: str,
        output_video: str,
    ) -> bool:
        if not Path(ass_path).is_file():
            return False

        has_audio = media_probe_service.has_audio_stream(input_video)
        command = [
            settings.ffmpeg_bin,
            "-y",
            "-i",
            input_video,
            "-vf",
            f"ass={self._escape_filter_path(ass_path)}",
            "-map_metadata",
            "-1",
            "-map_chapters",
            "-1",
            "-dn",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-movflags",
            "+faststart",
        ]
        if has_audio:
            command.extend(["-c:a", "copy"])
        else:
            command.append("-an")
        command.append(output_video)

        try:
            self._run(command)
            return True
        except subprocess.CalledProcessError:
            return False

    def mux_voiceover_video(
        self,
        input_video: str,
        voiceover_audio: str,
        output_video: str,
        *,
        keep_original_audio: bool,
    ) -> bool:
        target_ms = max(1, media_probe_service.probe_duration_ms(voiceover_audio))
        input_video_ms = max(1, media_probe_service.probe_duration_ms(input_video))
        if input_video_ms + 80 < target_ms:
            return False
        target_seconds = target_ms / 1000.0
        keep_source_audio = bool(keep_original_audio) and media_probe_service.has_audio_stream(input_video)

        command = [
            settings.ffmpeg_bin,
            "-y",
            "-i",
            input_video,
            "-i",
            voiceover_audio,
        ]

        video_filter = "[0:v]"
        video_filter += f"trim=duration={target_seconds:.3f},setpts=PTS-STARTPTS[vout]"

        if keep_source_audio:
            filter_parts = [
                video_filter,
                f"[0:a]volume={float(settings.tts_original_audio_volume):.3f},apad,atrim=0:{target_seconds:.3f}[bg]",
                f"[1:a]volume=1.0,atrim=0:{target_seconds:.3f}[vo]",
                "[vo][bg]amix=inputs=2:duration=first:dropout_transition=0[mix]",
            ]
            command.extend(
                [
                    "-filter_complex",
                    ";".join(filter_parts),
                    "-map",
                    "[vout]",
                    "-map",
                    "[mix]",
                ]
            )
        else:
            filter_parts = [
                video_filter,
                f"[1:a]atrim=0:{target_seconds:.3f}[vo]",
            ]
            command.extend(
                [
                    "-filter_complex",
                    ";".join(filter_parts),
                    "-map",
                    "[vout]",
                    "-map",
                    "[vo]",
                ]
            )

        command.extend(
            [
                "-map_metadata",
                "-1",
                "-map_chapters",
                "-1",
                "-dn",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                output_video,
            ]
        )

        try:
            self._run(command)
            return True
        except subprocess.CalledProcessError:
            return False

    def cut_and_concat_video(self, input_video: str, output_video: str, segments: List[Dict]) -> bool:
        if not segments:
            return False

        has_audio = media_probe_service.has_audio_stream(input_video)
        filter_parts: List[str] = []
        concat_inputs: List[str] = []
        for index, segment in enumerate(segments):
            start_sec = max(0.0, float(segment["start"]) / 1000.0)
            end_sec = max(start_sec, float(segment["end"]) / 1000.0)
            filter_parts.append(
                f"[0:v]trim=start={start_sec:.3f}:end={end_sec:.3f},setpts=PTS-STARTPTS[v{index}]"
            )
            if has_audio:
                filter_parts.append(
                    f"[0:a]atrim=start={start_sec:.3f}:end={end_sec:.3f},asetpts=PTS-STARTPTS[a{index}]"
                )
                concat_inputs.append(f"[v{index}][a{index}]")
            else:
                concat_inputs.append(f"[v{index}]")

        if has_audio:
            filter_parts.append(
                "".join(concat_inputs) + f"concat=n={len(segments)}:v=1:a=1[vout][aout]"
            )
        else:
            filter_parts.append(
                "".join(concat_inputs) + f"concat=n={len(segments)}:v=1:a=0[vout]"
            )

        command = [
            settings.ffmpeg_bin,
            "-y",
            "-i",
            input_video,
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            "[vout]",
            "-map_metadata",
            "-1",
            "-map_chapters",
            "-1",
            "-dn",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-movflags",
            "+faststart",
            output_video,
        ]
        if has_audio:
            movflags_index = command.index("-movflags")
            command[movflags_index:movflags_index] = ["-map", "[aout]", "-c:a", "aac"]
        else:
            movflags_index = command.index("-movflags")
            command[movflags_index:movflags_index] = ["-an"]

        try:
            self._run(command)
            return True
        except subprocess.CalledProcessError:
            return False

    def _escape_filter_path(self, path: str) -> str:
        normalized = str(Path(path).resolve()).replace("\\", "/")
        escaped = normalized.replace(":", r"\:").replace("'", r"\'")
        return f"'{escaped}'"


media_video_service = MediaVideoService()
