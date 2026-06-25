# Map Agent

Backend-only A2A/A2UI Cloud Run service for transportation map questions.

It handles:

- Schema-aware search across related BigQuery map/search tables
- Different table schemas for bridge, crash, road, traffic, and asset data
- A2UI response creation for Gemini Enterprise
- WebFrameUrl map responses for Gemini Enterprise using Google Maps Embed API
- Google Maps Embed URL proxying through `/maps/embed` for compatibility links

There is no separate frontend folder in this monorepo version. Gemini Enterprise
is the client that renders the A2UI `WebFrameUrl` response. The map iframe uses
Google Maps Embed API directly because Gemini Enterprise can block custom HTML
and JavaScript. Multiple results are listed below the map; the iframe uses a
centered map view instead of custom JavaScript pins or a directions route.

## Configure

Copy and edit the environment template:

```powershell
Copy-Item cloudrun-env.example.yaml cloudrun-env.yaml
notepad cloudrun-env.yaml
```

Important values:

```yaml
GOOGLE_CLOUD_PROJECT: "YOUR_PROJECT_ID"
GOOGLE_CLOUD_LOCATION: "global"
MODEL: "gemini-3.5-flash"
AGENT_URL: "https://YOUR-MAP-AGENT-URL.run.app"
MAP_BIGQUERY_TABLES: "YOUR_PROJECT_ID.transportation.bridge_data,YOUR_PROJECT_ID.transportation.crash_data,YOUR_PROJECT_ID.transportation.road_data,YOUR_PROJECT_ID.transportation.traffic_data,YOUR_PROJECT_ID.transportation.asset_data"
MAP_BIGQUERY_TABLE_ALIASES: "bridge,crash,road,traffic,asset"
MAP_BIGQUERY_MAX_BYTES_BILLED: "1000000000"
MAP_DEFAULT_LIMIT: "10"
MAP_MAX_LIMIT: "50"
BIGQUERY_JOB_PROJECT: "YOUR_PROJECT_ID"
GOOGLE_MAPS_SECRET_NAME: "google_map_api_key"
```

`MAP_BIGQUERY_TABLES` accepts comma-separated BigQuery table IDs in either
`project.dataset.table` or `dataset.table` form. `MAP_BIGQUERY_TABLE_ALIASES`
is optional, but recommended, and must have the same number of values as the
table list.

The tables do not need identical columns. At runtime, the agent reads each
configured BigQuery table schema, asks Gemini to choose the relevant table or
join, validates the generated SQL, and then runs it as a read-only query.

The generated SQL must return these standard output aliases so the map renderer
can work:

```text
latitude
longitude
title
description
source_table
```

At least one configured table must contain usable latitude/longitude columns or
joinable data that leads to latitude/longitude columns. If the schemas do not
contain map-ready fields, the tool returns `cannot_map` instead of inventing
coordinates.

The old bridge-focused settings still work as fallback values, but new
deployments should use `MAP_BIGQUERY_TABLES`:

```yaml
BRIDGE_BIGQUERY_TABLES: "YOUR_PROJECT_ID.transportation.bridge_data"
BRIDGE_BIGQUERY_TABLE: "YOUR_PROJECT_ID.transportation.bridge_data"
```

## Local Run

```powershell
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Check:

```powershell
curl.exe http://localhost:8000/.well-known/agent-card.json
```

## Google Maps Secret

Create or update the Google Maps API key secret. The key must allow the Maps
Embed API:

```powershell
gcloud services enable secretmanager.googleapis.com maps-embed-backend.googleapis.com --project YOUR_PROJECT_ID

.\scripts\set_maps_secret.ps1 `
  -ProjectId YOUR_PROJECT_ID `
  -MapsApiKey "YOUR_MAPS_API_KEY"
```

For production, restrict the browser key by HTTP referrer to the deployed map
agent Cloud Run domain.

## Deploy

```powershell
.\scripts\deploy_cloud_run.ps1 `
  -ProjectId YOUR_PROJECT_ID `
  -Region us-central1 `
  -ServiceName ge-map-a2a-agent `
  -Model gemini-3.5-flash
```

After deployment, copy the map Cloud Run URL into:

```text
router-agent/cloudrun-env.yaml
```

## Test Questions

```text
Show bridges in county 001 on a map.
Find bridge structure 1234567.
Show recent crashes in Franklin County on a map.
Show traffic locations near route 23.
Show road assets around bridge 1234567.
```

## Key Files

- `app/main.py`: A2A Starlette application and `/maps/embed` compatibility proxy.
- `app/agent.py`: ADK transportation map agent and agent card.
- `app/agent_executor.py`: Converts ADK events into A2A/A2UI responses.
- `app/bridge_tools.py`: Schema-aware BigQuery map search tool.
- `app/bridge_ui.py`: A2UI map payload helpers.
- `app/catalog_schemas/`: A2UI catalog schemas used by Gemini Enterprise.
- `scripts/deploy_cloud_run.ps1`: Windows Cloud Run deployment.
