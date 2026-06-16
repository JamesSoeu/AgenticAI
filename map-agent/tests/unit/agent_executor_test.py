# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for agent_executor post-processing helpers."""

from a2a.types import DataPart, Part
from a2ui.a2a.parts import create_a2ui_part
from a2ui.adk.send_a2ui_to_client_toolset import A2uiPartConverter
from google.genai import types

from app.agent_executor import (
    _process_a2ui_parts,
    _proxy_url_to_full_embed_url,
    _repair_catalog_id,
)

VALID_CATALOG_ID = "https://a2ui.org/specification/v0_9/basic_catalog.json"
HALLUCINATED_CATALOG_ID = "a2ui_wrong_catalog:v0_9"


def test_repair_leaves_correct_catalog_id_unchanged():
    msg = {
        "version": "v0.9",
        "createSurface": {"surfaceId": "s1", "catalogId": VALID_CATALOG_ID},
    }
    _repair_catalog_id(msg, VALID_CATALOG_ID)
    assert msg["createSurface"]["catalogId"] == VALID_CATALOG_ID


def test_repair_replaces_hallucinated_catalog_id():
    msg = {
        "version": "v0.9",
        "createSurface": {"surfaceId": "s1", "catalogId": HALLUCINATED_CATALOG_ID},
    }
    _repair_catalog_id(msg, VALID_CATALOG_ID)
    assert msg["createSurface"]["catalogId"] == VALID_CATALOG_ID


def test_repair_fills_missing_catalog_id():
    msg = {"version": "v0.9", "createSurface": {"surfaceId": "s1"}}
    _repair_catalog_id(msg, VALID_CATALOG_ID)
    assert msg["createSurface"]["catalogId"] == VALID_CATALOG_ID


def test_repair_ignores_non_create_surface_messages():
    msg = {
        "version": "v0.9",
        "updateDataModel": {"surfaceId": "s1", "path": "/x", "value": 1},
    }
    _repair_catalog_id(msg, VALID_CATALOG_ID)
    assert "catalogId" not in msg["updateDataModel"]


def test_repair_skips_v0_8_begin_rendering():
    """v0.8 beginRendering carries no catalogId; should be untouched."""
    msg = {"beginRendering": {"surfaceId": "s1", "root": "root"}}
    _repair_catalog_id(msg, VALID_CATALOG_ID)
    assert "catalogId" not in msg["beginRendering"]


def test_process_parts_repairs_catalog_id_end_to_end():
    bad_part = create_a2ui_part(
        {
            "version": "v0.9",
            "createSurface": {
                "surfaceId": "s1",
                "catalogId": HALLUCINATED_CATALOG_ID,
            },
        }
    )
    out = _process_a2ui_parts([bad_part], valid_catalog_id=VALID_CATALOG_ID)
    assert len(out) == 1
    assert out[0].root.data["createSurface"]["catalogId"] == VALID_CATALOG_ID


def test_process_parts_no_op_when_no_valid_catalog_id():
    """When no session catalog is known, leave catalogId untouched."""
    bad_part = create_a2ui_part(
        {
            "version": "v0.9",
            "createSurface": {
                "surfaceId": "s1",
                "catalogId": HALLUCINATED_CATALOG_ID,
            },
        }
    )
    out = _process_a2ui_parts([bad_part], valid_catalog_id=None)
    assert out[0].root.data["createSurface"]["catalogId"] == HALLUCINATED_CATALOG_ID


def test_process_parts_passes_through_non_a2ui_parts():
    plain_part = Part(root=DataPart(data={"foo": "bar"}, metadata={"mimeType": "x"}))
    out = _process_a2ui_parts([plain_part], valid_catalog_id=VALID_CATALOG_ID)
    assert out == [plain_part]


def test_proxy_url_preserves_all_bridge_direction_points(monkeypatch):
    monkeypatch.setattr("app.agent_executor.get_google_maps_api_key", lambda: "key")
    url = (
        "/maps/embed?mode=directions"
        "&origin=38.1%2C-83.1"
        "&waypoints=38.2%2C-83.2%7C38.3%2C-83.3"
        "&destination=38.4%2C-83.4"
    )

    full_url = _proxy_url_to_full_embed_url(url)

    assert full_url.startswith("https://www.google.com/maps/embed/v1/directions?key=key&")
    assert "origin=38.1%2C-83.1" in full_url
    assert "waypoints=38.2%2C-83.2%7C38.3%2C-83.3" in full_url
    assert "destination=38.4%2C-83.4" in full_url


def test_converter_turns_search_result_directly_into_a2ui_parts():
    from app.agent import BridgeInventoryAgent

    catalog = (
        BridgeInventoryAgent("http://localhost:8000")
        .get_schema_manager("0.8")
        .get_selected_catalog()
    )
    messages = [
        {"beginRendering": {"surfaceId": "s1", "root": "root"}},
        {
            "surfaceUpdate": {
                "surfaceId": "s1",
                "components": [
                    {
                        "id": "root",
                        "component": {
                            "Text": {"text": {"literalString": "Bridge results"}}
                        },
                    }
                ],
            }
        },
    ]
    response = types.Part.from_function_response(
        name="search_bridges",
        response={"validated_a2ui_json": messages},
    )

    parts = A2uiPartConverter(catalog, bypass_tool_check=True).convert(response)

    assert [part.root.data for part in parts] == messages
    assert all(part.root.metadata["mimeType"] == "application/json+a2ui" for part in parts)
