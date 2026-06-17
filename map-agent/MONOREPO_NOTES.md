# Map Agent In The Monorepo

This folder is copied from the bridge map A2A/A2UI project, with the local
frontend removed. Gemini Enterprise renders the A2UI map response.

It handles:

- Bridge inventory search from BigQuery
- A2UI payload generation
- Google Maps display inside Gemini Enterprise

Deploy from this folder:

```powershell
gcloud services enable secretmanager.googleapis.com maps-embed-backend.googleapis.com --project us-con-gcp-sbx-dep0049-081624

.\scripts\set_maps_secret.ps1 `
  -ProjectId us-con-gcp-sbx-dep0049-081624 `
  -MapsApiKey "YOUR_MAPS_API_KEY"

.\scripts\deploy_cloud_run.ps1 `
  -ProjectId us-con-gcp-sbx-dep0049-081624 `
  -Region us-central1 `
  -ServiceName ge-map-a2a-agent `
  -Model gemini-3.5-flash
```

After deployment, copy the map Cloud Run URL into:

```text
router-agent/cloudrun-env.yaml
```
