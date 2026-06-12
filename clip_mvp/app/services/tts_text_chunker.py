from __future__ import annotations

from typing import List


class TTSTextChunker:
    _STRONG_BREAK_CHARS = "。！？!?；;：:\n"
    _WEAK_BREAK_CHARS = "，,、"

    def split(self, text: str, *, soft_limit: int, hard_limit: int) -> List[str]:
        raw_text = str(text or "").strip()
        if not raw_text:
            return []

        normalized_soft = max(1, int(soft_limit or 1))
        normalized_hard = max(normalized_soft, int(hard_limit or normalized_soft))
        if len(raw_text) <= normalized_hard:
            return [raw_text]

        units: List[str] = []
        sentence_units = self._split_keep_delimiter(raw_text, self._STRONG_BREAK_CHARS)
        if not sentence_units:
            sentence_units = [raw_text]

        for sentence in sentence_units:
            item = str(sentence or "").strip()
            if not item:
                continue
            if len(item) <= normalized_hard:
                units.append(item)
                continue

            clause_units = self._split_keep_delimiter(item, self._WEAK_BREAK_CHARS)
            if len(clause_units) <= 1:
                units.extend(
                    self._fallback_split_unit(
                        item,
                        soft_limit=normalized_soft,
                        hard_limit=normalized_hard,
                    )
                )
                continue

            for clause in clause_units:
                clause_text = str(clause or "").strip()
                if not clause_text:
                    continue
                if len(clause_text) <= normalized_hard:
                    units.append(clause_text)
                    continue
                units.extend(
                    self._fallback_split_unit(
                        clause_text,
                        soft_limit=normalized_soft,
                        hard_limit=normalized_hard,
                    )
                )

        chunks = self._pack_units(
            units,
            soft_limit=normalized_soft,
            hard_limit=normalized_hard,
        )
        return chunks or [raw_text]

    def _last_break_before(
        self,
        positions: List[int],
        *,
        start: int,
        end: int,
    ) -> int:
        for position in reversed(positions):
            if start < position <= end:
                return position
        return 0

    def _split_keep_delimiter(self, text: str, delimiters: str) -> List[str]:
        items: List[str] = []
        start = 0
        for index, char in enumerate(str(text or "")):
            if char not in delimiters:
                continue
            item = text[start : index + 1].strip()
            if item:
                items.append(item)
            start = index + 1

        tail = text[start:].strip()
        if tail:
            items.append(tail)
        return items

    def _join_text_parts(self, left: str, right: str) -> str:
        if not left:
            return right
        if not right:
            return left
        if left[-1].isascii() and right[0].isascii() and not left[-1].isspace() and not right[0].isspace():
            return f"{left} {right}"
        return f"{left}{right}"

    def _fallback_split_unit(
        self,
        text: str,
        *,
        soft_limit: int,
        hard_limit: int,
    ) -> List[str]:
        raw_text = str(text or "").strip()
        if not raw_text:
            return []
        if len(raw_text) <= hard_limit:
            return [raw_text]

        strong_breaks: List[int] = []
        weak_breaks: List[int] = []
        for index, char in enumerate(raw_text):
            position = index + 1
            if char in self._STRONG_BREAK_CHARS:
                strong_breaks.append(position)
            elif char in self._WEAK_BREAK_CHARS or char.isspace():
                weak_breaks.append(position)

        chunks: List[str] = []
        cursor = 0
        while cursor < len(raw_text):
            remaining = len(raw_text) - cursor
            if remaining <= hard_limit:
                item = raw_text[cursor:].strip()
                if item:
                    chunks.append(item)
                break

            preferred_end = min(len(raw_text), cursor + soft_limit)
            max_end = min(len(raw_text), cursor + hard_limit)
            split_at = (
                self._last_break_before(strong_breaks, start=cursor, end=preferred_end)
                or self._last_break_before(weak_breaks, start=cursor, end=preferred_end)
                or self._last_break_before(strong_breaks, start=cursor, end=max_end)
                or self._last_break_before(weak_breaks, start=cursor, end=max_end)
                or max_end
            )
            if split_at <= cursor:
                split_at = max_end

            item = raw_text[cursor:split_at].strip()
            if item:
                chunks.append(item)
            cursor = split_at
            while cursor < len(raw_text) and raw_text[cursor].isspace():
                cursor += 1

        return chunks or [raw_text]

    def _pack_units(
        self,
        units: List[str],
        *,
        soft_limit: int,
        hard_limit: int,
    ) -> List[str]:
        chunks: List[str] = []
        current = ""
        min_fill = max(18, int(soft_limit * 0.72))

        for unit in units:
            text = str(unit or "").strip()
            if not text:
                continue

            if len(text) > hard_limit:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.extend(
                    self._fallback_split_unit(
                        text,
                        soft_limit=soft_limit,
                        hard_limit=hard_limit,
                    )
                )
                continue

            if not current:
                current = text
                continue

            candidate = self._join_text_parts(current, text)
            if len(candidate) <= soft_limit:
                current = candidate
                continue

            if len(current) < min_fill and len(candidate) <= hard_limit:
                current = candidate
                continue

            chunks.append(current)
            current = text

        if current:
            chunks.append(current)

        return chunks


tts_text_chunker = TTSTextChunker()
