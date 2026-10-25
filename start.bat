@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo The Python environment is missing. Follow the setup steps in README.md.
    pause
    exit /b 1
)
echo Starting Filter. The local NLP model can take a few seconds to load.
if exist "%~dp0.tools\ollama\ollama.exe" (
    set "OLLAMA_HOST=127.0.0.1:11434"
    set "OLLAMA_NO_CLOUD=1"
    set "OLLAMA_DEBUG=0"
    set "OLLAMA_DEBUG_LOG_REQUESTS=0"
    set "OLLAMA_NOHISTORY=1"
    set "OLLAMA_MODELS=%~dp0.tools\ollama-models"
    set "OLLAMA_MAX_LOADED_MODELS=1"
    set "OLLAMA_NUM_PARALLEL=1"
    set "FILTER_OLLAMA_EXE=%~dp0.tools\ollama\ollama.exe"
    powershell.exe -NoProfile -Command "if (-not (Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue)) { Start-Process -FilePath $env:FILTER_OLLAMA_EXE -ArgumentList 'serve' -WindowStyle Hidden }"
)
if exist "%~dp0.tools\tesseract\tesseract.exe" set "TESSERACT_CMD=%~dp0.tools\tesseract\tesseract.exe"
echo Keep this window open while using the app. Press Ctrl+C to stop.
".venv\Scripts\python.exe" -m app.main
if errorlevel 1 (
    echo.
    echo Filter could not start. Copy the error above for troubleshooting.
    pause
    exit /b 1
)
