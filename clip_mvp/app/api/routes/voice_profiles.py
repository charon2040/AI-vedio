from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.api.auth_dependencies import current_user_id, get_current_user
from app.api.voice_profile_presenter import serialize_voice_profile, serialize_voice_profiles
from app.core.config import settings
from app.services.voice_profile_upload_service import voice_profile_upload_service
from app.services.voice_profile_service import voice_profile_service


router = APIRouter(prefix=settings.api_prefix)


@router.get("/voice-profiles")
async def list_voice_profiles(user=Depends(get_current_user)):
    items = voice_profile_service.list_profiles(active_only=True, user_id=current_user_id(user))
    return {"items": serialize_voice_profiles(items)}


@router.post("/voice-profiles")
async def create_voice_profile(
    label: str = Form(""),
    description: str = Form(""),
    language: str = Form(""),
    prompt_text: str = Form(""),
    prompt_audio: UploadFile = File(...),
    user=Depends(get_current_user),
):
    if not prompt_audio.filename:
        raise HTTPException(status_code=400, detail="缺少参考音频文件")

    try:
        content = await prompt_audio.read()
        profile = voice_profile_upload_service.create_user_profile_from_upload(
            label=label,
            description=description,
            language=str(language or "").strip(),
            prompt_text=prompt_text,
            original_filename=prompt_audio.filename,
            content=content,
            user_id=current_user_id(user),
        )
        return serialize_voice_profile(profile)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        await prompt_audio.close()


@router.get("/voice-profiles/{profile_id}")
async def get_voice_profile(profile_id: str, user=Depends(get_current_user)):
    profile = voice_profile_service.get_profile(profile_id, user_id=current_user_id(user))
    if not profile or profile.get("is_active") is False:
        raise HTTPException(status_code=404, detail="Voice profile not found")
    return serialize_voice_profile(profile)


@router.get("/voice-profiles/{profile_id}/audio")
async def get_voice_profile_audio(profile_id: str, user=Depends(get_current_user)):
    profile = voice_profile_service.get_profile(profile_id, user_id=current_user_id(user))
    if not profile or profile.get("is_active") is False:
        raise HTTPException(status_code=404, detail="Voice profile not found")
    wav_path = voice_profile_service.resolve_prompt_wav_path(profile)
    if not wav_path.exists():
        raise HTTPException(status_code=404, detail="Voice profile audio not found")
    return FileResponse(wav_path, media_type="audio/wav", filename=wav_path.name)
