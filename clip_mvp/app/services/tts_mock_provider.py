from __future__ import annotations

import subprocess
from pathlib import Path

from app.core.config import settings


class TTSMockProvider:
    def synthesize_to_file(self, output_path: Path) -> Path:
        command = [
            settings.ffmpeg_bin,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=16000:cl=mono",
            "-t",
            "1",
            str(output_path),
        ]
        try:
            subprocess.run(command, check=True, capture_output=True)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError("Mock TTS 音频生成失败，请检查 FFmpeg。") from exc
        return output_path


tts_mock_provider = TTSMockProvider()
