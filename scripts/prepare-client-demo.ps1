param(
  [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"

$CordobaRoot = Join-Path $ProjectRoot "cordoba"
if (-not (Test-Path (Join-Path $CordobaRoot "manage.py"))) {
  throw "No se encontró manage.py en $CordobaRoot"
}

Push-Location $CordobaRoot
try {
  $env:DJANGO_SETTINGS_MODULE = "config.settings.development"
  uv run python manage.py check
  uv run python manage.py migrate
  uv run python manage.py seed_client_demo --reset-passwords
  Write-Host ""
  Write-Host "Demo lista. Ahora ejecutá:" -ForegroundColor Green
  Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\start-client-demo.ps1"
  Write-Host "y en otra terminal:"
  Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\start-client-demo-tunnel.ps1"
} finally {
  Pop-Location
}
