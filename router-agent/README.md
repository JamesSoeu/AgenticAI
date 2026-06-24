# Router Agent

Cloud Run service registered with Gemini Enterprise.

It routes user requests to:

- `DATA_AGENT_URL` for BigQuery, Cloud Storage, PDF, crash, road, and traffic questions.
- `MAP_AGENT_URL` for bridge lookup and Google Maps/A2UI display questions.

Routing is handled by a Gemini LLM classifier, not static keyword rules. The
router asks `ROUTER_MODEL` to return strict JSON with one allowed route:

```json
{
  "route": "data",
  "confidence": 0.93,
  "reason": "The user asked for a table count."
}
```

The code validates the result against an allowlist, so the model can choose
only `data` or `map`.

Deploy from this folder after the data and map agents are deployed:

```powershell
Copy-Item cloudrun-env.example.yaml cloudrun-env.yaml
notepad cloudrun-env.yaml

gcloud run deploy ge-transport-router-agent `
  --source . `
  --region us-central1 `
  --project YOUR_PROJECT_ID `
  --allow-unauthenticated `
  --env-vars-file cloudrun-env.yaml
```

After deploy, update `ROUTER_PUBLIC_URL` in `cloudrun-env.yaml` with the Cloud
Run URL and redeploy.

## Private child agent authentication

The router supports calling data and map agents deployed with Cloud Run
authentication required. Set this in `cloudrun-env.yaml`:

```yaml
ROUTER_USE_ID_TOKEN: "true"
DATA_AGENT_URL: "https://YOUR-DATA-AGENT-URL.run.app"
MAP_AGENT_URL: "https://YOUR-MAP-AGENT-URL.run.app"
```

When `ROUTER_USE_ID_TOKEN` is true, the router fetches a Google-signed ID token
from the Cloud Run metadata credentials and sends it to the selected child agent:

```text
Authorization: Bearer <ID_TOKEN>
```

The token audience defaults to `DATA_AGENT_URL` or `MAP_AGENT_URL`. If either
URL points through a proxy, path, gateway, or custom domain, set the audience to
the actual target Cloud Run service base URL:

```yaml
DATA_AGENT_AUDIENCE: "https://YOUR-DATA-AGENT-URL.run.app"
MAP_AGENT_AUDIENCE: "https://YOUR-MAP-AGENT-URL.run.app"
```

The router Cloud Run service account must have `roles/run.invoker` on each
private child service:

```powershell
gcloud run services add-iam-policy-binding ge-data-a2a-agent `
  --region us-central1 `
  --member "serviceAccount:orchestrator-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" `
  --role "roles/run.invoker"

gcloud run services add-iam-policy-binding ge-map-a2a-agent `
  --region us-central1 `
  --member "serviceAccount:orchestrator-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" `
  --role "roles/run.invoker"
```

Deploy the router with that service account:

```powershell
gcloud run deploy ge-transport-router-agent `
  --source . `
  --region us-central1 `
  --project YOUR_PROJECT_ID `
  --allow-unauthenticated `
  --service-account orchestrator-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com `
  --env-vars-file cloudrun-env.yaml
```

Register this with Gemini Enterprise:

```text
https://YOUR-ROUTER-URL/.well-known/agent-card.json
```

The router Agent Card includes the A2A `protocolVersion` field required by the
Gemini Enterprise import screen.

Important model settings in `cloudrun-env.yaml`:

```yaml
GOOGLE_CLOUD_LOCATION: "global"
ROUTER_MODEL: "gemini-3.5-flash"
ROUTER_CLASSIFIER_MIN_CONFIDENCE: "0.65"
```

Keep Cloud Run deployed in `us-central1`; `GOOGLE_CLOUD_LOCATION` is the Gemini
model endpoint location and should remain `global` for newer Gemini models.

Test prompts:

```text
How many bridge records are in the bridge table?
Search the bridge inspection PDF manual for inspection responsibility.
Show bridges in county 001 on a Google map.
Find bridge structure 1234567.
Show crash counts by severity for the latest year.
```
