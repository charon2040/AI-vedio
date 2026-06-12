from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from app.core.config import settings
from app.services.media_probe_service import media_probe_service


class MediaAudioService:
    _voiceover_sample_rate = 24000

    def _run(self, command: List[str]) -> None:
        subprocess.run(command, check=True, capture_output=True)

    def normalize_reference_audio(self, input_media: str, output_audio: str) -> bool:
        output_path = Path(output_audio)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            settings.ffmpeg_bin,
            "-y",
            "-i",
            input_media,
            "-vn",
            "-ac",
            "1",
            "-c:a",
            "pcm_f32le",
            "-ar",
            "22050",
            output_audio,
        ]
        try:
            self._run(command)
            return True
        except subprocess.CalledProcessError:
            return False

    def normalize_voiceover_audio(self, input_media: str, output_audio: str) -> bool:
        output_path = Path(output_audio)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            settings.ffmpeg_bin,
            "-y",
            "-i",
            input_media,
            "-vn",
            "-c:a",
            "pcm_s16le",
            "-ar",
            str(self._voiceover_sample_rate),
            "-ac",
            "1",
            output_audio,
        ]
        try:
            self._run(command)
            return True
        except subprocess.CalledProcessError:
            return False

    def trim_audio_segment(
        self,
        input_audio: str,
        output_audio: str,
        *,
        start_ms: int,
        duration_ms: int,
    ) -> bool:
        target_ms = max(1, int(duration_ms or 0))
        start_seconds = max(0.0, float(start_ms or 0) / 1000.0)
        target_seconds = target_ms / 1000.0
        output_path = Path(output_audio)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            settings.ffmpeg_bin,
            "-y",
            "-ss",
            f"{start_seconds:.3f}",
            "-i",
            input_audio,
            "-t",
            f"{target_seconds:.3f}",
            "-vn",
            "-af",
            f"apad,atrim=0:{target_seconds:.3f}",
            "-c:a",
            "pcm_s16le",
            "-ar",
            str(self._voiceover_sample_rate),
            "-ac",
            "1",
            output_audio,
        ]
        try:
            self._run(command)
            return True
        except subprocess.CalledProcessError:
            return False

    def _build_atempo_filter(self, ratio: float) -> str:
        if ratio <= 0:
            return "atempo=1.0"

        parts: List[str] = []
        remaining = float(ratio)
        while remaining > 2.0:
            parts.append("atempo=2.0")
            remaining /= 2.0
        while remaining < 0.5:
            parts.append("atempo=0.5")
            remaining /= 0.5
        parts.append(f"atempo={remaining:.5f}")
        return ",".join(parts)

    def fit_audio_to_duration(self, input_audio: str, output_audio: str, target_ms: int) -> bool:
        target_ms = max(1, int(target_ms or 0))
        raw_duration_ms = max(1, media_probe_service.probe_duration_ms(input_audio))
        ratio = raw_duration_ms / float(target_ms)
        target_seconds = target_ms / 1000.0
        filter_chain = [
            self._build_atempo_filter(ratio),
            "apad",
            f"atrim=0:{target_seconds:.3f}",
        ]

        command = [
            settings.ffmpeg_bin,
            "-y",
            "-i",
            input_audio,
            "-af",
            ",".join(filter_chain),
            "-c:a",
            "pcm_s16le",
            "-ar",
            str(self._voiceover_sample_rate),
            "-ac",
            "1",
            output_audio,
        ]
        try:
            self._run(command)
            return True
        except subprocess.CalledProcessError:
            return False

    def pad_audio_to_duration(self, input_audio: str, output_audio: str, target_ms: int) -> bool:
        target_ms = max(1, int(target_ms or 0))
        target_seconds = target_ms / 1000.0
        command = [
            settings.ffmpeg_bin,
            "-y",
            "-i",
            input_audio,
            "-af",
            f"apad,atrim=0:{target_seconds:.3f}",
            "-c:a",
            "pcm_s16le",
            "-ar",
            str(self._voiceover_sample_rate),
            "-ac",
            "1",
            output_audio,
        ]
        try:
            self._run(command)
            return True
        except subprocess.CalledProcessError:
            return False

    def concat_audio_tracks(self, input_files: List[str], output_audio: str) -> bool:
        if not input_files:
            return False

        output_path = Path(output_audio)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            command = [settings.ffmpeg_bin, "-y"]
            filter_parts: List[str] = []
            concat_inputs: List[str] = []
            for index, path in enumerate(input_files):
                command.extend(["-i", path])
                filter_parts.append(
                    f"[{index}:a]aresample={self._voiceover_sample_rate},aformat=sample_fmts=s16:channel_layouts=mono[a{index}]"
                )
                concat_inputs.append(f"[a{index}]")

            filter_parts.append(
                "".join(concat_inputs) + f"concat=n={len(input_files)}:v=0:a=1[aout]"
            )
            command.extend(
                [
                    "-filter_complex",
                    ";".join(filter_parts),
                    "-map",
                    "[aout]",
                    "-c:a",
                    "pcm_s16le",
                    "-ar",
                    str(self._voiceover_sample_rate),
                    "-ac",
                    "1",
                    output_audio,
                ]
            )
            self._run(command)
            return True
        except subprocess.CalledProcessError:
            return False

    def build_voiceover_track(
        self,
        synthesized_segments: List[Dict[str, Any]],
        output_audio: str,
    ) -> bool:
        if not synthesized_segments:
            return False

        adjusted_paths: List[str] = []
        output_path = Path(output_audio)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        for item in synthesized_segments:
            input_path = Path(item["audio_path"])
            adjusted_path = input_path.with_name(f"{input_path.stem}_fit.wav")
            target_ms = int(item.get("duration_ms", 0) or 0)
            raw_duration_ms = max(1, media_probe_service.probe_duration_ms(str(input_path)))
            if target_ms <= 0:
                shutil.copyfile(str(input_path), str(adjusted_path))
            elif raw_duration_ms > target_ms + 120:
                return False
            elif raw_duration_ms < target_ms - 120:
                if not self.pad_audio_to_duration(
                    str(input_path),
                    str(adjusted_path),
                    target_ms,
                ):
                    return False
            else:
                shutil.copyfile(str(input_path), str(adjusted_path))
            adjusted_paths.append(str(adjusted_path))

        return self.concat_audio_tracks(adjusted_paths, output_audio)


media_audio_service = MediaAudioService()
