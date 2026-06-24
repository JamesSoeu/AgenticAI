# Windows Setup In VS Code

Use these steps on your Windows laptop from the VS Code integrated terminal.

## Prerequisites

Install:

- Python 3.12 from <https://www.python.org/downloads/windows/>
- Google Cloud CLI from <https://cloud.google.com/sdk/docs/install-sdk#windows>
- VS Code Python extension

Confirm the tools:

```powershell
py -3.12 --version
gcloud --version
```

## Open The Project

Copy this project folder to your Windows laptop, then open it in VS Code.

Open a PowerShell terminal in VS Code:

```powershell
code .
```

## Configure Environment

```powershell
Copy-Item .env.example .env
notepad .env
```

Fill in:

- `GOOGLE_CLOUD_PROJECT`
- `GOOGLE_CLOUD_LOCATION`
- `AGENT_MODEL`
- `BIGQUERY_TABLES`
- `BIGQUERY_TABLE_ALIASES`
- `GCS_BUCKET_NAME`
- `GCS_PREFIX`, if needed

The `BIGQUERY_TABLES` value should contain your five BigQuery tables:

```powershell
BIGQUERY_TABLES=your-project-id.transportation.bridge,your-project-id.transportation.crash,your-project-id.transportation.eilis,your-project-id.transportation.road,your-project-id.transportation.traffic
BIGQUERY_TABLE_ALIASES=bridge,crash,eilis,road,traffic
GCS_BUCKET_NAME=YOUR_BUCKET_NAME
```

For Gemini Enterprise A2A, start with this model value:

```powershell
AGENT_MODEL=gemini-2.0-flash
```

Good test questions after deployment:

```text
How many bridge records are available by route?
Show crash counts by severity for the latest year.
Summarize traffic count trends by route or station.
List source files in the YOUR_BUCKET_NAME bucket.
Search the bridge inspection PDF manuals for bridge inspection responsibility and cite the source page.
```

If you maintain `cloudrun-env.yaml` manually, include the PDF settings:

```yaml
GCS_MAX_PDF_BYTES: "25000000"
GCS_MAX_PDF_PAGES: "20"
GCS_MAX_PDF_TEXT_CHARS: "60000"
```

## Install And Run Locally

From VS Code PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\run-local.ps1
```

Check the local service in another terminal:

```powershell
curl.exe http://localhost:8080/healthz
curl.exe http://localhost:8080/.well-known/agent-card.json
```

## Run Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

## Authenticate Google Cloud

```powershell
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

## Deploy To Cloud Run

IAM-protected deployment:

```powershell
.\scripts\deploy-cloud-run.ps1
```

Public endpoint deployment, if your Gemini Enterprise setup requires a public A2A endpoint:

```powershell
.\scripts\deploy-cloud-run.ps1 -AllowUnauthenticated
```

After the first deployment, copy the Cloud Run service URL into `.env`:

```powershell
A2A_PUBLIC_URL=https://YOUR-CLOUD-RUN-URL
```

Then redeploy:

```powershell
.\scripts\deploy-cloud-run.ps1
```

Register either the Cloud Run service URL or:

```text
https://YOUR-CLOUD-RUN-URL/.well-known/agent-card.json
```

with Gemini Enterprise as the A2A agent endpoint.

## Orchestrator Router

If you want Gemini Enterprise to call one front-door agent that routes to both
this data agent and the Google Maps A2UI bridge agent, follow [ROUTER.md](ROUTER.md).
