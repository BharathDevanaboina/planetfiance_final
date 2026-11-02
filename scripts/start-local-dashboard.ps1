param(
    [int]$Port = 8005
)

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

# This mode is deliberately constrained by Settings.validate_for_environment:
# local environment, fake identity, SQLite, local storage and fake Sheets only.
$env:APP_ENV = "local"
$env:LOCAL_DASHBOARD_MODE = "true"
$env:DATABASE_URL = "sqlite:///var/planetfiance-dev.db"
$env:AUTH_MODE = "fake"
$env:APP_CHECK_ENABLED = "false"
$env:STORAGE_BACKEND = "local"
$env:LOCAL_STORAGE_DIR = "var/planetfiance-dev-storage"
$env:PUBLIC_BASE_URL = "http://127.0.0.1:$Port"
$env:SHEETS_BACKEND = "fake"
$env:FAKE_SHEETS_DIR = "var/planetfiance-dev-sheets"
$env:INTERNAL_AUTH_MODE = "token"
$env:INTERNAL_TASK_TOKEN = "local-internal-token-change-me-0123456789"

python -m uvicorn app.main:app --host 127.0.0.1 --port $Port
