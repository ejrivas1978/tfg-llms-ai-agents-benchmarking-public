#!/bin/sh
# ===========================================================
# Script:  docker-entrypoint.sh
# Ruta:    backend/docker-entrypoint.sh
#
# Descripcion:
#     Punto de entrada del contenedor backend en Cloud Run.
#     Ejecuta las migraciones de Alembic antes de arrancar
#     uvicorn para garantizar que el esquema de BD esta
#     actualizado en cada despliegue.
#
#     He elegido ejecutar las migraciones en el entrypoint
#     en lugar de en un Job de Cloud Run separado para
#     simplificar el pipeline de despliegue del TFG.
#     La desventaja es que si hay dos instancias arrancando
#     en paralelo ambas intentan migrar; Alembic tiene un
#     bloqueo de tabla (advisory lock en PostgreSQL) que
#     evita conflictos. Para produccion real se recomienda
#     un Job de migracion separado.
#
#     El puerto lo lee de la variable PORT que Cloud Run
#     inyecta automaticamente (por defecto 8080).
#
# Sprint: Sprint 4
# ===========================================================
set -e

echo "[entrypoint] Ejecutando migraciones Alembic..."
alembic upgrade head

echo "[entrypoint] Iniciando FastAPI con uvicorn en puerto ${PORT:-8080}..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8080}" \
    --workers 1 \
    --no-access-log
