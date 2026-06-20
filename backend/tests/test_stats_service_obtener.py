"""
Modulo: test_stats_service_obtener
Ruta:   backend/tests/test_stats_service_obtener.py

Descripcion:
    Tests unitarios para StatsService.obtener().
    Se mockean los tres repositorios (benchmark_repo, respuesta_repo, eval_repo)
    para cubrir el metodo que agrega las 12 consultas en cascada.

Sprint: Sprint 4
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import LLMProvider, TestCategory
from app.schemas.stats import RespuestaStats
from app.services.stats_service import StatsService


# ── Helpers ───────────────────────────────────────────────────────────────────


def _servicio_con_repos(
    benchmark_repo=None,
    respuesta_repo=None,
    eval_repo=None,
) -> StatsService:
    """Construye un StatsService con repositorios mockeados."""
    db = MagicMock()
    servicio = StatsService(db)
    if benchmark_repo is not None:
        servicio._benchmark_repo = benchmark_repo
    if respuesta_repo is not None:
        servicio._respuesta_repo = respuesta_repo
    if eval_repo is not None:
        servicio._eval_repo = eval_repo
    return servicio


def _benchmark_repo_mock(
    total: int = 5,
    imagen: int = 2,
    evaluadores: int = 3,
    puntuadas: int = 1,
) -> AsyncMock:
    repo = AsyncMock()
    repo.contar_evaluaciones = AsyncMock(return_value=total)
    repo.contar_evaluaciones_imagen_generativa = AsyncMock(return_value=imagen)
    repo.contar_evaluadores = AsyncMock(return_value=evaluadores)
    repo.contar_evaluaciones_puntuadas = AsyncMock(return_value=puntuadas)
    repo.evaluaciones_por_semana = AsyncMock(return_value=[])
    repo.evaluaciones_por_categoria = AsyncMock(return_value={})
    return repo


def _respuesta_repo_mock() -> AsyncMock:
    repo = AsyncMock()
    repo.medias_por_proveedor = AsyncMock(return_value=[])
    repo.medias_imagen_por_proveedor = AsyncMock(return_value=[])
    repo.costes_imagen_por_proveedor_y_modo = AsyncMock(return_value=[])
    repo.textos_por_evaluacion_y_proveedor = AsyncMock(return_value=[])
    repo.medias_comparativa_es_en = AsyncMock(return_value=[])
    return repo


def _eval_repo_mock() -> AsyncMock:
    repo = AsyncMock()
    repo.ratings_por_proveedor = AsyncMock(return_value=[])
    repo.ranking_medio_por_proveedor = AsyncMock(return_value=[])
    repo.ratings_por_proveedor_y_categoria = AsyncMock(return_value=[])
    repo.ratings_generacion_imagen_por_proveedor = AsyncMock(return_value=[])
    repo.ranking_generacion_imagen_por_proveedor = AsyncMock(return_value=[])
    repo.metricas_humanas_imagen_por_subcategoria = AsyncMock(return_value=[])
    repo.tasa_rechazo_por_proveedor = AsyncMock(return_value=[])
    return repo


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestStatsServiceObtener:
    """Pruebas para StatsService.obtener()."""

    async def test_devuelve_respuesta_stats(self):
        servicio = _servicio_con_repos(
            benchmark_repo=_benchmark_repo_mock(),
            respuesta_repo=_respuesta_repo_mock(),
            eval_repo=_eval_repo_mock(),
        )
        resultado = await servicio.obtener()
        assert isinstance(resultado, RespuestaStats)

    async def test_total_evaluaciones_correcto(self):
        servicio = _servicio_con_repos(
            benchmark_repo=_benchmark_repo_mock(total=10, imagen=3),
            respuesta_repo=_respuesta_repo_mock(),
            eval_repo=_eval_repo_mock(),
        )
        resultado = await servicio.obtener()
        assert resultado.total_evaluaciones == 10
        assert resultado.total_imagen_generativa == 3
        assert resultado.total_texto_vision == 7

    async def test_evaluadores_y_puntuadas(self):
        servicio = _servicio_con_repos(
            benchmark_repo=_benchmark_repo_mock(evaluadores=7, puntuadas=4),
            respuesta_repo=_respuesta_repo_mock(),
            eval_repo=_eval_repo_mock(),
        )
        resultado = await servicio.obtener()
        assert resultado.total_evaluadores == 7
        assert resultado.evaluaciones_puntuadas == 4

    async def test_semanas_se_mapean_correctamente(self):
        repo_bench = _benchmark_repo_mock()
        repo_bench.evaluaciones_por_semana = AsyncMock(
            return_value=[{"semana": "2026-W18", "total": 3}, {"semana": "2026-W19", "total": 5}]
        )
        servicio = _servicio_con_repos(
            benchmark_repo=repo_bench,
            respuesta_repo=_respuesta_repo_mock(),
            eval_repo=_eval_repo_mock(),
        )
        resultado = await servicio.obtener()
        assert len(resultado.evaluaciones_por_semana) == 2
        assert resultado.evaluaciones_por_semana[0].semana == "2026-W18"
        assert resultado.evaluaciones_por_semana[1].total == 5

    async def test_por_categoria_se_devuelve(self):
        repo_bench = _benchmark_repo_mock()
        repo_bench.evaluaciones_por_categoria = AsyncMock(
            return_value={"razonamiento": 3, "codigo": 2}
        )
        servicio = _servicio_con_repos(
            benchmark_repo=repo_bench,
            respuesta_repo=_respuesta_repo_mock(),
            eval_repo=_eval_repo_mock(),
        )
        resultado = await servicio.obtener()
        assert resultado.evaluaciones_por_categoria["razonamiento"] == 3

    async def test_listas_vacias_devuelve_listas_vacias(self):
        servicio = _servicio_con_repos(
            benchmark_repo=_benchmark_repo_mock(),
            respuesta_repo=_respuesta_repo_mock(),
            eval_repo=_eval_repo_mock(),
        )
        resultado = await servicio.obtener()
        assert resultado.metricas_por_modelo == []
        assert resultado.heatmap == []
        assert resultado.jaccard == []
        assert resultado.tasa_rechazo == []
