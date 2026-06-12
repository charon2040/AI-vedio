from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

from app.core.config import settings
from app.services.tts_service import tts_service
from app.services.voice_profile_service import voice_profile_service


class TTSCacheService:
    def cache_path(
        self,
        voice: str,
        text: str,
        *,
        speed: float = 1.0,
        voice_mode: str = "",
        user_id: str = "",
    ) -> Path:
        cache_dir = settings.voiceover_dir / "_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        profile = voice_profile_service.resolve_profile(
            voice,
            label=voice,
            allow_default=True,
            user_id=user_id,
        )
        cache_key = hashlib.sha256(
            json.dumps(
                self._cache_payload(
                    voice=voice,
                    text=text,
                    speed=speed,
                    voice_mode=voice_mode,
                    profile=profile,
                    user_id=user_id,
                ),
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        return cache_dir / f"{cache_key}.wav"

    def _cache_payload(
        self,
        *,
        voice: str,
        text: str,
        speed: float,
        voice_mode: str,
        profile: Dict[str, Any],
        user_id: str,
    ) -> Dict[str, Any]:
        prompt_wav_raw = str(profile.get("prompt_wav_abs_path", "") or "").strip()
        prompt_wav_path = Path(prompt_wav_raw) if prompt_wav_raw else None
        prompt_wav_stat = None
        if prompt_wav_path is not None and prompt_wav_path.exists():
            try:
                prompt_wav_stat = prompt_wav_path.stat()
            except Exception:
                prompt_wav_stat = None

        return {
            "voice_mode": tts_service.normalize_voice_mode(voice_mode),
            "provider": tts_service._provider_for_mode(voice_mode),
            "voice": voice,
            "text": str(text or "").strip(),
            "speed": round(float(speed or settings.tts_speed_default), 3),
            "cosyvoice_model_dir": str(settings.cosyvoice_model_dir or ""),
            "profile_id": str(profile.get("id", "") or ""),
            "profile_user_id": str(profile.get("user_id", "") or ""),
            "request_user_id": str(user_id or ""),
            "profile_prompt_text": str(profile.get("prompt_text", "") or ""),
            "profile_prompt_wav": str(prompt_wav_path) if prompt_wav_path is not None else "",
            "profile_prompt_wav_mtime_ns": int(prompt_wav_stat.st_mtime_ns) if prompt_wav_stat else 0,
            "profile_prompt_wav_size": int(prompt_wav_stat.st_size) if prompt_wav_stat else 0,
        }


tts_cache_service = TTSCacheService()
