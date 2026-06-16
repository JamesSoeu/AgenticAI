"""Deployment contract checks for Cloud Run and Gemini Enterprise."""

from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_cloud_run_deploy_binds_maps_secret_and_gemini_enterprise_invoker():
    script = (ROOT / "scripts" / "deploy_cloud_run.sh").read_text()

    assert "--no-allow-unauthenticated" in script
    assert "GOOGLE_MAPS_API_KEY=${MAPS_SECRET}:latest" in script
    assert "gcp-sa-discoveryengine.iam.gserviceaccount.com" in script
    assert 'roles/bigquery.jobUser' in script
    assert 'roles/bigquery.dataViewer' in script
    assert 'BRIDGE_BIGQUERY_TABLE=${BRIDGE_BIGQUERY_TABLE}' in script
    assert 'AGENT_URL=${SERVICE_URL}' in script


def test_docker_context_excludes_local_artifacts():
    dockerignore = (ROOT / ".dockerignore").read_text().splitlines()

    assert ".venv" in dockerignore
    assert ".env" in dockerignore


def test_powershell_deploy_matches_cloud_run_contract():
    script = (ROOT / "scripts" / "deploy_cloud_run.ps1").read_text()

    assert "--no-allow-unauthenticated" in script
    assert "GOOGLE_MAPS_API_KEY=$MapsSecret`:latest" in script
    assert "roles/bigquery.jobUser" in script
    assert "roles/bigquery.dataViewer" in script
    assert "gcp-sa-discoveryengine.iam.gserviceaccount.com" in script
    assert "BRIDGE_BIGQUERY_TABLE=$BridgeBigQueryTable" in script


def test_powershell_verify_and_registration_scripts_exist():
    verify = (ROOT / "scripts" / "verify_deployment.ps1").read_text()
    register = (ROOT / "scripts" / "register_gemini_enterprise.ps1").read_text()
    secret = (ROOT / "scripts" / "set_maps_secret.ps1").read_text()

    assert "Bridge Inventory Agent" in verify
    assert "search_bridge_inventory" in verify
    assert "register-gemini-enterprise" in register
    assert "agent-starter-pack@0.41.3" in register
    assert "WriteAllText" in secret
    assert "secrets versions add" in secret
