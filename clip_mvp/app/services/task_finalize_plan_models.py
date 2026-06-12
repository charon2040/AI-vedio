from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List


UpdateTaskCallback = Callable[..., Dict[str, Any]]
RecordTaskEventCallback = Callable[..., None]


@dataclass(frozen=True)
class FinalizePlanningResult:
    reviewed_beats: List[Dict[str, Any]]
    synthesized_beats: List[Dict[str, Any]]
    source_segments: List[Dict[str, Any]]
    approved_script: str
    selection_strategy: str
    total_duration_ms: int
