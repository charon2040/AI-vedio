from __future__ import annotations

import json
import subprocess
from typing import List

from app.core.config import settings


class MediaProbeService:
    def probe_duration_ms(self, media_path: str) -> int:
        command = [
            settings.ffprobe_bin,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,duration",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            media_path,
        ]
        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            payload = json.loads(result.stdout or "{}")

            stream_durations: List[float] = []
            for stream in payload.get("streams", []) or []:
                if str(stream.get("codec_type", "") or "").strip().lower() not in {"audio", "video"}:
                    continue
                try:
                    duration = float(stream.get("duration", 0) or 0)
                except Exception:
                    continue
                if duration > 0:
                    stream_durations.append(duration)

            if stream_durations:
                return max(0, int(max(stream_durations) * 1000))

            format_duration = float(((payload.get("format") or {}).get("duration", 0) or 0))
            return max(0, int(format_duration * 1000))
        except Exception:
            return 0

    def has_audio_stream(self, media_path: str) -> bool:
        command = [
            settings.ffprobe_bin,
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "json",
            media_path,
        ]
        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            payload = json.loads(result.stdout or "{}")
            return any(
                str(stream.get("codec_type", "") or "").strip().lower() == "audio"
                for stream in payload.get("streams", []) or []
                if isinstance(stream, dict)
            )
        except Exception:
            return False

    def probe_video_size(self, media_path: str) -> tuple[int, int]:
        command = [
            settings.ffprobe_bin,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "json",
            media_path,
        ]
        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            payload = json.loads(result.stdout or "{}")
            for stream in payload.get("streams", []) or []:
                width = int(stream.get("width", 0) or 0)
                height = int(stream.get("height", 0) or 0)
                if width > 0 and height > 0:
                    return width, height
        except Exception:
            pass
        return 1920, 1080


media_probe_service = MediaProbeService()
