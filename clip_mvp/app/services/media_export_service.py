from __future__ import annotations

import math
import re
from typing import Any, Dict, Iterable, List


class MediaExportService:
    _target_chars_per_line = 16
    _soft_max_chars = 20
    _hard_max_chars = 26
    _min_cue_duration_ms = 900
    _max_cue_duration_ms = 2800

    def build_timeline_segments(self, segments: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        timeline_segments: List[Dict[str, Any]] = []
        current_time = 0
        for seg in segments:
            source_start = int(seg.get("start", 0) or 0)
            source_end = int(seg.get("end", 0) or 0)
            duration = max(0, source_end - source_start)
            item = dict(seg)
            item["source_start"] = source_start
            item["source_end"] = source_end
            item["start"] = current_time
            item["end"] = current_time + duration
            timeline_segments.append(item)
            current_time += duration
        return timeline_segments

    def remap_subtitles_to_cut(self, subtitles: List[Dict[str, Any]], segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        mapped: List[Dict[str, Any]] = []
        timeline_cursor = 0
        for seg in segments:
            seg_start = int(seg.get("start", 0) or 0)
            seg_end = int(seg.get("end", 0) or 0)
            for subtitle in subtitles:
                sub_start = int(subtitle.get("start", 0) or 0)
                sub_end = int(subtitle.get("end", 0) or 0)
                if sub_end <= seg_start or sub_start >= seg_end:
                    continue
                start = max(sub_start, seg_start)
                end = min(sub_end, seg_end)
                text = str(subtitle.get("text", "")).strip()
                if not text or end <= start:
                    continue
                mapped.append(
                    {
                        "start": timeline_cursor + start - seg_start,
                        "end": timeline_cursor + end - seg_start,
                        "text": text,
                    }
                )
            timeline_cursor += max(0, seg_end - seg_start)
        return mapped

    def export_srt(self, subtitles: List[Dict[str, Any]], output_path: str) -> bool:
        try:
            lines: List[str] = []
            for index, subtitle in enumerate(subtitles, start=1):
                lines.append(str(index))
                lines.append(
                    f"{self._format_srt_time(int(subtitle['start']))} --> {self._format_srt_time(int(subtitle['end']))}"
                )
                lines.append(str(subtitle["text"]).strip())
                lines.append("")
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(lines))
            return True
        except Exception:
            return False

    def build_single_line_subtitles_from_beats(
        self,
        beats: List[Dict[str, Any]],
        *,
        total_duration_ms: int = 0,
    ) -> List[Dict[str, Any]]:
        cues: List[Dict[str, Any]] = []
        timeline_ms = 0
        for index, beat in enumerate(beats or [], start=1):
            text = str(beat.get("text", "") or beat.get("dubbing", "") or "").strip()
            if not text:
                continue
            duration_ms = max(0, int(beat.get("voice_duration_ms", 0) or 0))
            if duration_ms <= 0:
                duration_ms = self._estimate_subtitle_duration_ms(text)
            beat_cues = self._split_text_for_single_line(text)
            cues.extend(self._allocate_cue_times(beat_cues, timeline_ms, duration_ms))
            timeline_ms += duration_ms

        if total_duration_ms > 0 and cues:
            cues[-1]["end"] = min(int(total_duration_ms), max(cues[-1]["start"] + 1, int(cues[-1]["end"])))
        return cues

    def build_single_line_subtitles_from_voice_timeline(
        self,
        beats: List[Dict[str, Any]],
        timeline_items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        cues: List[Dict[str, Any]] = []
        for beat, item in zip(beats or [], timeline_items or []):
            text = str(beat.get("text", "") or beat.get("dubbing", "") or "").strip()
            if not text:
                continue
            start_ms = max(0, int(item.get("start_ms", 0) or 0))
            voice_duration_ms = max(
                0,
                int(item.get("voice_duration_ms", 0) or beat.get("voice_duration_ms", 0) or 0),
            )
            if voice_duration_ms <= 0:
                voice_duration_ms = self._estimate_subtitle_duration_ms(text)
            beat_cues = self._split_text_for_single_line(text)
            cues.extend(self._allocate_cue_times(beat_cues, start_ms, voice_duration_ms))
        return cues

    def normalize_single_line_subtitles(
        self,
        subtitles: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for subtitle in subtitles or []:
            try:
                start = int(subtitle.get("start", 0) or 0)
                end = int(subtitle.get("end", 0) or 0)
            except Exception:
                continue
            if end <= start:
                continue
            text = str(subtitle.get("text", "") or "").strip()
            if not text:
                continue
            pieces = self._split_text_for_single_line(text)
            normalized.extend(self._allocate_cue_times(pieces, start, end - start))
        return normalized

    def export_ass(
        self,
        subtitles: List[Dict[str, Any]],
        output_path: str,
        *,
        video_width: int = 1920,
        video_height: int = 1080,
    ) -> bool:
        try:
            width = max(1, int(video_width or 1920))
            height = max(1, int(video_height or 1080))
            font_size = max(18, int(round(36 * height / 1080)))
            margin_v = max(42, int(round(72 * height / 1080)))
            outline = max(1, int(round(2 * height / 1080)))
            shadow = max(0, int(round(1 * height / 1080)))
            lines = [
                "[Script Info]",
                "ScriptType: v4.00+",
                f"PlayResX: {width}",
                f"PlayResY: {height}",
                "ScaledBorderAndShadow: yes",
                "WrapStyle: 2",
                "",
                "[V4+ Styles]",
                "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
                "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
                "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
                "Style: Default,Microsoft YaHei,"
                f"{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H64000000,"
                f"0,0,0,0,100,100,0,0,1,{outline},{shadow},2,80,80,{margin_v},1",
                "",
                "[Events]",
                "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
            ]
            for subtitle in subtitles or []:
                try:
                    start = int(subtitle.get("start", 0) or 0)
                    end = int(subtitle.get("end", 0) or 0)
                except Exception:
                    continue
                text = self._escape_ass_text(str(subtitle.get("text", "") or "").strip())
                if not text or end <= start:
                    continue
                lines.append(
                    f"Dialogue: 0,{self._format_ass_time(start)},{self._format_ass_time(end)},"
                    f"Default,,0,0,0,,{{\\an2}}{text}"
                )
            with open(output_path, "w", encoding="utf-8-sig") as handle:
                handle.write("\n".join(lines))
            return True
        except Exception:
            return False

    def export_edl(self, segments: List[Dict[str, Any]], original_video_name: str, output_path: str, fps: float = 25.0) -> bool:
        try:
            lines = ["TITLE: CLIP_MVP", "FCM: NON-DROP FRAME", ""]
            timeline_ms = 0
            for index, segment in enumerate(segments, start=1):
                start_ms = int(segment.get("start", 0) or 0)
                end_ms = int(segment.get("end", 0) or 0)
                duration = max(0, end_ms - start_ms)
                lines.append(
                    f"{index:03d}  AX       V     C        "
                    f"{self._ms_to_smpte(start_ms, fps)} {self._ms_to_smpte(end_ms, fps)} "
                    f"{self._ms_to_smpte(timeline_ms, fps)} {self._ms_to_smpte(timeline_ms + duration, fps)}"
                )
                lines.append(f"* FROM CLIP NAME: {original_video_name}")
                lines.append("")
                timeline_ms += duration
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(lines))
            return True
        except Exception:
            return False

    def _format_srt_time(self, ms: int) -> str:
        total = max(0, int(ms))
        hours = total // 3_600_000
        minutes = (total % 3_600_000) // 60_000
        seconds = (total % 60_000) // 1000
        millis = total % 1000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"

    def _ms_to_smpte(self, ms: int, fps: float = 25.0) -> str:
        total_seconds = ms / 1000.0
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        frames = int((total_seconds - int(total_seconds)) * fps)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"

    def _format_ass_time(self, ms: int) -> str:
        total = max(0, int(ms))
        hours = total // 3_600_000
        minutes = (total % 3_600_000) // 60_000
        seconds = (total % 60_000) // 1000
        centiseconds = int(round((total % 1000) / 10.0))
        if centiseconds >= 100:
            seconds += 1
            centiseconds = 0
        return f"{hours:d}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"

    def _estimate_subtitle_duration_ms(self, text: str) -> int:
        char_count = max(1, self._display_len(text))
        return max(
            self._min_cue_duration_ms,
            min(self._max_cue_duration_ms * 3, int(char_count / 5.0 * 1000)),
        )

    def _allocate_cue_times(
        self,
        texts: List[str],
        start_ms: int,
        duration_ms: int,
    ) -> List[Dict[str, Any]]:
        if not texts:
            return []
        start = max(0, int(start_ms or 0))
        duration = max(len(texts), int(duration_ms or 0))
        weights = [max(1, self._display_len(text)) for text in texts]
        total_weight = max(1, sum(weights))
        result: List[Dict[str, Any]] = []
        cursor = start
        for index, text in enumerate(texts):
            if index == len(texts) - 1:
                end = start + duration
            else:
                raw = int(round(duration * weights[index] / total_weight))
                raw = max(self._min_cue_duration_ms, min(self._max_cue_duration_ms, raw))
                remaining_min = len(texts) - index - 1
                latest_end = start + duration - remaining_min
                end = min(cursor + raw, latest_end)
            if end <= cursor:
                end = cursor + 1
            result.append({"start": cursor, "end": end, "text": text})
            cursor = end
        return result

    def _split_text_for_single_line(self, text: str) -> List[str]:
        normalized = self._normalize_subtitle_text(text)
        if not normalized:
            return []

        punctuation_parts = self._split_by_pattern(normalized, r"(?<=[。！？!?；;])")
        weak_parts: List[str] = []
        for part in punctuation_parts:
            if self._display_len(part) <= self._hard_max_chars:
                weak_parts.append(part)
            else:
                weak_parts.extend(self._split_by_weak_punctuation(part))

        semantic_parts: List[str] = []
        for part in weak_parts:
            if self._display_len(part) <= self._hard_max_chars:
                semantic_parts.append(part)
            else:
                semantic_parts.extend(self._split_by_semantic_markers(part))

        result: List[str] = []
        for part in semantic_parts:
            if self._display_len(part) <= self._hard_max_chars:
                result.append(part)
            else:
                result.extend(self._hard_split_phrase(part))

        return self._merge_short_subtitle_parts(result)

    def _normalize_subtitle_text(self, text: str) -> str:
        value = re.sub(r"\s+", "", str(text or "").strip())
        value = value.replace("\r", "").replace("\n", "")
        return value

    def _split_by_pattern(self, text: str, pattern: str) -> List[str]:
        return [part for part in re.split(pattern, text) if part]

    def _split_by_weak_punctuation(self, text: str) -> List[str]:
        parts = [part for part in re.split(r"(?<=[，,、：:])", text) if part]
        return parts if len(parts) > 1 else [text]

    def _split_by_semantic_markers(self, text: str) -> List[str]:
        markers = (
            "但是",
            "但",
            "不过",
            "随后",
            "接着",
            "紧接着",
            "与此同时",
            "同时",
            "关键时刻",
            "最终",
            "因此",
            "于是",
            "然后",
            "这也让",
            "直接让",
            "彻底",
        )
        pieces = [text]
        for marker in markers:
            next_pieces: List[str] = []
            for piece in pieces:
                if self._display_len(piece) <= self._hard_max_chars:
                    next_pieces.append(piece)
                    continue
                split_piece = self._split_before_marker(piece, marker)
                next_pieces.extend(split_piece)
            pieces = next_pieces
        return pieces

    def _split_before_marker(self, text: str, marker: str) -> List[str]:
        if not marker or marker not in text:
            return [text]
        parts: List[str] = []
        cursor = 0
        for match in re.finditer(re.escape(marker), text):
            index = match.start()
            if index <= cursor:
                continue
            prefix = text[cursor:index]
            if self._display_len(prefix) >= 6:
                parts.append(prefix)
                cursor = index
        tail = text[cursor:]
        if tail:
            parts.append(tail)
        return parts if len(parts) > 1 else [text]

    def _hard_split_phrase(self, text: str) -> List[str]:
        value = str(text or "")
        if self._display_len(value) <= self._hard_max_chars:
            return [value] if value else []

        boundaries = "的了着过和与及在把被对向从到为是就都也还又而"
        result: List[str] = []
        remaining = value
        while self._display_len(remaining) > self._hard_max_chars:
            split_at = self._best_split_index(remaining, boundaries)
            result.append(remaining[:split_at])
            remaining = remaining[split_at:]
        if remaining:
            result.append(remaining)
        return [item for item in result if item]

    def _best_split_index(self, text: str, boundaries: str) -> int:
        max_index = min(len(text) - 1, self._hard_max_chars)
        min_index = min(len(text) - 1, max(6, self._target_chars_per_line))
        for index in range(max_index, min_index - 1, -1):
            if text[index - 1] in boundaries or text[index] in boundaries:
                return index
        return max(1, min(max_index, self._target_chars_per_line))

    def _merge_short_subtitle_parts(self, parts: List[str]) -> List[str]:
        result: List[str] = []
        for raw in parts:
            part = raw.strip()
            if not part:
                continue
            if (
                result
                and self._display_len(result[-1]) < 8
                and self._display_len(result[-1] + part) <= self._soft_max_chars
            ):
                result[-1] = result[-1] + part
            else:
                result.append(part)
        return result

    def _display_len(self, text: str) -> int:
        length = 0
        for char in str(text or ""):
            length += 1 if ord(char) > 127 else 0.55
        return int(math.ceil(length))

    def _escape_ass_text(self, text: str) -> str:
        return (
            str(text or "")
            .replace("\\", "\\\\")
            .replace("{", "\\{")
            .replace("}", "\\}")
            .replace("\n", "")
            .replace("\r", "")
        )


media_export_service = MediaExportService()
