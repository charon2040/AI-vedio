from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

from app.core.config import settings


logger = logging.getLogger(__name__)


class VoiceProfileManifestService:
    _PROMPT_PREFIX = "You are a helpful assistant.<|endofprompt|>"

    def now_iso(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def slugify_profile_id(self, value: str) -> str:
        raw = str(value or "").strip().lower()
        slug = re.sub(r"[^a-z0-9]+", "_", raw).strip("_")
        if slug:
            return slug
        digest = hashlib.sha1(str(value or "").encode("utf-8")).hexdigest()[:10]
        return f"profile_{digest}"

    def resolve_profile_path(self, raw_path: str) -> Path:
        path = Path(str(raw_path or "").strip())
        if path.is_absolute():
            return path
        return settings.data_dir / path

    def relative_profile_path(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(settings.data_dir.resolve())).replace("\\", "/")
        except Exception:
            return str(path.resolve())

    def resolve_prompt_wav_path(self, profile: Dict[str, Any]) -> Path:
        return self.resolve_profile_path(str(profile.get("prompt_wav_path", "") or ""))

    def runtime_manifest_path(self) -> Path:
        return settings.tts_runtime_profile_manifest

    def load_seed_profiles(self) -> List[Dict[str, Any]]:
        payload = self._load_seed_manifest_payload()
        items = [
            self._normalize_seed_profile(profile_id, raw)
            for profile_id, raw in self._iter_seed_manifest_items(payload)
        ]

        profiles = [
            item
            for item in items
            if item.get("id") and item.get("label") and item.get("prompt_text") and item.get("prompt_wav_path")
        ]
        if not profiles:
            return []

        if not any(item.get("is_default") for item in profiles):
            preferred_label = str(settings.tts_default_voice or "").strip()
            for item in profiles:
                if str(item.get("label", "")).strip() == preferred_label:
                    item["is_default"] = True
                    break
            else:
                profiles[0]["is_default"] = True

        return sorted(
            profiles,
            key=lambda item: (
                0 if item.get("is_default") else 1,
                int(item.get("sort_order", 0) or 0),
                str(item.get("label", "")),
            ),
        )

    def export_runtime_manifest(self, profiles: Iterable[Dict[str, Any]]) -> Path:
        runtime_items: Dict[str, Dict[str, Any]] = {}
        for profile in profiles:
            prompt_text = self.prepare_runtime_prompt_text(str(profile.get("prompt_text", "") or "").strip())
            prompt_wav_path = str(profile.get("prompt_wav_path", "") or "").strip()
            if not prompt_text or not prompt_wav_path:
                continue
            wav_path = self.resolve_prompt_wav_path(profile)
            if not wav_path.exists():
                logger.warning(
                    "Skip runtime profile %s because prompt wav is missing: %s",
                    profile.get("id", ""),
                    wav_path,
                )
                continue
            runtime_items[str(profile.get("id", "") or "")] = {
                "label": str(profile.get("label", "") or ""),
                "description": str(profile.get("description", "") or ""),
                "language": str(profile.get("language", "") or ""),
                "source_type": str(profile.get("source_type", "seed") or "seed"),
                "prompt_text": prompt_text,
                "prompt_wav_path": self.relative_profile_path(wav_path),
                "sort_order": int(profile.get("sort_order", 0) or 0),
                "is_default": bool(profile.get("is_default", False)),
                "is_active": bool(profile.get("is_active", True)),
            }

        manifest_path = self.runtime_manifest_path()
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(runtime_items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return manifest_path

    def prepare_runtime_prompt_text(self, raw_text: str) -> str:
        normalized = str(raw_text or "").strip()
        if not normalized:
            return ""
        if "<|endofprompt|>" in normalized:
            return normalized
        return f"{self._PROMPT_PREFIX}{normalized}"

    def _load_seed_manifest_payload(self) -> Any:
        manifest_path = settings.tts_profile_manifest
        if not manifest_path.exists():
            logger.warning("TTS profile manifest not found: %s", manifest_path)
            return {}
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to read TTS profile manifest: %s", exc)
            return {}

    def _iter_seed_manifest_items(self, payload: Any) -> Iterable[tuple[str, Dict[str, Any]]]:
        if isinstance(payload, dict) and isinstance(payload.get("profiles"), list):
            for item in payload.get("profiles", []):
                if not isinstance(item, dict):
                    continue
                profile_id = str(item.get("id", "") or "").strip()
                if not profile_id:
                    profile_id = self.slugify_profile_id(str(item.get("label", "") or "profile"))
                yield profile_id, item
            return

        if isinstance(payload, dict) and isinstance(payload.get("profiles"), dict):
            for profile_id, item in payload.get("profiles", {}).items():
                if isinstance(item, dict):
                    yield str(profile_id).strip(), item
            return

        if isinstance(payload, dict):
            for profile_id, item in payload.items():
                if isinstance(item, dict):
                    yield str(profile_id).strip(), item

    def _normalize_seed_profile(self, profile_id_hint: str, raw: Dict[str, Any]) -> Dict[str, Any]:
        raw_label = str(raw.get("label", "") or "").strip()
        fallback_label = str(profile_id_hint or "").strip()
        profile_id = str(raw.get("id", "") or profile_id_hint or self.slugify_profile_id(raw_label)).strip()
        label = raw_label or fallback_label or profile_id
        prompt_wav_path = str(raw.get("prompt_wav_path", "") or raw.get("wav_path", "") or "").strip()
        resolved_wav_path = self.resolve_profile_path(prompt_wav_path) if prompt_wav_path else None

        return {
            "id": profile_id or self.slugify_profile_id(label),
            "label": label,
            "description": str(raw.get("description", "") or "").strip(),
            "prompt_text": str(raw.get("prompt_text", "") or "").strip(),
            "prompt_wav_path": prompt_wav_path,
            "prompt_wav_exists": bool(resolved_wav_path and resolved_wav_path.exists()),
            "prompt_wav_abs_path": str(resolved_wav_path) if resolved_wav_path is not None else "",
            "language": str(raw.get("language", "") or "").strip(),
            "source_type": "seed",
            "is_default": bool(raw.get("is_default", False)),
            "is_active": raw.get("is_active", True) is not False,
            "sort_order": int(raw.get("sort_order", 0) or 0),
        }


voice_profile_manifest_service = VoiceProfileManifestService()
