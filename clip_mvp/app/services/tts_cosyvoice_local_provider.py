from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from app.core.config import settings
from app.services.tts_provider_config_service import tts_provider_config_service


logger = logging.getLogger(__name__)


class TTSCosyVoiceLocalProvider:
    def synthesize_to_file(
        self,
        *,
        text: str,
        voice: str,
        output_path: Path,
        speed: float = 1.0,
        user_id: str = "",
    ) -> Path:
        self.run_batch(
            segments=[
                {
                    "index": 0,
                    "text": text,
                    "audio_path": str(output_path),
                }
            ],
            voice=voice,
            task_dir=output_path.parent,
            speed=speed,
        )
        if not output_path.exists():
            raise RuntimeError(f"本地 CosyVoice 没有生成音频文件: {output_path}")
        return output_path

    def synthesize_batch(
        self,
        *,
        task_dir: Path,
        voice: str,
        segments: List[Dict[str, Any]],
        speed: float = 1.0,
    ) -> List[Dict[str, Any]]:
        payload: List[Dict[str, Any]] = []
        for item in segments:
            output_path = task_dir / f"segment_{item['index']:02d}.wav"
            payload.append(
                {
                    **item,
                    "audio_path": str(output_path),
                }
            )

        self.run_batch(
            segments=payload,
            voice=voice,
            task_dir=task_dir,
            speed=speed,
        )

        outputs: List[Dict[str, Any]] = []
        for item in payload:
            audio_path = Path(item["audio_path"])
            if not audio_path.exists():
                raise RuntimeError(f"本地 CosyVoice 未生成片段音频: {audio_path}")
            outputs.append({**item, "audio_path": audio_path})
        return outputs

    def run_batch(
        self,
        *,
        segments: List[Dict[str, Any]],
        voice: str,
        task_dir: Path,
        speed: float = 1.0,
    ) -> None:
        python_bin = Path(settings.cosyvoice_local_python)
        helper_path = settings.cosyvoice_helper_path
        repo_dir = Path(settings.cosyvoice_repo_dir)
        model_dir = Path(settings.cosyvoice_model_dir)
        cache_dir = Path(settings.cosyvoice_cache_dir)

        if not tts_provider_config_service.native_sft_supported():
            raise RuntimeError("当前 zero-shot 配音模板模式请使用常驻 CosyVoice 服务，不支持 cosyvoice_local 子进程模式。")
        if not python_bin.exists():
            raise RuntimeError(f"CosyVoice Python 环境不存在: {python_bin}")
        if not helper_path.exists():
            raise RuntimeError(f"CosyVoice 本地助手脚本不存在: {helper_path}")
        if not repo_dir.exists():
            raise RuntimeError(f"CosyVoice 仓库不存在: {repo_dir}")
        if not model_dir.exists():
            raise RuntimeError(f"CosyVoice 模型目录不存在: {model_dir}")

        task_dir.mkdir(parents=True, exist_ok=True)
        cache_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = task_dir / "_cosyvoice_segments.json"
        manifest_path.write_text(
            json.dumps(segments, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        command = [
            str(python_bin),
            str(helper_path),
            "--repo-dir",
            str(repo_dir),
            "--model-dir",
            str(model_dir),
            "--cache-dir",
            str(cache_dir),
            "--voice",
            voice,
            "--manifest",
            str(manifest_path),
            "--speed",
            f"{tts_provider_config_service.normalize_speed(speed):.3f}",
        ]
        timeout_seconds = max(
            600,
            max(1, len(segments)) * int(settings.tts_timeout_seconds),
        )

        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("本地 CosyVoice 合成超时，请检查模型加载或显存占用。") from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip()
            raise RuntimeError(f"本地 CosyVoice 合成失败: {detail[:500]}") from exc

        detail = (completed.stdout or "").strip()
        if detail:
            logger.info("Local CosyVoice batch finished: %s", detail)


tts_cosyvoice_local_provider = TTSCosyVoiceLocalProvider()
