from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from app.services.cosyvoice_runtime_service import cosyvoice_runtime_service
from app.services.tts_cosyvoice_http_provider import tts_cosyvoice_http_provider
from app.services.tts_cosyvoice_local_provider import tts_cosyvoice_local_provider
from app.services.tts_mock_provider import tts_mock_provider
from app.services.tts_provider_config_service import tts_provider_config_service
from app.services.tts_voice_target_service import tts_voice_target_service


class TTSProviderService:
    def get_provider(self) -> str:
        return tts_provider_config_service.get_provider()

    def normalize_voice_mode(self, voice_mode: str | None) -> str:
        return tts_provider_config_service.normalize_voice_mode(voice_mode)

    def normalize_speed(self, speed: float | int | str | None) -> float:
        return tts_provider_config_service.normalize_speed(speed)

    def provider_for_mode(self, voice_mode: str | None) -> str:
        return tts_provider_config_service.provider_for_mode(voice_mode)

    def native_sft_supported(self) -> bool:
        return tts_provider_config_service.native_sft_supported()

    def default_voice_ref(self, *, user_id: str = "") -> str:
        return tts_voice_target_service.default_voice_ref(user_id=user_id)

    def is_managed_local_cosyvoice(self, provider: str) -> bool:
        return tts_provider_config_service.is_managed_local_cosyvoice(provider)

    def is_subprocess_local_cosyvoice(self, provider: str) -> bool:
        return tts_provider_config_service.is_subprocess_local_cosyvoice(provider)

    def supports_native_speed(self, provider: str) -> bool:
        return tts_provider_config_service.supports_native_speed(provider)

    def synthesize_to_file(
        self,
        *,
        text: str,
        voice: str,
        output_path: Path,
        voice_mode: str | None = None,
        speed: float = 1.0,
        user_id: str = "",
    ) -> Path:
        normalized_mode = self.normalize_voice_mode(voice_mode)
        provider = self.provider_for_mode(normalized_mode)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if provider == "mock":
            return tts_mock_provider.synthesize_to_file(output_path)
        if self.is_managed_local_cosyvoice(provider):
            cosyvoice_runtime_service.ensure_service_running()
            return tts_cosyvoice_http_provider.synthesize_to_file(
                text=text,
                voice=voice,
                output_path=output_path,
                speed=speed,
                provider=provider,
                user_id=user_id,
            )
        if self.is_subprocess_local_cosyvoice(provider):
            return tts_cosyvoice_local_provider.synthesize_to_file(
                text=text,
                voice=voice,
                output_path=output_path,
                speed=speed,
                user_id=user_id,
            )
        if provider in {"cosyvoice_http", "cosyvoice_service"}:
            return tts_cosyvoice_http_provider.synthesize_to_file(
                text=text,
                voice=voice,
                output_path=output_path,
                speed=speed,
                provider=provider,
                user_id=user_id,
            )
        raise RuntimeError(f"不支持的 TTS provider: {provider} mode={normalized_mode}")

    def synthesize_cosyvoice_local_batch(
        self,
        *,
        task_dir: Path,
        voice: str,
        segments: List[Dict[str, Any]],
        speed: float = 1.0,
    ) -> List[Dict[str, Any]]:
        return tts_cosyvoice_local_provider.synthesize_batch(
            task_dir=task_dir,
            voice=voice,
            segments=segments,
            speed=speed,
        )


tts_provider_service = TTSProviderService()
