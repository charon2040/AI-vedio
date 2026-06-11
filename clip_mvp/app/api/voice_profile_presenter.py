from __future__ import annotations

from app.core.config import settings


def sample_text(prompt_text: str) -> str:
    raw = str(prompt_text or "").strip()
    if "<|endofprompt|>" in raw:
        return raw.split("<|endofprompt|>", 1)[-1].strip()
    return raw


def serialize_voice_profile(profile: dict) -> dict:
    source_type = str(profile.get("source_type", "") or "").strip().lower()
    return {
        "id": profile.get("id", ""),
        "label": profile.get("label", ""),
        "description": profile.get("description", ""),
        "language": profile.get("language", ""),
        "source_type": profile.get("source_type", ""),
        "voice_kind": "clone" if source_type == "user" else "standard",
        "is_default": bool(profile.get("is_default", False)),
        "is_active": bool(profile.get("is_active", True)),
        "sort_order": int(profile.get("sort_order", 0) or 0),
        "sample_text": sample_text(str(profile.get("prompt_text", "") or "")),
        "preview_available": bool(profile.get("prompt_wav_exists", False)),
        "preview_url": (
            f"{settings.api_prefix}/voice-profiles/{profile.get('id', '')}/audio"
            if profile.get("prompt_wav_exists")
            else ""
        ),
    }


def serialize_voice_profiles(profiles: list[dict]) -> list[dict]:
    return [serialize_voice_profile(item) for item in profiles]
