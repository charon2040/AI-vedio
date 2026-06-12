from __future__ import annotations

from typing import Any, Dict, List


class AlignmentSubtitleService:
    def normalize_subtitles_for_alignment(self, subtitles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for item in subtitles or []:
            try:
                start = int(item.get("start", 0) or 0)
                end = int(item.get("end", 0) or 0)
            except Exception:
                continue
            text = str(item.get("text", "") or "").strip()
            if not text or end <= start:
                continue
            normalized.append({"start": start, "end": end, "text": text})
        return sorted(normalized, key=lambda value: (int(value["start"]), int(value["end"])))

    def find_overlapping_range(
        self,
        subtitles: List[Dict[str, Any]],
        *,
        start_ms: int,
        end_ms: int,
    ) -> tuple[int, int] | None:
        start_index: int | None = None
        end_index: int | None = None
        for index, item in enumerate(subtitles):
            item_start = int(item.get("start", 0) or 0)
            item_end = int(item.get("end", 0) or 0)
            if item_end <= start_ms or item_start >= end_ms:
                continue
            if start_index is None:
                start_index = index
            end_index = index
        if start_index is None or end_index is None:
            return None
        return start_index, end_index

    def compose_segment_from_subtitles(
        self,
        subtitles: List[Dict[str, Any]],
        *,
        start_index: int,
        end_index: int,
        dubbing: str,
        voice_duration_ms: int,
    ) -> Dict[str, Any]:
        units = subtitles[start_index : end_index + 1]
        return {
            "start": int(units[0]["start"]),
            "end": int(units[-1]["end"]),
            "content": " ".join(str(item.get("text", "") or "").strip() for item in units).strip(),
            "dubbing": dubbing,
            "voice_duration_ms": int(voice_duration_ms or 0),
        }

    def content_for_subtitle_range(
        self,
        subtitles: List[Dict[str, Any]],
        *,
        start_ms: int,
        end_ms: int,
    ) -> str:
        texts: List[str] = []
        for item in subtitles:
            try:
                unit_start = int(item.get("start", 0) or 0)
                unit_end = int(item.get("end", 0) or 0)
            except Exception:
                continue
            if unit_end <= start_ms:
                continue
            if unit_start >= end_ms:
                break
            text = str(item.get("text", "") or "").strip()
            if text:
                texts.append(text)
        return " ".join(texts).strip()


alignment_subtitle_service = AlignmentSubtitleService()
