@echo off
rem Folio - one-step local start (Windows).
rem Creates the virtual environment, installs dependencies, builds the web UI
rem if needed, then starts the app and opens it in the browser.
setlocal
cd /d "%~dp0"
if "%PORT%"=="" set PORT=8010

if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo Created .env - open it, paste your OpenAI key after OPENAI_API_KEY= and run start.bat again.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv || goto :error
)
echo Installing Python dependencies...
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt || goto :error

if not exist "frontend\dist\index.html" (
    echo Building the web interface...
    pushd frontend
    call npm install || goto :error
    call npm run build || goto :error
    popd
)

echo.
echo Folio is starting on http://localhost:%PORT%  (press Ctrl+C to stop)
start "" "http://localhost:%PORT%"
".venv\Scripts\python.exe" -m uvicorn app.main:create_app --factory --app-dir backend --port %PORT%
exit /b 0

:error
echo.
echo Setup failed. See the message above.
pause
exit /b 1
