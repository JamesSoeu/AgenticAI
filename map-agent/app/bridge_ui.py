"""Deterministic A2UI payload generation for map search results."""

from uuid import uuid4

from a2ui.schema.constants import VERSION_0_9

DEFAULT_V09_CATALOG_ID = "https://a2ui.org/specification/v0_9/basic_catalog.json"


def _display(value) -> str:
    return "Not available" if value in (None, "") else str(value)


def _record_lines(record: dict) -> list[tuple[str, str]]:
    lines = [
        ("title", f"Title: {_display(record.get('title') or record.get('structure_id'))}"),
        (
            "description",
            f"Description: {_display(record.get('description') or record.get('location'))}",
        ),
    ]
    optional_fields = [
        ("sfn", "Structure ID (SFN)", record.get("structure_id")),
        ("route", "Route code", record.get("route_code")),
        ("feature", "Feature crossed", record.get("feature_crossed")),
        ("county", "County code", record.get("county_code")),
    ]
    for key, label, value in optional_fields:
        if value not in (None, ""):
            lines.append((key, f"{label}: {_display(value)}"))
    lines.extend(
        [
            ("source", f"Source table: {_display(record.get('source_table'))}"),
            (
                "coordinates",
                "Coordinates: "
                f"{_display(record.get('latitude'))}, {_display(record.get('longitude'))}",
            ),
        ]
    )
    return lines


def _record_heading(index: int, record: dict) -> str:
    title = _display(record.get("title") or record.get("structure_id"))
    return f"Record {index}: {title}"


def _record_map_url(map_data: dict | None, index: int) -> str | None:
    if not map_data:
        return None
    record_maps = map_data.get("record_maps") or []
    if index - 1 >= len(record_maps):
        return None
    return record_maps[index - 1].get("frame_url")


def _component_ids(records: list[dict], map_data: dict | None) -> list[str]:
    ids = ["results-header", "results-summary"]
    for index, record in enumerate(records, start=1):
        ids.append(f"divider-{index}")
        ids.append(f"record-{index}-header")
        ids.extend(f"record-{index}-{key}" for key, _ in _record_lines(record))
        if _record_map_url(map_data, index):
            ids.append(f"record-{index}-map")
    return ids


def _build_v08(
    records: list[dict], map_data: dict | None, surface_id: str
) -> list[dict]:
    component_ids = _component_ids(records, map_data)
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
                    "text": {"literalString": "Map Search Results"},
                    "usageHint": "h2",
                }
            },
        },
        {
            "id": "results-summary",
            "component": {
                "Text": {
                    "text": {
                        "literalString": f"Found {len(records)} matching map records."
                    },
                    "usageHint": "body",
                }
            },
        },
    ]
    for index, record in enumerate(records, start=1):
        components.extend(
            [
                {
                    "id": f"divider-{index}",
                    "component": {"Divider": {"axis": "horizontal"}},
                },
                {
                    "id": f"record-{index}-header",
                    "component": {
                        "Text": {
                            "text": {"literalString": _record_heading(index, record)},
                            "usageHint": "h3",
                        }
                    },
                },
            ]
            )
        for key, text in _record_lines(record):
            components.append(
                {
                    "id": f"record-{index}-{key}",
                    "component": {
                        "Text": {
                            "text": {"literalString": text},
                            "usageHint": "body",
                        }
                    },
                }
            )
        map_url = _record_map_url(map_data, index)
        if map_url:
            components.append(
                {
                    "id": f"record-{index}-map",
                    "component": {
                        "WebFrameUrl": {
                            "url": {"literalString": map_url}
                        }
                    },
                }
            )

    return [
        {"beginRendering": {"surfaceId": surface_id, "root": "root-column"}},
        {"surfaceUpdate": {"surfaceId": surface_id, "components": components}},
    ]


def _build_v09(
    records: list[dict],
    map_data: dict | None,
    surface_id: str,
    catalog_id: str,
) -> list[dict]:
    component_ids = _component_ids(records, map_data)
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
            "text": "Map Search Results",
        },
        {
            "id": "results-summary",
            "component": "Text",
            "text": f"Found {len(records)} matching map records.",
        },
    ]
    for index, record in enumerate(records, start=1):
        components.extend(
            [
                {
                    "id": f"divider-{index}",
                    "component": "Divider",
                    "axis": "horizontal",
                },
                {
                    "id": f"record-{index}-header",
                    "component": "Text",
                    "variant": "h3",
                    "text": _record_heading(index, record),
                },
            ]
        )
        for key, text in _record_lines(record):
            components.append(
                {
                    "id": f"record-{index}-{key}",
                    "component": "Text",
                    "text": text,
                }
            )
        map_url = _record_map_url(map_data, index)
        if map_url:
            components.append(
                {
                    "id": f"record-{index}-map",
                    "component": "WebFrameUrl",
                    "url": map_url,
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
    records: list[dict],
    map_data: dict | None,
    *,
    version: str | None = None,
    catalog_id: str | None = None,
) -> list[dict]:
    """Build render-ready A2UI messages without asking the model to write JSON."""
    surface_id = f"map-results-{uuid4().hex[:12]}"
    if version == VERSION_0_9:
        return _build_v09(
            records,
            map_data,
            surface_id,
            catalog_id or DEFAULT_V09_CATALOG_ID,
        )
    return _build_v08(records, map_data, surface_id)
