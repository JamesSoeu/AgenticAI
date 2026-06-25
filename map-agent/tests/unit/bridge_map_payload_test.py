"""Checks for the bridge search-result A2UI examples."""

import json
from pathlib import Path

from app.agent import BridgeInventoryAgent
from app.bridge_ui import build_bridge_a2ui


ROOT = Path(__file__).parents[2]
EXPECTED_MAP = {
    "center": {"lat": 38.9351, "lng": -83.4596},
    "zoom": 14,
    "map_mode": "place-per-record",
    "pins": [
        {
            "lat": 38.9351,
            "lng": -83.4596,
            "name": "Bridge 1: SFN 1",
            "description": (
                "Route: SR-1 | Feature: Creek | "
                "Location: Location | County: 001"
            ),
        }
    ],
    "record_maps": [
        {
            "lat": 38.9351,
            "lng": -83.4596,
            "title": "Bridge 1: SFN 1",
            "description": "Location",
            "frame_url": "https://www.google.com/maps/embed/v1/place?key=EXAMPLE_MAPS_KEY&q=38.9351%2C-83.4596",
        }
    ],
}


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
    assert frame["component"]["WebFrameUrl"]["url"]["literalString"].startswith(
        "https://www.google.com/maps/embed/v1/"
    )
    assert "Structure ID (SFN)" in component_text
    assert "Route code" in component_text
    assert "Feature crossed" in component_text
    assert "County code" in component_text
    assert "Coordinates" in component_text
    assert component_text.count("WebFrameUrl") == 1
    assert "directions" not in component_text
    assert "Record 2" in component_text


def test_local_v09_payload_has_bridge_details_and_map():
    messages = _load("0.9")
    components = messages[1]["updateComponents"]["components"]
    frame = next(item for item in components if item["id"] == "map-frame")
    component_text = str(components)

    assert messages[0]["createSurface"]["surfaceId"] == "bridge-results-view"
    assert frame["component"] == "WebFrameUrl"
    assert frame["url"].startswith("https://www.google.com/maps/embed/v1/")
    assert "Structure ID (SFN)" in component_text
    assert "Route code" in component_text
    assert "Feature crossed" in component_text
    assert "County code" in component_text
    assert "Coordinates" in component_text
    assert sum(item.get("component") == "WebFrameUrl" for item in components) == 1
    assert "directions" not in component_text
    assert "Record 2" in component_text


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
            EXPECTED_MAP,
            version=version,
            catalog_id=catalog.catalog_id,
        )
        catalog.validator.validate(messages)
        assert "WebFrameUrl" in str(messages)
        assert "place?key=EXAMPLE_MAPS_KEY" in str(messages)


def test_v09_payload_creates_one_surface_per_map_record():
    records = [
        {
            "latitude": 38.9351 + index,
            "longitude": -83.4596 - index,
            "title": f"Bridge {index}",
            "description": f"Bridge location {index}",
            "source_table": "bridge",
        }
        for index in range(3)
    ]
    map_data = {
        "record_maps": [
            {
                "frame_url": (
                    "https://www.google.com/maps/embed/v1/place?"
                    f"key=EXAMPLE_MAPS_KEY&q={record['latitude']}%2C{record['longitude']}"
                )
            }
            for record in records
        ]
    }
    agent = BridgeInventoryAgent(base_url="http://localhost:8000")
    catalog = agent.get_schema_manager("0.9").get_selected_catalog()

    messages = build_bridge_a2ui(
        records,
        map_data,
        version="0.9",
        catalog_id=catalog.catalog_id,
    )

    assert sum("createSurface" in message for message in messages) == 3
    assert sum("updateComponents" in message for message in messages) == 3
    assert str(messages).count("WebFrameUrl") == 3
    assert "Map Search Result 1 of 3" in str(messages)
    assert "Map Search Result 3 of 3" in str(messages)
