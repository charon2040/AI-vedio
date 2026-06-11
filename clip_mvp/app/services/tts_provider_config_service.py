from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.services.cosyvoice_runtime_service import cosyvoice_runtime_service


class TTSProviderConfigService:
    def get_provider(self) -> str:
        return str(settings.tts_provider or "cosyvoice").strip().lower()

    def normalize_voice_mode(self, voice_mode: str | None) -> str:
        value = str(voice_mode or settings.tts_default_mode or "standard").strip().lower()
        return value if value in {"standard", "clone"} else "standard"

    def normalize_speed(self, speed: float | int | str | None) -> float:
        try:
            value = float(speed if speed is not None else settings.tts_speed_default)
        except Exception:
            value = float(settings.tts_speed_default)
        return max(
            float(settings.tts_speed_min),
            min(float(settings.tts_speed_max), value),
        )

    def provider_for_mode(self, voice_mode: str | None) -> str:
        normalized_mode = self.normalize_voice_mode(voice_mode)
        if normalized_mode == "clone":
            return str(settings.tts_clone_provider or settings.tts_provider or "cosyvoice").strip().lower()
        return str(settings.tts_standard_provider or settings.tts_provider or "cosyvoice").strip().lower()

    def native_sft_supported(self) -> bool:
        return (Path(settings.cosyvoice_model_dir) / "spk2info.pt").exists()

    def is_managed_local_cosyvoice(self, provider: str) -> bool:
        return cosyvoice_runtime_service.is_managed_local_service(provider)

    def is_subprocess_local_cosyvoice(self, provider: str) -> bool:
        return cosyvoice_runtime_service.is_subprocess_local_service(provider)

    def supports_native_speed(self, provider: str) -> bool:
        return (
            self.is_managed_local_cosyvoice(provider)
            or self.is_subprocess_local_cosyvoice(provider)
            or provider in {"cosyvoice_http", "cosyvoice_service"}
        )


tts_provider_config_service = TTSProviderConfigService()
