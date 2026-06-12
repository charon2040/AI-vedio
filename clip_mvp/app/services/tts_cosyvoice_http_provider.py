from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

import requests

from app.core.config import settings
from app.services.cosyvoice_runtime_service import cosyvoice_runtime_service
from app.services.tts_provider_config_service import tts_provider_config_service
from app.services.tts_voice_target_service import tts_voice_target_service


logger = logging.getLogger(__name__)


class TTSCosyVoiceHttpProvider:
    def synthesize_to_file(
        self,
        *,
        text: str,
        voice: str,
        output_path: Path,
        speed: float = 1.0,
        provider: str,
        user_id: str = "",
    ) -> Path:
        base_url = str(settings.cosyvoice_base_url or "").rstrip("/")
        endpoint = str(settings.cosyvoice_sft_endpoint or "/inference_sft").strip() or "/inference_sft"
        speaker_id, profile = tts_voice_target_service.resolve_voice_target(voice, user_id=user_id)
        payload: Dict[str, str] = {
            "tts_text": text,
            "spk_id": speaker_id,
            "speed": f"{tts_provider_config_service.normalize_speed(speed):.3f}",
        }
        if not tts_provider_config_service.native_sft_supported():
            endpoint = "/inference_zero_shot_spk"
            payload = {
                "tts_text": text,
                "spk_id": speaker_id,
                "speed": f"{tts_provider_config_service.normalize_speed(speed):.3f}",
            }
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
        url = f"{base_url}{endpoint}"

        response = None
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response = requests.post(
                    url,
                    data=payload,
                    timeout=(10.0, float(settings.tts_http_read_timeout_seconds)),
                )
                break
            except requests.RequestException as exc:
                last_error = exc
                if attempt == 0 and tts_provider_config_service.is_managed_local_cosyvoice(provider):
                    cosyvoice_runtime_service.ensure_service_running()
                    continue
                raise RuntimeError(
                    f"CosyVoice 服务不可用，请确认本地 TTS 服务已启动：{url}"
                ) from exc

        if response is None:
            raise RuntimeError(
                f"CosyVoice 服务不可用，请确认本地 TTS 服务已启动：{url}"
            ) from last_error

        if response.status_code != 200:
            detail = response.text.strip()
            raise RuntimeError(
                f"CosyVoice 合成失败：HTTP {response.status_code} {detail[:200]}"
            )
        if not response.content:
            raise RuntimeError("CosyVoice 没有返回有效音频数据。")

        output_path.write_bytes(response.content)
        logger.info(
            "CosyVoice HTTP synthesized segment: voice=%s chars=%s output=%s",
            profile.get("label", "") or speaker_id,
            len(text),
            output_path.name,
        )
        return output_path


tts_cosyvoice_http_provider = TTSCosyVoiceHttpProvider()
