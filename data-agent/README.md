# Data Agent

Cloud Run service for transportation data questions.

It handles:

- BigQuery table counts, schemas, previews, and read-only SQL
- Cloud Storage object listing
- Text and PDF extraction from the configured bucket
- A2UI table rendering for BigQuery result rows in Gemini Enterprise

For table-shaped BigQuery results, `run_bigquery_select` returns raw `rows`, a
Markdown fallback, and an A2UI table payload when Gemini Enterprise activates
A2UI. The A2UI path is preferred because it renders as interactive content and
does not depend on Gemini consistently formatting Markdown tables.

Recommended Gemini model settings:

```yaml
GOOGLE_CLOUD_LOCATION: "global"
AGENT_MODEL: "gemini-3.5-flash"
```

Cloud Run can still deploy in `us-central1`. The model location is separate
from the Cloud Run service region.

Deploy from this folder:

```powershell
Copy-Item cloudrun-env.example.yaml cloudrun-env.yaml
notepad cloudrun-env.yaml

gcloud run deploy ge-data-a2a-agent `
  --source . `
  --region us-central1 `
  --project YOUR_PROJECT_ID `
  --allow-unauthenticated `
  --env-vars-file cloudrun-env.yaml
```

After deploy, update `A2A_PUBLIC_URL` in `cloudrun-env.yaml` with the Cloud Run
URL and redeploy so the public agent card is correct.

Health checks:

```powershell
curl.exe https://YOUR-DATA-AGENT-URL/healthz
curl.exe https://YOUR-DATA-AGENT-URL/.well-known/agent-card.json
```
