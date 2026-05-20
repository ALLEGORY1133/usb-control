#Requires -Version 5.1
<#
.SYNOPSIS
    USB Xavfsizlik Tizimi - local dev muhiti ishga tushiruvchi skript
.PARAMETER Port
    Django dev server porti (default: 8000)
.PARAMETER NoBrowser
    Brauzer avtomatik ochilmasin
.EXAMPLE
    .\dev.ps1
    .\dev.ps1 -Port 8080
    .\dev.ps1 -NoBrowser
    .\dev.ps1 -WithAgent
#>
param(
    [int]$Port = 8000,
    [switch]$NoBrowser,
    [switch]$WithAgent
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step { param($msg) Write-Host "`n>> $msg" -ForegroundColor Cyan }
function Write-OK   { param($msg) Write-Host "   [OK] $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "   [!]  $msg" -ForegroundColor Yellow }
function Write-Fail { param($msg) Write-Host "`n[XATO] $msg" -ForegroundColor Red; exit 1 }

$Root = $PSScriptRoot
Set-Location $Root

Write-Host ""
Write-Host "  USB Xavfsizlik Tizimi - Dev muhiti" -ForegroundColor Magenta
Write-Host "  =====================================" -ForegroundColor DarkGray
Write-Host ""

# 1. Python tekshirish
Write-Step "Python tekshirilmoqda..."
try {
    $pyVer = python --version 2>&1
    Write-OK "$pyVer"
} catch {
    Write-Fail "Python topilmadi. https://python.org dan yuklab o'rnating."
}

# 2. Virtualenv
Write-Step "Virtual muhit tekshirilmoqda..."
$VenvDir = Join-Path $Root ".venv"
if (-not (Test-Path $VenvDir)) {
    Write-Warn ".venv topilmadi - yaratilmoqda..."
    python -m venv .venv
    Write-OK ".venv yaratildi"
} else {
    Write-OK ".venv mavjud"
}

$Activate = Join-Path $VenvDir "Scripts\Activate.ps1"
if (-not (Test-Path $Activate)) {
    Write-Fail ".venv/Scripts/Activate.ps1 topilmadi. .venv ni o'chirib qayta ishga tushiring."
}
. $Activate
Write-OK "Virtual muhit faollashtirildi"

# 3. Paketlar
Write-Step "requirements.txt tekshirilmoqda..."
$ReqFile = Join-Path $Root "requirements.txt"
if (-not (Test-Path $ReqFile)) {
    Write-Fail "requirements.txt topilmadi!"
}

$PipList  = pip list --format=freeze 2>$null
$ReqLines = Get-Content $ReqFile | Where-Object { $_ -match "==" }
$Missing  = $ReqLines | Where-Object {
    $pkg = ($_ -split "==")[0].ToLower()
    -not ($PipList -match "(?i)^$pkg==")
}

if ($Missing) {
    Write-Warn "Yangi paketlar o'rnatilmoqda..."
    pip install -r requirements.txt --quiet
    Write-OK "Paketlar o'rnatildi"
} else {
    Write-OK "Barcha paketlar mavjud"
}

# 4. .env fayl
Write-Step ".env fayl tekshirilmoqda..."
$EnvFile = Join-Path $Root ".env"
if (-not (Test-Path $EnvFile)) {
    Write-Warn ".env topilmadi - namuna yaratilyapti..."
    $envContent = @"
# Django
SECRET_KEY=django-insecure-local-dev-key-change-in-production
DEBUG=True

# Ma'lumotlar bazasi (bo'sh qolsa SQLite ishlatiladi)
# DATABASE_URL=postgres://user:password@localhost:5432/usb_db
"@
    [System.IO.File]::WriteAllText($EnvFile, $envContent, [System.Text.Encoding]::UTF8)
    Write-Warn ".env yaratildi. SECRET_KEY ni o'zgartiring!"
} else {
    Write-OK ".env mavjud"
    $envRaw = Get-Content $EnvFile -Raw
    if ($envRaw -match "insecure") {
        Write-Warn "SECRET_KEY xavfli - production uchun almashtiring"
    }
}

# 5. Migratsiyalar
Write-Step "Migratsiyalar tekshirilmoqda..."
$migrOut = python manage.py showmigrations --list 2>&1
if ($migrOut -match "\[ \]") {
    Write-Warn "Qo'llanmagan migratsiyalar bor - migrate ishlatilmoqda..."
    python manage.py migrate
    Write-OK "Migratsiyalar qo'llanildi"
} else {
    Write-OK "Barcha migratsiyalar qo'llanilgan"
}

# 6. Superuser
Write-Step "Superuser tekshirilmoqda..."
$userCount = python -c @"
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()
from django.contrib.auth.models import User
print(User.objects.filter(is_superuser=True).count())
"@ 2>$null

if ($userCount -eq "0") {
    Write-Warn "Superuser topilmadi. Yaratish uchun:"
    Write-Host "       python manage.py createsuperuser" -ForegroundColor White
} else {
    Write-OK "Superuser mavjud ($userCount ta)"
}

# 7. Static fayllar
Write-Step "Static fayllar tekshirilmoqda..."
$StaticDir = Join-Path $Root "staticfiles"
$hasStatic = (Test-Path $StaticDir) -and (Get-ChildItem $StaticDir -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1)
if (-not $hasStatic) {
    Write-Warn "staticfiles bo'sh - collectstatic ishlatilmoqda..."
    python manage.py collectstatic --noinput --quiet
    Write-OK "Static fayllar yig'ildi"
} else {
    Write-OK "Static fayllar mavjud"
}

# 8. Agent (ixtiyoriy)
if ($WithAgent) {
    Write-Step "USB Agent tekshirilmoqda..."

    $AgentReq = Join-Path $Root "agent_requirements.txt"
    if (Test-Path $AgentReq) {
        $AgentPipList = pip list --format=freeze 2>$null
        $AgentMissing = Get-Content $AgentReq | Where-Object { $_ -match "\S" } | Where-Object {
            $pkg = ($_ -split "==")[0].ToLower()
            -not ($AgentPipList -match "(?i)^$pkg(==|$)")
        }
        if ($AgentMissing) {
            Write-Warn "Agent paketlari o'rnatilmoqda..."
            pip install -r agent_requirements.txt --quiet
            Write-OK "Agent paketlari o'rnatildi"
        } else {
            Write-OK "Agent paketlari mavjud"
        }
    }

    $AgentFile = Join-Path $Root "usb_agent.pyw"
    if (-not (Test-Path $AgentFile)) {
        Write-Warn "usb_agent.pyw topilmadi - o'tkazib yuborildi"
    } else {
        $pythonw = Join-Path $VenvDir "Scripts\pythonw.exe"
        if (-not (Test-Path $pythonw)) {
            $pythonw = "pythonw"
        }
        Start-Process $pythonw -ArgumentList "`"$AgentFile`"" -Verb RunAs
        Write-OK "USB Agent ishga tushirildi (tray ikonkasini tekshiring)"
    }
}

# 9. Ishga tushirish
Write-Host ""
Write-Host "  +------------------------------------------+" -ForegroundColor Green
Write-Host "  |  Server ishga tushmoqda...               |" -ForegroundColor Green
Write-Host "  |                                          |" -ForegroundColor Green
Write-Host "  |  API   :  http://localhost:$Port/api/    |" -ForegroundColor Green
Write-Host "  |  Admin :  http://localhost:$Port/admin/  |" -ForegroundColor Green
Write-Host "  |  Ping  :  http://localhost:$Port/api/ping|" -ForegroundColor Green
Write-Host "  |                                          |" -ForegroundColor Green
Write-Host "  |  To'xtatish: Ctrl+C                      |" -ForegroundColor Green
Write-Host "  +------------------------------------------+" -ForegroundColor Green
Write-Host ""

if (-not $NoBrowser) {
    Start-Sleep -Seconds 1
    Start-Process "http://localhost:$Port/admin/"
}

python manage.py runserver $Port
