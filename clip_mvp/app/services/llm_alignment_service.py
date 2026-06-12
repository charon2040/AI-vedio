from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from openai import OpenAI

from app.core.config import settings
from app.services import llm_format_service as llm_format
from app.services import llm_prompt_service as llm_prompts


logger = logging.getLogger(__name__)


def align_beats_with_subtitles(
    client: OpenAI,
    beats: List[Dict[str, Any]],
    subtitles: List[Dict[str, Any]],
    style: str = "",
    project_context: str = "",
) -> List[Dict[str, Any]]:
    payload_beats: List[Dict[str, Any]] = []
    for index, beat in enumerate(beats, start=1):
        text = str(beat.get("text", "") or "").strip()
        if not text:
            continue
        voice_duration_ms = int(beat.get("voice_duration_ms", 0) or 0)
        payload_beats.append(
            {
                "id": str(beat.get("id", "") or f"beat_{index}"),
                "title": str(beat.get("title", "") or f"第 {index} 段"),
                "text": text,
                "order": int(beat.get("order", index) or index),
                "voice_duration_ms": voice_duration_ms,
                **llm_format.beat_duration_guidance(voice_duration_ms),
            }
        )

    if not payload_beats:
        return []

    subtitle_units = llm_format.build_alignment_units(subtitles)
    if not subtitle_units:
        return []

    user_content = json.dumps(
        {
            "style": style,
            "project_context": str(project_context or "").strip()[:12000],
            "beats": payload_beats,
            "context_mode": "raw_full_subtitle_units",
            "subtitle_units": subtitle_units,
        },
        ensure_ascii=False,
    )

    try:
        request_timeout = max(float(settings.llm_timeout_seconds), 180.0)
        logger.info(
            "LLM beat align request: model=%s timeout=%ss beats=%s subtitle_units=%s raw_chars=%s",
            settings.llm_model,
            request_timeout,
            len(payload_beats),
            len(subtitle_units),
            llm_format.subtitle_char_count(subtitle_units),
        )
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": llm_prompts.BEAT_ALIGNMENT_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.1,
            timeout=request_timeout,
        )
        parsed = json.loads(llm_format.clean_content(response.choices[0].message.content or ""))
        if not isinstance(parsed, list):
            return []
        return llm_format.normalize_alignment_response(parsed, subtitle_units)
    except Exception as exc:
        logger.warning("LLM beat align failed without local fallback: %s", exc)
        return []


def align_voiceover_beats_with_subtitles(
    client: OpenAI,
    beats: List[Dict[str, Any]],
    subtitles: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    payload_beats: List[Dict[str, Any]] = []
    for index, beat in enumerate(beats, start=1):
        text = str(beat.get("text", "") or "").strip()
        if not text:
            continue
        payload_beats.append(
            {
                "id": str(beat.get("id", "") or f"beat_{index}"),
                "title": str(beat.get("title", "") or f"第 {index} 段"),
                "text": text,
                "order": int(beat.get("order", index) or index),
            }
        )

    if not payload_beats:
        return []

    subtitle_units = llm_format.build_alignment_units(subtitles)
    if not subtitle_units:
        return []

    user_content = json.dumps(
        {
            "beats": payload_beats,
            "context_mode": "uploaded_voiceover_raw_asr_units",
            "subtitle_units": subtitle_units,
        },
        ensure_ascii=False,
    )

    try:
        request_timeout = max(float(settings.llm_timeout_seconds), 180.0)
        logger.info(
            "LLM voiceover segmentation request: model=%s timeout=%ss beats=%s subtitle_units=%s raw_chars=%s",
            settings.llm_model,
            request_timeout,
            len(payload_beats),
            len(subtitle_units),
            llm_format.subtitle_char_count(subtitle_units),
        )
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": llm_prompts.VOICEOVER_BEAT_SEGMENTATION_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.0,
            timeout=request_timeout,
        )
        parsed = json.loads(llm_format.clean_content(response.choices[0].message.content or ""))
        if not isinstance(parsed, list):
            return []
        return llm_format.normalize_alignment_response(parsed, subtitle_units)
    except Exception as exc:
        logger.warning("LLM voiceover segmentation failed: %s", exc)
        return []
