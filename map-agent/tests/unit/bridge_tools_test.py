"""Unit tests for the read-only BigQuery bridge search tool."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.bridge_tools import search_bridges
from app.session_keys import A2UI_CATALOG_KEY


@patch("app.bridge_tools.bigquery.Client")
def test_search_bridges_uses_parameterized_query(mock_client_class):
    client = MagicMock()
    mock_client_class.return_value = client
    client.query.return_value.result.return_value = []

    result = search_bridges(
        query="creek",
        county_code="001",
        route_code="SR-1",
        limit=50,
    )

    sql = client.query.call_args.args[0]
    job_config = client.query.call_args.kwargs["job_config"]
    parameters = {parameter.name: parameter.value for parameter in job_config.query_parameters}

    assert result["status"] == "success"
    assert "SELECT" in sql
    assert "FROM `your-project-id.transportation.bridge_data`" in sql
    assert "creek" not in sql
    assert "001" not in sql
    assert parameters["query"] == "%creek%"
    assert parameters["county_code"] == "%001%"
    assert parameters["route_code"] == "%sr-1%"
    assert parameters["limit"] == 10


@patch("app.bridge_tools.bigquery.Client")
def test_search_bridges_returns_key_columns_and_single_bridge_map_path(mock_client_class):
    client = MagicMock()
    mock_client_class.return_value = client
    client.query.return_value.result.return_value = [
        {
            "LATITUDE_DD": 38.9351,
            "LONGITUDE_DD": -83.4596,
            "INVENT_FEAT": "Example Creek",
            "RTE_ON_BRG_CD": "SR-001",
            "SFN": "0123456",
            "STR_LOC": "Example location",
            "COUNTY_CD": "001",
        }
    ]

    result = search_bridges(structure_id="0123456")
    bridge = result["bridges"][0]

    assert result["count"] == 1
    assert bridge["structure_id"] == "0123456"
    assert bridge["feature_crossed"] == "Example Creek"
    assert result["all_bridges_map"]["center"] == {"lat": 38.9351, "lng": -83.4596}
    assert result["all_bridges_map"]["zoom"] == 14
    assert result["all_bridges_map"]["frame_url"].startswith(
        "http://127.0.0.1:8000/bridge-map?data="
    )
    assert result["all_bridges_map"]["pins"] == [
        {
            "lat": 38.9351,
            "lng": -83.4596,
            "name": "Bridge 1: SFN 0123456",
            "description": (
                "Route: SR-001 | Feature: Example Creek | "
                "Location: Example location | County: 001"
            ),
        }
    ]


@patch("app.bridge_tools.bigquery.Client")
def test_search_bridges_puts_all_bridge_coordinates_on_one_map(mock_client_class):
    client = MagicMock()
    mock_client_class.return_value = client
    client.query.return_value.result.return_value = [
        {
            "LATITUDE_DD": 38.1,
            "LONGITUDE_DD": -83.1,
            "INVENT_FEAT": "Creek A",
            "RTE_ON_BRG_CD": "SR-1",
            "SFN": "1",
            "STR_LOC": "Location A",
            "COUNTY_CD": "001",
        },
        {
            "LATITUDE_DD": 38.2,
            "LONGITUDE_DD": -83.2,
            "INVENT_FEAT": "Creek B",
            "RTE_ON_BRG_CD": "SR-2",
            "SFN": "2",
            "STR_LOC": "Location B",
            "COUNTY_CD": "001",
        },
        {
            "LATITUDE_DD": 38.3,
            "LONGITUDE_DD": -83.3,
            "INVENT_FEAT": "Creek C",
            "RTE_ON_BRG_CD": "SR-3",
            "SFN": "3",
            "STR_LOC": "Location C",
            "COUNTY_CD": "001",
        },
    ]

    result = search_bridges(county_code="001")
    map_data = result["all_bridges_map"]

    assert result["count"] == 3
    assert map_data["center"] == {"lat": 38.2, "lng": -83.2}
    assert map_data["zoom"] == 10
    assert map_data["frame_url"].startswith(
        "http://127.0.0.1:8000/bridge-map?data="
    )
    assert [pin["name"] for pin in map_data["pins"]] == [
        "Bridge 1: SFN 1",
        "Bridge 2: SFN 2",
        "Bridge 3: SFN 3",
    ]
    assert "directions" not in str(map_data)
    assert sum("map_embed_path" in bridge for bridge in result["bridges"]) == 0


@patch("app.bridge_tools.bigquery.Client")
def test_search_bridges_returns_render_ready_a2ui_for_gemini_enterprise(
    mock_client_class,
):
    client = MagicMock()
    mock_client_class.return_value = client
    client.query.return_value.result.return_value = [
        {
            "LATITUDE_DD": 38.9351,
            "LONGITUDE_DD": -83.4596,
            "INVENT_FEAT": "Creek",
            "RTE_ON_BRG_CD": "SR-1",
            "SFN": "1",
            "STR_LOC": "Location",
            "COUNTY_CD": "001",
        }
    ]
    tool_context = MagicMock()
    tool_context.state = {
        A2UI_CATALOG_KEY: SimpleNamespace(
            version="0.8",
            catalog_id="urn:gemini-enterprise-bridge-map:a2ui-catalog:v0.8",
        )
    }

    result = search_bridges(feature="creek", tool_context=tool_context)

    messages = result["validated_a2ui_json"]
    assert "beginRendering" in messages[0]
    assert "surfaceUpdate" in messages[1]
    assert "Bridge Search Results" in str(messages)
    assert "WebFrameUrl" in str(messages)
    assert "/bridge-map?data=" in str(messages)
    assert "directions" not in str(messages)
    assert "Bridge 1: SFN 1" in str(messages)
    assert tool_context.actions.skip_summarization is True


@patch("app.bridge_tools.bigquery.Client")
def test_search_bridges_returns_safe_error(mock_client_class):
    mock_client_class.side_effect = RuntimeError("permission denied")

    result = search_bridges(query="bridge")

    assert result["status"] == "error"
    assert result["count"] == 0
    assert result["bridges"] == []
    assert "permission denied" in result["message"]


@patch("app.bridge_tools.BRIDGE_BIGQUERY_TABLE", "not-a-table")
def test_search_bridges_rejects_invalid_configured_table():
    result = search_bridges(query="bridge")

    assert result["status"] == "error"
    assert result["count"] == 0
    assert "PROJECT.DATASET.TABLE" in result["message"]
