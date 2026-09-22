# File Organizer — start the server
# Usage: .\run.ps1

$ErrorActionPreference = "Stop"

if (-not (Test-Path "app.py")) {
    Write-Host "Error: run this from the file-organizer folder." -ForegroundColor Red
    exit 1
}

Write-Host "Starting File Organizer..." -ForegroundColor Cyan
Write-Host "Open http://127.0.0.1:8000 in your browser" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop." -ForegroundColor DarkGray
Write-Host ""

python -m uvicorn app:app --reload --port 8000