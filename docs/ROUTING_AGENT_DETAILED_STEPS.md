# Routing Agent Detailed Step Guide

## 1. Purpose

The routing agent is the front-door A2A agent for Gemini Enterprise. Gemini
Enterprise imports and talks to the router only. The router decides whether a
user request should go to the data agent or the map agent, then forwards the
same A2A JSON request to the selected child Cloud Run service.

```text
Gemini Enterprise
        |
        v
router-agent Cloud Run
        |
        |-- data-agent Cloud Run
        |   BigQuery + Cloud Storage + PDF/manual answers
        |
        |-- map-agent Cloud Run
            Bridge BigQuery + A2UI Google Maps display
```

## 2. Why Use A Router Agent

Use the router because it keeps the Gemini Enterprise setup simple while the
backend stays modular.

- Gemini Enterprise registers one Agent Card instead of multiple specialist
  agents.
- The data and map agents can scale independently.
- Each specialist agent can have its own service account, IAM permissions, and
  deployment cycle.
- Logs are easier to inspect because router, data, and map activity are
  separated by Cloud Run service.
- New specialist agents can be added later without changing the Gemini
  Enterprise user experience.

## 3. Repository Location

The router lives in:

```text
router-agent/
```

Important files:

```text
router-agent/orchestrator_router/app.py
router-agent/orchestrator_router/card.py
router-agent/orchestrator_router/config.py
router-agent/orchestrator_router/routing.py
router-agent/cloudrun-env.example.yaml
router-agent/Dockerfile
router-agent/tests/test_router.py
```

## 4. Router File Responsibilities

### 4.1 `app.py`

`app.py` creates the Starlette web application that Cloud Run serves.

It provides:

- `GET /healthz`
- `GET /.well-known/agent-card.json`
- `GET /.well-known/agent.json`
- `POST /`

The `POST /` route receives the Gemini Enterprise A2A request, extracts the
user text, chooses a target child agent, forwards the JSON payload, then returns
the child response back to Gemini Enterprise.

### 4.2 `card.py`

`card.py` builds the router Agent Card JSON. This is the JSON that Gemini
Enterprise imports.

The Agent Card must include:

```json
{
  "protocolVersion": "0.3.0",
  "name": "Transportation Orchestrator Agent",
  "url": "https://YOUR-ROUTER-URL",
  "version": "0.1.0",
  "capabilities": {
    "streaming": true
  }
}
```

The `protocolVersion` field is required by Gemini Enterprise. If it is missing,
the Gemini Enterprise import screen shows:

```text
Missing required field: "protocolVersion"
```

### 4.3 `config.py`

`config.py` reads environment variables used by the router.

Main values:

```text
GOOGLE_CLOUD_PROJECT
GOOGLE_CLOUD_LOCATION
GOOGLE_GENAI_USE_VERTEXAI
ROUTER_MODEL
ROUTER_NAME
ROUTER_PUBLIC_URL
DATA_AGENT_URL
MAP_AGENT_URL
ROUTER_DEFAULT_AGENT
ROUTER_CLASSIFIER_MIN_CONFIDENCE
ROUTER_REQUEST_TIMEOUT_SECONDS
ROUTER_USE_ID_TOKEN
PORT
```

### 4.4 `routing.py`

`routing.py` extracts user text from incoming A2A JSON-RPC payloads.

### 4.5 `classifier.py`

`classifier.py` uses Gemini to classify the user request into one of the
allowed child agents. It replaces deterministic keyword routing.

The classifier prompt allows only these routes:

```text
data
map
```

The model must return strict JSON:

```json
{
  "route": "data",
  "confidence": 0.93,
  "reason": "The request asks for a BigQuery table count."
}
```

The router validates that JSON before forwarding the request. If the model
returns invalid JSON, an unknown route, or low confidence, the router falls back
to `ROUTER_DEFAULT_AGENT`.

Examples routed to the data agent:

