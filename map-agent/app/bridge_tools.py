"""Schema-aware BigQuery tools for map-ready transportation records."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from google.adk.tools.tool_context import ToolContext
from google.cloud import bigquery

from app.bridge_ui import build_bridge_a2ui
from app.config import (
    BIGQUERY_JOB_PROJECT,
    BIGQUERY_LOCATION,
    DEFAULT_MODEL,
    GOOGLE_CLOUD_LOCATION,
    GOOGLE_CLOUD_PROJECT,
    GOOGLE_GENAI_USE_VERTEXAI,
    MAP_BIGQUERY_MAX_BYTES_BILLED,
    MAP_BIGQUERY_TABLES,
    MAP_DEFAULT_LIMIT,
    MAP_MAX_LIMIT,
    MapBigQueryTable,
    build_maps_embed_url,
)
from app.session_keys import A2UI_CATALOG_KEY

logger = logging.getLogger(__name__)

_BLOCKED_SQL = re.compile(
    r"\b(ALTER|CALL|CREATE|DELETE|DROP|EXPORT|GRANT|INSERT|MERGE|REPLACE|REVOKE|TRUNCATE|UPDATE)\b",
    re.IGNORECASE,
)
_FROM_OR_JOIN = re.compile(
    r"\b(?:FROM|JOIN)\s+`?([A-Za-z0-9_-]+\.[A-Za-z_][A-Za-z0-9_]+\.[A-Za-z_][A-Za-z0-9_]+)`?",
    re.IGNORECASE,
)
_REQUIRED_OUTPUTS = ("latitude", "longitude", "title", "description", "source_table")


def _clean_map_text(value) -> str:
    return "Not available" if value in (None, "") else str(value)


def _bounded_limit(limit: int | None) -> int:
    value = MAP_DEFAULT_LIMIT if limit is None else int(limit)
    return max(1, min(value, MAP_MAX_LIMIT))


def _configured_tables() -> tuple[MapBigQueryTable, ...]:
    return MAP_BIGQUERY_TABLES


def _configured_tables_display() -> str:
    return ",".join(table.full_id for table in _configured_tables())


def _table_schema_summary(client: bigquery.Client) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for table in _configured_tables():
        bq_table = client.get_table(table.full_id)
        summaries.append(
            {
                "alias": table.alias,
                "table": table.full_id,
                "description": bq_table.description or "",
                "num_rows": bq_table.num_rows,
                "columns": [
                    {
                        "name": field.name,
                        "type": field.field_type,
                        "mode": field.mode,
                        "description": field.description or "",
                    }
                    for field in bq_table.schema
                ],
            }
        )
    return summaries


def _zoom_for_coordinates(coordinates: list[tuple[float, float]]) -> int:
    if len(coordinates) <= 1:
        return 14

    latitudes = [latitude for latitude, _ in coordinates]
    longitudes = [longitude for _, longitude in coordinates]
    spread = round(
        max(max(latitudes) - min(latitudes), max(longitudes) - min(longitudes)),
        6,
    )
    if spread > 1.0:
        return 7
    if spread > 0.5:
        return 8
    if spread > 0.2:
        return 9
    if spread > 0.08:
        return 10
    return 11


def _build_map_data(records: list[dict[str, Any]]) -> dict | None:
    coordinates = [
        (float(record["latitude"]), float(record["longitude"]), record)
        for record in records
        if record.get("latitude") is not None and record.get("longitude") is not None
    ]
    if not coordinates:
        return None

    coordinate_pairs = [(latitude, longitude) for latitude, longitude, _ in coordinates]
    center = {
        "lat": round(
            sum(latitude for latitude, _, _ in coordinates) / len(coordinates), 6
        ),
        "lng": round(
            sum(longitude for _, longitude, _ in coordinates) / len(coordinates), 6
        ),
    }
    pins = [
        {
            "lat": latitude,
            "lng": longitude,
            "name": _clean_map_text(record.get("title")),
            "description": _clean_map_text(record.get("description")),
        }
        for latitude, longitude, record in coordinates
    ]

    zoom = _zoom_for_coordinates(coordinate_pairs)
    if len(coordinates) == 1:
        latitude, longitude, record = coordinates[0]
        frame_url = build_maps_embed_url(
            center=f"{latitude},{longitude}",
            zoom=17,
        )
    else:
        frame_url = build_maps_embed_url(
            center=f"{center['lat']},{center['lng']}",
            zoom=zoom,
        )
    if not frame_url:
        return None

    return {
        "center": center,
        "zoom": zoom,
        "pins": pins,
        "frame_url": frame_url,
        "map_mode": "view",
        "embed_note": (
            "Google Maps Embed API is used for Gemini Enterprise compatibility. "
            "Multiple returned records are listed below the map; the iframe uses "
            "a centered map view instead of custom JavaScript pins."
        ),
    }


def _extract_json_object(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Gemini SQL planner did not return a JSON object.")
    return json.loads(text[start : end + 1])


def _call_gemini_sql_planner(
    user_request: str,
    schema_summary: list[dict[str, Any]],
    limit: int,
) -> dict[str, Any]:
    from google import genai
    from google.genai import types

    client = genai.Client(
        vertexai=GOOGLE_GENAI_USE_VERTEXAI,
        project=GOOGLE_CLOUD_PROJECT or None,
        location=GOOGLE_CLOUD_LOCATION,
    )
    response = client.models.generate_content(
        model=DEFAULT_MODEL,
        contents=_sql_planner_prompt(user_request, schema_summary, limit),
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
        ),
    )
    text = getattr(response, "text", None)
    if not text:
        raise ValueError("Gemini SQL planner returned an empty response.")
    parsed = _extract_json_object(text)
    if parsed.get("cannot_map"):
        return parsed
    if not parsed.get("sql"):
        raise ValueError("Gemini SQL planner response did not include sql.")
    return parsed


def _sql_planner_prompt(
    user_request: str,
    schema_summary: list[dict[str, Any]],
    limit: int,
) -> str:
    return f"""You are a BigQuery SQL planner for a Gemini Enterprise map agent.

