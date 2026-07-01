param(
  [int]$Port = 8000,
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
  $env:PORT = "$Port"
  $env:ALLOWED_HOSTS = "localhost,127.0.0.1,.ngrok-free.app,.trycloudflare.com"
  $env:CSRF_TRUSTED_ORIGINS = "http://localhost:$Port,http://127.0.0.1:$Port,https://*.ngrok-free.app,https://*.trycloudflare.com"

  Write-Host "Django local: http://127.0.0.1:$Port" -ForegroundColor Green
  Write-Host "Para compartirlo, dejá esta terminal abierta y ejecutá start-client-demo-tunnel.ps1 en otra."
  uv run python manage.py runserver 0.0.0.0:$Port
} finally {
  Pop-Location
}
