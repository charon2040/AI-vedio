from __future__ import annotations

from typing import Dict

from app.core.config import settings
from app.services.tts_service import tts_service
from app.services.voice_profile_service import voice_profile_service


class VoiceBindingService:
    def normalize_voice_mode(self, voice_mode: str = "") -> str:
        return tts_service.normalize_voice_mode(voice_mode)

    def infer_voice_mode(
        self,
        *,
        voice_mode: str = "",
        voice_profile_id: str = "",
        tts_voice: str = "",
        user_id: str = "",
    ) -> str:
        raw = str(voice_mode or "").strip().lower()
        if raw in {"standard", "clone"}:
            return self.normalize_voice_mode(raw)
        profile = voice_profile_service.resolve_profile(
            str(voice_profile_id or "").strip(),
            label=str(tts_voice or "").strip(),
            allow_default=False,
            user_id=user_id,
        )
        if str(profile.get("source_type", "") or "").strip().lower() == "user":
            return "clone"
        return "standard"

    def resolve_payload(
        self,
        *,
        voice_mode: str = "",
        voice_profile_id: str = "",
        tts_voice: str = "",
        user_id: str = "",
    ) -> Dict[str, str]:
        normalized_mode = self.infer_voice_mode(
            voice_mode=voice_mode,
            voice_profile_id=voice_profile_id,
            tts_voice=tts_voice,
            user_id=user_id,
        )
        profile = voice_profile_service.resolve_profile(
            str(voice_profile_id or "").strip(),
            label=str(tts_voice or "").strip(),
            allow_default=normalized_mode != "clone",
            user_id=user_id,
        )
        source_type = str(profile.get("source_type", "") or "").strip().lower()
        if normalized_mode == "clone":
            if not profile:
                raise ValueError("克隆配音需要先选择一个已上传的配音模板。")
            if source_type != "user":
                raise ValueError("克隆配音只能使用你上传的参考音频模板。")
        elif profile and source_type == "user":
            raise ValueError("普通配音请使用内置音色；克隆模板请切换到“克隆配音（CosyVoice）”。")
        if profile:
            label = str(profile.get("label", "") or "").strip()
            return {
                "voice_profile_id": str(profile.get("id", "") or "").strip(),
                "voice_profile_label": label,
                "tts_voice": label or str(tts_voice or settings.tts_default_voice).strip(),
            }
        fallback_label = str(tts_voice or settings.tts_default_voice).strip() or "中文女"
        return {
            "voice_profile_id": "",
            "voice_profile_label": fallback_label,
            "tts_voice": fallback_label,
        }


voice_binding_service = VoiceBindingService()
