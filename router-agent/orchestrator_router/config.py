from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RouterSettings:
    router_name: str
    router_public_url: str | None
    data_agent_url: str
    map_agent_url: str
    default_agent: str
    request_timeout_seconds: float
    use_id_token: bool
    port: int


def load_settings() -> RouterSettings:
    return RouterSettings(
        router_name=os.getenv("ROUTER_NAME", "Transportation Orchestrator Agent").strip(),
        router_public_url=os.getenv("ROUTER_PUBLIC_URL", "").strip() or None,
        data_agent_url=_normalize_base_url(os.getenv("DATA_AGENT_URL", "")),
        map_agent_url=_normalize_base_url(os.getenv("MAP_AGENT_URL", "")),
        default_agent=os.getenv("ROUTER_DEFAULT_AGENT", "data").strip().lower(),
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


def _parse_bool(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}
