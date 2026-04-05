@echo off
REM Test Case Executor E2E Test Script

echo ========================================
echo Test Case Executor E2E Test
echo ========================================
echo.

REM Activate virtual environment
echo Activating virtual environment...
call ..\..\venv\Scripts\activate.bat

REM Check if activation succeeded
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

echo Virtual environment activated
echo.

REM Install dependencies
echo Checking dependencies...
pip show websockets >nul 2>&1
if errorlevel 1 (
    echo Installing websockets...
    pip install websockets
)

pip show requests >nul 2>&1
if errorlevel 1 (
    echo Installing requests...
    pip install requests
)

echo.
echo ========================================
echo Starting test execution
echo ========================================
echo.

REM Run test script
python test_case_executor_e2e.py

REM Check test result
if errorlevel 1 (
    echo.
    echo ========================================
    echo TEST FAILED
    echo ========================================
    pause
    exit /b 1
) else (
    echo.
    echo ========================================
    echo TEST PASSED
    echo ========================================
    pause
    exit /b 0
)
