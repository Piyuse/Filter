# Run the project-local Ollama server in this terminal. Downloads are setup-only.
$ErrorActionPreference = 'Stop'
$filterRoot = $PSScriptRoot
$filterRuntime = Join-Path $filterRoot '.tools\ollama\ollama.exe'
if (-not (Test-Path -LiteralPath $filterRuntime)) {
    throw 'Project-local Ollama is missing. See the local AI setup in README.md.'
}
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_DEBUG = '0'
$env:OLLAMA_DEBUG_LOG_REQUESTS = '0'
$env:OLLAMA_NOHISTORY = '1'
$env:OLLAMA_MODELS = Join-Path $filterRoot '.tools\ollama-models'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_NUM_PARALLEL = '1'
& $filterRuntime serve
