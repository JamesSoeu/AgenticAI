# Transportation Orchestrator Router

The router is a separate Cloud Run service that Gemini Enterprise can register as
the single A2A endpoint. It forwards each A2A request to one specialist agent:

- Data Agent: BigQuery, Cloud Storage, PDF manuals, crash/road/traffic analysis.
- Map Agent: bridge inventory search with A2UI Google Maps display.

The router passes child A2A responses through unchanged so the map agent's A2UI
payload can still render inside Gemini Enterprise.

## Routing Rules

Typical Data Agent prompts:

```text
How many bridge records are in the bridge table?
Search the bridge inspection PDF manuals for inspection responsibility.
Show crash counts by severity for the latest year.
Describe the schemas for bridge, crash, road, traffic, and eilis.
```

Typical Map Agent prompts:

```text
Show bridges in county 001 on a map.
Find bridge structure 1234567 and display it on Google Maps.
Show bridges crossing a creek.
Where is this bridge located?
```

## Windows PowerShell Deploy

Set the two child agent URLs first:

```powershell
$env:GOOGLE_CLOUD_PROJECT="YOUR_PROJECT_ID"
$env:GOOGLE_CLOUD_LOCATION="us-central1"
$env:ROUTER_SERVICE_NAME="ge-transport-router-agent"
$env:ROUTER_SERVICE_ACCOUNT="orchestrator-sa@$($env:GOOGLE_CLOUD_PROJECT).iam.gserviceaccount.com"

$env:DATA_AGENT_URL="https://YOUR-DATA-AGENT-URL.run.app"
$env:MAP_AGENT_URL="https://YOUR-MAP-AGENT-URL"
$env:ROUTER_PUBLIC_URL=""
```

Create a router env file. You can either copy the template and edit it:

```powershell
Copy-Item cloudrun-router-env.example.yaml cloudrun-router-env.yaml
notepad cloudrun-router-env.yaml
```

Or generate it from PowerShell:

```powershell
@"
APP_MODULE: "orchestrator_router.app:app"
ROUTER_NAME: "Transportation Orchestrator Agent"
ROUTER_PUBLIC_URL: "$env:ROUTER_PUBLIC_URL"
DATA_AGENT_URL: "$env:DATA_AGENT_URL"
DATA_AGENT_AUDIENCE: ""
MAP_AGENT_URL: "$env:MAP_AGENT_URL"
MAP_AGENT_AUDIENCE: ""
ROUTER_DEFAULT_AGENT: "data"
ROUTER_REQUEST_TIMEOUT_SECONDS: "120"
ROUTER_USE_ID_TOKEN: "true"
"@ | Set-Content cloudrun-router-env.yaml
```

Deploy the router:

```powershell
gcloud run deploy $env:ROUTER_SERVICE_NAME `
  --source . `
  --region $env:GOOGLE_CLOUD_LOCATION `
  --project $env:GOOGLE_CLOUD_PROJECT `
  --allow-unauthenticated `
  --service-account $env:ROUTER_SERVICE_ACCOUNT `
  --env-vars-file cloudrun-router-env.yaml
```

Get the router URL:

```powershell
gcloud run services describe $env:ROUTER_SERVICE_NAME `
  --region $env:GOOGLE_CLOUD_LOCATION `
  --project $env:GOOGLE_CLOUD_PROJECT `
  --format="value(status.url)"
```

Set `ROUTER_PUBLIC_URL` to that URL in `cloudrun-router-env.yaml`, then redeploy.

Register this router Agent Card with Gemini Enterprise:

```text
https://YOUR-ROUTER-URL/.well-known/agent-card.json
```

## Private Child Agents

If the data or map child services are IAM-protected, set:

```yaml
ROUTER_USE_ID_TOKEN: "true"
```

The ID-token audience defaults to each child URL. If a child URL uses a custom
domain, proxy, or path, set `DATA_AGENT_AUDIENCE` and `MAP_AGENT_AUDIENCE` to
the real child Cloud Run service base URLs.

Then grant the router service account `roles/run.invoker` on both child Cloud
Run services:

```powershell
gcloud run services add-iam-policy-binding ge-data-a2a-agent `
  --region $env:GOOGLE_CLOUD_LOCATION `
  --project $env:GOOGLE_CLOUD_PROJECT `
  --member "serviceAccount:$env:ROUTER_SERVICE_ACCOUNT" `
  --role "roles/run.invoker"

gcloud run services add-iam-policy-binding ge-map-a2a-agent `
  --region $env:GOOGLE_CLOUD_LOCATION `
  --project $env:GOOGLE_CLOUD_PROJECT `
  --member "serviceAccount:$env:ROUTER_SERVICE_ACCOUNT" `
  --role "roles/run.invoker"
```
