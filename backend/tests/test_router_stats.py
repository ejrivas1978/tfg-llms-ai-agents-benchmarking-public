"""
Modulo: test_router_stats
Ruta:   backend/tests/test_router_stats.py

Descripcion:
    Tests de integracion para el endpoint GET /api/v1/stats.
    Se mockea StatsService.obtener para evitar consultas
    a tablas PostgreSQL-especificas que no existen en SQLite.

Sprint: Sprint 4
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from decimal import Decimal

from app.schemas.stats import RespuestaStats
from app.schemas.tarifa import RespuestaListaTarifas


def _tarifas_vacias() -> RespuestaListaTarifas:
    """Tarifas vacias para tests; ADR-028 hizo el campo obligatorio."""
    return RespuestaListaTarifas(
        items=[],
        baseline_entrada_usd_por_mtoken=Decimal("0"),
        baseline_salida_usd_por_mtoken=Decimal("0"),
    )


def _stats_vacias() -> RespuestaStats:
    return RespuestaStats(
        total_evaluaciones=0,
        total_texto_vision=0,
        total_imagen_generativa=0,
        total_evaluadores=0,
        evaluaciones_puntuadas=0,
        metricas_por_modelo=[],
        metricas_imagen_por_modelo=[],
        costes_imagen_por_modo=[],
        tarifas_vigentes=_tarifas_vacias(),
        ratings_imagen_generativa=[],
        heatmap=[],
        jaccard=[],
        evaluaciones_por_semana=[],
        evaluaciones_por_categoria={},
        tasa_rechazo=[],
        comparativa_es_en=[],
    )


class TestRouterStats:
    """Tests de integracion para GET /api/v1/stats."""

    async def test_stats_devuelve_200(self, client: AsyncClient):
        with patch(
            "app.services.stats_service.StatsService.obtener",
            new_callable=lambda: lambda self: AsyncMock(return_value=_stats_vacias())(),
        ):
            with patch(
                "app.routers.stats.StatsService.obtener",
                new=AsyncMock(return_value=_stats_vacias()),
            ):
                respuesta = await client.get("/api/v1/stats")
        assert respuesta.status_code == 200

    async def test_stats_estructura_correcta(self, client: AsyncClient):
        stats = RespuestaStats(
            total_evaluaciones=10,
            total_texto_vision=7,
            total_imagen_generativa=3,
            total_evaluadores=5,
            evaluaciones_puntuadas=4,
            metricas_por_modelo=[],
            metricas_imagen_por_modelo=[],
            costes_imagen_por_modo=[],
            tarifas_vigentes=_tarifas_vacias(),
            ratings_imagen_generativa=[],
            heatmap=[],
            jaccard=[],
            evaluaciones_por_semana=[],
            evaluaciones_por_categoria={"razonamiento": 5, "codigo": 2},
            tasa_rechazo=[],
            comparativa_es_en=[],
        )
        with patch("app.routers.stats.StatsService") as mock_cls:
            mock_servicio = AsyncMock()
            mock_servicio.obtener = AsyncMock(return_value=stats)
            mock_cls.return_value = mock_servicio

            respuesta = await client.get("/api/v1/stats")

        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["total_evaluaciones"] == 10
        assert cuerpo["total_evaluadores"] == 5
        assert "metricas_por_modelo" in cuerpo

    async def test_stats_sin_auth_accesible(self, client: AsyncClient):
        """El endpoint no requiere JWT."""
        with patch("app.routers.stats.StatsService") as mock_cls:
            mock_servicio = AsyncMock()
            mock_servicio.obtener = AsyncMock(return_value=_stats_vacias())
            mock_cls.return_value = mock_servicio

            respuesta = await client.get("/api/v1/stats")

        assert respuesta.status_code == 200
        # Sin cabecera Authorization igualmente devuelve 200
