"""Read-only BigQuery tools for searching bridge inventory records."""

import logging
import re
from urllib.parse import urlencode

from google.cloud import bigquery
from google.adk.tools.tool_context import ToolContext

from app.bridge_ui import build_bridge_a2ui
from app.config import BIGQUERY_JOB_PROJECT, BIGQUERY_LOCATION, BRIDGE_BIGQUERY_TABLE
from app.session_keys import A2UI_CATALOG_KEY

logger = logging.getLogger(__name__)

_KEY_COLUMNS = (
    "LATITUDE_DD",
    "LONGITUDE_DD",
    "INVENT_FEAT",
    "RTE_ON_BRG_CD",
    "SFN",
    "STR_LOC",
    "COUNTY_CD",
)
_TABLE_ID_RE = re.compile(
    r"^[a-z][a-z0-9-]{4,28}[a-z0-9]\.[A-Za-z0-9_]+\.[A-Za-z0-9_]+$"
)


def _contains_clause(column: str, parameter: str) -> str:
    return f"LOWER(COALESCE(CAST({column} AS STRING), '')) LIKE @{parameter}"


def _row_to_bridge(row) -> dict:
    latitude = row.get("LATITUDE_DD")
    longitude = row.get("LONGITUDE_DD")

    return {
        "latitude": latitude,
        "longitude": longitude,
        "feature_crossed": row.get("INVENT_FEAT"),
        "route_code": row.get("RTE_ON_BRG_CD"),
        "structure_id": row.get("SFN"),
        "location": row.get("STR_LOC"),
        "county_code": row.get("COUNTY_CD"),
    }


def _build_all_bridges_map_embed_path(bridges: list[dict]) -> str | None:
    """Build one Google Maps Embed path containing every valid bridge coordinate."""
    coordinates = [
        f"{bridge['latitude']},{bridge['longitude']}"
        for bridge in bridges
        if bridge.get("latitude") is not None and bridge.get("longitude") is not None
    ]
    if not coordinates:
        return None
    if len(coordinates) == 1:
        return f"/maps/embed?{urlencode({'mode': 'place', 'q': coordinates[0]})}"

    params = {
        "mode": "directions",
        "origin": coordinates[0],
        "destination": coordinates[-1],
    }
    if len(coordinates) > 2:
        params["waypoints"] = "|".join(coordinates[1:-1])
    return f"/maps/embed?{urlencode(params)}"


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
    """Search the bridge inventory in BigQuery.

    Use this tool for every bridge lookup. Pass values explicitly mentioned by
    the user into the matching filters. Use ``query`` for general search text
    that should match the structure ID, route, location, county, or crossed
    feature. Leave all filters empty to return a small sample of bridges.

    Args:
        query: General free-text bridge search.
        county_code: County code to match.
        route_code: Route number or route code to match.
        structure_id: Bridge structure ID (SFN) to match.
        location: Location description to match.
        feature: Feature, creek, or road crossed to match.
        limit: Maximum records to return, from 1 through 10. Defaults to 10 so
            all returned bridges can be displayed together on the map.

    Returns:
        A dictionary containing matching bridge records and one combined map path.
    """
    try:
        limit = max(1, min(int(limit), 10))
    except (TypeError, ValueError):
        limit = 10

    if not _TABLE_ID_RE.fullmatch(BRIDGE_BIGQUERY_TABLE):
        return {
            "status": "error",
            "table": BRIDGE_BIGQUERY_TABLE,
            "message": "BRIDGE_BIGQUERY_TABLE must be PROJECT.DATASET.TABLE.",
            "count": 0,
            "bridges": [],
        }

    filters: list[str] = []
    parameters: list[bigquery.ScalarQueryParameter] = [
        bigquery.ScalarQueryParameter("limit", "INT64", limit)
    ]

    specific_filters = {
        "county_code": ("COUNTY_CD", county_code),
        "route_code": ("RTE_ON_BRG_CD", route_code),
        "structure_id": ("SFN", structure_id),
        "location": ("STR_LOC", location),
        "feature": ("INVENT_FEAT", feature),
    }
    for parameter, (column, value) in specific_filters.items():
        if value.strip():
            filters.append(_contains_clause(column, parameter))
            parameters.append(
                bigquery.ScalarQueryParameter(
                    parameter, "STRING", f"%{value.strip().lower()}%"
                )
            )

    if query.strip():
        query_columns = (
            "INVENT_FEAT",
            "RTE_ON_BRG_CD",
            "SFN",
            "STR_LOC",
            "COUNTY_CD",
        )
        filters.append(
            "("
            + " OR ".join(_contains_clause(column, "query") for column in query_columns)
            + ")"
        )
        parameters.append(
            bigquery.ScalarQueryParameter(
                "query", "STRING", f"%{query.strip().lower()}%"
            )
        )

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    selected_columns = ",\n  ".join(
        (
            "SAFE_CAST(LATITUDE_DD AS FLOAT64) AS LATITUDE_DD",
            "SAFE_CAST(LONGITUDE_DD AS FLOAT64) AS LONGITUDE_DD",
            *[f"CAST({column} AS STRING) AS {column}" for column in _KEY_COLUMNS[2:]],
        )
    )
    sql = f"""
SELECT
  {selected_columns}
FROM `{BRIDGE_BIGQUERY_TABLE}`
{where_clause}
ORDER BY SFN
LIMIT @limit
"""

    try:
        client = bigquery.Client(project=BIGQUERY_JOB_PROJECT)
        job_config = bigquery.QueryJobConfig(query_parameters=parameters)
        query_options = {"job_config": job_config}
        if BIGQUERY_LOCATION:
            query_options["location"] = BIGQUERY_LOCATION
        rows = client.query(sql, **query_options).result()
        bridges = [_row_to_bridge(row) for row in rows]
        result = {
            "status": "success",
            "table": BRIDGE_BIGQUERY_TABLE,
            "count": len(bridges),
            "bridges": bridges,
            "all_bridges_map_embed_path": _build_all_bridges_map_embed_path(bridges),
            "display_guidance": (
                "Display every returned key column for each bridge. "
                "Use all_bridges_map_embed_path once to show all returned bridges "
                "on the same Google Map."
            ),
        }
        if bridges and tool_context is not None:
            catalog = tool_context.state.get(A2UI_CATALOG_KEY)
            catalog_id = getattr(catalog, "catalog_id", None)
            version = getattr(catalog, "version", None)
            result["validated_a2ui_json"] = build_bridge_a2ui(
                bridges,
                result["all_bridges_map_embed_path"],
                version=version,
                catalog_id=catalog_id,
            )
            tool_context.actions.skip_summarization = True
        return result
    except Exception as exc:
        logger.exception("BigQuery bridge search failed")
        return {
            "status": "error",
            "table": BRIDGE_BIGQUERY_TABLE,
            "message": f"Bridge inventory query failed: {exc}",
            "count": 0,
            "bridges": [],
        }
