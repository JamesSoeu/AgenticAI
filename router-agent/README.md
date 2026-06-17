# Router Agent

Cloud Run service registered with Gemini Enterprise.

It routes user requests to:

- `DATA_AGENT_URL` for BigQuery, Cloud Storage, PDF, crash, road, and traffic questions.
- `MAP_AGENT_URL` for bridge lookup and Google Maps/A2UI display questions.

Deploy from this folder after the data and map agents are deployed:

```powershell
Copy-Item cloudrun-env.example.yaml cloudrun-env.yaml
notepad cloudrun-env.yaml

gcloud run deploy ge-transport-router-agent `
  --source . `
  --region us-central1 `
  --project us-con-gcp-sbx-dep0049-081624 `
  --allow-unauthenticated `
  --env-vars-file cloudrun-env.yaml
```

After deploy, update `ROUTER_PUBLIC_URL` in `cloudrun-env.yaml` with the Cloud
Run URL and redeploy.

Register this with Gemini Enterprise:

```text
https://YOUR-ROUTER-URL/.well-known/agent-card.json
```

The router Agent Card includes the A2A `protocolVersion` field required by the
Gemini Enterprise import screen.

Test prompts:

```text
How many bridge records are in the bridge table?
Search the bridge inspection PDF manual for inspection responsibility.
Show bridges in county 001 on a Google map.
Find bridge structure 1234567.
Show crash counts by severity for the latest year.
```
