# Map Agent Schema-Aware BigQuery Tables

The map agent can search multiple related BigQuery tables even when the tables
do not have identical columns. This is intended for transportation datasets such
as bridge inventory, crash records, road inventory, traffic records, and asset
or inspection tables.

## What Changed

The map agent no longer assumes every table has the same bridge columns. It now:

1. Reads the schema for every configured BigQuery table.
2. Sends the user request and schema summaries to Gemini.
3. Asks Gemini to generate BigQuery Standard SQL for the right table or join.
4. Validates that the SQL is read-only and references only configured tables.
5. Requires the final SQL to return standard map fields.
6. Runs the query and renders the result through a Gemini Enterprise-safe
   Google Maps Embed iframe.

## Files To Update

Use these files when configuring or changing the map agent:

| File | What to update |
| --- | --- |
| `map-agent/cloudrun-env.yaml` | Main Cloud Run environment values for deployed map agent |
| `map-agent/.env` | Local development values |
| `map-agent/cloudrun-env.example.yaml` | Team template for deployment config |
| `map-agent/app/config.py` | Environment parsing and defaults |
| `map-agent/app/bridge_tools.py` | Schema-aware BigQuery planner, SQL validation, and map result builder |
| `map-agent/app/agent.py` | Agent card, instructions, and exposed ADK tool |
| `map-agent/app/bridge_ui.py` | A2UI map/search result payload |
| `map-agent/scripts/deploy_cloud_run.ps1` | Windows deployment command wrapper |
| `map-agent/scripts/deploy_cloud_run.sh` | Mac/Linux deployment command wrapper |

Most day-to-day table changes should only require updating `cloudrun-env.yaml`
or Cloud Run environment variables. Code changes are needed only when behavior
or validation rules change.

## Environment Variables

Use the new `MAP_*` variables for new deployments:

```yaml
MAP_BIGQUERY_TABLES: "PROJECT.DATASET.bridge,PROJECT.DATASET.crash,PROJECT.DATASET.road,PROJECT.DATASET.traffic,PROJECT.DATASET.asset"
MAP_BIGQUERY_TABLE_ALIASES: "bridge,crash,road,traffic,asset"
MAP_BIGQUERY_MAX_BYTES_BILLED: "1000000000"
MAP_DEFAULT_LIMIT: "10"
MAP_MAX_LIMIT: "50"
GOOGLE_MAPS_SECRET_NAME: "google_map_api_key"
GOOGLE_MAPS_SECRET_LOCATION: "us-central1"
```

`MAP_BIGQUERY_TABLES` can contain five tables, or more if needed. The aliases
are optional but recommended because they make SQL output and result summaries
easier to read. If aliases are provided, the count must match the table count.

The older `BRIDGE_BIGQUERY_TABLES` and `BRIDGE_BIGQUERY_TABLE` values still work
as fallback settings, but they should not be used for new deployments.

## Required SQL Output

The generated SQL can use any real columns from the configured tables, but the
final `SELECT` must return these aliases:

```sql
latitude
longitude
title
description
source_table
```

Example final projection:

```sql
SELECT
  SAFE_CAST(CRASH_LATITUDE AS FLOAT64) AS latitude,
  SAFE_CAST(CRASH_LONGITUDE AS FLOAT64) AS longitude,
  CAST(CRASH_ID AS STRING) AS title,
  CONCAT('Crash date: ', CAST(CRASH_DATE AS STRING)) AS description,
  'crash' AS source_table
FROM `PROJECT.DATASET.crash`
LIMIT 10
```

## Limits

The agent validates and controls generated SQL:

- Only `SELECT` and `WITH` queries are allowed.
- DDL, DML, `EXPORT`, permission statements, scripts, and multiple statements
  are blocked.
- SQL can only reference configured tables.
- BigQuery cost is capped by `MAP_BIGQUERY_MAX_BYTES_BILLED`.
- Result count is bounded by `MAP_DEFAULT_LIMIT` and `MAP_MAX_LIMIT`.

## Required Permissions

The map agent Cloud Run runtime service account needs:

- `roles/aiplatform.user` on the agent project for Gemini SQL planning.
- `roles/bigquery.jobUser` on the job project.
- `roles/bigquery.dataViewer` on the BigQuery data project, dataset, or tables.
- `roles/secretmanager.secretAccessor` on the Google Maps API key secret.

Gemini Enterprise also needs `roles/run.invoker` on the private map-agent Cloud
Run service if authentication is required.

## Important Behavior

This approach does not hardcode every table column in Python. However, SQL still
must use real column names, so the agent discovers those names from BigQuery
schema metadata and asks Gemini to plan the query.

If none of the configured tables have usable latitude/longitude fields, or if
the user asks for something that cannot be mapped, the tool returns `cannot_map`
instead of inventing coordinates.
