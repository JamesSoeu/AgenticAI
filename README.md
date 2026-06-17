# Transportation Multi-Agent Monorepo

This repository contains three separate deployable A2A agents for Gemini
Enterprise.

```text
data-agent/      BigQuery, Cloud Storage, and PDF/manual answers
map-agent/       BigQuery bridge search plus A2UI Google Maps responses
router-agent/    Orchestrator/router registered with Gemini Enterprise
docs/            Team workflow and end-to-end deployment guide
```

Production structure:

```text
One Git repository
One Google Cloud project
Three separate Cloud Run services
One Gemini Enterprise registration: router-agent
```

Gemini Enterprise should register only:

```text
https://YOUR-ROUTER-URL/.well-known/agent-card.json
```

The router forwards requests to either the data agent or map agent.

## Start Here

Read:

```text
docs/TEAM_AND_REPO_GUIDE.md
```

Per-agent docs:

```text
data-agent/README.md
map-agent/README.md
router-agent/README.md
```

## Deploy Order

1. Deploy `data-agent/`.
2. Deploy `map-agent/`.
3. Put both child Cloud Run URLs into `router-agent/cloudrun-env.yaml`.
4. Deploy `router-agent/`.
5. Register the router agent card with Gemini Enterprise.

## Windows PowerShell Summary

Deploy data:

```powershell
Push-Location data-agent
Copy-Item cloudrun-env.example.yaml cloudrun-env.yaml
notepad cloudrun-env.yaml
gcloud run deploy ge-data-a2a-agent `
  --source . `
  --region us-central1 `
  --project us-con-gcp-sbx-dep0049-081624 `
  --allow-unauthenticated `
  --env-vars-file cloudrun-env.yaml
Pop-Location
```

Deploy map:

```powershell
Push-Location map-agent
.\scripts\set_maps_secret.ps1 `
  -ProjectId us-con-gcp-sbx-dep0049-081624 `
  -MapsApiKey "YOUR_MAPS_API_KEY"
.\scripts\deploy_cloud_run.ps1 `
  -ProjectId us-con-gcp-sbx-dep0049-081624 `
  -Region us-central1 `
  -ServiceName ge-map-a2a-agent `
  -Model gemini-3.5-flash
Pop-Location
```

Deploy router:

```powershell
Push-Location router-agent
Copy-Item cloudrun-env.example.yaml cloudrun-env.yaml
notepad cloudrun-env.yaml
gcloud run deploy ge-transport-router-agent `
  --source . `
  --region us-central1 `
  --project us-con-gcp-sbx-dep0049-081624 `
  --allow-unauthenticated `
  --env-vars-file cloudrun-env.yaml
Pop-Location
```

## Repository Notes

The map agent is backend-only in this version. The previous local frontend code
was removed; Gemini Enterprise renders the A2UI map response.
