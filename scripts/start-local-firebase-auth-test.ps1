param(
    [int]$Port = 8006,
    [switch]$RegisterAdmin,
    [string]$AdminEmail,
    [string]$AdminName
)

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot
$testConfig = Join-Path $projectRoot "config\local-firebase-auth-test.env"

if (-not (Test-Path -LiteralPath $testConfig)) {
    throw "Create config/local-firebase-auth-test.env from config/local-firebase-auth-test.env.example first."
}

# Import only this ignored local file. Values are never written to stdout.
Get-Content -LiteralPath $testConfig | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return }
    $separator = $line.IndexOf("=")
    if ($separator -lt 1) { throw "Invalid local Firebase auth test configuration line." }
    $name = $line.Substring(0, $separator).Trim()
    $value = $line.Substring($separator + 1).Trim()
    Set-Item -Path "Env:$name" -Value $value
}

foreach ($name in "GCP_PROJECT_ID", "FIREBASE_WEB_API_KEY", "FIREBASE_WEB_AUTH_DOMAIN", "FIREBASE_WEB_APP_ID", "GOOGLE_APPLICATION_CREDENTIALS") {
    if (-not (Get-Item -Path "Env:$name" -ErrorAction SilentlyContinue).Value) {
        throw "The local Firebase auth test configuration must set $name."
    }
}
if (-not (Test-Path -LiteralPath $env:GOOGLE_APPLICATION_CREDENTIALS)) {
    throw "GOOGLE_APPLICATION_CREDENTIALS must reference an existing local credential file."
}

# Local-only guardrails: separate SQLite data, local files, fake Sheets and real Firebase token checks.
$env:APP_ENV = "local"
$env:LOCAL_DASHBOARD_MODE = "false"
$env:LOCAL_FIREBASE_AUTH_TEST_MODE = "true"
$env:DATABASE_URL = "sqlite:///var/planetfiance-firebase-auth-test.db"
$env:AUTH_MODE = "firebase"
$env:APP_CHECK_ENABLED = "false"
$env:STORAGE_BACKEND = "local"
$env:LOCAL_STORAGE_DIR = "var/planetfiance-firebase-auth-test-storage"
$env:PUBLIC_BASE_URL = "http://127.0.0.1:$Port"
$env:SHEETS_BACKEND = "fake"
$env:FAKE_SHEETS_DIR = "var/planetfiance-firebase-auth-test-sheets"
$env:INTERNAL_AUTH_MODE = "token"
$env:INTERNAL_TASK_TOKEN = "local-internal-token-change-me-0123456789"

if ($RegisterAdmin) {
    if (-not $AdminEmail) { throw "-AdminEmail is required with -RegisterAdmin." }
    $arguments = @("-m", "app.cli", "grant-existing-admin", "--email", $AdminEmail)
    if ($AdminName) { $arguments += @("--name", $AdminName) }
    & python @arguments
    exit $LASTEXITCODE
}

python -m uvicorn app.main:app --host 127.0.0.1 --port $Port
