"""Authenticated smoke tests for the deployed Cloud Run A2A agent."""

import os
import subprocess
import uuid

import pytest
import requests
from a2a.types import Message, MessageSendParams, Part, Role, SendMessageRequest, TextPart


AGENT_URL = os.environ.get("AGENT_URL", "").rstrip("/")
pytestmark = pytest.mark.skipif(not AGENT_URL, reason="AGENT_URL not set")


def _auth_headers() -> dict[str, str]:
    result = subprocess.run(
        ["gcloud", "auth", "print-identity-token"],
        capture_output=True,
        check=True,
        text=True,
    )
    return {
        "Authorization": f"Bearer {result.stdout.strip()}",
        "Content-Type": "application/json",
    }


def test_deployed_agent_card_is_transportation_map_agent():
    response = requests.get(
        f"{AGENT_URL}/.well-known/agent-card.json",
        headers=_auth_headers(),
        timeout=30,
    )
    response.raise_for_status()
    card = response.json()

    assert card["name"] == "Transportation Map Agent"
    assert card["url"] == AGENT_URL
    assert any(
        skill["id"] == "search_transportation_map_records"
        for skill in card["skills"]
    )
    assert any(
        extension["uri"] == "https://a2ui.org/a2a-extension/a2ui/v0.8"
        for extension in card["capabilities"]["extensions"]
    )


def test_deployed_agent_returns_gemini_enterprise_bridge_results():
    message = Message(
        message_id=str(uuid.uuid4()),
        role=Role.user,
        parts=[Part(root=TextPart(text="Show bridges"))],
    )
    request = SendMessageRequest(
        id=str(uuid.uuid4()),
        params=MessageSendParams(message=message),
    )

    response = requests.post(
        f"{AGENT_URL}/",
        headers=_auth_headers(),
        json=request.model_dump(mode="json", exclude_none=True),
        timeout=180,
    )
    response.raise_for_status()
    result = response.json()["result"]

    parts = []
    parts.extend(result.get("status", {}).get("message", {}).get("parts", []))
    for artifact in result.get("artifacts", []):
        parts.extend(artifact.get("parts", []))

    a2ui = [
        part["data"]
        for part in parts
        if part.get("kind") == "data"
        and part.get("metadata", {}).get("mimeType") == "application/json+a2ui"
    ]

    assert any("beginRendering" in message for message in a2ui)
    assert any("surfaceUpdate" in message for message in a2ui)
    assert "Map Search Results" in str(a2ui)
    assert "Structure ID (SFN)" in str(a2ui)
