#Requires -Version 5.1
$ROOT    = Split-Path $PSScriptRoot -Parent
$BACKEND = Join-Path $ROOT "backend"
$ALEMBIC = Join-Path $BACKEND ".venv-tfg-llm\Scripts\alembic.exe"

Write-Host ""
Write-Host "  TFG -- Migracion inicial de base de datos" -ForegroundColor White
Write-Host "  ==========================================" -ForegroundColor DarkGray
Write-Host ""

Set-Location $BACKEND

Write-Host "==> Generando migracion inicial..." -ForegroundColor Cyan
& $ALEMBIC revision --autogenerate -m "initial_schema"
if ($LASTEXITCODE -ne 0) {
    Write-Host "    [X] Error al generar la migracion" -ForegroundColor Red
    exit 1
}
Write-Host "    [OK] Fichero de migracion generado" -ForegroundColor Green

Write-Host ""
Write-Host "==> Aplicando migracion (upgrade head)..." -ForegroundColor Cyan
& $ALEMBIC upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Host "    [X] Error al aplicar la migracion" -ForegroundColor Red
    exit 1
}
Write-Host "    [OK] Schema aplicado en la base de datos" -ForegroundColor Green

Write-Host ""
Write-Host "==> Verificando tablas creadas..." -ForegroundColor Cyan
$tables = & psql -U postgres -d tfg_llm_db -tAc "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename" 2>&1
Write-Host "    Tablas en tfg_llm_db:" -ForegroundColor DarkGray
$tables | ForEach-Object { Write-Host "      - $_" -ForegroundColor Yellow }

Write-Host ""
Write-Host "  ==========================================" -ForegroundColor DarkGray
Write-Host "  Migracion completada." -ForegroundColor White
Write-Host ""
