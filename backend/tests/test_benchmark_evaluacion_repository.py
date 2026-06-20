"""
Modulo: test_benchmark_evaluacion_repository
Ruta:   backend/tests/test_benchmark_evaluacion_repository.py

Descripcion:
    Tests unitarios para BenchmarkEvaluacionRepository.
    La sesion SQLAlchemy se sustituye por mocks para evitar
    dependencias de PostgreSQL.

Sprint: Sprint 4
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import SessionStatus, TestCategory
from app.repositories.benchmark_evaluacion_repository import BenchmarkEvaluacionRepository


# ── Helpers ───────────────────────────────────────────────────────────────────


def _db_mock() -> MagicMock:
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    return db


def _resultado_escalar(valor) -> AsyncMock:
    res = MagicMock()
    res.scalar_one.return_value = valor
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


def _repo(db=None) -> BenchmarkEvaluacionRepository:
    return BenchmarkEvaluacionRepository(db or _db_mock())


# ── Tests: crear ──────────────────────────────────────────────────────────────


class TestCrear:
    async def test_crear_llama_add_flush_refresh(self):
        db = _db_mock()
        db.refresh = AsyncMock(side_effect=lambda obj: None)
        repo = _repo(db)

        evaluacion = await repo.crear("tester", "prompt", TestCategory.razonamiento)

        db.add.assert_called_once()
        db.flush.assert_awaited_once()
        db.refresh.assert_awaited_once()

    async def test_crear_imagen_generativa(self):
        db = _db_mock()
        repo = _repo(db)
        await repo.crear("user", "prompt imagen", TestCategory.imagen, es_generacion_imagen=True)
        db.add.assert_called_once()


# ── Tests: obtener_por_id ─────────────────────────────────────────────────────


class TestObtenerPorId:
    async def test_devuelve_evaluacion_existente(self):
        evaluacion = SimpleNamespace(id=1, nickname="test")
        db = _db_mock()
        db.execute = _resultado_escalar(evaluacion)

        resultado = await _repo(db).obtener_por_id(1)
        assert resultado is evaluacion

    async def test_devuelve_none_si_no_existe(self):
        db = _db_mock()
        db.execute = _resultado_escalar(None)

        resultado = await _repo(db).obtener_por_id(999)
        assert resultado is None


# ── Tests: actualizar_estado ──────────────────────────────────────────────────


class TestActualizarEstado:
    async def test_actualiza_estado_y_llama_flush(self):
        evaluacion = SimpleNamespace(status=SessionStatus.pendiente)
        db = _db_mock()
        repo = _repo(db)

        resultado = await repo.actualizar_estado(evaluacion, SessionStatus.completada)

        assert resultado.status == SessionStatus.completada
        db.flush.assert_awaited_once()


# ── Tests: actualizar_jaccard ─────────────────────────────────────────────────


class TestActualizarJaccard:
    async def test_actualiza_jaccard(self):
        evaluacion = SimpleNamespace(similitud_jaccard_media=None)
        db = _db_mock()

        resultado = await _repo(db).actualizar_jaccard(evaluacion, 0.75)

        assert resultado.similitud_jaccard_media == 0.75

    async def test_acepta_none(self):
        evaluacion = SimpleNamespace(similitud_jaccard_media=0.5)
        resultado = await _repo().actualizar_jaccard(evaluacion, None)
        assert resultado.similitud_jaccard_media is None


# ── Tests: contar_* ───────────────────────────────────────────────────────────


class TestContadores:
    async def test_contar_evaluaciones(self):
        db = _db_mock()
        db.execute = _resultado_escalar(42)
        assert await _repo(db).contar_evaluaciones() == 42

    async def test_contar_imagen_generativa(self):
        db = _db_mock()
        db.execute = _resultado_escalar(5)
        assert await _repo(db).contar_evaluaciones_imagen_generativa() == 5

    async def test_contar_evaluadores(self):
        db = _db_mock()
        db.execute = _resultado_escalar(7)
        assert await _repo(db).contar_evaluadores() == 7

    async def test_contar_puntuadas(self):
        db = _db_mock()
        db.execute = _resultado_escalar(3)
        assert await _repo(db).contar_evaluaciones_puntuadas() == 3


# ── Tests: eliminar ───────────────────────────────────────────────────────────


class TestEliminar:
    async def test_eliminar_llama_delete_y_flush(self):
        evaluacion = SimpleNamespace(id=1)
        db = _db_mock()

        await _repo(db).eliminar(evaluacion)

        db.delete.assert_awaited_once_with(evaluacion)
        db.flush.assert_awaited_once()

    async def test_eliminar_todas_devuelve_count(self):
        eval1 = SimpleNamespace(id=1)
        eval2 = SimpleNamespace(id=2)
        db = _db_mock()
        db.execute = _resultado_scalars([eval1, eval2])

        count = await _repo(db).eliminar_todas()

        assert count == 2
        assert db.delete.await_count == 2

    async def test_eliminar_por_nickname(self):
        eval1 = SimpleNamespace(id=1, nickname="user1")
        db = _db_mock()
        db.execute = _resultado_scalars([eval1])

        count = await _repo(db).eliminar_por_nickname("user1")

        assert count == 1
        db.delete.assert_awaited_once_with(eval1)


# ── Tests: evaluaciones_por_categoria ────────────────────────────────────────


class TestEvaluacionesPorCategoria:
    async def test_devuelve_dict_categoria_total(self):
        fila = MagicMock()
        fila.category.value = "razonamiento"
        fila.total = 5
        db = _db_mock()
        res = MagicMock()
        res.all.return_value = [fila]
        db.execute = AsyncMock(return_value=res)

        resultado = await _repo(db).evaluaciones_por_categoria()

        assert resultado == {"razonamiento": 5}

    async def test_devuelve_dict_vacio_sin_datos(self):
        db = _db_mock()
        res = MagicMock()
        res.all.return_value = []
        db.execute = AsyncMock(return_value=res)

        resultado = await _repo(db).evaluaciones_por_categoria()
        assert resultado == {}


# ── Tests: evaluaciones_por_semana ───────────────────────────────────────────


class TestEvaluacionesPorSemana:
    async def test_devuelve_lista_de_dicts(self):
        fila = MagicMock()
        fila._asdict.return_value = {"semana": "2026-W18", "total": 3}
        db = _db_mock()
        res = MagicMock()
        res.all.return_value = [fila]
        db.execute = AsyncMock(return_value=res)

        resultado = await _repo(db).evaluaciones_por_semana()

        assert len(resultado) == 1
        assert resultado[0]["semana"] == "2026-W18"
