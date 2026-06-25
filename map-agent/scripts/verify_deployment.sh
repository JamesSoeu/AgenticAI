#!/usr/bin/env bash

set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-gemini-enterprise-bridge-map}"
REGION="${REGION:-us-central1}"
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"

SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --format='value(status.url)')"
TOKEN="$(gcloud auth print-identity-token)"

CARD="$(curl --fail --silent --show-error \
  -H "Authorization: Bearer ${TOKEN}" \
  "${SERVICE_URL}/.well-known/agent-card.json")"

python3 -c '
import json
import sys

card = json.load(sys.stdin)
assert card["name"] == "Transportation Map Agent", card["name"]
assert any(skill["id"] == "search_transportation_map_records" for skill in card["skills"])
uris = {extension["uri"] for extension in card["capabilities"]["extensions"]}
assert "https://a2ui.org/a2a-extension/a2ui/v0.8" in uris
print("Agent card OK:", card["name"])
' <<<"${CARD}"

MAP_STATUS="$(curl --silent --output /dev/null --write-out '%{http_code}' \
  -H "Authorization: Bearer ${TOKEN}" \
  "${SERVICE_URL}/maps/embed?mode=place&q=38.9351%2C-83.4596")"

if [[ "${MAP_STATUS}" != "307" && "${MAP_STATUS}" != "302" ]]; then
  echo "Expected the Maps proxy to redirect, got HTTP ${MAP_STATUS}" >&2
  exit 1
fi

echo "Maps proxy OK: HTTP ${MAP_STATUS}"
echo "Deployment verification passed: ${SERVICE_URL}"
