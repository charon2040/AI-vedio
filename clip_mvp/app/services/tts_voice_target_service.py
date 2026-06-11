from __future__ import annotations

from typing import Any, Dict

from app.core.config import settings
from app.services.tts_provider_config_service import tts_provider_config_service
from app.services.voice_profile_service import voice_profile_service


class TTSVoiceTargetService:
    def default_voice_ref(self, *, user_id: str = "") -> str:
        default_profile = voice_profile_service.get_default_profile(user_id=user_id)
        if default_profile:
            return str(default_profile.get("id", "") or "")
        return str(settings.tts_default_voice or "中文女").strip()

    def resolve_voice_target(self, voice: str, *, user_id: str = "") -> tuple[str, Dict[str, Any]]:
        normalized_voice = str(voice or "").strip()
        profile = voice_profile_service.resolve_profile(
            normalized_voice,
            label=normalized_voice,
            allow_default=True,
            user_id=user_id,
        )
        if tts_provider_config_service.native_sft_supported():
            if profile:
                return str(profile.get("label", "") or normalized_voice or settings.tts_default_voice), profile
            return normalized_voice or str(settings.tts_default_voice or "中文女").strip(), {}

        if not profile:
            raise RuntimeError(f"未找到可用的配音模板：{normalized_voice or 'default'}")
        if not profile.get("prompt_text"):
            raise RuntimeError(f"配音模板缺少参考文案：{profile.get('label', profile.get('id', 'unknown'))}")
        if not profile.get("prompt_wav_exists"):
            raise RuntimeError(f"配音模板缺少参考音频：{profile.get('prompt_wav_abs_path', '')}")
        return str(profile.get("id", "") or normalized_voice), profile


tts_voice_target_service = TTSVoiceTargetService()
