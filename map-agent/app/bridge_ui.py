"""Deterministic A2UI payload generation for bridge search results."""

from uuid import uuid4

from a2ui.schema.constants import VERSION_0_9

DEFAULT_V09_CATALOG_ID = "https://a2ui.org/specification/v0_9/basic_catalog.json"


def _display(value) -> str:
    return "Not available" if value in (None, "") else str(value)


def _bridge_lines(bridge: dict) -> list[tuple[str, str]]:
    return [
        ("sfn", f"Structure ID (SFN): {_display(bridge.get('structure_id'))}"),
        ("route", f"Route code: {_display(bridge.get('route_code'))}"),
        ("location", f"Location: {_display(bridge.get('location'))}"),
        ("feature", f"Feature crossed: {_display(bridge.get('feature_crossed'))}"),
        ("county", f"County code: {_display(bridge.get('county_code'))}"),
        ("source", f"Source table: {_display(bridge.get('source_table'))}"),
        (
            "coordinates",
            "Coordinates: "
            f"{_display(bridge.get('latitude'))}, {_display(bridge.get('longitude'))}",
        ),
    ]


def _bridge_heading(index: int, bridge: dict) -> str:
    structure_id = _display(bridge.get("structure_id"))
    return f"Bridge {index}: SFN {structure_id}"


def _component_ids(bridges: list[dict], include_map: bool) -> list[str]:
    ids = ["results-header", "results-summary"]
    if include_map:
        ids.append("map-frame")
    for index, bridge in enumerate(bridges, start=1):
        ids.append(f"divider-{index}")
        ids.append(f"bridge-{index}-header")
        ids.extend(f"bridge-{index}-{key}" for key, _ in _bridge_lines(bridge))
    return ids


def _build_v08(
    bridges: list[dict], map_data: dict | None, surface_id: str
) -> list[dict]:
    component_ids = _component_ids(bridges, bool(map_data))
    components = [
        {
            "id": "root-column",
            "component": {
                "Column": {
                    "children": {"explicitList": component_ids},
                    "distribution": "start",
                    "alignment": "stretch",
                }
            },
        },
        {
            "id": "results-header",
            "component": {
                "Text": {
                    "text": {"literalString": "Bridge Search Results"},
                    "usageHint": "h2",
                }
            },
        },
        {
            "id": "results-summary",
            "component": {
                "Text": {
                    "text": {
                        "literalString": f"Found {len(bridges)} matching bridges."
                    },
                    "usageHint": "body",
                }
            },
        },
    ]
    if map_data:
        components.append(
            {
                "id": "map-frame",
                "component": {
                    "WebFrameUrl": {
                        "url": {"literalString": map_data["frame_url"]}
                    }
                },
            }
        )

    for index, bridge in enumerate(bridges, start=1):
        components.extend(
            [
                {
                    "id": f"divider-{index}",
                    "component": {"Divider": {"axis": "horizontal"}},
                },
                {
                    "id": f"bridge-{index}-header",
                    "component": {
                        "Text": {
                            "text": {"literalString": _bridge_heading(index, bridge)},
                            "usageHint": "h3",
                        }
                    },
                },
            ]
        )
        for key, text in _bridge_lines(bridge):
            components.append(
                {
                    "id": f"bridge-{index}-{key}",
                    "component": {
                        "Text": {
                            "text": {"literalString": text},
                            "usageHint": "body",
                        }
                    },
                }
            )

    return [
        {"beginRendering": {"surfaceId": surface_id, "root": "root-column"}},
        {"surfaceUpdate": {"surfaceId": surface_id, "components": components}},
    ]


def _build_v09(
    bridges: list[dict],
    map_data: dict | None,
    surface_id: str,
    catalog_id: str,
) -> list[dict]:
    component_ids = _component_ids(bridges, bool(map_data))
    components = [
        {
            "id": "root",
            "component": "Column",
            "justify": "start",
            "align": "stretch",
            "children": component_ids,
        },
        {
            "id": "results-header",
            "component": "Text",
            "variant": "h2",
            "text": "Bridge Search Results",
        },
        {
            "id": "results-summary",
            "component": "Text",
            "text": f"Found {len(bridges)} matching bridges.",
        },
    ]
    if map_data:
        components.append(
            {
                "id": "map-frame",
                "component": "WebFrameUrl",
                "url": map_data["frame_url"],
            }
        )

    for index, bridge in enumerate(bridges, start=1):
        components.extend(
            [
                {
                    "id": f"divider-{index}",
                    "component": "Divider",
                    "axis": "horizontal",
                },
                {
                    "id": f"bridge-{index}-header",
                    "component": "Text",
                    "variant": "h3",
                    "text": _bridge_heading(index, bridge),
                },
            ]
        )
        for key, text in _bridge_lines(bridge):
            components.append(
                {
                    "id": f"bridge-{index}-{key}",
                    "component": "Text",
                    "text": text,
                }
            )

    return [
        {
            "version": "v0.9",
            "createSurface": {"surfaceId": surface_id, "catalogId": catalog_id},
        },
        {
            "version": "v0.9",
            "updateComponents": {"surfaceId": surface_id, "components": components},
        },
    ]


def build_bridge_a2ui(
    bridges: list[dict],
    map_data: dict | None,
    *,
    version: str | None = None,
    catalog_id: str | None = None,
) -> list[dict]:
    """Build render-ready A2UI messages without asking the model to write JSON."""
    surface_id = f"bridge-results-{uuid4().hex[:12]}"
    if version == VERSION_0_9:
        return _build_v09(
            bridges,
            map_data,
            surface_id,
            catalog_id or DEFAULT_V09_CATALOG_ID,
        )
    return _build_v08(bridges, map_data, surface_id)
