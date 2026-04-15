# Test Suite Executor E2E Test Script (PowerShell)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Test Suite Executor E2E Test" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& "..\..\venv\Scripts\Activate.ps1"

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to activate virtual environment" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Virtual environment activated" -ForegroundColor Green
Write-Host ""

# Check and install dependencies
Write-Host "Checking dependencies..." -ForegroundColor Yellow

$websockets = pip show websockets 2>$null
if (-not $websockets) {
    Write-Host "Installing websockets..." -ForegroundColor Yellow
    pip install websockets
}

$requests = pip show requests 2>$null
if (-not $requests) {
    Write-Host "Installing requests..." -ForegroundColor Yellow
    pip install requests
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting test execution" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Execute test script
python test_suite_executor_e2e.py

# Check test result
if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "TEST PASSED" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "TEST FAILED" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
}

Write-Host ""
Read-Host "Press Enter to exit"
