# Build cn.exe with PyInstaller
# Usage: .\build.ps1           -- normal build
#        .\build.ps1 -Debug    -- verbose output for troubleshooting

param([switch]$Debug)

$ErrorActionPreference = "Stop"

Write-Host "=== claude-note Build ===" -ForegroundColor Cyan

# Ensure tray dependencies are installed
Write-Host "Checking dependencies..." -ForegroundColor Yellow
python -m pip install --quiet pystray Pillow fastapi "uvicorn[standard]" pyinstaller

# Clean previous build
if (Test-Path dist)  { Remove-Item dist  -Recurse -Force }
if (Test-Path build) { Remove-Item build -Recurse -Force }

# Build
if ($Debug) {
    Write-Host "Building cn.exe (debug)..." -ForegroundColor Yellow
    python -m PyInstaller cn.spec --clean --debug all
} else {
    Write-Host "Building cn.exe..." -ForegroundColor Yellow
    python -m PyInstaller cn.spec --clean
}

if (Test-Path "dist\cn.exe") {
    $size = [math]::Round((Get-Item "dist\cn.exe").Length / 1MB, 1)
    Write-Host "Done: dist\cn.exe ($size MB)" -ForegroundColor Green
    Write-Host "Run:    .\dist\cn.exe           (tray)" -ForegroundColor Gray
    Write-Host "Status: .\dist\cn.exe status" -ForegroundColor Gray
    Write-Host "Worker: .\dist\cn.exe worker --foreground" -ForegroundColor Gray
    Write-Host "Web UI: .\dist\cn.exe web" -ForegroundColor Gray
} else {
    Write-Host "Build failed." -ForegroundColor Red
    exit 1
}
