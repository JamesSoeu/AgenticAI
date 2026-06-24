# Map Agent

Backend-only A2A/A2UI Cloud Run service for bridge inventory map questions.

It handles:

- Bridge search from BigQuery
- A2UI response creation for Gemini Enterprise
- WebFrameUrl map responses for Gemini Enterprise
- Cloud Run-hosted interactive Google Maps JavaScript page with bridge pins,
  not directions routes
- Google Maps Embed URL proxying through `/maps/embed` for compatibility links

There is no separate frontend folder in this monorepo version. Gemini Enterprise
is the client that renders the A2UI `WebFrameUrl` response. Multiple bridge
results are displayed as pins on one map so the user can inspect assets without
seeing a route, origin, destination, or waypoint list.

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
BRIDGE_BIGQUERY_TABLE: "your-project-id.transportation.bridge_data"
BIGQUERY_JOB_PROJECT: "YOUR_PROJECT_ID"
GOOGLE_MAPS_SECRET_NAME: "google_map_api_key"
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
JavaScript API for `/bridge-map` and Maps Embed API for the compatibility
`/maps/embed` endpoint:

```powershell
gcloud services enable secretmanager.googleapis.com maps-backend.googleapis.com maps-embed-backend.googleapis.com --project YOUR_PROJECT_ID

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
Show bridges crossing a creek.
Where is this bridge located?
```

## Key Files

- `app/main.py`: A2A Starlette application, `/bridge-map` pin map page, and
  `/maps/embed` compatibility proxy.
- `app/agent.py`: ADK bridge inventory agent and agent card.
- `app/agent_executor.py`: Converts ADK events into A2A/A2UI responses.
- `app/bridge_tools.py`: BigQuery bridge search tool.
- `app/bridge_ui.py`: A2UI map payload helpers.
- `app/catalog_schemas/`: A2UI catalog schemas used by Gemini Enterprise.
- `scripts/deploy_cloud_run.ps1`: Windows Cloud Run deployment.
