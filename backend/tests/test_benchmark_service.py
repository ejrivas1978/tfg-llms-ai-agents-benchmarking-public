"""
Modulo: test_benchmark_service
Ruta:   backend/tests/test_benchmark_service.py

Descripcion:
    Tests unitarios para los metodos puros de BenchmarkService.
    Los repositorios se sustituyen por mocks; los tests cubren:
    - _es_rechazo_politica: deteccion de cada keyword de censura
    - _enriquecer_resultado: calculo de metricas para texto, imagen y error

Sprint: Sprint 4
"""

from unittest.mock import MagicMock

import pytest

from app.llm_engine.resultado import ResultadoLLM
from app.models.enums import LLMProvider
from app.services.benchmark_service import BenchmarkService


def _servicio() -> BenchmarkService:
    """Instancia BenchmarkService con una sesion de BD mockeada."""
    return BenchmarkService(MagicMock())


# ── Tests: _es_rechazo_politica ───────────────────────────────────────────────


class TestEsRechazosPolitica:
    """Pruebas para BenchmarkService._es_rechazo_politica."""

    def test_resultado_sin_error_devuelve_false(self):
        resultado = ResultadoLLM(proveedor=LLMProvider.claude, modelo="claude-sonnet")
        assert _servicio()._es_rechazo_politica(resultado) is False

    def test_error_tecnico_de_red_devuelve_false(self):
        resultado = ResultadoLLM(
            proveedor=LLMProvider.openai, modelo="gpt-4o",
            tuvo_error=True, mensaje_error="Connection timeout after 30s",
        )
        assert _servicio()._es_rechazo_politica(resultado) is False

    def test_mensaje_error_none_devuelve_false(self):
        resultado = ResultadoLLM(
            proveedor=LLMProvider.claude, modelo="claude-sonnet",
            tuvo_error=True, mensaje_error=None,
        )
        assert _servicio()._es_rechazo_politica(resultado) is False

    def test_keyword_content_moderation(self):
        """Keyword usada por Grok en rechazos de imagen."""
        resultado = ResultadoLLM(
            proveedor=LLMProvider.grok, modelo="grok-imagine",
            tuvo_error=True,
            mensaje_error="Generated image rejected by content moderation.",
        )
        assert _servicio()._es_rechazo_politica(resultado) is True

    def test_keyword_content_policy(self):
        """Keyword usada por OpenAI en rechazos de texto e imagen."""
        resultado = ResultadoLLM(
            proveedor=LLMProvider.openai, modelo="gpt-4o",
            tuvo_error=True,
            mensaje_error="Violacion de content_policy detectada",
        )
        assert _servicio()._es_rechazo_politica(resultado) is True

    def test_keyword_politicas_de_seguridad(self):
        """Keyword del mensaje normalizado para Anthropic."""
        resultado = ResultadoLLM(
            proveedor=LLMProvider.claude, modelo="claude-sonnet",
            tuvo_error=True,
            mensaje_error="Contenido rechazado por las politicas de seguridad de Anthropic.",
        )
        assert _servicio()._es_rechazo_politica(resultado) is True

    def test_keyword_filtros_de_seguridad(self):
        """Keyword del mensaje normalizado para Google Gemini."""
        resultado = ResultadoLLM(
            proveedor=LLMProvider.gemini, modelo="gemini-flash",
            tuvo_error=True,
            mensaje_error="Contenido bloqueado por los filtros de seguridad de Google.",
        )
        assert _servicio()._es_rechazo_politica(resultado) is True

    def test_keyword_safety_system(self):
        resultado = ResultadoLLM(
            proveedor=LLMProvider.openai, modelo="gpt-4o",
            tuvo_error=True,
            mensaje_error="Blocked by safety system policy.",
        )
        assert _servicio()._es_rechazo_politica(resultado) is True

    def test_keyword_contenido_bloqueado(self):
        resultado = ResultadoLLM(
            proveedor=LLMProvider.gemini, modelo="gemini-flash",
            tuvo_error=True,
            mensaje_error="contenido bloqueado por politica RAI",
        )
        assert _servicio()._es_rechazo_politica(resultado) is True

    def test_keyword_contenido_rechazado(self):
        resultado = ResultadoLLM(
            proveedor=LLMProvider.grok, modelo="grok-4",
            tuvo_error=True,
            mensaje_error="contenido rechazado por las normas de uso",
        )
        assert _servicio()._es_rechazo_politica(resultado) is True

    def test_case_insensitive(self):
        """La deteccion no depende de mayusculas o minusculas."""
        resultado = ResultadoLLM(
            proveedor=LLMProvider.claude, modelo="claude",
            tuvo_error=True,
            mensaje_error="CONTENT MODERATION triggered for this request.",
        )
        assert _servicio()._es_rechazo_politica(resultado) is True


