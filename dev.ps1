#Requires -Version 5.1
<#
.SYNOPSIS
    Arranca el entorno de desarrollo completo del TFG en tres ventanas.

.DESCRIPTION
    Levanta en orden:
      1. PostgreSQL  (Docker o servicio Windows, segun disponibilidad)
      2. Backend     (FastAPI en http://localhost:8000)
      3. Frontend    (Vite  en http://localhost:5173)

    Uso desde la raiz del proyecto:
        .\dev.ps1                  arranca todo
        .\dev.ps1 -SoloBackend     solo postgres + backend
        .\dev.ps1 -SoloFrontend    solo frontend

    Sprint: Sprint 3
#>
param(
    [switch]$SoloBackend,
    [switch]$SoloFrontend
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ROOT     = $PSScriptRoot
$BACKEND  = Join-Path $ROOT 'backend'
$FRONTEND = Join-Path $ROOT 'frontend'
$UVICORN  = Join-Path $BACKEND '.venv-tfg-llm\Scripts\uvicorn.exe'

function Write-Step { param($m) Write-Host "  -> $m" -ForegroundColor Cyan    }
function Write-Ok   { param($m) Write-Host "  OK $m"  -ForegroundColor Green   }
function Write-Warn { param($m) Write-Host "   ! $m"  -ForegroundColor Yellow  }
function Write-Err  { param($m) Write-Host "  XX $m"  -ForegroundColor Red     }

Clear-Host
Write-Host ''
Write-Host '  TFG - Benchmarking LLMs  |  dev.ps1' -ForegroundColor Magenta
Write-Host '  =====================================' -ForegroundColor Magenta
Write-Host ''

# ─── 1. PostgreSQL ─────────────────────────────────────────────────────────────
if (-not $SoloFrontend) {
    Write-Step 'Comprobando PostgreSQL...'

    $pgOk = $false

    # Intento 1: Docker (solo si docker esta instalado)
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        $dockerInfo = docker info 2>&1
        if ($LASTEXITCODE -eq 0) {
            $contenedor = docker ps --filter 'name=tfg_llm_postgres' --format '{{.Names}}' 2>&1
            if ($contenedor -match 'tfg_llm_postgres') {
                Write-Ok 'PostgreSQL (Docker) ya esta corriendo'
                $pgOk = $true
            } else {
                Write-Step 'Levantando PostgreSQL con docker-compose...'
                docker-compose -f "$ROOT\docker-compose.yml" up -d postgres 2>&1 | Out-Null
                if ($LASTEXITCODE -eq 0) {
                    Write-Ok 'PostgreSQL (Docker) arrancado'
                    $pgOk = $true
                }
            }
        }
    }

    # Intento 2: servicio Windows
    if (-not $pgOk) {
        $svc = Get-Service -Name 'postgresql*' -ErrorAction SilentlyContinue |
               Select-Object -First 1
        if ($null -ne $svc) {
            if ($svc.Status -ne 'Running') {
                Write-Step "Arrancando servicio $($svc.Name)..."
                Start-Service $svc.Name
                Start-Sleep -Seconds 2
            }
            Write-Ok "PostgreSQL (servicio Windows: $($svc.Name)) activo"
            $pgOk = $true
        }
    }

    if (-not $pgOk) {
        Write-Err 'PostgreSQL no disponible.'
        Write-Warn 'Opciones: instala Docker Desktop o PostgreSQL 15 para Windows.'
        exit 1
    }
}

# ─── 2. Backend ────────────────────────────────────────────────────────────────
if (-not $SoloFrontend) {
    if (-not (Test-Path $UVICORN)) {
        Write-Err 'Entorno virtual no encontrado en backend\.venv-tfg-llm'
        Write-Warn 'Ejecuta primero: cd backend && python -m venv .venv-tfg-llm && pip install -r requirements.txt'
        exit 1
    }

    Write-Step 'Abriendo ventana del Backend...'
    $cmdBackend = "& { `$Host.UI.RawUI.WindowTitle='TFG Backend :8000'; " +
                  "Write-Host 'Backend FastAPI  http://localhost:8000' -ForegroundColor Green; " +
                  "Write-Host 'Docs             http://localhost:8000/api/v1/docs' -ForegroundColor DarkGray; " +
                  "Write-Host 'CTRL+C para parar' -ForegroundColor DarkGray; Write-Host ''; " +
                  "Set-Location '$BACKEND'; " +
                  "& '$UVICORN' app.main:app --reload --port 8000 }"
    Start-Process powershell -ArgumentList '-NoExit', '-Command', $cmdBackend
    Start-Sleep -Seconds 2
    Write-Ok 'Backend arrancando en http://localhost:8000'
}

# ─── 3. Frontend ───────────────────────────────────────────────────────────────
if (-not $SoloBackend) {
    if (-not (Test-Path (Join-Path $FRONTEND 'node_modules'))) {
        Write-Step 'Instalando dependencias npm (primera vez)...'
        Push-Location $FRONTEND
        npm install 2>&1 | Out-Null
        Pop-Location
        Write-Ok 'Dependencias instaladas'
    }

    Write-Step 'Abriendo ventana del Frontend...'
    $cmdFrontend = "& { `$Host.UI.RawUI.WindowTitle='TFG Frontend :5173'; " +
                   "Write-Host 'Frontend Vite+React  http://localhost:5173' -ForegroundColor Green; " +
                   "Write-Host 'CTRL+C para parar' -ForegroundColor DarkGray; Write-Host ''; " +
                   "Set-Location '$FRONTEND'; npm run dev }"
    Start-Process powershell -ArgumentList '-NoExit', '-Command', $cmdFrontend
    Write-Ok 'Frontend arrancando en http://localhost:5173'
}

# ─── Resumen ───────────────────────────────────────────────────────────────────
Write-Host ''
Write-Host '  URLs de acceso:' -ForegroundColor DarkGray
if (-not $SoloFrontend) {
    Write-Host '    Backend  ->  http://localhost:8000'           -ForegroundColor White
    Write-Host '    Swagger  ->  http://localhost:8000/api/v1/docs' -ForegroundColor White
}
if (-not $SoloBackend) {
    Write-Host '    Frontend ->  http://localhost:5173'           -ForegroundColor White
}
Write-Host ''
Write-Host '  Esta ventana puede cerrarse. Los servicios siguen en sus propias ventanas.' -ForegroundColor DarkGray
Write-Host ''
