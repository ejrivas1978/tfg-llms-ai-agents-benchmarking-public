# ===========================================================
# Dockerfile — Backend FastAPI
# Ruta: backend/Dockerfile
#
# Descripcion:
#     Imagen multi-stage para el backend FastAPI.
#
#     Stage 1 (builder): instala dependencias Python en un
#     entorno virtual aislado.
#
#     Stage 2 (final): copia solo el venv y el codigo fuente.
#     Resultado: imagen de ~300 MB en lugar de ~700 MB si
#     instalara todo en una sola stage. He elegido python:3.11-slim
#     (no alpine) porque asyncpg y Pillow requieren glibc, que
#     no esta disponible en alpine sin mucho trabajo adicional.
#
#     Cloud Run inyecta la variable PORT (por defecto 8080).
#     El entrypoint ejecuta 'alembic upgrade head' antes de
#     arrancar uvicorn para que cada despliegue aplique
#     automaticamente las migraciones pendientes.
#
# Construir localmente (solo para prueba en CI, no en Windows sin Docker):
#     docker build -t tfg-backend .
#
# Sprint: Sprint 4
# ===========================================================

# ── Stage 1: dependencias ─────────────────────────────────
FROM python:3.11-slim AS builder

# He instalado build-essential y libpq-dev porque psycopg2-binary
# y algunas dependencias de Pillow/pdfplumber necesitan compilar
# extensiones C durante la instalacion con pip.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copio solo requirements-prod.txt primero para aprovechar el cache
# de capas de Docker: si no cambian las dependencias, esta capa no
# se reconstruye aunque el codigo fuente haya cambiado.
COPY requirements-prod.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements-prod.txt


# ── Stage 2: imagen final ─────────────────────────────────
FROM python:3.11-slim AS final

# libpq es necesaria en runtime para asyncpg y psycopg2-binary
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Usuario sin privilegios para ejecutar la app (buena practica de seguridad)
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

# Copio los paquetes instalados en el stage builder
COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /usr/local/bin /usr/local/bin

# Copio el codigo fuente, las migraciones y los scripts de administracion
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY scripts/ ./scripts/
COPY alembic.ini .
COPY docker-entrypoint.sh .

# He añadido sed para eliminar los \r (CRLF) que Git en Windows introduce
# en los ficheros de texto. Sin esto el shebang quedaria como '#!/bin/sh\r'
# y Linux no reconoceria el interprete, haciendo que el contenedor falle
# al arrancar con "exec format error".
RUN sed -i 's/\r$//' docker-entrypoint.sh && \
    chmod +x docker-entrypoint.sh && \
    chown -R appuser:appgroup /app

USER appuser

# Cloud Run expone el puerto a traves de la variable PORT.
# La declaramos como documentacion; el valor real lo inyecta Cloud Run.
EXPOSE 8080

ENTRYPOINT ["./docker-entrypoint.sh"]