# ── Tests: _enriquecer_resultado ──────────────────────────────────────────────


class TestEnriquecerResultado:
    """Pruebas para BenchmarkService._enriquecer_resultado."""

    def test_resultado_con_error_se_devuelve_sin_modificar(self):
        """Los resultados con error no se procesan: se devuelven tal como llegan."""
        resultado = ResultadoLLM(
            proveedor=LLMProvider.claude, modelo="claude",
            tuvo_error=True, mensaje_error="Error de red",
        )
        devuelto = _servicio()._enriquecer_resultado(resultado)
        assert devuelto is resultado
        assert devuelto.palabras == 0
        assert devuelto.tokens_por_segundo == 0.0

    def test_resultado_imagen_asigna_coste_imagen(self):
        """Para imagenes se asigna el coste fijo por imagen, no metricas de texto."""
        resultado = ResultadoLLM(
            proveedor=LLMProvider.openai, modelo="dall-e-3",
            es_imagen=True, tuvo_error=False,
        )
        devuelto = _servicio()._enriquecer_resultado(resultado)
        assert devuelto.coste_usd > 0
        assert devuelto.palabras == 0

    def test_resultado_imagen_no_calcula_metricas_texto(self):
        resultado = ResultadoLLM(
            proveedor=LLMProvider.gemini, modelo="imagen-4",
            es_imagen=True, tuvo_error=False,
        )
        devuelto = _servicio()._enriquecer_resultado(resultado)
        assert devuelto.diversidad_lexica == 0.0
        assert devuelto.parrafos == 0
        assert devuelto.tokens_por_segundo == 0.0

    def test_resultado_texto_calcula_palabras(self):
        resultado = ResultadoLLM(
            proveedor=LLMProvider.claude, modelo="claude-sonnet",
            tuvo_error=False, es_imagen=False,
            texto_respuesta="Hola mundo esto es una respuesta de prueba con varias palabras aqui",
            tokens_entrada=10, tokens_salida=15, latencia_ms=1000,
        )
        devuelto = _servicio()._enriquecer_resultado(resultado)
        assert devuelto.palabras > 0

    def test_resultado_texto_calcula_tokens_por_segundo(self):
        """100 tokens en 2000 ms -> 50 t/s."""
        resultado = ResultadoLLM(
            proveedor=LLMProvider.openai, modelo="gpt-4o",
            tuvo_error=False, es_imagen=False,
            texto_respuesta="texto de prueba",
            tokens_entrada=10, tokens_salida=100, latencia_ms=2000,
        )
        devuelto = _servicio()._enriquecer_resultado(resultado)
        assert devuelto.tokens_por_segundo == pytest.approx(50.0)

    def test_resultado_texto_calcula_coste_usd(self):
        resultado = ResultadoLLM(
            proveedor=LLMProvider.claude, modelo="claude-sonnet",
            tuvo_error=False, es_imagen=False,
            texto_respuesta="respuesta",
            tokens_entrada=1000, tokens_salida=500, latencia_ms=1000,
        )
        devuelto = _servicio()._enriquecer_resultado(resultado)
        assert devuelto.coste_usd > 0

    def test_resultado_texto_vacio_no_rompe(self):
        """Texto vacio no debe lanzar excepcion."""
        resultado = ResultadoLLM(
            proveedor=LLMProvider.openai, modelo="gpt-4o",
            tuvo_error=False, es_imagen=False,
            texto_respuesta="",
            tokens_entrada=0, tokens_salida=0, latencia_ms=0,
        )
        devuelto = _servicio()._enriquecer_resultado(resultado)
        assert devuelto.palabras == 0
        assert devuelto.diversidad_lexica == 0.0
