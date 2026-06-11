from __future__ import annotations

import hashlib
from pathlib import Path
import uuid

from app.core.config import settings
from app.services.cosyvoice_runtime_service import cosyvoice_runtime_service
from app.services.media_service import media_service
from app.services.voice_profile_service import voice_profile_service


class VoiceProfileUploadService:
    def create_user_profile_from_upload(
        self,
        *,
        label: str,
        description: str,
        language: str,
        prompt_text: str,
        original_filename: str,
        content: bytes,
        user_id: str = "local",
    ) -> dict:
        normalized_label = str(label or "").strip()
        normalized_prompt_text = str(prompt_text or "").strip()
        if not normalized_label:
            raise ValueError("模板名称不能为空")
        if not normalized_prompt_text:
            raise ValueError("参考文案不能为空")
        if not original_filename:
            raise ValueError("缺少参考音频文件")
        if not content:
            raise ValueError("参考音频文件为空")

        suffix = "".join(Path(original_filename).suffixes) or ".bin"
        digest = hashlib.sha1(content).hexdigest()[:12]
        temp_path = settings.temp_dir / f"voice_profile_upload_{digest}{suffix}"
        output_wav_path = (
            settings.tts_user_profile_audio_dir
            / f"voice_profile_{digest}_{uuid.uuid4().hex[:8]}_prompt.wav"
        )
        created = False
        try:
            temp_path.write_bytes(content)
            if not media_service.normalize_reference_audio(str(temp_path), str(output_wav_path)):
                raise ValueError("参考音频转换失败，请检查文件格式或 FFmpeg 配置")

            relative_wav_path = str(
                output_wav_path.resolve().relative_to(settings.data_dir.resolve())
            ).replace("\\", "/")
            profile = voice_profile_service.create_user_profile(
                label=normalized_label,
                description=str(description or "").strip(),
                language=str(language or "").strip(),
                prompt_text=normalized_prompt_text,
                prompt_wav_path=relative_wav_path,
                user_id=user_id,
            )
            if cosyvoice_runtime_service.is_managed_local_service():
                cosyvoice_runtime_service.restart_service()
            created = True
            return profile
        finally:
            temp_path.unlink(missing_ok=True)
            if not created:
                output_wav_path.unlink(missing_ok=True)


voice_profile_upload_service = VoiceProfileUploadService()
