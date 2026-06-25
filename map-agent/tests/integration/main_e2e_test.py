"""Local end-to-end checks for the Bridge Map A2A server."""

import os
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Iterator

import pytest
import requests
from a2a.types import Message, MessageSendParams, Part, Role, SendMessageRequest, TextPart

from app.config import A2UI_EXTENSION_URI_V0_8

BASE_URL = "http://127.0.0.1:8001"


def _log(pipe) -> None:
    for _ in iter(pipe.readline, ""):
        pass


@pytest.fixture(scope="session")
def server() -> Iterator[subprocess.Popen]:
    env = os.environ.copy()
    env["AGENT_URL"] = BASE_URL
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8001",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    threading.Thread(target=_log, args=(process.stdout,), daemon=True).start()
    threading.Thread(target=_log, args=(process.stderr,), daemon=True).start()

    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            if requests.get(f"{BASE_URL}/.well-known/agent-card.json", timeout=2).ok:
                break
        except requests.RequestException:
            time.sleep(0.5)
    else:
        process.terminate()
        pytest.fail("Bridge Map server did not start")

    yield process
    process.terminate()
    process.wait()


def _send(text: str) -> dict:
    message = Message(
        message_id=str(uuid.uuid4()),
        role=Role.user,
        parts=[Part(root=TextPart(text=text))],
        extensions=[A2UI_EXTENSION_URI_V0_8],
    )
    request = SendMessageRequest(
        id=str(uuid.uuid4()),
        params=MessageSendParams(message=message),
    )
    return requests.post(
        f"{BASE_URL}/",
        json=request.model_dump(mode="json", exclude_none=True),
        timeout=180,
    ).json()


def test_agent_card_is_transportation_map_agent(server):
    card = requests.get(f"{BASE_URL}/.well-known/agent-card.json", timeout=10).json()
    assert card["name"] == "Transportation Map Agent"
    assert card["url"] == BASE_URL
    assert [skill["id"] for skill in card["skills"]] == [
        "search_transportation_map_records"
    ]


def test_bridge_inventory_request_returns_a2ui_results(server):
    result = _send("Show bridges")["result"]
    parts = []
    for artifact in result.get("artifacts", []):
        parts.extend(artifact.get("parts", []))

    a2ui = [
        part["data"]
        for part in parts
        if part.get("kind") == "data"
        and part.get("metadata", {}).get("mimeType") == "application/json+a2ui"
    ]
    assert any("beginRendering" in item for item in a2ui)
    assert any("surfaceUpdate" in item for item in a2ui)
    assert "Map Search Results" in str(a2ui)
    assert "Structure ID (SFN)" in str(a2ui)
