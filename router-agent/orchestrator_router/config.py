from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RouterSettings:
    google_cloud_project: str
    google_cloud_location: str
    google_genai_use_vertexai: bool
    router_model: str
    router_name: str
    router_public_url: str | None
    data_agent_url: str
    data_agent_audience: str | None
    map_agent_url: str
    map_agent_audience: str | None
    default_agent: str
    classifier_min_confidence: float
    request_timeout_seconds: float
    use_id_token: bool
    port: int


def load_settings() -> RouterSettings:
    return RouterSettings(
        google_cloud_project=os.getenv("GOOGLE_CLOUD_PROJECT", "").strip(),
        google_cloud_location=os.getenv("GOOGLE_CLOUD_LOCATION", "global").strip(),
        google_genai_use_vertexai=_parse_bool(os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "true")),
        router_model=os.getenv("ROUTER_MODEL", "gemini-3.5-flash").strip(),
        router_name=os.getenv("ROUTER_NAME", "Transportation Orchestrator Agent").strip(),
        router_public_url=os.getenv("ROUTER_PUBLIC_URL", "").strip() or None,
        data_agent_url=_normalize_base_url(os.getenv("DATA_AGENT_URL", "")),
        data_agent_audience=_normalize_optional_url(os.getenv("DATA_AGENT_AUDIENCE", "")),
        map_agent_url=_normalize_base_url(os.getenv("MAP_AGENT_URL", "")),
        map_agent_audience=_normalize_optional_url(os.getenv("MAP_AGENT_AUDIENCE", "")),
        default_agent=os.getenv("ROUTER_DEFAULT_AGENT", "data").strip().lower(),
        classifier_min_confidence=float(os.getenv("ROUTER_CLASSIFIER_MIN_CONFIDENCE", "0.65")),
        request_timeout_seconds=float(os.getenv("ROUTER_REQUEST_TIMEOUT_SECONDS", "120")),
        use_id_token=_parse_bool(os.getenv("ROUTER_USE_ID_TOKEN", "false")),
        port=int(os.getenv("PORT", "8080")),
    )


def _normalize_base_url(raw: str) -> str:
    url = raw.strip().rstrip("/")
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"Agent URL must start with http:// or https://: {url}")
    return url


def _normalize_optional_url(raw: str) -> str | None:
    return _normalize_base_url(raw) or None


def _parse_bool(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}
