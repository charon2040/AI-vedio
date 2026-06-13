from __future__ import annotations

from typing import Any, Dict, List

from openai import OpenAI

from app.core.config import settings
from app.services import llm_alignment_service
from app.services import llm_narration_service


class LLMService:
    def __init__(self) -> None:
        self._client: OpenAI | None = None

    def _ensure_client(self) -> bool:
        if self._client is not None:
            return True
        if not settings.llm_api_key:
            return False
        self._client = OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            timeout=float(settings.llm_timeout_seconds),
        )
        return True

    def generate_narration_draft(
        self,
        requirements: str,
        subtitles: List[Dict[str, Any]],
        duration_seconds: int = 0,
        style: str = "",
        project_context: str = "",
    ) -> Dict[str, Any]:
        if not self._ensure_client():
            raise RuntimeError("未配置 LLM，无法根据原始字幕生成文案草稿。")
        return llm_narration_service.generate_narration_draft(
            self._client,
            requirements,
            subtitles,
            duration_seconds=duration_seconds,
            style=style,
            project_context=project_context,
        )

    def align_beats_with_subtitles(
        self,
        beats: List[Dict[str, Any]],
        subtitles: List[Dict[str, Any]],
        style: str = "",
        project_context: str = "",
    ) -> List[Dict[str, Any]]:
        if not beats or not subtitles or not self._ensure_client():
            return []
        return llm_alignment_service.align_beats_with_subtitles(
            self._client,
            beats,
            subtitles,
            style=style,
            project_context=project_context,
        )

    def align_voiceover_beats_with_subtitles(
        self,
        beats: List[Dict[str, Any]],
        subtitles: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not beats or not subtitles or not self._ensure_client():
            return []
        return llm_alignment_service.align_voiceover_beats_with_subtitles(
            self._client,
            beats,
            subtitles,
        )


llm_service = LLMService()
