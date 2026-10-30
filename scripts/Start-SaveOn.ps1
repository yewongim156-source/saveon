[CmdletBinding()]
param(
    [string]$RuntimeDrive = "S:"
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $projectRoot ".runtime"
$logRoot = Join-Path $runtimeRoot "logs"
$pidFile = Join-Path $runtimeRoot "processes.json"
$postgresRoot = Join-Path $runtimeRoot "postgres16"
$postgresData = Join-Path $runtimeRoot "postgres-data"

function Wait-HttpReady {
    param(
        [string]$Name,
        [string]$Url,
        [int]$TimeoutSeconds = 90
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-RestMethod -Uri $Url -TimeoutSec 3
            if ($response) {
                Write-Host "[ready] $Name - $Url"
                return
            }
        }
        catch {
            Start-Sleep -Seconds 1
        }
    } while ((Get-Date) -lt $deadline)

    throw "$Name did not become ready within $TimeoutSeconds seconds."
}

function Test-HttpReady {
    param([string]$Url)

    try {
        $response = Invoke-RestMethod -Uri $Url -TimeoutSec 2
        return $null -ne $response
    }
    catch {
        return $false
    }
}

function Start-HiddenProcess {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$WorkingDirectory
    )

    $stdout = Join-Path $logRoot "$Name.out.log"
    $stderr = Join-Path $logRoot "$Name.err.log"
    $process = Start-Process `
        -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -PassThru

    Write-Host "[started] $Name (PID $($process.Id))"
    return $process.Id
}

New-Item -ItemType Directory -Force -Path $logRoot | Out-Null

$previousProcesses = $null
if (Test-Path $pidFile) {
    try {
        $previousProcesses = Get-Content $pidFile -Raw | ConvertFrom-Json
    }
    catch {
        Write-Warning "Ignoring an invalid process file: $pidFile"
    }
}

$requiredFiles = @(
    (Join-Path $postgresRoot "bin\pg_ctl.exe"),
    (Join-Path $projectRoot "ai\.venv\Scripts\python.exe"),
    (Join-Path $projectRoot "developer-api\.venv\Scripts\python.exe"),
    (Join-Path $projectRoot "api\gradlew.bat")
)
foreach ($requiredFile in $requiredFiles) {
    if (-not (Test-Path $requiredFile)) {
        throw "Missing local E2E dependency: $requiredFile"
    }
}
if (-not (Test-Path (Join-Path $postgresData "PG_VERSION"))) {
    throw "PostgreSQL data directory is not initialized: $postgresData"
}

# PostgreSQL's Windows bootstrap tools can misread the Korean project path.
# The drive mapping is only an alias; all files stay under this repository.
if (-not (Test-Path "$RuntimeDrive\")) {
    & subst.exe $RuntimeDrive $projectRoot | Out-Null
}
$mappedRuntime = "$RuntimeDrive\.runtime"
$mappedPgRoot = Join-Path $mappedRuntime "postgres16"
$mappedPgData = Join-Path $mappedRuntime "postgres-data"

$pgIsReady = Join-Path $mappedPgRoot "bin\pg_isready.exe"
$pgCtl = Join-Path $mappedPgRoot "bin\pg_ctl.exe"
& $pgIsReady -h 127.0.0.1 -p 5432 -d saveon -U saveon *> $null
if ($LASTEXITCODE -ne 0) {
    & $pgCtl `
        -D $mappedPgData `
        -l (Join-Path $mappedRuntime "postgres.log") `
        -o "-p 5432" `
        start
}
& $pgIsReady -h 127.0.0.1 -p 5432 -d saveon -U saveon
if ($LASTEXITCODE -ne 0) {
    throw "PostgreSQL is not ready on port 5432."
}

if (Test-HttpReady "http://127.0.0.1:8100/health") {
    $developerApiPid = $previousProcesses.developerApi
    Write-Host "[running] Developer API is already available."
}
else {
    $developerApiPid = Start-HiddenProcess `
        -Name "developer-api" `
        -FilePath (Join-Path $projectRoot "developer-api\.venv\Scripts\python.exe") `
        -ArgumentList @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8100") `
        -WorkingDirectory (Join-Path $projectRoot "developer-api")
}

if (Test-HttpReady "http://127.0.0.1:8000/health") {
    $aiPid = $previousProcesses.ai
    Write-Host "[running] AI API is already available."
}
else {
    $aiPid = Start-HiddenProcess `
        -Name "ai" `
        -FilePath (Join-Path $projectRoot "ai\.venv\Scripts\python.exe") `
        -ArgumentList @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000") `
        -WorkingDirectory (Join-Path $projectRoot "ai")
}

if (Test-HttpReady "http://127.0.0.1:8080/api/v1/contents") {
    $apiPid = $previousProcesses.api
    Write-Host "[running] Spring API is already available."
}
else {
    $apiPid = Start-HiddenProcess `
        -Name "api" `
        -FilePath (Join-Path $projectRoot "api\gradlew.bat") `
        -ArgumentList @("bootRun", "--no-daemon") `
        -WorkingDirectory (Join-Path $projectRoot "api")
}

@{
    developerApi = $developerApiPid
    ai = $aiPid
    api = $apiPid
    runtimeDrive = $RuntimeDrive
    startedAt = (Get-Date).ToString("o")
} | ConvertTo-Json | Set-Content -Path $pidFile -Encoding UTF8

Wait-HttpReady -Name "Developer API" -Url "http://127.0.0.1:8100/health"
Wait-HttpReady -Name "AI API" -Url "http://127.0.0.1:8000/health"
Wait-HttpReady -Name "Spring API" -Url "http://127.0.0.1:8080/api/v1/contents" -TimeoutSeconds 120

$geminiLine = Get-Content (Join-Path $projectRoot "ai\.env") -ErrorAction SilentlyContinue |
    Where-Object { $_ -match '^GEMINI_API_KEY=.+' } |
    Select-Object -First 1
if ($geminiLine) {
    Write-Host "[config] GEMINI_API_KEY is set."
}
else {
    Write-Warning "GEMINI_API_KEY is empty. URL storage works, but Gemini structuring, fact-checking, and semantic embeddings will fail."
}

Write-Host "Save:On local E2E environment is ready."

