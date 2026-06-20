#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$ROOT    = Split-Path $PSScriptRoot -Parent
$BACKEND = Join-Path $ROOT "backend"
$VENV    = Join-Path $BACKEND ".venv-tfg-llm"
$PIP     = Join-Path $VENV "Scripts\pip.exe"
$PYTHON  = Join-Path $VENV "Scripts\python.exe"
$PG_BIN  = "C:\Program Files\PostgreSQL\15\bin"
$PG_SVC  = "postgresql-15"
$DB_NAME = "tfg_llm_db"
$DB_USER = "postgres"

function Write-Step { param($msg) Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-OK   { param($msg) Write-Host "    [OK] $msg" -ForegroundColor Green }
function Write-SKIP { param($msg) Write-Host "    [--] $msg" -ForegroundColor DarkGray }
function Write-WARN { param($msg) Write-Host "    [!]  $msg" -ForegroundColor Yellow }
function Write-FAIL { param($msg) Write-Host "    [X]  $msg" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "  TFG LLM Benchmarking -- Setup entorno local" -ForegroundColor White
Write-Host "  ============================================" -ForegroundColor DarkGray
Write-Host ""

Write-Step "1/7  PATH de PostgreSQL"
if (-not (Test-Path $PG_BIN)) { Write-FAIL "No se encontro $PG_BIN. Instala PostgreSQL 15." }
if ($env:PATH -notlike "*$PG_BIN*") { $env:PATH += ";$PG_BIN"; Write-OK "Anadido al PATH" } else { Write-SKIP "psql ya en PATH" }

Write-Step "2/7  Servicio PostgreSQL ($PG_SVC)"
$svc = Get-Service -Name $PG_SVC -ErrorAction SilentlyContinue
if ($null -eq $svc) { Write-FAIL "Servicio '$PG_SVC' no encontrado. Sigue la seccion 6.2 de la guia." }
if ($svc.Status -ne "Running") { Start-Service $PG_SVC; Start-Sleep -Seconds 2; Write-OK "Servicio iniciado" } else { Write-SKIP "Servicio Running" }

Write-Step "3/7  Base de datos '$DB_NAME'"
$dbCheck = & psql -U $DB_USER -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" 2>&1
if ($dbCheck -match "1") { Write-SKIP "'$DB_NAME' ya existe" } else { & psql -U $DB_USER -c "CREATE DATABASE $DB_NAME;" | Out-Null; Write-OK "'$DB_NAME' creada" }

Write-Step "4/7  Fichero backend\.env"
$envFile = Join-Path $BACKEND ".env"
$envEx   = Join-Path $ROOT ".env.example"
if (Test-Path $envFile) { Write-SKIP "backend\.env ya existe" } else { Copy-Item $envEx $envFile; Write-WARN "backend\.env creado -- edita passwords y API keys" }

Write-Step "5/7  Entorno virtual Python"
if (Test-Path (Join-Path $VENV "Scripts\python.exe")) { Write-SKIP ".venv-tfg-llm ya existe" } else { python -m venv $VENV; Write-OK "Entorno virtual creado" }

Write-Step "6/7  Dependencias Python"
Write-Host "    Instalando paquetes (puede tardar 2-4 min)..." -ForegroundColor DarkGray
& $PIP install --upgrade pip --quiet
& $PIP install -r (Join-Path $BACKEND "requirements.txt") --quiet
if ($LASTEXITCODE -ne 0) { Write-FAIL "pip install fallo" }
Write-OK "Dependencias instaladas"

Write-Step "7/7  Verificacion"
$r1 = & $PYTHON -c "import asyncio,asyncpg;asyncio.run(asyncpg.connect('postgresql://postgres@localhost:5432/$DB_NAME'));print('ok')" 2>&1
if ($r1 -match "ok") { Write-OK "asyncpg conecta a PostgreSQL" } else { Write-WARN "asyncpg fallo: $r1" }

$r2 = & $PYTHON -c "import fastapi,sqlalchemy,alembic,anthropic,openai,pydantic_settings;print('ok')" 2>&1
if ($r2 -match "ok") { Write-OK "Importaciones OK" } else { Write-WARN "Error importaciones: $r2" }

Push-Location $BACKEND
$r3 = & $PYTHON -c "from app.core.config import get_settings;s=get_settings();print(s.app_name)" 2>&1
Pop-Location
if ($r3 -match "TFG") { Write-OK "Config OK -- $r3" } else { Write-WARN "Error config: $r3" }

Write-Host ""
Write-Host "  ============================================" -ForegroundColor DarkGray
Write-Host "  Setup completado. Para arrancar el backend:" -ForegroundColor White
Write-Host "    cd backend" -ForegroundColor Yellow
Write-Host "    .venv-tfg-llm\Scripts\Activate.ps1" -ForegroundColor Yellow
Write-Host "    uvicorn app.main:app --reload --port 8000" -ForegroundColor Yellow
Write-Host ""
Write-Host "  API docs: http://localhost:8000/api/v1/docs" -ForegroundColor DarkGray
Write-Host "  Health:   http://localhost:8000/api/v1/health" -ForegroundColor DarkGray
Write-Host ""
