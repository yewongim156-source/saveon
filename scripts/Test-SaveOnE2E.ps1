[CmdletBinding()]
param(
    [string]$YouTubeUrl,
    [int]$TimeoutSeconds = 300
)

$ErrorActionPreference = "Stop"

function Assert-Http {
    param([string]$Name, [string]$Url)
    try {
        $result = Invoke-RestMethod -Uri $Url -TimeoutSec 5
        Write-Host "[ok] $Name"
        return $result
    }
    catch {
        throw "$Name is unavailable at $Url. Start the E2E environment first."
    }
}

Assert-Http -Name "Developer API" -Url "http://127.0.0.1:8100/health" | Out-Null
Assert-Http -Name "AI API" -Url "http://127.0.0.1:8000/health" | Out-Null
Assert-Http -Name "Spring API" -Url "http://127.0.0.1:8080/api/v1/contents" | Out-Null

if ([string]::IsNullOrWhiteSpace($YouTubeUrl)) {
    Write-Host "All local services are connected. Pass -YouTubeUrl to run a complete analysis."
    exit 0
}

$payload = @{
    sourceUrl = $YouTubeUrl
    platform = "YOUTUBE"
} | ConvertTo-Json

$content = Invoke-RestMethod `
    -Uri "http://127.0.0.1:8080/api/v1/contents" `
    -Method Post `
    -ContentType "application/json" `
    -Body $payload

Write-Host "[created] content ID $($content.id)"
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
do {
    Start-Sleep -Seconds 3
    $content = Invoke-RestMethod "http://127.0.0.1:8080/api/v1/contents/$($content.id)"
    Write-Host "[status] $($content.status)"
    if ($content.status -in @("COMPLETED", "FAILED")) {
        break
    }
} while ((Get-Date) -lt $deadline)

if ($content.status -ne "COMPLETED") {
    throw "YouTube E2E analysis did not complete. Final status: $($content.status)"
}

$content | ConvertTo-Json -Depth 20
Write-Host "[ok] YouTube URL -> analysis -> PostgreSQL E2E completed."
