"""Checks for the bridge search-result A2UI examples."""

import json
from pathlib import Path

from app.agent import BridgeInventoryAgent
from app.bridge_ui import build_bridge_a2ui


ROOT = Path(__file__).parents[2]
EXPECTED_QUERY = (
    "/maps/embed?mode=directions&origin=38.9351%2C-83.4596"
    "&destination=38.9451%2C-83.4696"
)


def _load(version: str) -> list[dict]:
    path = (
        ROOT
        / "app"
        / "examples"
        / "bridge_map_catalog"
        / version
        / "map.json"
    )
    return json.loads(path.read_text())


def test_gemini_enterprise_v08_payload_has_bridge_details_and_map():
    messages = _load("0.8")
    components = messages[1]["surfaceUpdate"]["components"]
    frame = next(item for item in components if item["id"] == "map-frame")
    component_text = str(components)

    assert messages[0]["beginRendering"]["surfaceId"] == "bridge-results-view"
    assert frame["component"]["WebFrameUrl"]["url"]["literalString"] == EXPECTED_QUERY
    assert "Structure ID (SFN)" in component_text
    assert "Route code" in component_text
    assert "Feature crossed" in component_text
    assert "County code" in component_text
    assert "Coordinates" in component_text
    assert component_text.count("WebFrameUrl") == 1
    assert "Bridge 2" in component_text


def test_local_v09_payload_has_bridge_details_and_map():
    messages = _load("0.9")
    components = messages[1]["updateComponents"]["components"]
    frame = next(item for item in components if item["id"] == "map-frame")
    component_text = str(components)

    assert messages[0]["createSurface"]["surfaceId"] == "bridge-results-view"
    assert frame["url"] == EXPECTED_QUERY
    assert "Structure ID (SFN)" in component_text
    assert "Route code" in component_text
    assert "Feature crossed" in component_text
    assert "County code" in component_text
    assert "Coordinates" in component_text
    assert sum(item.get("component") == "WebFrameUrl" for item in components) == 1
    assert "Bridge 2" in component_text


def test_deterministic_payloads_validate_for_both_supported_versions():
    bridges = [
        {
            "latitude": 38.9351,
            "longitude": -83.4596,
            "feature_crossed": "Creek",
            "route_code": "SR-1",
            "structure_id": "1",
            "location": "Location",
            "county_code": "001",
        }
    ]
    agent = BridgeInventoryAgent(base_url="http://localhost:8000")

    for version in ("0.8", "0.9"):
        manager = agent.get_schema_manager(version)
        catalog = manager.get_selected_catalog()
        messages = build_bridge_a2ui(
            bridges,
            "/maps/embed?mode=place&q=38.9351%2C-83.4596",
            version=version,
            catalog_id=catalog.catalog_id,
        )
        catalog.validator.validate(messages)