```text
How many bridge records are in the bridge table?
Search the bridge inspection PDF manual for inspection responsibility.
Show crash counts by severity for the latest year.
Describe the schema for bridge, crash, road, traffic, and eilis.
```

Examples routed to the map agent:

```text
Show bridges in county 001 on a map.
Find bridge structure 1234567.
Display bridges crossing a creek.
Where is this bridge located?
```

## 5. Environment Configuration

Create the router environment file:

```powershell
cd router-agent
Copy-Item cloudrun-env.example.yaml cloudrun-env.yaml
notepad cloudrun-env.yaml
```

Example `cloudrun-env.yaml`:

```yaml
GOOGLE_CLOUD_PROJECT: "us-con-gcp-sbx-dep0049-081624"
GOOGLE_CLOUD_LOCATION: "global"
GOOGLE_GENAI_USE_VERTEXAI: "true"
ROUTER_MODEL: "gemini-3.5-flash"
ROUTER_NAME: "Transportation Orchestrator Agent"
ROUTER_PUBLIC_URL: "https://YOUR-ROUTER-URL"
DATA_AGENT_URL: "https://YOUR-DATA-AGENT-URL"
MAP_AGENT_URL: "https://YOUR-MAP-AGENT-URL"
ROUTER_DEFAULT_AGENT: "data"
ROUTER_CLASSIFIER_MIN_CONFIDENCE: "0.65"
ROUTER_REQUEST_TIMEOUT_SECONDS: "120"
ROUTER_USE_ID_TOKEN: "false"
```

Use empty `ROUTER_PUBLIC_URL` for the first deployment if you do not yet know
the router Cloud Run URL. After the first deployment, copy the Cloud Run URL
into `ROUTER_PUBLIC_URL` and redeploy.

## 6. Deploy Order

Deploy the three Cloud Run services in this order:

1. Deploy `data-agent`.
2. Deploy `map-agent`.
3. Deploy `router-agent`.
4. Register only the router Agent Card in Gemini Enterprise.

The router needs the data and map URLs before it can route correctly.

## 7. Deploy The Router Agent

From Windows PowerShell:

```powershell
cd router-agent

gcloud run deploy ge-transport-router-agent `
  --source . `
  --region us-central1 `
  --project us-con-gcp-sbx-dep0049-081624 `
  --allow-unauthenticated `
  --env-vars-file cloudrun-env.yaml
```

After deployment, get the router URL:

```powershell
gcloud run services describe ge-transport-router-agent `
  --region us-central1 `
  --project us-con-gcp-sbx-dep0049-081624 `
  --format="value(status.url)"
```

Update `ROUTER_PUBLIC_URL` in `cloudrun-env.yaml`, then redeploy the router.

## 8. Import Into Gemini Enterprise

Open the router Agent Card URL:

```text
https://YOUR-ROUTER-URL/.well-known/agent-card.json
```

Copy the full JSON and paste it into the Gemini Enterprise Add Agent import
screen.

Verify the JSON includes:

```json
{
  "protocolVersion": "0.3.0"
}
```

After previewing the agent details, continue to the authorization step.

## 9. Request Flow

When a user asks a question in Gemini Enterprise:

1. Gemini Enterprise sends the A2A request to the router Cloud Run URL.
2. Router reads the request JSON.
3. Router extracts text from nested A2A message parts.
4. Router sends the text to Gemini using `ROUTER_MODEL`.
5. Gemini returns strict JSON with `route`, `confidence`, and `reason`.
6. Router validates the JSON against the route allowlist.
7. Router picks either `data` or `map`.
8. Router forwards the original request JSON to the selected child agent.
9. Child agent returns its A2A response.
10. Router passes the child response back to Gemini Enterprise.

The map agent response can contain A2UI parts. The router does not rewrite those
parts; it passes the child response through so Gemini Enterprise can render the
map.

## 10. Routing Logic

Routing is no longer based on static keyword lists. The Gemini classifier reads
the full user request and chooses one route from an allowlist.

Classifier route definitions:

