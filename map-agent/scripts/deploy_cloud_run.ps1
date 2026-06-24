[CmdletBinding()]
param(
    [string]$ProjectId = $env:PROJECT_ID,
    [string]$Region = $(if ($env:REGION) { $env:REGION } else { "us-central1" }),
    [string]$ServiceName = $(if ($env:SERVICE_NAME) { $env:SERVICE_NAME } else { "gemini-enterprise-bridge-map" }),
    [string]$MapsSecret = $(if ($env:GOOGLE_MAPS_SECRET_NAME) { $env:GOOGLE_MAPS_SECRET_NAME } else { "google_map_api_key" }),
    [string]$RuntimeServiceAccountName = $(if ($env:RUNTIME_SA_NAME) { $env:RUNTIME_SA_NAME } else { "bridge-map-agent-sa" }),
    [string]$Model = $(if ($env:MODEL) { $env:MODEL } else { "gemini-3.5-flash" }),
    [string]$BridgeBigQueryTables = $(if ($env:BRIDGE_BIGQUERY_TABLES) { $env:BRIDGE_BIGQUERY_TABLES } elseif ($env:BRIDGE_BIGQUERY_TABLE) { $env:BRIDGE_BIGQUERY_TABLE } else { "your-project-id.transportation.bridge_data" }),
    [string]$BridgeDataProject = $env:BRIDGE_DATA_PROJECT,
    [string]$BigQueryLocation = $env:BIGQUERY_LOCATION
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-GCloud {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)

    & gcloud @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "gcloud command failed: gcloud $($Arguments -join ' ')"
    }
}

if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    throw "Google Cloud CLI is required. Install it and reopen PowerShell."
}

if (-not $ProjectId) {
    $ProjectId = (& gcloud config get-value project 2>$null).Trim()
}
if (-not $ProjectId -or $ProjectId -eq "(unset)") {
    throw "Set -ProjectId, `$env:PROJECT_ID, or run: gcloud config set project YOUR_PROJECT_ID"
}
if (-not $BridgeDataProject) {
    $FirstBridgeBigQueryTable = $BridgeBigQueryTables.Split(",")[0].Trim()
    $BridgeDataProject = $FirstBridgeBigQueryTable.Split(".")[0]
}

$ProjectNumber = (& gcloud projects describe $ProjectId --format="value(projectNumber)").Trim()
if ($LASTEXITCODE -ne 0 -or -not $ProjectNumber) {
    throw "Unable to read project number for $ProjectId"
}

$RuntimeServiceAccount = "$RuntimeServiceAccountName@$ProjectId.iam.gserviceaccount.com"
$DiscoveryEngineServiceAccount = "service-$ProjectNumber@gcp-sa-discoveryengine.iam.gserviceaccount.com"

Write-Host "Enabling required Google Cloud APIs..."
Invoke-GCloud services enable `
    aiplatform.googleapis.com `
    bigquery.googleapis.com `
    cloudbuild.googleapis.com `
    discoveryengine.googleapis.com `
    iam.googleapis.com `
    maps-embed-backend.googleapis.com `
    run.googleapis.com `
    secretmanager.googleapis.com `
    serviceusage.googleapis.com `
    --project $ProjectId

Write-Host "Ensuring runtime service account exists..."
& gcloud iam service-accounts describe $RuntimeServiceAccount --project $ProjectId *> $null
if ($LASTEXITCODE -ne 0) {
    Invoke-GCloud iam service-accounts create $RuntimeServiceAccountName `
        --display-name "Bridge Inventory Agent Runtime" `
        --project $ProjectId
}

Invoke-GCloud projects add-iam-policy-binding $ProjectId `
    --member "serviceAccount:$RuntimeServiceAccount" `
    --role "roles/aiplatform.user" `
    --condition=None `
    --quiet

Invoke-GCloud projects add-iam-policy-binding $ProjectId `
    --member "serviceAccount:$RuntimeServiceAccount" `
    --role "roles/bigquery.jobUser" `
    --condition=None `
    --quiet

Write-Host "Granting read access to bridge inventory project $BridgeDataProject..."
Invoke-GCloud projects add-iam-policy-binding $BridgeDataProject `
    --member "serviceAccount:$RuntimeServiceAccount" `
    --role "roles/bigquery.dataViewer" `
    --condition=None `
    --quiet

& gcloud secrets describe $MapsSecret --project $ProjectId *> $null
if ($LASTEXITCODE -ne 0) {
    throw @"
Missing Secret Manager secret: $MapsSecret
Create it from PowerShell:
  .\scripts\set_maps_secret.ps1 -ProjectId $ProjectId -MapsApiKey "YOUR_MAPS_API_KEY"
"@
}

Invoke-GCloud secrets add-iam-policy-binding $MapsSecret `
    --member "serviceAccount:$RuntimeServiceAccount" `
    --role "roles/secretmanager.secretAccessor" `
    --project $ProjectId `
    --quiet

$EnvironmentVariables = @(
    "GOOGLE_CLOUD_PROJECT=$ProjectId"
    "GOOGLE_CLOUD_LOCATION=global"
    "GOOGLE_GENAI_USE_VERTEXAI=true"
    "MODEL=$Model"
    "BRIDGE_BIGQUERY_TABLES=$BridgeBigQueryTables"
    "BIGQUERY_JOB_PROJECT=$ProjectId"
    "BIGQUERY_LOCATION=$BigQueryLocation"
) -join ","

Write-Host "Deploying $ServiceName to Cloud Run..."
Invoke-GCloud run deploy $ServiceName `
    --source . `
    --project $ProjectId `
    --region $Region `
    --service-account $RuntimeServiceAccount `
    --memory 2Gi `
    --no-allow-unauthenticated `
    --no-cpu-throttling `
    --set-secrets "GOOGLE_MAPS_API_KEY=$MapsSecret`:latest" `
    --set-env-vars $EnvironmentVariables `
    --quiet

$ServiceUrl = (& gcloud run services describe $ServiceName `
    --project $ProjectId `
    --region $Region `
    --format="value(status.url)").Trim()
if ($LASTEXITCODE -ne 0 -or -not $ServiceUrl) {
    throw "Unable to read the Cloud Run service URL."
}

Write-Host "Updating the agent card URL to $ServiceUrl..."
Invoke-GCloud run services update $ServiceName `
    --project $ProjectId `
    --region $Region `
    --update-env-vars "AGENT_URL=$ServiceUrl,APP_URL=$ServiceUrl" `
    --quiet

Write-Host "Granting Gemini Enterprise permission to invoke the private service..."
Invoke-GCloud beta services identity create `
    --service discoveryengine.googleapis.com `
    --project $ProjectId

Invoke-GCloud run services add-iam-policy-binding $ServiceName `
    --project $ProjectId `
    --region $Region `
    --member "serviceAccount:$DiscoveryEngineServiceAccount" `
    --role "roles/run.invoker" `
    --quiet

Write-Host ""
Write-Host "Cloud Run deployment is ready."
Write-Host "Service URL: $ServiceUrl"
Write-Host "Agent card:  $ServiceUrl/.well-known/agent-card.json"
Write-Host ""
Write-Host "Next:"
Write-Host "  .\scripts\verify_deployment.ps1 -ProjectId $ProjectId"
Write-Host "  .\scripts\register_gemini_enterprise.ps1 -ProjectId $ProjectId"
