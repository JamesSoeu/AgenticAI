
-include .env
UV := $(shell command -v uv 2>/dev/null || printf '%s' '$(HOME)/.local/bin/uv')
UVX := $(shell command -v uvx 2>/dev/null || printf '%s' '$(HOME)/.local/bin/uvx')

install:
	@test -x "$(UV)" || { echo "uv is not installed. Installing uv..."; curl -LsSf https://astral.sh/uv/0.8.13/install.sh | sh; }
	$(UV) sync

playground:
	$(UV) run adk web . --port 8501 --reload_agents

local-backend:
	$(UV) run uvicorn app.main:app --host 0.0.0.0 --port $(or $(PORT),8000) --reload

local-docker: local-docker-build local-docker-run

local-docker-build:
	docker build -t gemini-enterprise-bridge-map .

local-docker-run:
	docker run --rm -p $(or $(PORT),8080):8080 \
		-e GOOGLE_CLOUD_PROJECT=$$(gcloud config get-value project 2>/dev/null) \
		-e GOOGLE_CLOUD_LOCATION=global \
		-e GOOGLE_GENAI_USE_VERTEXAI=true \
		-e GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/adc.json \
		-v $$HOME/.config/gcloud/application_default_credentials.json:/tmp/keys/adc.json:ro \
		gemini-enterprise-bridge-map

deploy:
	bash scripts/deploy_cloud_run.sh

verify-deployment:
	bash scripts/verify_deployment.sh

test:
	$(UV) sync --dev
	$(UV) run pytest tests/unit && $(UV) run pytest tests/integration

test-remote:
	$(UV) sync --dev
	@PROJECT_ID=$$(gcloud config get-value project 2>/dev/null) && \
	SERVICE_URL=$$(gcloud run services describe $${SERVICE_NAME:-gemini-enterprise-bridge-map} --region $${REGION:-us-central1} --project $$PROJECT_ID --format="value(status.url)") && \
	AGENT_URL=$${AGENT_URL:-$$SERVICE_URL} $(UV) run pytest tests/integration/remote_e2e_test.py -v

lint:
	$(UV) sync --dev --extra lint
	$(UV) run codespell
	$(UV) run ruff check . --diff
	$(UV) run ruff format . --check --diff
	$(UV) run ty check .

register-gemini-enterprise:
	@PROJECT_ID=$$(gcloud config get-value project 2>/dev/null) && \
	PROJECT_NUMBER=$$(gcloud projects describe $$PROJECT_ID --format="value(projectNumber)" 2>/dev/null) && \
	SERVICE_URL=$$(gcloud run services describe $${SERVICE_NAME:-gemini-enterprise-bridge-map} --region $${REGION:-us-central1} --project $$PROJECT_ID --format="value(status.url)") && \
	$(UVX) agent-starter-pack@0.41.3 register-gemini-enterprise \
		--agent-card-url="$$SERVICE_URL/.well-known/agent-card.json" \
		--deployment-target="cloud_run" \
		--registration-type="a2a" \
		--project-number="$$PROJECT_NUMBER"

.PHONY: install playground local-backend \
	local-docker local-docker-build local-docker-run deploy verify-deployment test \
	test-remote lint register-gemini-enterprise
