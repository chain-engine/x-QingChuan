# Start the x-QingChuan application

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

Set-Location $ProjectDir

# Create data directories if they don't exist
$DataDir = Join-Path $ProjectDir "data"
if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir | Out-Null
}
$ChromaDir = Join-Path $DataDir "chroma"
$DocDir = Join-Path $DataDir "documents"
$LogsDir = Join-Path $ProjectDir "logs"

@($ChromaDir, $DocDir, $LogsDir) | ForEach-Object {
    if (-not (Test-Path $_)) {
        New-Item -ItemType Directory -Path $_ | Out-Null
    }
}

# Check if .env exists
$EnvFile = Join-Path $ProjectDir ".env"
if (-not (Test-Path $EnvFile)) {
    Write-Host "Warning: .env file not found. Copying from .env.example..."
    Copy-Item (Join-Path $ProjectDir ".env.example") $EnvFile
    Write-Host "Please edit .env and add your API keys."
}

# Run with uvicorn
uv run uvicorn qingchuan_rag.main:app --host 0.0.0.0 --port 8010 --reload
