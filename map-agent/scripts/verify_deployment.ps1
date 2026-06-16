[CmdletBinding()]
param(
    [string]$ProjectId = $env:PROJECT_ID,
    [string]$Region = $(if ($env:REGION) { $env:REGION } else { "us-central1" }),
    [string]$ServiceName = $(if ($env:SERVICE_NAME) { $env:SERVICE_NAME } else { "gemini-enterprise-bridge-map" })
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    throw "Google Cloud CLI is required."
}
if (-not $ProjectId) {
    $ProjectId = (& gcloud config get-value project 2>$null).Trim()
}
if (-not $ProjectId -or $ProjectId -eq "(unset)") {
    throw "Set -ProjectId, `$env:PROJECT_ID, or configure the gcloud project."
}

$ServiceUrl = (& gcloud run services describe $ServiceName `
    --project $ProjectId `
    --region $Region `
    --format="value(status.url)").Trim()
if ($LASTEXITCODE -ne 0 -or -not $ServiceUrl) {
    throw "Unable to read the Cloud Run service URL."
}

$Token = (& gcloud auth print-identity-token).Trim()
if ($LASTEXITCODE -ne 0 -or -not $Token) {
    throw "Unable to create an identity token."
}
$Headers = @{ Authorization = "Bearer $Token" }

$Card = Invoke-RestMethod `
    -Uri "$ServiceUrl/.well-known/agent-card.json" `
    -Headers $Headers `
    -Method Get

if ($Card.name -ne "Bridge Inventory Agent") {
    throw "Unexpected agent card name: $($Card.name)"
}
if (-not ($Card.skills.id -contains "search_bridge_inventory")) {
    throw "Agent card is missing search_bridge_inventory."
}
if (-not ($Card.capabilities.extensions.uri -contains "https://a2ui.org/a2a-extension/a2ui/v0.8")) {
    throw "Agent card is missing the A2UI v0.8 extension."
}
Write-Host "Agent card OK: $($Card.name)"

$MapUrl = "$ServiceUrl/maps/embed?mode=directions&origin=38.9351%2C-83.4596&destination=38.9451%2C-83.4696"
try {
    $Response = Invoke-WebRequest `
        -Uri $MapUrl `
        -Headers $Headers `
        -Method Get `
        -MaximumRedirection 0 `
        -ErrorAction Stop
    $MapStatus = [int]$Response.StatusCode
}
catch {
    if ($_.Exception.Response) {
        $MapStatus = [int]$_.Exception.Response.StatusCode
    }
    else {
        throw
    }
}

if ($MapStatus -notin @(302, 307)) {
    throw "Expected the Maps proxy to redirect, got HTTP $MapStatus"
}

Write-Host "Maps proxy OK: HTTP $MapStatus"
Write-Host "Deployment verification passed: $ServiceUrl"
