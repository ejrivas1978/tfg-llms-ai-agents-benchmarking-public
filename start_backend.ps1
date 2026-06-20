#Requires -Version 5.1
$ROOT    = Split-Path $MyInvocation.MyCommand.Path -Parent
$BACKEND = Join-Path $ROOT "backend"
$UVICORN = Join-Path $BACKEND ".venv-tfg-llm\Scripts\uvicorn.exe"
$PG_BIN  = "C:\Program Files\PostgreSQL\15\bin"
$PG_SVC  = "postgresql-15"

if ($env:PATH -notlike "*$PG_BIN*") { $env:PATH += ";$PG_BIN" }

$svc = Get-Service -Name $PG_SVC -ErrorAction SilentlyContinue
if ($null -eq $svc) {
    Write-Host "[X] Servicio '$PG_SVC' no encontrado. Ejecuta .\scripts\setup_local.ps1 primero." -ForegroundColor Red
    exit 1
}
if ($svc.Status -ne "Running") {
    Write-Host "[!] Arrancando PostgreSQL..." -ForegroundColor Yellow
    Start-Service $PG_SVC
    Start-Sleep -Seconds 2
}

Write-Host ""
Write-Host "  Backend: http://localhost:8000" -ForegroundColor Green
Write-Host "  API docs: http://localhost:8000/api/v1/docs" -ForegroundColor DarkGray
Write-Host "  CTRL+C para parar" -ForegroundColor DarkGray
Write-Host ""

Set-Location $BACKEND
& $UVICORN app.main:app --reload --port 8000
