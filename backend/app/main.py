"""
Modulo: main
Ruta:   backend/app/main.py

Descripcion:
    Factoria de la aplicacion FastAPI. Configura middleware, monta los routers
    y expone la app ASGI que consume uvicorn.

    Arrancar el servidor con:
        cd backend && uvicorn app.main:app --reload --port 8000

    Endpoints montados:
        /api/v1/auth        -> autenticacion del administrador
        /api/v1/usuarios    -> autenticacion de usuarios web
        /api/v1/benchmarks  -> ejecucion y consulta de sesiones
        /api/v1/evaluaciones-> valoraciones de usuario
        /api/v1/stats       -> estadisticas del dashboard
        /api/v1/admin       -> gestion de datos (solo administrador)
        /api/v1/upload      -> extraccion de texto desde ficheros

Dependencias:
    - fastapi>=0.115
    - app.core.config

Sprint: Sprint 2
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import get_settings
from app.core.database import SesionLocalAsincrona
from app.llm_engine.metricas import refrescar_cache_precios
from app.middleware.rate_limit import limitador
from app.routers import admin, auth, benchmark, evaluacion, stats, upload_router, usuarios

logger = logging.getLogger(__name__)
_configuracion = get_settings()


@asynccontextmanager
async def ciclo_vida(app: FastAPI) -> AsyncGenerator[None, None]:
    """Gestiona los eventos de arranque y apagado de la aplicacion.

    Arranque:
      - Hidrata el cache en memoria de tarifas LLM desde la tabla tarifas_llm
        para que las primeras llamadas LLM ya usen los precios reales y no
        los defaults hardcoded de metricas.py.

    Apagado: aqui va la logica de limpieza (ej: cerrar clientes externos).

    Args:
        app: Instancia de la aplicacion FastAPI.
    """
    # arranque: cache de tarifas
    try:
        async with SesionLocalAsincrona() as db:
            await refrescar_cache_precios(db)
    except Exception as exc:
        # No queremos que un fallo de BD impida arrancar el servidor:
        # los defaults hardcoded de metricas.py funcionan como fallback.
        logger.warning("No se pudo hidratar cache de tarifas al arranque: %s", exc)
    yield
    # apagado


_en_produccion = _configuracion.environment == "production"

# B2-seguridad: Swagger y OpenAPI deshabilitados en produccion para
# no exponer la superficie de ataque de la API publicamente.
app = FastAPI(
    title=_configuracion.app_name,
    version=_configuracion.app_version,
    docs_url=None if _en_produccion else f"{_configuracion.api_prefix}/docs",
    redoc_url=None if _en_produccion else f"{_configuracion.api_prefix}/redoc",
    openapi_url=None if _en_produccion else f"{_configuracion.api_prefix}/openapi.json",
    lifespan=ciclo_vida,
)

app.state.limiter = limitador
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# B1-seguridad: metodos y cabeceras restringidos a los que usa el frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_configuracion.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router, prefix=_configuracion.api_prefix)
app.include_router(usuarios.router, prefix=_configuracion.api_prefix)
app.include_router(benchmark.router, prefix=_configuracion.api_prefix)
app.include_router(evaluacion.router, prefix=_configuracion.api_prefix)
app.include_router(stats.router, prefix=_configuracion.api_prefix)
app.include_router(admin.router, prefix=_configuracion.api_prefix)
app.include_router(upload_router.router, prefix=_configuracion.api_prefix)


@app.get("/", include_in_schema=False)
async def raiz() -> RedirectResponse:
    """Redirige la raiz a la documentacion interactiva de la API."""
    return RedirectResponse(url=f"{_configuracion.api_prefix}/docs")


@app.get(
    f"{_configuracion.api_prefix}/health",
    tags=["infraestructura"],
    summary="Comprobacion de estado del servicio",
    description="Endpoint usado por balanceadores de carga y pipelines CI para verificar que el servicio esta activo.",
)
async def health_check() -> dict[str, str]:
    """Devuelve el estado de salud de la aplicacion.

    Returns:
        Objeto JSON con la clave 'status' con valor 'ok'.
    """
    return {"status": "ok"}
