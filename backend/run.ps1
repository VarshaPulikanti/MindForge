# Stable backend start (no --reload; avoids Windows/OneDrive hang)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$port = 8000
$conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($conn) {
    Write-Host "Stopping process on port $port (PID $($conn.OwningProcess))..."
    Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "Create venv first: python -m venv .venv"
    exit 1
}

. .venv\Scripts\Activate.ps1
Write-Host "Starting MindForge API on http://127.0.0.1:$port (no reload)"
uvicorn app.main:app --host 127.0.0.1 --port $port
