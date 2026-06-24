# Transportation Multi-Agent Repository Guide

This repository is organized as one codebase with three independently deployed
Cloud Run services.

```text
transportation-agents/
  data-agent/      BigQuery, Cloud Storage, and PDF/manual question answering
  map-agent/       Bridge inventory search with A2UI Google Maps display
  router-agent/    Public Gemini Enterprise A2A router/orchestrator
  docs/            Team, deployment, and architecture notes
```

Gemini Enterprise should register only the router agent:

```text
https://YOUR-ROUTER-URL/.well-known/agent-card.json
```

The router uses a Gemini LLM classifier to choose the correct specialist
service, then forwards the original A2A request to that service.

The router Agent Card must include the A2A `protocolVersion` field. If Gemini
Enterprise says `Missing required field: "protocolVersion"`, redeploy
`router-agent/` and import the latest router card.

The recommended model configuration for all three services is:

```text
Cloud Run region: us-central1
Gemini model location: global
Router classifier model: gemini-3.5-flash
Data agent model: gemini-3.5-flash
Map agent model: gemini-3.5-flash
```

## Recommended Cloud Run Services

Use one Google Cloud project and three separate Cloud Run services:

```text
ge-transport-router-agent
ge-data-a2a-agent
ge-map-a2a-agent
```

This gives clean scaling, deployment, logs, and ownership while keeping the code
easy for a small team to maintain.

## Team Workflow For Two Developers

Use a Git repository. For a company laptop and Cloud Run deployment, the best
choices are usually:

- GitHub Enterprise: best if your company already uses GitHub.
- GitLab: good if your company prefers built-in DevOps controls.
- Azure DevOps Repos: good if your company is mostly Microsoft/Azure/Entra.
- Google Cloud Source Repositories is not recommended for new projects because
  it has been deprecated for new customers.

For two developers, start simple:

```text
main       stable branch
dev        optional integration branch
feature/*  one branch per change
```

Each developer clones the same repo, works in one agent folder, runs local tests,
then opens a pull request.

## Ownership

Suggested ownership:

```text
Developer 1: data-agent/
Developer 2: map-agent/
Shared:     router-agent/ and docs/
```

The router is intentionally small. Changes there should be reviewed by both
developers because it controls Gemini Enterprise routing.

## Deploy Order

Deploy in this order:

1. Data agent
2. Map agent
3. Router agent

After deploying data and map agents, put their Cloud Run URLs into:

```text
router-agent/cloudrun-env.yaml
```

Then deploy the router and register the router agent card in Gemini Enterprise.

## Windows PowerShell Commands

From the repository root:

```powershell
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

Deploy the data agent:

```powershell
Push-Location data-agent
Copy-Item cloudrun-env.example.yaml cloudrun-env.yaml
notepad cloudrun-env.yaml
gcloud run deploy ge-data-a2a-agent `
  --source . `
  --region us-central1 `
  --project YOUR_PROJECT_ID `
  --allow-unauthenticated `
  --env-vars-file cloudrun-env.yaml
Pop-Location
```

Deploy the map agent:

```powershell
Push-Location map-agent
gcloud services enable secretmanager.googleapis.com maps-embed-backend.googleapis.com --project YOUR_PROJECT_ID
.\scripts\set_maps_secret.ps1 -ProjectId YOUR_PROJECT_ID -MapsApiKey "YOUR_MAPS_API_KEY"
.\scripts\deploy_cloud_run.ps1 `
  -ProjectId YOUR_PROJECT_ID `
  -Region us-central1 `
  -ServiceName ge-map-a2a-agent `
  -Model gemini-3.5-flash
Pop-Location
```

Deploy the router:

```powershell
Push-Location router-agent
Copy-Item cloudrun-env.example.yaml cloudrun-env.yaml
notepad cloudrun-env.yaml
gcloud run deploy ge-transport-router-agent `
  --source . `
  --region us-central1 `
  --project YOUR_PROJECT_ID `
  --allow-unauthenticated `
  --env-vars-file cloudrun-env.yaml
Pop-Location
```

Before deploying the router, confirm `router-agent/cloudrun-env.yaml` includes:

```yaml
GOOGLE_CLOUD_PROJECT: "YOUR_PROJECT_ID"
GOOGLE_CLOUD_LOCATION: "global"
GOOGLE_GENAI_USE_VERTEXAI: "true"
ROUTER_MODEL: "gemini-3.5-flash"
ROUTER_CLASSIFIER_MIN_CONFIDENCE: "0.65"
```

After the router deploys, get its URL:

```powershell
gcloud run services describe ge-transport-router-agent `
  --region us-central1 `
  --project YOUR_PROJECT_ID `
  --format="value(status.url)"
```

Update `ROUTER_PUBLIC_URL` in `router-agent/cloudrun-env.yaml`, redeploy the
router, then register:

```text
https://YOUR-ROUTER-URL/.well-known/agent-card.json
```

The imported JSON should include:

```json
{
  "protocolVersion": "0.3.0"
}
```

## Private Versus Public Cloud Run

For a first end-to-end test, public unauthenticated endpoints are easier.

For production, make the data and map agents private, keep the router public to
Gemini Enterprise if required, then set:

```yaml
ROUTER_USE_ID_TOKEN: "true"
```

Grant the router service account:

```text
roles/run.invoker
```

on both child Cloud Run services.
