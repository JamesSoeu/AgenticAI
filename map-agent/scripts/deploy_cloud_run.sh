#!/usr/bin/env bash

set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-gemini-enterprise-bridge-map}"
REGION="${REGION:-us-central1}"
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
MAPS_SECRET="${GOOGLE_MAPS_SECRET_NAME:-google_map_api_key}"
RUNTIME_SA_NAME="${RUNTIME_SA_NAME:-bridge-map-agent-sa}"
MODEL="${MODEL:-gemini-3.5-flash}"
MAP_BIGQUERY_TABLES="${MAP_BIGQUERY_TABLES:-${BRIDGE_BIGQUERY_TABLES:-${BRIDGE_BIGQUERY_TABLE:-your-project-id.transportation.bridge_data}}}"
MAP_BIGQUERY_TABLE_ALIASES="${MAP_BIGQUERY_TABLE_ALIASES:-${BRIDGE_BIGQUERY_TABLE_ALIASES:-}}"
MAP_BIGQUERY_MAX_BYTES_BILLED="${MAP_BIGQUERY_MAX_BYTES_BILLED:-1000000000}"
MAP_DEFAULT_LIMIT="${MAP_DEFAULT_LIMIT:-10}"
MAP_MAX_LIMIT="${MAP_MAX_LIMIT:-50}"
FIRST_MAP_BIGQUERY_TABLE="${MAP_BIGQUERY_TABLES%%,*}"
MAP_DATA_PROJECT="${MAP_DATA_PROJECT:-${BRIDGE_DATA_PROJECT:-${FIRST_MAP_BIGQUERY_TABLE%%.*}}}"
BIGQUERY_LOCATION="${BIGQUERY_LOCATION:-}"

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "Set PROJECT_ID or run: gcloud config set project YOUR_PROJECT_ID" >&2
  exit 1
fi

for command in gcloud; do
  command -v "${command}" >/dev/null || {
    echo "Missing required command: ${command}" >&2
    exit 1
  }
done

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
RUNTIME_SA="${RUNTIME_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
DISCOVERY_ENGINE_SA="service-${PROJECT_NUMBER}@gcp-sa-discoveryengine.iam.gserviceaccount.com"

echo "Enabling required Google Cloud APIs..."
gcloud services enable \
  aiplatform.googleapis.com \
  bigquery.googleapis.com \
  cloudbuild.googleapis.com \
  discoveryengine.googleapis.com \
  iam.googleapis.com \
  maps-embed-backend.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com \
  serviceusage.googleapis.com \
  --project "${PROJECT_ID}"

echo "Ensuring the runtime service account exists..."
if ! gcloud iam service-accounts describe "${RUNTIME_SA}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${RUNTIME_SA_NAME}" \
    --display-name "Transportation Map Agent Runtime" \
    --project "${PROJECT_ID}"
fi

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member "serviceAccount:${RUNTIME_SA}" \
  --role "roles/aiplatform.user" \
  --condition=None \
  --quiet >/dev/null

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member "serviceAccount:${RUNTIME_SA}" \
  --role "roles/bigquery.jobUser" \
  --condition=None \
  --quiet >/dev/null

echo "Granting read access to map data project ${MAP_DATA_PROJECT}..."
gcloud projects add-iam-policy-binding "${MAP_DATA_PROJECT}" \
  --member "serviceAccount:${RUNTIME_SA}" \
  --role "roles/bigquery.dataViewer" \
  --condition=None \
  --quiet >/dev/null

if ! gcloud secrets describe "${MAPS_SECRET}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  echo "Missing Secret Manager secret: ${MAPS_SECRET}" >&2
  echo "Create it with:" >&2
  echo "  printf '%s' \"YOUR_MAPS_API_KEY\" | gcloud secrets create ${MAPS_SECRET} --data-file=- --replication-policy=automatic --project ${PROJECT_ID}" >&2
  exit 1
fi

gcloud secrets add-iam-policy-binding "${MAPS_SECRET}" \
  --member "serviceAccount:${RUNTIME_SA}" \
  --role "roles/secretmanager.secretAccessor" \
  --project "${PROJECT_ID}" \
  --quiet >/dev/null

echo "Deploying ${SERVICE_NAME} to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --service-account "${RUNTIME_SA}" \
  --memory 2Gi \
  --no-allow-unauthenticated \
  --no-cpu-throttling \
  --set-secrets "GOOGLE_MAPS_API_KEY=${MAPS_SECRET}:latest" \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=global,GOOGLE_GENAI_USE_VERTEXAI=true,MODEL=${MODEL},MAP_BIGQUERY_TABLES=${MAP_BIGQUERY_TABLES},MAP_BIGQUERY_TABLE_ALIASES=${MAP_BIGQUERY_TABLE_ALIASES},MAP_BIGQUERY_MAX_BYTES_BILLED=${MAP_BIGQUERY_MAX_BYTES_BILLED},MAP_DEFAULT_LIMIT=${MAP_DEFAULT_LIMIT},MAP_MAX_LIMIT=${MAP_MAX_LIMIT},BIGQUERY_JOB_PROJECT=${PROJECT_ID},BIGQUERY_LOCATION=${BIGQUERY_LOCATION}" \
  --quiet

SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --format='value(status.url)')"

echo "Updating the agent card URL to ${SERVICE_URL}..."
gcloud run services update "${SERVICE_NAME}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --update-env-vars "AGENT_URL=${SERVICE_URL},APP_URL=${SERVICE_URL}" \
  --quiet >/dev/null

echo "Granting Gemini Enterprise permission to invoke the private service..."
gcloud beta services identity create \
  --service discoveryengine.googleapis.com \
  --project "${PROJECT_ID}" >/dev/null

gcloud run services add-iam-policy-binding "${SERVICE_NAME}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --member "serviceAccount:${DISCOVERY_ENGINE_SA}" \
  --role "roles/run.invoker" \
  --quiet >/dev/null

echo
echo "Cloud Run deployment is ready."
echo "Service URL: ${SERVICE_URL}"
echo "Agent card:  ${SERVICE_URL}/.well-known/agent-card.json"
echo
echo "Next:"
echo "  make verify-deployment"
echo "  make register-gemini-enterprise"
