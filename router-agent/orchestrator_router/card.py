from __future__ import annotations

from typing import Any

from orchestrator_router.config import RouterSettings


def build_agent_card(settings: RouterSettings) -> dict[str, Any]:
    public_url = settings.router_public_url or f"http://localhost:{settings.port}"
    return {
        "protocolVersion": "0.3.0",
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
