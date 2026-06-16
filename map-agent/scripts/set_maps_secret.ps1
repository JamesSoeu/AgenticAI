[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$MapsApiKey,
    [string]$ProjectId = $env:PROJECT_ID,
    [string]$MapsSecret = $(if ($env:GOOGLE_MAPS_SECRET_NAME) { $env:GOOGLE_MAPS_SECRET_NAME } else { "google_map_api_key" })
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

$TemporaryFile = Join-Path ([System.IO.Path]::GetTempPath()) "bridge-map-key-$([guid]::NewGuid()).txt"
try {
    [System.IO.File]::WriteAllText(
        $TemporaryFile,
        $MapsApiKey,
        [System.Text.UTF8Encoding]::new($false)
    )

    & gcloud secrets describe $MapsSecret --project $ProjectId *> $null
    if ($LASTEXITCODE -eq 0) {
        & gcloud secrets versions add $MapsSecret `
            --data-file=$TemporaryFile `
            --project $ProjectId
    }
    else {
        & gcloud secrets create $MapsSecret `
            --data-file=$TemporaryFile `
            --replication-policy=automatic `
            --project $ProjectId
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Unable to create or update Maps secret $MapsSecret."
    }
}
finally {
    Remove-Item $TemporaryFile -Force -ErrorAction SilentlyContinue
}

Write-Host "Secret ready: $MapsSecret"
