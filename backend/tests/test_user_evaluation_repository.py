"""
Modulo: test_user_evaluation_repository
Ruta:   backend/tests/test_user_evaluation_repository.py

Descripcion:
    Tests unitarios para UserEvaluationRepository.
    La sesion SQLAlchemy se sustituye por mocks.

Sprint: Sprint 4
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import LLMProvider, TestCategory
from app.repositories.user_evaluation_repository import UserEvaluationRepository


# ── Helpers ───────────────────────────────────────────────────────────────────


def _db_mock() -> MagicMock:
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    return db


def _resultado_escalar(valor) -> AsyncMock:
    res = MagicMock()
    res.scalar_one_or_none.return_value = valor
    return AsyncMock(return_value=res)


def _resultado_scalars(lista) -> AsyncMock:
    res = MagicMock()
    res.scalars.return_value.all.return_value = lista
    return AsyncMock(return_value=res)


def _resultado_all(filas) -> AsyncMock:
    res = MagicMock()
    res.all.return_value = filas
    return AsyncMock(return_value=res)


def _repo(db=None) -> UserEvaluationRepository:
    return UserEvaluationRepository(db or _db_mock())


# ── Tests: crear ──────────────────────────────────────────────────────────────


class TestCrear:
    async def test_crea_evaluacion_y_llama_flush_refresh(self):
        db = _db_mock()
        await _repo(db).crear(response_id=1, nickname="tester", rating=4, rango_preferencia=1)

        db.add.assert_called_once()
        db.flush.assert_awaited_once()
        db.refresh.assert_awaited_once()

    async def test_sin_rango_preferencia(self):
        db = _db_mock()
        await _repo(db).crear(response_id=2, nickname="anon", rating=3, rango_preferencia=None)
        db.add.assert_called_once()


# ── Tests: obtener_por_response_id ───────────────────────────────────────────


class TestObtenerPorResponseId:
    async def test_devuelve_evaluacion_existente(self):
        eval_orm = SimpleNamespace(id=1, response_id=10)
        db = _db_mock()
        db.execute = _resultado_escalar(eval_orm)

        resultado = await _repo(db).obtener_por_response_id(10)
        assert resultado is eval_orm

    async def test_devuelve_none_si_no_existe(self):
        db = _db_mock()
        db.execute = _resultado_escalar(None)

        resultado = await _repo(db).obtener_por_response_id(999)
        assert resultado is None


# ── Tests: obtener_por_evaluacion_id ─────────────────────────────────────────


class TestObtenerPorEvaluacionId:
    async def test_devuelve_lista_de_evaluaciones(self):
        eval1 = SimpleNamespace(id=1, rango_preferencia=1)
        eval2 = SimpleNamespace(id=2, rango_preferencia=2)
        db = _db_mock()
        db.execute = _resultado_scalars([eval1, eval2])

        resultado = await _repo(db).obtener_por_evaluacion_id(5)
        assert len(resultado) == 2

    async def test_devuelve_lista_vacia(self):
        db = _db_mock()
        db.execute = _resultado_scalars([])

        resultado = await _repo(db).obtener_por_evaluacion_id(999)
        assert resultado == []


# ── Tests: actualizar ─────────────────────────────────────────────────────────


class TestActualizar:
    async def test_actualiza_rating_y_rango(self):
        eval_orm = SimpleNamespace(rating=3, rango_preferencia=2)
        db = _db_mock()

        resultado = await _repo(db).actualizar(eval_orm, rating=5, rango_preferencia=1)

        assert resultado.rating == 5
        assert resultado.rango_preferencia == 1
        db.flush.assert_awaited_once()
        db.refresh.assert_awaited_once()


# ── Tests: ratings_por_proveedor ──────────────────────────────────────────────


class TestRatingsPorProveedor:
    async def test_devuelve_lista_de_dicts(self):
        fila = MagicMock()
        fila._asdict.return_value = {
            "provider": LLMProvider.claude,
            "rating_medio": 4.2,
            "n_puntuadas": 10,
        }
        db = _db_mock()
        db.execute = _resultado_all([fila])

        resultado = await _repo(db).ratings_por_proveedor()
        assert len(resultado) == 1
        assert resultado[0]["rating_medio"] == 4.2

    async def test_vacio_sin_datos(self):
        db = _db_mock()
        db.execute = _resultado_all([])
        assert await _repo(db).ratings_por_proveedor() == []


# ── Tests: ranking_medio_por_proveedor ────────────────────────────────────────


class TestRankingMedioPorProveedor:
    async def test_devuelve_lista_con_rango_medio(self):
        fila = MagicMock()
        fila._asdict.return_value = {"provider": LLMProvider.openai, "rango_medio": 1.8, "n": 5}
        db = _db_mock()
        db.execute = _resultado_all([fila])

        resultado = await _repo(db).ranking_medio_por_proveedor()
        assert resultado[0]["rango_medio"] == 1.8


# ── Tests: ratings_por_proveedor_y_categoria ──────────────────────────────────


class TestRatingsPorProveedorYCategoria:
    async def test_devuelve_lista_de_dicts_con_categoria(self):
        fila = MagicMock()
        fila._asdict.return_value = {
            "provider": LLMProvider.gemini,
            "categoria": TestCategory.razonamiento,
            "rating_medio": 3.5,
            "n": 4,
        }
        db = _db_mock()
        db.execute = _resultado_all([fila])

        resultado = await _repo(db).ratings_por_proveedor_y_categoria()
        assert resultado[0]["categoria"] == TestCategory.razonamiento


# ── Tests: ratings_generacion_imagen_por_proveedor ───────────────────────────


class TestRatingsGeneracionImagenPorProveedor:
    async def test_devuelve_lista_de_imagen(self):
        fila = MagicMock()
        fila._asdict.return_value = {"provider": LLMProvider.grok, "rating_medio": 4.0, "n": 2}
        db = _db_mock()
        db.execute = _resultado_all([fila])

        resultado = await _repo(db).ratings_generacion_imagen_por_proveedor()
        assert resultado[0]["n"] == 2


# ── Tests: tasa_rechazo_por_proveedor ─────────────────────────────────────────


class TestTasaRechazoPorProveedor:
    async def test_devuelve_tasa_correcta(self):
        fila = MagicMock()
        fila._asdict.return_value = {
            "provider": LLMProvider.openai,
            "total": 10,
            "rechazos": 2,
        }
        db = _db_mock()
        db.execute = _resultado_all([fila])

        resultado = await _repo(db).tasa_rechazo_por_proveedor()
        assert resultado[0]["rechazos"] == 2

    async def test_sin_datos_devuelve_lista_vacia(self):
        db = _db_mock()
        db.execute = _resultado_all([])
        assert await _repo(db).tasa_rechazo_por_proveedor() == []
