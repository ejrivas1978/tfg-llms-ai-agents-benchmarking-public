"""
Modulo: test_benchmark_service_dto
Ruta:   backend/tests/test_benchmark_service_dto.py

Descripcion:
    Tests unitarios para los metodos de BenchmarkService no cubiertos
    por test_benchmark_service.py: _construir_dto, obtener_por_id
    y los casos de validacion rapida de ejecutar (cuota agotada, sin clientes).

    Metodos cubiertos:
    - _construir_dto: mapeo de ORM a DTO para texto e imagen
    - obtener_por_id: evaluacion no encontrada (404) y recuperacion exitosa
    - ejecutar: cuota agotada (402) y sin clientes LLM (503)

Sprint: Sprint 4
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.enums import SessionStatus, TestCategory
from app.services.benchmark_service import BenchmarkService


# ── Helpers ───────────────────────────────────────────────────────────────────


def _respuesta_orm(
    id: int = 1,
    provider: str = "claude",
    model_name: str = "claude-sonnet",
    response_text: str = "respuesta de ejemplo",
    tuvo_error: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        provider=provider,
        model_name=model_name,
        response_text=response_text,
        input_tokens=10,
        output_tokens=20,
        latency_ms=800,
        tokens_por_segundo=25.0,
        ratio_sal_ent=2.0,
        cost_usd=0.0005,
        coste_por_100_palabras=0.01,
        palabras=4,
        diversidad_lexica=1.0,
        parrafos=1,
        tuvo_error=tuvo_error,
        error_message=None,
        imagen_miniatura=None,
        idioma_prompt="es",
    )


def _evaluacion_orm(
    id: int = 1,
    nickname: str = "evaluador",
    prompt: str = "prompt de prueba",
    es_generacion_imagen: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        nickname=nickname,
        prompt=prompt,
        category=TestCategory.razonamiento,
        status=SessionStatus.completada,
        similitud_jaccard_media=0.75,
        created_at=datetime(2026, 5, 1, 10, 0, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 5, 1, 10, 1, 0, tzinfo=timezone.utc),
        es_generacion_imagen=es_generacion_imagen,
        respuestas=[],
    )


def _servicio() -> BenchmarkService:
    db = MagicMock()
    return BenchmarkService(db)


# ── Tests: _construir_dto ─────────────────────────────────────────────────────


class TestConstruirDto:
    """Pruebas para BenchmarkService._construir_dto."""

    def test_mapea_id_y_nickname(self):
        evaluacion = _evaluacion_orm(id=42, nickname="tester")
        servicio = _servicio()
        resultado = servicio._construir_dto(evaluacion, [], False)
        assert resultado.id == 42
        assert resultado.nickname == "tester"

    def test_respuestas_texto_incluyen_texto(self):
        evaluacion = _evaluacion_orm()
        resp = _respuesta_orm(response_text="hola mundo")
        servicio = _servicio()
        resultado = servicio._construir_dto(evaluacion, [resp], False)
        assert len(resultado.respuestas) == 1
        assert resultado.respuestas[0].texto_respuesta == "hola mundo"

    def test_respuestas_imagen_ocultan_texto(self):
        """Para imagenes, texto_respuesta debe ser None; url_imagen tiene el valor."""
        evaluacion = _evaluacion_orm(es_generacion_imagen=True)
        resp = _respuesta_orm(response_text="https://url.de.imagen.com/img.png")
        servicio = _servicio()
        resultado = servicio._construir_dto(evaluacion, [resp], True)
        assert resultado.respuestas[0].texto_respuesta is None
        assert resultado.respuestas[0].url_imagen == "https://url.de.imagen.com/img.png"

    def test_lista_vacia_de_respuestas(self):
        evaluacion = _evaluacion_orm()
        servicio = _servicio()
        resultado = servicio._construir_dto(evaluacion, [], False)
        assert resultado.respuestas == []

    def test_multiples_respuestas(self):
        evaluacion = _evaluacion_orm()
        respuestas = [
            _respuesta_orm(id=1, provider="claude"),
            _respuesta_orm(id=2, provider="openai"),
        ]
        servicio = _servicio()
        resultado = servicio._construir_dto(evaluacion, respuestas, False)
        assert len(resultado.respuestas) == 2


# ── Tests: obtener_por_id ─────────────────────────────────────────────────────


class TestObtenerPorId:
    """Pruebas para BenchmarkService.obtener_por_id."""

    async def test_evaluacion_inexistente_lanza_404(self):
        servicio = _servicio()
        servicio._benchmark_repo = MagicMock()
        servicio._benchmark_repo.obtener_por_id = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await servicio.obtener_por_id(999)
        assert exc_info.value.status_code == 404

    async def test_evaluacion_existente_devuelve_dto(self):
        evaluacion = _evaluacion_orm(id=7, nickname="tester")
        evaluacion.respuestas = [_respuesta_orm()]
        servicio = _servicio()
        servicio._benchmark_repo = MagicMock()
        servicio._benchmark_repo.obtener_por_id = AsyncMock(return_value=evaluacion)

        resultado = await servicio.obtener_por_id(7)
        assert resultado.id == 7
        assert resultado.nickname == "tester"


# ── Tests: ejecutar — validaciones rapidas ────────────────────────────────────


class TestEjecutarValidaciones:
    """Pruebas para BenchmarkService.ejecutar: casos de error temprano."""

    async def test_cuota_agotada_lanza_402(self):
        usuario = SimpleNamespace(consultas_usadas=10, cuota_asignada=10)
        servicio = _servicio()

        with pytest.raises(HTTPException) as exc_info:
            await servicio.ejecutar(
                nickname="evaluador",
                prompt="prompt",
                categoria=TestCategory.razonamiento,
                usuario_app=usuario,
            )
        assert exc_info.value.status_code == 402

    async def test_sin_clientes_lanza_503(self):
        usuario = SimpleNamespace(consultas_usadas=0, cuota_asignada=10)
        servicio = _servicio()

        with (
            patch("app.services.benchmark_service.get_settings") as mock_settings,
            patch("app.services.benchmark_service.construir_clientes", return_value=[]),
        ):
            mock_settings.return_value = MagicMock(
                anthropic_api_key=None,
                openai_api_key=None,
                google_api_key=None,
                xai_api_key=None,
            )
            with pytest.raises(HTTPException) as exc_info:
                await servicio.ejecutar(
                    nickname="evaluador",
                    prompt="prompt",
                    categoria=TestCategory.razonamiento,
                    usuario_app=usuario,
                )
        assert exc_info.value.status_code == 503

    async def test_admin_sin_cuota_no_lanza_402(self):
        """Si usuario_app es None (admin), no se comprueba la cuota."""
        servicio = _servicio()

        with (
            patch("app.services.benchmark_service.get_settings") as mock_settings,
            patch("app.services.benchmark_service.construir_clientes", return_value=[]),
        ):
            mock_settings.return_value = MagicMock(
                anthropic_api_key=None,
                openai_api_key=None,
                google_api_key=None,
                xai_api_key=None,
            )
            with pytest.raises(HTTPException) as exc_info:
                await servicio.ejecutar(
                    nickname="admin",
                    prompt="prompt",
                    categoria=TestCategory.razonamiento,
                    usuario_app=None,
                )
        # Debe llegar al 503 (sin clientes), no al 402
        assert exc_info.value.status_code == 503
