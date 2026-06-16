# Data Agent

Cloud Run service for transportation data questions.

It handles:

- BigQuery table counts, schemas, previews, and read-only SQL
- Cloud Storage object listing
- Text and PDF extraction from the configured bucket

Deploy from this folder:

```powershell
Copy-Item cloudrun-env.example.yaml cloudrun-env.yaml
notepad cloudrun-env.yaml

gcloud run deploy ge-data-a2a-agent `
  --source . `
  --region us-central1 `
  --project us-con-gcp-sbx-dep0049-081624 `
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
