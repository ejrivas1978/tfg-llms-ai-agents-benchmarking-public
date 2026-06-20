"""
Modulo: test_evaluacion_service
Ruta:   backend/tests/test_evaluacion_service.py

Descripcion:
    Tests unitarios para EvaluacionService.
    Los repositorios se sustituyen por mocks para aislar la logica
    de validacion de negocio sin necesidad de base de datos.

    Casos cubiertos:
    - crear: respuesta inexistente (404), nickname incorrecto (403),
      creacion nueva, actualizacion de evaluacion existente
    - obtener_por_evaluacion: lista con resultados y lista vacia

Sprint: Sprint 4
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.services.evaluacion_service import EvaluacionService


# ── Helpers ───────────────────────────────────────────────────────────────────


def _respuesta_llm(id: int = 1, nickname_evaluacion: str = "evaluador") -> SimpleNamespace:
    """Imita LLMResponse con el benchmark adjunto que lleva el nickname."""
    benchmark = SimpleNamespace(nickname=nickname_evaluacion)
    return SimpleNamespace(id=id, benchmark=benchmark)


def _evaluacion_orm(
    id: int = 1,
    response_id: int = 1,
    nickname: str = "evaluador",
    rating: int = 4,
    rango_preferencia: int = 1,
) -> SimpleNamespace:
    """Imita UserEvaluation con los atributos minimos."""
    return SimpleNamespace(
        id=id,
        response_id=response_id,
        nickname=nickname,
        rating=rating,
        rango_preferencia=rango_preferencia,
        created_at=datetime(2026, 5, 1, 10, 0, 0),
    )


def _servicio(repo_resp: MagicMock, repo_eval: MagicMock) -> EvaluacionService:
    """Instancia EvaluacionService con repos mockeados."""
    db = MagicMock()
    servicio = EvaluacionService(db)
    servicio._resp_repo = repo_resp
    servicio._eval_repo = repo_eval
    return servicio


# ── Tests: crear ──────────────────────────────────────────────────────────────


class TestCrear:
    """Pruebas para EvaluacionService.crear."""

    async def test_respuesta_inexistente_lanza_404(self):
        repo_resp = MagicMock()
        repo_resp.obtener_por_id = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await _servicio(repo_resp, MagicMock()).crear(99, "evaluador", 4, 1)
        assert exc_info.value.status_code == 404

    async def test_nickname_incorrecto_lanza_403(self):
        repo_resp = MagicMock()
        repo_resp.obtener_por_id = AsyncMock(return_value=_respuesta_llm(nickname_evaluacion="otro_nick"))

        with pytest.raises(HTTPException) as exc_info:
            await _servicio(repo_resp, MagicMock()).crear(1, "evaluador", 4, 1)
        assert exc_info.value.status_code == 403

    async def test_crea_evaluacion_nueva_cuando_no_existe(self):
        repo_resp = MagicMock()
        repo_resp.obtener_por_id = AsyncMock(return_value=_respuesta_llm())
        repo_eval = MagicMock()
        repo_eval.obtener_por_response_id = AsyncMock(return_value=None)
        nueva_eval = _evaluacion_orm(rating=4)
        repo_eval.crear = AsyncMock(return_value=nueva_eval)

        resultado = await _servicio(repo_resp, repo_eval).crear(1, "evaluador", 4, 1)

        repo_eval.crear.assert_called_once_with(
            response_id=1, nickname="evaluador", rating=4, rango_preferencia=1
        )
        assert resultado.rating == 4
        assert resultado.nickname == "evaluador"

    async def test_actualiza_evaluacion_cuando_ya_existe(self):
        """Si ya existe una evaluacion para esa respuesta, se actualiza en lugar de crear."""
        repo_resp = MagicMock()
        repo_resp.obtener_por_id = AsyncMock(return_value=_respuesta_llm())
        repo_eval = MagicMock()
        existente = _evaluacion_orm(rating=2)
        repo_eval.obtener_por_response_id = AsyncMock(return_value=existente)
        actualizada = _evaluacion_orm(rating=5)
        repo_eval.actualizar = AsyncMock(return_value=actualizada)

        resultado = await _servicio(repo_resp, repo_eval).crear(1, "evaluador", 5, 1)

        repo_eval.actualizar.assert_called_once_with(
            evaluacion=existente, rating=5, rango_preferencia=1
        )
        repo_eval.crear.assert_not_called()
        assert resultado.rating == 5

    async def test_respuesta_contiene_todos_los_campos(self):
        repo_resp = MagicMock()
        repo_resp.obtener_por_id = AsyncMock(return_value=_respuesta_llm())
        repo_eval = MagicMock()
        repo_eval.obtener_por_response_id = AsyncMock(return_value=None)
        eval_creada = _evaluacion_orm(id=7, response_id=1, nickname="evaluador", rating=3, rango_preferencia=2)
        repo_eval.crear = AsyncMock(return_value=eval_creada)

        resultado = await _servicio(repo_resp, repo_eval).crear(1, "evaluador", 3, 2)

        assert resultado.id == 7
        assert resultado.response_id == 1
        assert resultado.rating == 3
        assert resultado.rango_preferencia == 2


# ── Tests: obtener_por_evaluacion ─────────────────────────────────────────────


class TestObtenerPorEvaluacion:
    """Pruebas para EvaluacionService.obtener_por_evaluacion."""

    async def test_devuelve_lista_de_evaluaciones(self):
        evals = [_evaluacion_orm(id=1), _evaluacion_orm(id=2)]
        repo_eval = MagicMock()
        repo_eval.obtener_por_evaluacion_id = AsyncMock(return_value=evals)

        resultado = await _servicio(MagicMock(), repo_eval).obtener_por_evaluacion(42)

        assert len(resultado) == 2
        assert resultado[0].id == 1
        assert resultado[1].id == 2

    async def test_devuelve_lista_vacia_cuando_no_hay_evaluaciones(self):
        repo_eval = MagicMock()
        repo_eval.obtener_por_evaluacion_id = AsyncMock(return_value=[])

        resultado = await _servicio(MagicMock(), repo_eval).obtener_por_evaluacion(42)

        assert resultado == []

    async def test_mapea_campos_correctamente(self):
        eval_orm = _evaluacion_orm(id=5, rating=4, rango_preferencia=1)
        repo_eval = MagicMock()
        repo_eval.obtener_por_evaluacion_id = AsyncMock(return_value=[eval_orm])

        resultado = await _servicio(MagicMock(), repo_eval).obtener_por_evaluacion(1)

        assert resultado[0].rating == 4
        assert resultado[0].rango_preferencia == 1
