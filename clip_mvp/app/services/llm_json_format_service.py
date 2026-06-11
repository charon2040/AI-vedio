from __future__ import annotations

import json
import re


def clean_content(content: str) -> str:
    text = str(content or "").strip()
    if not text:
        return ""

    text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text).strip()

    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char not in "{[":
            continue
        try:
            _, end = decoder.raw_decode(text[index:])
        except Exception:
            continue
        return text[index : index + end].strip()

    return text
