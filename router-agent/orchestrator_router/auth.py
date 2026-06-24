from __future__ import annotations

from orchestrator_router.config import RouterSettings


def target_audience(route: str, target_base: str, settings: RouterSettings) -> str:
    if route == "map" and settings.map_agent_audience:
        return settings.map_agent_audience
    if route != "map" and settings.data_agent_audience:
        return settings.data_agent_audience
    return target_base


def fetch_id_token(audience: str) -> str:
    try:
        from google.auth.transport.requests import Request as AuthRequest
        from google.oauth2 import id_token

        return id_token.fetch_id_token(AuthRequest(), audience)
    except Exception as exc:
        raise RuntimeError(
            "Could not fetch Google-signed ID token for child Cloud Run agent "
            f"with audience {audience}. Confirm the router runs on Google Cloud "
            "with a service account and that google-auth can reach metadata credentials."
        ) from exc
