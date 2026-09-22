# Build File Organizer into a standalone .exe
# Usage: .\build.ps1
# Output: dist\FileOrganizer.exe

$ErrorActionPreference = "Stop"

if (-not (Test-Path "file_organizer.spec")) {
    Write-Host "Error: run this from the file-organizer folder." -ForegroundColor Red
    exit 1
}

Write-Host "Cleaning previous build..." -ForegroundColor Cyan
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue

Write-Host "Running PyInstaller..." -ForegroundColor Cyan
python -m PyInstaller file_organizer.spec --noconfirm

if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed." -ForegroundColor Red
    exit 1
}

$exePath = "dist\FileOrganizer.exe"
if (-not (Test-Path $exePath)) {
    Write-Host "Error: $exePath not found after build." -ForegroundColor Red
    exit 1
}

$size = [math]::Round((Get-Item $exePath).Length / 1MB, 1)
Write-Host ""
Write-Host "Build complete." -ForegroundColor Green
Write-Host "  Output: $exePath ($size MB)" -ForegroundColor Green
Write-Host "  Run it: .\$exePath" -ForegroundColor Green
Write-Host ""
Write-Host "Note: config files (rules.yaml, settings.yaml, etc.) will be created" -ForegroundColor DarkGray
Write-Host "      in a data\ folder next to the executable on first run." -ForegroundColor DarkGray