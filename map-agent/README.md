# Map Agent

Backend-only A2A/A2UI Cloud Run service for bridge inventory map questions.

It handles:

- Bridge search from BigQuery
- A2UI response creation for Gemini Enterprise
- Google Maps Embed URL proxying through `/maps/embed`

There is no separate frontend folder in this monorepo version. Gemini Enterprise
is the client that renders the A2UI map response.

## Configure

Copy and edit the environment template:

```powershell
Copy-Item cloudrun-env.example.yaml cloudrun-env.yaml
notepad cloudrun-env.yaml
```

Important values:

```yaml
GOOGLE_CLOUD_PROJECT: "us-con-gcp-sbx-dep0049-081624"
GOOGLE_CLOUD_LOCATION: "global"
MODEL: "gemini-2.5-flash"
BRIDGE_BIGQUERY_TABLE: "us-con-gcp-sbx-dep0049-081624.bridge_inventory.bridge_data"
BIGQUERY_JOB_PROJECT: "us-con-gcp-sbx-dep0049-081624"
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

Create or update the Maps Embed API key secret:

```powershell
gcloud services enable secretmanager.googleapis.com maps-embed-backend.googleapis.com --project us-con-gcp-sbx-dep0049-081624

.\scripts\set_maps_secret.ps1 `
  -ProjectId us-con-gcp-sbx-dep0049-081624 `
  -MapsApiKey "YOUR_MAPS_API_KEY"
```

## Deploy

```powershell
.\scripts\deploy_cloud_run.ps1 `
  -ProjectId us-con-gcp-sbx-dep0049-081624 `
  -Region us-central1 `
  -ServiceName ge-map-a2a-agent `
  -Model gemini-2.5-flash
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

- `app/main.py`: A2A Starlette application and `/maps/embed` proxy.
- `app/agent.py`: ADK bridge inventory agent and agent card.
- `app/agent_executor.py`: Converts ADK events into A2A/A2UI responses.
- `app/bridge_tools.py`: BigQuery bridge search tool.
- `app/bridge_ui.py`: A2UI map payload helpers.
- `app/catalog_schemas/`: A2UI catalog schemas used by Gemini Enterprise.
- `scripts/deploy_cloud_run.ps1`: Windows Cloud Run deployment.
