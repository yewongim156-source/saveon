[CmdletBinding()]
param(
    [string]$RuntimeDrive = "S:"
)

$ErrorActionPreference = "Continue"

$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $projectRoot ".runtime"
$pidFile = Join-Path $runtimeRoot "processes.json"

if (Test-Path $pidFile) {
    $processes = Get-Content $pidFile -Raw | ConvertFrom-Json
    foreach ($name in @("api", "ai", "developerApi")) {
        $processId = $processes.$name
        if ($processId -and (Get-Process -Id $processId -ErrorAction SilentlyContinue)) {
            & taskkill.exe /PID $processId /T /F | Out-Null
            Write-Host "[stopped] $name (PID $processId)"
        }
    }
    Remove-Item -LiteralPath $pidFile -Force
}

if (-not (Test-Path "$RuntimeDrive\")) {
    & subst.exe $RuntimeDrive $projectRoot | Out-Null
}
$pgCtl = "$RuntimeDrive\.runtime\postgres16\bin\pg_ctl.exe"
$pgData = "$RuntimeDrive\.runtime\postgres-data"
if (Test-Path $pgCtl) {
    & $pgCtl -D $pgData status *> $null
    if ($LASTEXITCODE -eq 0) {
        & $pgCtl -D $pgData stop -m fast
        Write-Host "[stopped] PostgreSQL"
    }
}

Write-Host "Save:On local E2E environment is stopped."

