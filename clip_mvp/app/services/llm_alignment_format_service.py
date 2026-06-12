from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.services.llm_subtitle_format_service import normalize_subtitle_text


logger = logging.getLogger(__name__)


def selected_duration_tolerances(voice_duration_ms: int) -> Dict[str, int]:
    target_ms = max(0, int(voice_duration_ms or 0))
    if target_ms <= 0:
        return {
            "short_tolerance_ms": 0,
            "long_tolerance_ms": 0,
        }

    return {
        "short_tolerance_ms": 0,
        "long_tolerance_ms": 700,
    }


def beat_duration_guidance(voice_duration_ms: int) -> Dict[str, int]:
    target_ms = max(0, int(voice_duration_ms or 0))
    if target_ms <= 0:
        return {
            "target_ms": 0,
            "final_min_ms": 0,
            "final_max_ms": 0,
            "semantic_hard_max_ms": 0,
        }

    tolerances = selected_duration_tolerances(target_ms)
    return {
        "target_ms": target_ms,
        "final_min_ms": max(1, target_ms - int(tolerances["short_tolerance_ms"])),
        "final_max_ms": target_ms + int(tolerances["long_tolerance_ms"]),
        "semantic_hard_max_ms": max(target_ms + 18000, int(target_ms * 1.65)),
    }


def normalize_alignment_response(
    parsed: List[Any],
    subtitle_units: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    unit_lookup = {
        str(unit.get("unit_id", "") or "").strip(): unit
        for unit in subtitle_units
        if str(unit.get("unit_id", "") or "").strip()
    }
    ordered_unit_ids = [
        str(unit.get("unit_id", "") or "").strip()
        for unit in subtitle_units
    ]
    unit_index_lookup = {
        unit_id: index
        for index, unit_id in enumerate(ordered_unit_ids)
        if unit_id
    }

    normalized: List[Dict[str, Any]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        beat_id = str(item.get("beat_id", "") or "").strip()
        start_unit_id = str(item.get("start_unit_id", "") or "").strip()
        end_unit_id = str(item.get("end_unit_id", "") or "").strip()
        semantic_start_unit_id = str(item.get("semantic_start_unit_id", "") or "").strip()
        semantic_end_unit_id = str(item.get("semantic_end_unit_id", "") or "").strip()
        start_unit = unit_lookup.get(start_unit_id)
        end_unit = unit_lookup.get(end_unit_id)

        if start_unit is None or end_unit is None:
            try:
                raw_start = int(item.get("start", 0) or 0)
                raw_end = int(item.get("end", 0) or 0)
            except Exception:
                continue
            raw_candidates = [
                unit
                for unit in subtitle_units
                if max(
                    0,
                    min(raw_end, int(unit.get("end", 0) or 0))
                    - max(raw_start, int(unit.get("start", 0) or 0)),
                )
                > 0
            ]
            if raw_candidates:
                start_unit = raw_candidates[0]
                end_unit = raw_candidates[-1]
                start_unit_id = str(start_unit.get("unit_id", "") or "").strip()
                end_unit_id = str(end_unit.get("unit_id", "") or "").strip()

        if start_unit is None or end_unit is None:
            continue

        start_index = unit_index_lookup.get(start_unit_id, -1)
        end_index = unit_index_lookup.get(end_unit_id, -1)
        if start_index < 0 or end_index < 0:
            continue
        if end_index < start_index:
            start_index, end_index = end_index, start_index
            start_unit, end_unit = end_unit, start_unit
            start_unit_id, end_unit_id = end_unit_id, start_unit_id

        unit_start = int(start_unit.get("start", 0) or 0)
        unit_end = int(end_unit.get("end", 0) or 0)
        try:
            raw_start = int(item.get("start", unit_start) or unit_start)
            raw_end = int(item.get("end", unit_end) or unit_end)
        except Exception:
            raw_start = unit_start
            raw_end = unit_end

        timeline_start = min(
            int(unit.get("start", 0) or 0)
            for unit in subtitle_units
        )
        timeline_end = max(
            int(unit.get("end", 0) or 0)
            for unit in subtitle_units
        )
        start = max(timeline_start, min(raw_start, timeline_end))
        end = max(start, min(raw_end, timeline_end))
        if end <= start:
            continue

        semantic_start_unit = unit_lookup.get(semantic_start_unit_id) or start_unit
        semantic_end_unit = unit_lookup.get(semantic_end_unit_id) or end_unit
        semantic_start = int(
            item.get("semantic_start", semantic_start_unit.get("start", start))
            or semantic_start_unit.get("start", start)
        )
        semantic_end = int(
            item.get("semantic_end", semantic_end_unit.get("end", end))
            or semantic_end_unit.get("end", end)
        )
        if semantic_end < semantic_start:
            semantic_start, semantic_end = semantic_end, semantic_start

        content = str(item.get("content", "") or "").strip()
        if not content:
            content = " ".join(
                normalize_subtitle_text(unit.get("text", ""))
                for unit in subtitle_units[start_index : end_index + 1]
                if normalize_subtitle_text(unit.get("text", ""))
            ).strip()
        if not content:
            continue

        normalized.append(
            {
                "beat_id": beat_id,
                "start_unit_id": start_unit_id,
                "end_unit_id": end_unit_id,
                "start": start,
                "end": end,
                "semantic_start_unit_id": semantic_start_unit_id or start_unit_id,
                "semantic_end_unit_id": semantic_end_unit_id or end_unit_id,
                "semantic_start": semantic_start,
                "semantic_end": semantic_end,
                "content": content,
            }
        )

    logger.info("LLM beat align response parsed successfully: items=%s", len(normalized))
    return normalized