Use only the configured tables and schemas below. The tables can have different
schemas but may be related by columns such as bridge IDs, crash IDs, route IDs,
county, milepost, location, or other shared fields.

Return only JSON. Do not include markdown.

Allowed output shapes:
{{
  "sql": "SELECT ...",
  "reason": "short reason"
}}

or, if the configured schemas do not contain usable map/location fields:
{{
  "cannot_map": true,
  "reason": "short reason"
}}

SQL requirements:
- Use BigQuery Standard SQL only.
- Use SELECT or WITH only.
- Use only configured tables listed below.
- Do not use DDL, DML, EXPORT, temporary functions, scripts, or multiple statements.
- The final SELECT must return these exact aliases:
  latitude      FLOAT64-compatible latitude
  longitude     FLOAT64-compatible longitude
  title         STRING label for the result
  description   STRING concise details for the result
  source_table  STRING configured table alias or table name
- Use SAFE_CAST for latitude/longitude.
- Filter according to the user request.
- Add LIMIT {limit}.

Configured table schemas:
{json.dumps(schema_summary, indent=2)}

User request:
{user_request}
"""


def _validate_map_sql(sql: str) -> str:
    clean_sql = sql.strip().rstrip(";").strip()
    if not clean_sql:
        raise ValueError("SQL query is empty.")
    if not re.match(r"^(WITH|SELECT)\b", clean_sql, re.IGNORECASE):
        raise ValueError("Only SELECT or WITH map queries are allowed.")
    if ";" in clean_sql:
        raise ValueError("Multiple SQL statements are not allowed.")
    if _BLOCKED_SQL.search(clean_sql):
        raise ValueError("Mutation, DDL, export, and permission statements are not allowed.")

    referenced_tables = set(_FROM_OR_JOIN.findall(clean_sql))
    allowed_ids = {table.full_id for table in _configured_tables()}
    if not referenced_tables:
        raise ValueError("Query must reference at least one configured table.")
    disallowed = referenced_tables - allowed_ids
    if disallowed:
        raise ValueError(
            "Query references non-configured tables: " + ", ".join(sorted(disallowed))
        )

    for alias in _REQUIRED_OUTPUTS:
        if not re.search(rf"\bAS\s+`?{alias}`?\b", clean_sql, re.IGNORECASE):
            raise ValueError(f"Map SQL must return `{alias}`.")
    return clean_sql


def _ensure_limit(sql: str, limit: int) -> str:
    if re.search(r"\bLIMIT\s+\d+\s*$", sql, re.IGNORECASE):
        return sql
    return f"SELECT * FROM ({sql}) LIMIT {limit}"


def _row_to_record(row) -> dict[str, Any]:
    data = {key.lower(): value for key, value in dict(row.items()).items()}
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    return {
        "latitude": latitude,
        "longitude": longitude,
        "title": data.get("title"),
        "description": data.get("description"),
        "source_table": data.get("source_table"),
        # Backward-compatible keys used by the existing A2UI builder/tests.
        "structure_id": data.get("title"),
        "location": data.get("description"),
        "feature_crossed": data.get("source_table"),
        "route_code": None,
        "county_code": None,
    }


def search_map_records(
    user_request: str,
    limit: int = 10,
    tool_context: ToolContext | None = None,
) -> dict:
    """Search configured BigQuery tables and return map-ready records.

    The tool reads schemas for all configured map tables, asks Gemini to choose
    the relevant table or join, validates the generated SQL, runs it read-only,
    and renders the records through A2UI when a tool context is available.
    """
    row_limit = _bounded_limit(limit)
    configured_tables = _configured_tables()
    if not configured_tables:
        return {
            "status": "error",
            "message": "MAP_BIGQUERY_TABLES is not configured.",
            "count": 0,
            "records": [],
            "bridges": [],
        }

    try:
        client = bigquery.Client(project=BIGQUERY_JOB_PROJECT)
        schema_summary = _table_schema_summary(client)
        plan = _call_gemini_sql_planner(user_request, schema_summary, row_limit)
        if plan.get("cannot_map"):
            return {
                "status": "cannot_map",
                "message": plan.get("reason", "No usable map fields were found."),
                "tables": [table.full_id for table in configured_tables],
                "count": 0,
                "records": [],
                "bridges": [],
            }

        clean_sql = _ensure_limit(_validate_map_sql(plan["sql"]), row_limit)
        job_config = bigquery.QueryJobConfig(
            maximum_bytes_billed=MAP_BIGQUERY_MAX_BYTES_BILLED,
            labels={"component": "gemini-enterprise-map-agent"},
        )
        query_options = {"job_config": job_config}
        if BIGQUERY_LOCATION:
            query_options["location"] = BIGQUERY_LOCATION
        rows = client.query(clean_sql, **query_options).result()
        records = [_row_to_record(row) for row in rows]
        map_data = _build_map_data(records)
        result = {
            "status": "success",
            "sql": clean_sql,
            "reason": plan.get("reason", ""),
            "tables": [table.full_id for table in configured_tables],
            "table_aliases": [table.alias for table in configured_tables],
            "count": len(records),
            "records": records,
            "bridges": records,
            "all_bridges_map": map_data,
            "display_guidance": (
                "Display every returned record. Use all_bridges_map once for the "
                "Google Maps Embed iframe. Do not create a directions route."
            ),
        }
        if records:
            result["validated_a2ui_json"] = build_bridge_a2ui(records, map_data)
        if records and tool_context is not None:
            catalog = tool_context.state.get(A2UI_CATALOG_KEY)
            catalog_id = getattr(catalog, "catalog_id", None)
            version = getattr(catalog, "version", None)
            result["validated_a2ui_json"] = build_bridge_a2ui(
                records,
                map_data,
                version=version,
                catalog_id=catalog_id,
            )
            tool_context.actions.skip_summarization = True
        return result
    except Exception as exc:
        logger.exception("Map BigQuery search failed")
        return {
            "status": "error",
            "table": _configured_tables_display(),
            "tables": [table.full_id for table in configured_tables],
            "message": f"Map query failed: {exc}",
            "count": 0,
            "records": [],
            "bridges": [],
        }


def search_bridges(
    query: str = "",
    county_code: str = "",
    route_code: str = "",
    structure_id: str = "",
    location: str = "",
    feature: str = "",
    limit: int = 10,
    tool_context: ToolContext | None = None,
) -> dict:
    """Backward-compatible wrapper for older bridge-focused prompts/tests."""
    parts = [
        query,
        f"county {county_code}" if county_code else "",
        f"route {route_code}" if route_code else "",
        f"structure {structure_id}" if structure_id else "",
        location,
        feature,
    ]
    user_request = " ".join(part for part in parts if part).strip() or "Show map records."
    return search_map_records(user_request, limit=limit, tool_context=tool_context)
