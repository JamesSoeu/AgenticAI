from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from orchestrator_router.config import RouterSettings, load_settings
from orchestrator_router.routing import extract_text, route_request


settings = load_settings()


def _agent_card() -> dict[str, Any]:
    public_url = settings.router_public_url or f"http://localhost:{settings.port}"
    return {
        "name": settings.router_name,
        "description": (
            "Routes Gemini Enterprise A2A requests to specialist transportation "
            "agents: a data agent for BigQuery, Cloud Storage, and PDF document "
            "answers, and a map agent for bridge inventory map displays."
        ),
        "url": public_url,
        "version": "0.1.0",
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "capabilities": {"streaming": True},
        "skills": [
            {
                "id": "route_transportation_questions",
                "name": "Route Transportation Questions",
                "description": (
                    "Selects the data agent for analytics/document questions and "
                    "the map agent for bridge map/display questions."
                ),
                "tags": [
                    "a2a",
                    "router",
                    "orchestrator",
                    "bigquery",
                    "cloud-storage",
                    "pdf",
                    "google-maps",
                    "a2ui",
                ],
                "examples": [
                    "How many bridge records are in the bridge table?",
                    "Search the bridge inspection PDF manuals for inspection responsibility.",
                    "Show bridges in county 001 on a map.",
                    "Find bridge structure 1234567 and display it on Google Maps.",
                    "Show crash counts by severity for the latest year.",
                ],
            }
        ],
    }


async def healthz(_request: Request) -> JSONResponse:
    return JSONResponse(
        {
            "status": "ok",
            "router": settings.router_name,
            "data_agent_configured": bool(settings.data_agent_url),
            "map_agent_configured": bool(settings.map_agent_url),
            "default_agent": settings.default_agent,
        }
    )


async def agent_card(_request: Request) -> JSONResponse:
    return JSONResponse(_agent_card())


async def route_a2a(request: Request) -> Response:
    try:
        payload = await request.json()
        user_text = extract_text(payload)
        route = route_request(user_text, settings.default_agent)
        target_base = _target_url(route, settings)
        target_url = urljoin(f"{target_base}/", "")
        headers = _forward_headers(request, target_base)

        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            response = await client.post(target_url, json=payload, headers=headers)

        return Response(
            content=response.content,
            status_code=response.status_code,
            media_type=response.headers.get("content-type", "application/json"),
            headers={
                "x-router-selected-agent": route,
                "x-router-target-url": target_base,
            },
        )
    except Exception as exc:
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32000,
                    "message": f"Router failed to forward request: {exc}",
                },
                "id": None,
            },
            status_code=500,
        )


def _target_url(route: str, current_settings: RouterSettings) -> str:
    if route == "map":
        if not current_settings.map_agent_url:
            raise ValueError("MAP_AGENT_URL is not configured.")
        return current_settings.map_agent_url
    if not current_settings.data_agent_url:
        raise ValueError("DATA_AGENT_URL is not configured.")
    return current_settings.data_agent_url


def _forward_headers(request: Request, target_base: str) -> dict[str, str]:
    headers: dict[str, str] = {
        "content-type": request.headers.get("content-type", "application/json"),
        "accept": request.headers.get("accept", "application/json"),
    }
    for header in (
        "x-a2a-extensions",
        "x-a2ui-version",
        "x-goog-authenticated-user-email",
        "x-goog-authenticated-user-id",
    ):
        value = request.headers.get(header)
        if value:
            headers[header] = value
    if settings.use_id_token:
        token = _fetch_id_token(target_base)
        if token:
            headers["authorization"] = f"Bearer {token}"
    return headers


def _fetch_id_token(audience: str) -> str | None:
    try:
        from google.auth.transport.requests import Request as AuthRequest
        from google.oauth2 import id_token

        return id_token.fetch_id_token(AuthRequest(), audience)
    except Exception:
        return None


routes = [
    Route("/healthz", healthz, methods=["GET"]),
    Route("/.well-known/agent-card.json", agent_card, methods=["GET"]),
    Route("/.well-known/agent.json", agent_card, methods=["GET"]),
    Route("/", route_a2a, methods=["POST"]),
]

app = Starlette(routes=routes)
