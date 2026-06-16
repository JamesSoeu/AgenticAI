[CmdletBinding()]
param(
    [string]$ProjectId = $env:PROJECT_ID,
    [string]$Region = $(if ($env:REGION) { $env:REGION } else { "us-central1" }),
    [string]$ServiceName = $(if ($env:SERVICE_NAME) { $env:SERVICE_NAME } else { "gemini-enterprise-bridge-map" }),
    [string]$GeminiEnterpriseAppId = $env:GEMINI_ENTERPRISE_APP_ID
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    throw "Google Cloud CLI is required."
}
if (-not (Get-Command uvx -ErrorAction SilentlyContinue)) {
    throw "uvx is required. Install uv from https://docs.astral.sh/uv/."
}
if (-not $ProjectId) {
    $ProjectId = (& gcloud config get-value project 2>$null).Trim()
}
if (-not $ProjectId -or $ProjectId -eq "(unset)") {
    throw "Set -ProjectId, `$env:PROJECT_ID, or configure the gcloud project."
}
if ($GeminiEnterpriseAppId) {
    $env:GEMINI_ENTERPRISE_APP_ID = $GeminiEnterpriseAppId
}

$ProjectNumber = (& gcloud projects describe $ProjectId --format="value(projectNumber)").Trim()
$ServiceUrl = (& gcloud run services describe $ServiceName `
    --region $Region `
    --project $ProjectId `
    --format="value(status.url)").Trim()

if ($LASTEXITCODE -ne 0 -or -not $ProjectNumber -or -not $ServiceUrl) {
    throw "Unable to determine the project number or Cloud Run service URL."
}

& uvx "agent-starter-pack@0.41.3" register-gemini-enterprise `
    "--agent-card-url=$ServiceUrl/.well-known/agent-card.json" `
    "--deployment-target=cloud_run" `
    "--registration-type=a2a" `
    "--project-number=$ProjectNumber"

if ($LASTEXITCODE -ne 0) {
    throw "Gemini Enterprise registration failed."
}
