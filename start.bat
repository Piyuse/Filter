@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo The Python environment is missing. Follow the setup steps in README.md.
    pause
    exit /b 1
)
echo Starting Veil. The local NLP model can take a few seconds to load.
echo Keep this window open while using the app. Press Ctrl+C to stop.
".venv\Scripts\python.exe" -m app.main
if errorlevel 1 (
    echo.
    echo Veil could not start. Copy the error above for troubleshooting.
    pause
    exit /b 1
)
