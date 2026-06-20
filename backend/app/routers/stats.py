"""
Modulo: routers.stats
Ruta:   backend/app/routers/stats.py

Descripcion:
    Capa HTTP para el endpoint del dashboard de estadisticas.
    Devuelve todos los datos necesarios para los 13 graficos del dashboard
    en una sola peticion, reduciendo la latencia percibida por el usuario.

    Endpoints:
        GET /api/v1/stats  -> RespuestaStats  200

Dependencias:
    - fastapi
    - app.core.database
    - app.schemas.stats
    - app.services.stats_service

Sprint: Sprint 2
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.stats import RespuestaStats
from app.services.stats_service import StatsService

router = APIRouter(prefix="/stats", tags=["estadisticas"])


@router.get(
    "",
    response_model=RespuestaStats,
    summary="Estadisticas agregadas para el dashboard",
    description=(
        "Devuelve en una sola llamada todos los datos necesarios para el dashboard: "
        "KPIs globales, metricas automaticas por modelo, heatmap de valoraciones, "
        "matriz de similitud Jaccard, evolucion semanal y distribucion por categoria. "
        "No requiere autenticacion."
    ),
)
async def obtener_stats(
    db: AsyncSession = Depends(get_db),
) -> RespuestaStats:
    """Agrega y devuelve todas las estadisticas del dashboard.

    Args:
        db: Sesion de base de datos asincrona.

    Returns:
        RespuestaStats con los 13 graficos del dashboard.
    """
    servicio = StatsService(db)
    return await servicio.obtener()
