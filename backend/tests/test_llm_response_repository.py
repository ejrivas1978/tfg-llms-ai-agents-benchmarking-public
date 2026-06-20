"""
Modulo: test_llm_response_repository
Ruta:   backend/tests/test_llm_response_repository.py

Descripcion:
    Tests unitarios para LLMResponseRepository.
    La sesion SQLAlchemy se sustituye por mocks.

Sprint: Sprint 4
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.llm_engine.resultado import ResultadoLLM
from app.models.enums import LLMProvider
from app.repositories.llm_response_repository import LLMResponseRepository


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


def _resultado_all(filas) -> AsyncMock:
    res = MagicMock()
    res.all.return_value = filas
    return AsyncMock(return_value=res)


def _repo(db=None) -> LLMResponseRepository:
    return LLMResponseRepository(db or _db_mock())


def _resultado_llm(
    proveedor: LLMProvider = LLMProvider.claude,
    texto: str = "respuesta",
    es_imagen: bool = False,
    url: str | None = None,
) -> ResultadoLLM:
    return ResultadoLLM(
        proveedor=proveedor,
        modelo="modelo-test",
        texto_respuesta=None if es_imagen else texto,
        tokens_entrada=10,
        tokens_salida=20,
        latencia_ms=500,
        coste_usd=0.001,
        es_imagen=es_imagen,
        url_imagen=url if es_imagen else None,
    )


# ── Tests: crear_desde_resultado ─────────────────────────────────────────────


class TestCrearDesdeResultado:
    async def test_texto_usa_texto_respuesta(self):
        db = _db_mock()
        repo = _repo(db)

        await repo.crear_desde_resultado(1, _resultado_llm(texto="hola mundo"))

        db.add.assert_called_once()
        db.flush.assert_awaited_once()
        db.refresh.assert_awaited_once()

    async def test_imagen_usa_url_como_response_text(self):
        db = _db_mock()
        repo = _repo(db)
        resultado = _resultado_llm(es_imagen=True, url="https://img.ejemplo.com/img.png")

        await repo.crear_desde_resultado(1, resultado)

        # El objeto creado debe tener response_text = url
        llamada = db.add.call_args[0][0]
        assert llamada.response_text == "https://img.ejemplo.com/img.png"

    async def test_error_llm_persiste_tuvo_error(self):
        resultado_error = ResultadoLLM(
            proveedor=LLMProvider.openai,
            modelo="gpt-4o",
            tuvo_error=True,
            mensaje_error="cuota excedida",
        )
        db = _db_mock()
        await _repo(db).crear_desde_resultado(1, resultado_error)

        llamada = db.add.call_args[0][0]
        assert llamada.tuvo_error is True
        assert llamada.error_message == "cuota excedida"


# ── Tests: obtener_por_id ─────────────────────────────────────────────────────


class TestObtenerPorId:
    async def test_devuelve_respuesta_existente(self):
        respuesta = SimpleNamespace(id=1)
        db = _db_mock()
        db.execute = _resultado_escalar(respuesta)

        resultado = await _repo(db).obtener_por_id(1)
        assert resultado is respuesta

    async def test_devuelve_none_si_no_existe(self):
        db = _db_mock()
        db.execute = _resultado_escalar(None)

        resultado = await _repo(db).obtener_por_id(999)
        assert resultado is None


# ── Tests: textos_por_evaluacion_y_proveedor ─────────────────────────────────


class TestTextosPorEvaluacionYProveedor:
    async def test_devuelve_lista_de_dicts(self):
        fila = MagicMock()
        fila._asdict.return_value = {
            "evaluacion_id": 1,
            "provider": LLMProvider.claude,
            "response_text": "texto de respuesta",
        }
        db = _db_mock()
        db.execute = _resultado_all([fila])

        resultado = await _repo(db).textos_por_evaluacion_y_proveedor()

        assert len(resultado) == 1
        assert resultado[0]["provider"] == LLMProvider.claude

    async def test_devuelve_lista_vacia_sin_datos(self):
        db = _db_mock()
        db.execute = _resultado_all([])

        resultado = await _repo(db).textos_por_evaluacion_y_proveedor()
        assert resultado == []


# ── Tests: medias_por_proveedor ───────────────────────────────────────────────


class TestMediasPorProveedor:
    async def test_devuelve_lista_de_dicts(self):
        fila = MagicMock()
        fila._asdict.return_value = {
            "provider": LLMProvider.gemini,
            "n": 5,
            "latencia_ms": 800.0,
            "tokens_entrada": 100.0,
            "tokens_salida": 200.0,
            "tokens_por_segundo": 50.0,
            "cost_usd": 0.01,
            "coste_por_100_palabras": 0.05,
            "palabras": 150.0,
            "diversidad_lexica": 0.8,
            "parrafos": 3.0,
        }
        db = _db_mock()
        db.execute = _resultado_all([fila])

        resultado = await _repo(db).medias_por_proveedor()

        assert len(resultado) == 1
        assert resultado[0]["provider"] == LLMProvider.gemini

    async def test_vacio_sin_datos(self):
        db = _db_mock()
        db.execute = _resultado_all([])
        assert await _repo(db).medias_por_proveedor() == []


# ── Tests: medias_imagen_por_proveedor ────────────────────────────────────────


class TestMediasImagenPorProveedor:
    async def test_devuelve_lista_de_dicts_imagen(self):
        fila = MagicMock()
        fila._asdict.return_value = {
            "provider": LLMProvider.openai,
            "n": 3,
            "latencia_ms": 3200.0,
            "cost_usd": 0.04,
        }
        db = _db_mock()
        db.execute = _resultado_all([fila])

        resultado = await _repo(db).medias_imagen_por_proveedor()
        assert resultado[0]["n"] == 3

    async def test_vacio_sin_datos_imagen(self):
        db = _db_mock()
        db.execute = _resultado_all([])
        assert await _repo(db).medias_imagen_por_proveedor() == []