```text
data:
  BigQuery analytics, Cloud Storage files, PDF/manual questions, table counts,
  schemas, columns, previews, SQL-style questions, crash analysis, road
  analysis, traffic analysis, EILIS questions, summaries, comparisons, and
  document search.

map:
  Bridge location lookup, Google Maps display, A2UI map display, coordinates,
  where-is questions, county/crossing map views, structure/SFN visual lookup,
  and requests where the user wants to see bridges on a map.
```

The code still enforces safety:

```text
Allowed routes: data, map
Minimum confidence: ROUTER_CLASSIFIER_MIN_CONFIDENCE
Fallback route: ROUTER_DEFAULT_AGENT
```

Default route is `data` unless `ROUTER_DEFAULT_AGENT` is changed.

## 11. Local Tests

Run router tests:

```powershell
cd router-agent
python -m unittest discover -s tests
```

Expected result:

```text
Ran 6 tests
OK
```

The tests verify:

- A2A text extraction.
- Classifier JSON parsing.
- Markdown-fenced JSON parsing.
- Confidence clamping.
- Agent Card includes `protocolVersion`.

## 12. Health Checks

Router health endpoint:

```text
https://YOUR-ROUTER-URL/healthz
```

Expected response shape:

```json
{
  "status": "ok",
  "router": "Transportation Orchestrator Agent",
  "data_agent_configured": true,
  "map_agent_configured": true,
  "default_agent": "data"
}
```

Agent Card endpoint:

```text
https://YOUR-ROUTER-URL/.well-known/agent-card.json
```

## 13. Troubleshooting

### Missing `protocolVersion`

Cause: Gemini Enterprise is using an old router Agent Card.

Fix:

1. Confirm `router-agent/orchestrator_router/card.py` contains
   `"protocolVersion": "0.3.0"`.
2. Redeploy `router-agent`.
3. Reopen `/.well-known/agent-card.json`.
4. Paste the latest JSON into Gemini Enterprise.

### Router Sends Everything To Data Agent

Cause: The classifier is failing, returning low confidence, or the router
cannot call Gemini.

Fix:

- Check router Cloud Run logs for classifier errors.
- Confirm `GOOGLE_CLOUD_LOCATION` is `global`.
- Confirm `ROUTER_MODEL` is a valid model ID, such as `gemini-3.5-flash`.
- Confirm the router runtime service account has `roles/aiplatform.user`.
- Lower `ROUTER_CLASSIFIER_MIN_CONFIDENCE` only if logs show useful low-confidence decisions.

### Map Response Does Not Render

Cause: The router should pass through the map agent response unchanged, but the
map agent may not be returning valid A2UI content or may not have the Maps API
key configured.

Fix:

1. Test the map agent directly.
2. Check map-agent Cloud Run logs.
3. Confirm the Maps API key secret exists.
4. Confirm the router `MAP_AGENT_URL` points to the deployed map service.

### Router Cannot Invoke Child Agents

Cause: Data or map Cloud Run service is private and router lacks permission.

Fix:

1. Set `ROUTER_USE_ID_TOKEN: "true"`.
2. Grant the router service account `roles/run.invoker` on the data and map
   Cloud Run services.
3. Redeploy router.

## 14. Adding Another Agent Later

To add a new specialist agent:

1. Create a new folder, for example `report-agent/`.
2. Deploy it as its own Cloud Run service.
3. Add `REPORT_AGENT_URL` to router config.
4. Add the new route to the classifier prompt in `classifier.py`.
5. Add a target branch in `app.py`.
6. Add parser and fallback tests in `router-agent/tests/test_router.py`.
7. Update the router Agent Card skill examples.
8. Redeploy router.

## 15. Best Practice Summary

Use:

```text
One GitHub repo
Three agent folders
Three Cloud Run services
One Gemini Enterprise registration
```

Do not put all agents inside one Cloud Run service for this project. Separate
Cloud Run services give better scaling, logging, deployment safety, and IAM
control.

The router should stay small. It should decide where to send the request, not
do BigQuery queries, parse PDFs, or build maps itself.
