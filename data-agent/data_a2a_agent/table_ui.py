"""Deterministic A2UI table payload generation for BigQuery results."""

from __future__ import annotations

from uuid import uuid4

try:  # pragma: no cover - exercised only when A2UI is installed.
    from a2ui.schema.constants import VERSION_0_9
except Exception:  # pragma: no cover - keeps unit tests dependency-light.
    VERSION_0_9 = "v0.9"


DEFAULT_V09_CATALOG_ID = "https://a2ui.org/specification/v0_9/basic_catalog.json"
MAX_A2UI_ROWS = 50
MAX_CELL_CHARS = 180


def build_bigquery_table_a2ui(
    *,
    rows: list[dict],
    sql: str,
    title: str = "BigQuery Results",
    version: str | None = None,
    catalog_id: str | None = None,
) -> list[dict]:
    """Build A2UI messages that render query rows as a table-like layout."""
    surface_id = f"bigquery-table-{uuid4().hex[:12]}"
    columns = _columns_for_rows(rows)
    visible_rows = rows[:MAX_A2UI_ROWS]
    status = _status_text(rows, visible_rows, columns)

    if version == VERSION_0_9:
        return _build_v09(
            surface_id=surface_id,
            title=title,
            status=status,
            columns=columns,
            rows=visible_rows,
            sql=sql,
            catalog_id=catalog_id or DEFAULT_V09_CATALOG_ID,
        )
    return _build_v08(
        surface_id=surface_id,
        title=title,
        status=status,
        columns=columns,
        rows=visible_rows,
        sql=sql,
    )


def _columns_for_rows(rows: list[dict]) -> list[str]:
    columns: list[str] = []
    for row in rows:
        for column in row.keys():
            if column not in columns:
                columns.append(column)
    return columns


def _status_text(rows: list[dict], visible_rows: list[dict], columns: list[str]) -> str:
    if not rows:
        return "No rows returned."
    status = f"Showing {len(visible_rows)} of {len(rows)} rows."
    if columns:
        status += f" Columns: {', '.join(columns)}."
    return status


def _display(value) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r", " ").replace("\n", " ")
    text = " ".join(text.split())
    if len(text) > MAX_CELL_CHARS:
        return f"{text[: MAX_CELL_CHARS - 3]}..."
    return text


def _component_ids(columns: list[str], rows: list[dict]) -> list[str]:
    ids = ["title", "status"]
    if columns:
        ids.append("header-row")
        ids.extend(f"data-row-{index}" for index, _ in enumerate(rows, start=1))
    ids.append("sql")
    return ids


def _build_v08(
    *,
    surface_id: str,
    title: str,
    status: str,
    columns: list[str],
    rows: list[dict],
    sql: str,
) -> list[dict]:
    components = [
        {
            "id": "root-column",
            "component": {
                "Column": {
                    "children": {"explicitList": _component_ids(columns, rows)},
                    "distribution": "start",
                    "alignment": "stretch",
                }
            },
        },
        {
            "id": "title",
            "component": {
                "Text": {"text": {"literalString": title}, "usageHint": "h2"}
            },
        },
        {
            "id": "status",
            "component": {
                "Text": {"text": {"literalString": status}, "usageHint": "body"}
            },
        },
        {
            "id": "sql",
            "component": {
                "Text": {
                    "text": {"literalString": f"SQL: {sql}"},
                    "usageHint": "caption",
                }
            },
        },
    ]

    if columns:
        components.extend(_v08_row("header-row", [_display(column) for column in columns]))
        for index, row in enumerate(rows, start=1):
            components.extend(
                _v08_row(
                    f"data-row-{index}",
                    [_display(row.get(column)) for column in columns],
                )
            )

    return [
        {"beginRendering": {"surfaceId": surface_id, "root": "root-column"}},
        {"surfaceUpdate": {"surfaceId": surface_id, "components": components}},
    ]


def _v08_row(component_id: str, values: list[str]) -> list[dict]:
    cell_ids = [f"{component_id}-cell-{index}" for index, _ in enumerate(values, start=1)]
    components = [
        {
            "id": component_id,
            "component": {
                "Row": {
                    "children": {"explicitList": cell_ids},
                    "distribution": "start",
                    "alignment": "stretch",
                }
            },
        }
    ]
    components.extend(
        {
            "id": cell_id,
            "component": {
                "Text": {"text": {"literalString": value}, "usageHint": "body"}
            },
        }
        for cell_id, value in zip(cell_ids, values)
    )
    return components


def _build_v09(
    *,
    surface_id: str,
    title: str,
    status: str,
    columns: list[str],
    rows: list[dict],
    sql: str,
    catalog_id: str,
) -> list[dict]:
    components = [
        {
            "id": "root",
            "component": "Column",
            "justify": "start",
            "align": "stretch",
            "children": _component_ids(columns, rows),
        },
        {"id": "title", "component": "Text", "variant": "h2", "text": title},
        {"id": "status", "component": "Text", "text": status},
        {"id": "sql", "component": "Text", "variant": "caption", "text": f"SQL: {sql}"},
    ]
    if columns:
        components.extend(_v09_row("header-row", [_display(column) for column in columns]))
        for index, row in enumerate(rows, start=1):
            components.extend(
                _v09_row(
                    f"data-row-{index}",
                    [_display(row.get(column)) for column in columns],
                )
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


def _v09_row(component_id: str, values: list[str]) -> list[dict]:
    cell_ids = [f"{component_id}-cell-{index}" for index, _ in enumerate(values, start=1)]
    components = [
        {
            "id": component_id,
            "component": "Row",
            "justify": "start",
            "align": "stretch",
            "children": cell_ids,
        }
    ]
    components.extend(
        {"id": cell_id, "component": "Text", "text": value}
        for cell_id, value in zip(cell_ids, values)
    )
    return components
