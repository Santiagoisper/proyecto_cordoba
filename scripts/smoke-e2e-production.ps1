# Smoke E2E - validacion HTTP contra URL publica de produccion (Railway)
# Uso:
#   .\scripts\smoke-e2e-production.ps1 -BaseUrl "https://tu-app.up.railway.app"
#   .\scripts\smoke-e2e-production.ps1 -Username asistente -Password "Admin123!Cordoba"

param(
    [string]$BaseUrl = $env:CORDOBA_PROD_URL,
    [string]$Username = "asistente",
    [string]$Password = $(if ($env:CORDOBA_DEMO_PASSWORD) { $env:CORDOBA_DEMO_PASSWORD } else { "Admin123!Cordoba" })
)

$ErrorActionPreference = "Stop"

if (-not $BaseUrl) {
    Write-Host "ERROR: Indica -BaseUrl o define CORDOBA_PROD_URL" -ForegroundColor Red
    Write-Host "Ejemplo: .\scripts\smoke-e2e-production.ps1 -BaseUrl https://proyecto-cordoba-production.up.railway.app"
    exit 1
}

$BaseUrl = $BaseUrl.TrimEnd("/")

function Write-Check($Name, $Ok, $Detail) {
    $icon = if ($Ok) { "[OK]" } else { "[FAIL]" }
    $color = if ($Ok) { "Green" } else { "Red" }
    Write-Host "$icon $Name - $Detail" -ForegroundColor $color
    if (-not $Ok) { $script:Failed = $true }
}

$Failed = $false
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession

Write-Host ""
Write-Host "=== Smoke E2E - $BaseUrl ===" -ForegroundColor Cyan
Write-Host ""

# 1. Login page
try {
    $loginPage = Invoke-WebRequest -Uri "$BaseUrl/accounts/login/" -UseBasicParsing -SessionVariable session
    Write-Check "Login page" ($loginPage.StatusCode -eq 200) "HTTP $($loginPage.StatusCode)"
    $csrf = [regex]::Match($loginPage.Content, 'name="csrfmiddlewaretoken" value="([^"]+)"').Groups[1].Value
    Write-Check "CSRF token" ($csrf.Length -gt 0) "token presente"
} catch {
    Write-Check "Login page" $false $_.Exception.Message
    exit 1
}

# 2. Dashboard protegido sin cookie
try {
    $dash = Invoke-WebRequest -Uri "$BaseUrl/dashboard/" -UseBasicParsing -MaximumRedirection 0 -ErrorAction SilentlyContinue
    Write-Check "Dashboard sin auth" ($dash.StatusCode -in 302, 301) "HTTP $($dash.StatusCode)"
} catch {
    if ($_.Exception.Response.StatusCode.value__ -in 302, 301) {
        Write-Check "Dashboard sin auth" $true "redirect a login"
    } else {
        Write-Check "Dashboard sin auth" $false $_.Exception.Message
    }
}

# 3. Login POST
try {
    $body = @{
        csrfmiddlewaretoken = $csrf
        login                 = $Username
        password              = $Password
    }
    $loginResp = Invoke-WebRequest -Uri "$BaseUrl/accounts/login/" -Method POST `
        -Body $body -WebSession $session -UseBasicParsing -MaximumRedirection 0 -ErrorAction SilentlyContinue
    $ok = $loginResp.StatusCode -in 302, 301
    Write-Check "Login POST ($Username)" $ok "HTTP $($loginResp.StatusCode)"
} catch {
    if ($_.Exception.Response.StatusCode.value__ -in 302, 301) {
        Write-Check "Login POST ($Username)" $true "redirect post-login"
    } else {
        Write-Check "Login POST ($Username)" $false $_.Exception.Message
    }
}

# 4. Dashboard autenticado
try {
    $dashAuth = Invoke-WebRequest -Uri "$BaseUrl/dashboard/" -WebSession $session -UseBasicParsing
    Write-Check "Dashboard autenticado" ($dashAuth.StatusCode -eq 200) "HTTP $($dashAuth.StatusCode)"
} catch {
    Write-Check "Dashboard autenticado" $false $_.Exception.Message
}

# 5. HTMX patients (requiere protocol id en seed demo)
try {
    $htmx = Invoke-WebRequest -Uri "$BaseUrl/expenses/htmx/patients/?protocol=1" `
        -WebSession $session -UseBasicParsing
    Write-Check "HTMX patients" ($htmx.StatusCode -eq 200) "HTTP $($htmx.StatusCode)"
} catch {
    Write-Check "HTMX patients" $false $_.Exception.Message
}

# 6. Service worker PWA
try {
    $sw = Invoke-WebRequest -Uri "$BaseUrl/sw.js" -UseBasicParsing
    $isJs = $sw.Headers["Content-Type"] -match "javascript"
    Write-Check "PWA sw.js" ($sw.StatusCode -eq 200 -and $isJs) "HTTP $($sw.StatusCode)"
} catch {
    Write-Check "PWA sw.js" $false $_.Exception.Message
}

# 7. Reportes index
try {
    $reports = Invoke-WebRequest -Uri "$BaseUrl/reports/" -WebSession $session -UseBasicParsing
    Write-Check "Reportes index" ($reports.StatusCode -eq 200) "HTTP $($reports.StatusCode)"
} catch {
    Write-Check "Reportes index" $false $_.Exception.Message
}

Write-Host ""
if ($Failed) {
    Write-Host "Smoke E2E: FALLO - revisar checks arriba." -ForegroundColor Red
    exit 1
}
Write-Host "Smoke E2E: OK - todos los checks pasaron." -ForegroundColor Green
exit 0
