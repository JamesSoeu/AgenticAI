from __future__ import annotations

import re
from typing import Any


MAP_PATTERNS = (
    r"\bmap\b",
    r"\bmaps\b",
    r"\bgoogle\s+map\b",
    r"\bshow\b.*\bbridge",
    r"\bdisplay\b.*\bbridge",
    r"\bplot\b",
    r"\bwhere\b.*\bbridge",
    r"\bnear\b",
    r"\bstructure\b",
    r"\bsfn\b",
    r"\blatitude\b",
    r"\blongitude\b",
    r"\bcoordinate",
    r"\bcounty\s+\d+",
    r"\bcrossing\b",
    r"\bcrosses\b",
)

DATA_PATTERNS = (
    r"\bhow many\b",
    r"\bcount\b",
    r"\btotal\b",
    r"\bschema\b",
    r"\bcolumns?\b",
    r"\bpreview\b",
    r"\btable\b",
    r"\bbigquery\b",
    r"\bbucket\b",
    r"\bcloud storage\b",
    r"\bpdf\b",
    r"\bmanual\b",
    r"\bguide\b",
    r"\binspection responsibility\b",
    r"\bcrash\b",
    r"\beilis\b",
    r"\broad\b",
    r"\btraffic\b",
    r"\btrend\b",
    r"\bseverity\b",
)


def extract_text(payload: Any) -> str:
    """Best-effort text extraction from A2A JSON-RPC request payloads."""
    texts: list[str] = []
    _collect_text(payload, texts)
    return " ".join(texts).strip()


def route_request(user_text: str, default_agent: str = "data") -> str:
    """Return 'data' or 'map' based on the user's request text."""
    text = user_text.lower()
    if not text:
        return default_agent if default_agent in {"data", "map"} else "data"

    data_score = _score(text, DATA_PATTERNS)
    map_score = _score(text, MAP_PATTERNS)

    # Explicit map/display intent should win because the map agent preserves A2UI.
    if map_score > data_score:
        return "map"
    if data_score > 0:
        return "data"
    if re.search(r"\bbridge|bridges|structure|sfn\b", text) and map_score > 0:
        return "map"
    return default_agent if default_agent in {"data", "map"} else "data"


def _score(text: str, patterns: tuple[str, ...]) -> int:
    return sum(1 for pattern in patterns if re.search(pattern, text))


def _collect_text(value: Any, texts: list[str]) -> None:
    if isinstance(value, dict):
        text_value = value.get("text")
        if isinstance(text_value, str):
            texts.append(text_value)
        for item in value.values():
            _collect_text(item, texts)
    elif isinstance(value, list):
        for item in value:
            _collect_text(item, texts)
