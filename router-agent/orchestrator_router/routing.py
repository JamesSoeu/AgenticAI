from __future__ import annotations

from typing import Any


def extract_text(payload: Any) -> str:
    """Best-effort text extraction from A2A JSON-RPC request payloads."""
    texts: list[str] = []
    _collect_text(payload, texts)
    return " ".join(texts).strip()


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
