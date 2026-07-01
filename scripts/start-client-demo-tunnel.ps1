param(
  [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$CloudflaredPath = $null
$Cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
if ($Cloudflared) {
  $CloudflaredPath = $Cloudflared.Source
}
if (-not $Cloudflared) {
  $Cloudflared = Get-ChildItem -Path "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter cloudflared.exe -ErrorAction SilentlyContinue |
    Select-Object -First 1
  if ($Cloudflared) {
    $CloudflaredPath = $Cloudflared.FullName
  }
}

if ($CloudflaredPath) {
  Write-Host "Abriendo túnel público Cloudflare hacia http://127.0.0.1:$Port" -ForegroundColor Green
  Write-Host "Copiá la URL https://...trycloudflare.com que aparezca abajo y mandásela al cliente."
  & $CloudflaredPath tunnel --url "http://127.0.0.1:$Port"
  exit $LASTEXITCODE
}

if (Get-Command ngrok -ErrorAction SilentlyContinue) {
  Write-Host "Abriendo túnel público ngrok hacia http://127.0.0.1:$Port" -ForegroundColor Green
  Write-Host "Copiá la URL https://...ngrok-free.app que aparezca abajo y mandásela al cliente."
  ngrok http $Port
  exit $LASTEXITCODE
}

throw "No se encontró cloudflared ni ngrok en PATH."
