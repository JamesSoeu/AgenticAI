"""Unit tests for the schema-aware BigQuery map search tool."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.bridge_tools import search_bridges, search_map_records
from app.config import MapBigQueryTable
from app.session_keys import A2UI_CATALOG_KEY


MAP_TABLES = (
    MapBigQueryTable("bridge", "project-id", "transportation", "bridge_data"),
    MapBigQueryTable("crash", "project-id", "transportation", "crash_data"),
    MapBigQueryTable("road", "project-id", "transportation", "road_data"),
    MapBigQueryTable("traffic", "project-id", "transportation", "traffic_data"),
    MapBigQueryTable("asset", "project-id", "transportation", "asset_data"),
)


def _field(name: str, field_type: str = "STRING", description: str = ""):
    return SimpleNamespace(
        name=name,
        field_type=field_type,
        mode="NULLABLE",
        description=description,
    )


def _table_schema(table_id: str):
    if table_id.endswith("bridge_data"):
        schema = [
            _field("SFN"),
            _field("COUNTY"),
            _field("LATITUDE_DD", "FLOAT"),
            _field("LONGITUDE_DD", "FLOAT"),
            _field("STR_LOC"),
        ]
    elif table_id.endswith("crash_data"):
        schema = [
            _field("CRASH_ID"),
            _field("COUNTY_NAME"),
            _field("CRASH_LATITUDE", "FLOAT"),
            _field("CRASH_LONGITUDE", "FLOAT"),
            _field("CRASH_DATE"),
        ]
    else:
        schema = [
            _field("OBJECT_ID"),
            _field("ROUTE"),
            _field("LAT", "FLOAT"),
            _field("LON", "FLOAT"),
            _field("DESCRIPTION"),
        ]
    return SimpleNamespace(
        description=f"Schema for {table_id}",
        num_rows=100,
        schema=schema,
    )


def _configure_client(mock_client_class):
    client = MagicMock()
    mock_client_class.return_value = client
    client.get_table.side_effect = _table_schema
    return client


@patch("app.bridge_tools.MAP_BIGQUERY_TABLES", MAP_TABLES)
@patch(
    "app.bridge_tools.build_maps_embed_url",
    return_value="https://www.google.com/maps/embed/v1/view?key=test&center=39.961%2C-82.999&zoom=11",
)
@patch("app.bridge_tools._call_gemini_sql_planner")
@patch("app.bridge_tools.bigquery.Client")
def test_search_map_records_uses_table_schemas_and_planner_sql(
    mock_client_class,
    mock_planner,
    _mock_embed_url,
):
    client = _configure_client(mock_client_class)
    mock_planner.return_value = {
        "sql": """
            SELECT
              SAFE_CAST(CRASH_LATITUDE AS FLOAT64) AS latitude,
              SAFE_CAST(CRASH_LONGITUDE AS FLOAT64) AS longitude,
              CAST(CRASH_ID AS STRING) AS title,
              CONCAT('Crash date: ', CAST(CRASH_DATE AS STRING)) AS description,
              'crash' AS source_table
            FROM `project-id.transportation.crash_data`
            WHERE LOWER(COUNTY_NAME) = 'franklin'
            LIMIT 3
        """,
        "reason": "Crash table has crash coordinates and county fields.",
    }
    client.query.return_value.result.return_value = [
        {
            "latitude": 39.9612,
            "longitude": -82.9988,
            "title": "C-100",
            "description": "Crash date: 2026-06-01",
            "source_table": "crash",
        }
    ]

    result = search_map_records("show me recent crashes in Franklin County", limit=3)

    assert result["status"] == "success"
    assert result["count"] == 1
    assert result["records"][0]["title"] == "C-100"
    assert result["records"][0]["source_table"] == "crash"
    assert result["table_aliases"] == ["bridge", "crash", "road", "traffic", "asset"]
    assert client.get_table.call_count == 5
    schema_summary = mock_planner.call_args.args[1]
    assert {item["alias"] for item in schema_summary} == {
        "bridge",
        "crash",
        "road",
        "traffic",
        "asset",
    }
    sql = client.query.call_args.args[0]
    assert "FROM `project-id.transportation.crash_data`" in sql
    assert "UNION ALL" not in sql
    assert result["all_bridges_map"]["map_mode"] == "view"
    _mock_embed_url.assert_called_once_with(center="39.9612,-82.9988", zoom=17)


@patch("app.bridge_tools.MAP_BIGQUERY_TABLES", MAP_TABLES)
@patch("app.bridge_tools._call_gemini_sql_planner")
@patch("app.bridge_tools.bigquery.Client")
def test_search_map_records_rejects_non_configured_tables(
    mock_client_class,
    mock_planner,
):
    _configure_client(mock_client_class)
    mock_planner.return_value = {
        "sql": """
            SELECT
              SAFE_CAST(lat AS FLOAT64) AS latitude,
              SAFE_CAST(lon AS FLOAT64) AS longitude,
              CAST(id AS STRING) AS title,
              CAST(name AS STRING) AS description,
              'other' AS source_table
            FROM `project-id.transportation.other_table`
            LIMIT 1
        """,
        "reason": "Bad table.",
    }

    result = search_map_records("show something on a map")

    assert result["status"] == "error"
    assert result["count"] == 0
    assert "non-configured tables" in result["message"]


@patch("app.bridge_tools.MAP_BIGQUERY_TABLES", MAP_TABLES)
@patch("app.bridge_tools._call_gemini_sql_planner")
@patch("app.bridge_tools.bigquery.Client")
def test_search_map_records_returns_cannot_map_when_schemas_lack_coordinates(
    mock_client_class,
    mock_planner,
):
    _configure_client(mock_client_class)
    mock_planner.return_value = {
        "cannot_map": True,
        "reason": "No latitude or longitude fields are available.",
    }

    result = search_map_records("show funding records on a map")

    assert result["status"] == "cannot_map"
    assert result["count"] == 0
    assert "No latitude" in result["message"]


@patch("app.bridge_tools.MAP_BIGQUERY_TABLES", MAP_TABLES)
@patch(
    "app.bridge_tools.build_maps_embed_url",
    return_value="https://www.google.com/maps/embed/v1/place?key=test&q=39.9612%2C-82.9988",
)
@patch("app.bridge_tools._call_gemini_sql_planner")
@patch("app.bridge_tools.bigquery.Client")
def test_search_map_records_returns_render_ready_a2ui_for_gemini_enterprise(
    mock_client_class,
    mock_planner,
    _mock_embed_url,
):
    client = _configure_client(mock_client_class)
    mock_planner.return_value = {
        "sql": """
            SELECT
              SAFE_CAST(LATITUDE_DD AS FLOAT64) AS latitude,
              SAFE_CAST(LONGITUDE_DD AS FLOAT64) AS longitude,
              CAST(SFN AS STRING) AS title,
              CAST(STR_LOC AS STRING) AS description,
              'bridge' AS source_table
            FROM `project-id.transportation.bridge_data`
            LIMIT 1
        """,
        "reason": "Bridge table has coordinates.",
    }
    client.query.return_value.result.return_value = [
        {
            "latitude": 39.9612,
            "longitude": -82.9988,
            "title": "1234567",
            "description": "Main Street bridge",
            "source_table": "bridge",
        }
    ]
    tool_context = MagicMock()
    tool_context.state = {
        A2UI_CATALOG_KEY: SimpleNamespace(
            version="0.8",
            catalog_id="urn:gemini-enterprise-map:a2ui-catalog:v0.8",
        )
    }

    result = search_map_records("show bridge 1234567 on a map", tool_context=tool_context)

    messages = result["validated_a2ui_json"]
    assert "beginRendering" in messages[0]
    assert "surfaceUpdate" in messages[1]
    assert "Map Search Results" in str(messages)
    assert "WebFrameUrl" in str(messages)
    assert "https://www.google.com/maps/embed/v1/place?" in str(messages)
    assert "directions" not in str(messages)
    assert "Record 1: 1234567" in str(messages)
    assert tool_context.actions.skip_summarization is True


@patch("app.bridge_tools.MAP_BIGQUERY_TABLES", MAP_TABLES)
@patch(
    "app.bridge_tools.build_maps_embed_url",
    return_value="https://www.google.com/maps/embed/v1/place?key=test&q=39.9612%2C-82.9988",
)
@patch("app.bridge_tools._call_gemini_sql_planner")
@patch("app.bridge_tools.bigquery.Client")
def test_search_map_records_returns_a2ui_without_tool_context(
    mock_client_class,
    mock_planner,
    _mock_embed_url,
):
    client = _configure_client(mock_client_class)
    mock_planner.return_value = {
        "sql": """
            SELECT
              SAFE_CAST(LATITUDE_DD AS FLOAT64) AS latitude,
              SAFE_CAST(LONGITUDE_DD AS FLOAT64) AS longitude,
              CAST(SFN AS STRING) AS title,
              CAST(STR_LOC AS STRING) AS description,
              'bridge' AS source_table
            FROM `project-id.transportation.bridge_data`
            LIMIT 1
        """,
        "reason": "Bridge table has coordinates.",
    }
    client.query.return_value.result.return_value = [
        {
            "latitude": 39.9612,
            "longitude": -82.9988,
            "title": "1234567",
            "description": "Main Street bridge",
            "source_table": "bridge",
        }
    ]

    result = search_map_records("show bridge 1234567 on a map")

    assert result["status"] == "success"
    assert "validated_a2ui_json" in result
    assert "Map Search Results" in str(result["validated_a2ui_json"])
    assert "WebFrameUrl" in str(result["validated_a2ui_json"])


@patch("app.bridge_tools.bigquery.Client")
def test_search_map_records_returns_safe_error(mock_client_class):
    mock_client_class.side_effect = RuntimeError("permission denied")

    result = search_map_records("show bridge records on a map")

    assert result["status"] == "error"
    assert result["count"] == 0
    assert result["records"] == []
    assert "permission denied" in result["message"]


@patch("app.bridge_tools.MAP_BIGQUERY_TABLES", ())
def test_search_map_records_handles_missing_configured_tables():
    result = search_map_records("show map records")

    assert result["status"] == "error"
    assert result["count"] == 0
    assert "MAP_BIGQUERY_TABLES" in result["message"]


@patch("app.bridge_tools.MAP_BIGQUERY_TABLES", MAP_TABLES)
@patch("app.bridge_tools._call_gemini_sql_planner")
@patch("app.bridge_tools.bigquery.Client")
def test_search_bridges_wrapper_preserves_older_agent_contract(
    mock_client_class,
    mock_planner,
):
    client = _configure_client(mock_client_class)
    mock_planner.return_value = {
        "sql": """
            SELECT
              SAFE_CAST(LATITUDE_DD AS FLOAT64) AS latitude,
              SAFE_CAST(LONGITUDE_DD AS FLOAT64) AS longitude,
              CAST(SFN AS STRING) AS title,
              CAST(STR_LOC AS STRING) AS description,
              'bridge' AS source_table
            FROM `project-id.transportation.bridge_data`
            LIMIT 1
        """,
        "reason": "Bridge query.",
    }
    client.query.return_value.result.return_value = []

    result = search_bridges(county_code="001", feature="creek")

    assert result["status"] == "success"
    assert "county 001" in mock_planner.call_args.args[0]
    assert "creek" in mock_planner.call_args.args[0]
