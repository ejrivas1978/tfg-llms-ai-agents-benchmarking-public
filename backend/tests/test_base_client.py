"""
Modulo: test_base_client
Ruta:   backend/tests/test_base_client.py

Descripcion:
    Tests unitarios para BaseLLMClient.
    Se crea una subclase concreta minima para poder instanciar la clase
    abstracta y probar los metodos heredados: proveedor, generar_imagen
    por defecto, editar_imagen por defecto, _marca_inicio y _latencia_ms.

Sprint: Sprint 4
"""

import time

import pytest

from app.llm_engine.clients.base_client import BaseLLMClient
from app.llm_engine.resultado import ResultadoLLM
from app.models.enums import LLMProvider


# ── Subclase concreta minima ──────────────────────────────────────────────────


class _ClienteConcreto(BaseLLMClient):
    """Subclase minima para instanciar BaseLLMClient en tests."""

    async def completar(
        self,
        prompt: str,
        max_tokens: int = 2048,
        imagen_base64: str | None = None,
        imagen_mime_type: str | None = None,
    ) -> ResultadoLLM:
        return ResultadoLLM(proveedor=self._proveedor, modelo=self._modelo)


def _cliente(proveedor: LLMProvider = LLMProvider.claude) -> _ClienteConcreto:
    return _ClienteConcreto("api_key_test", "modelo-test", proveedor)


# ── Tests: constructor y propiedades ─────────────────────────────────────────


class TestConstructorYPropiedades:
    """Pruebas para el constructor y la propiedad proveedor."""

    def test_proveedor_devuelve_enum_correcto(self):
        cliente = _cliente(LLMProvider.openai)
        assert cliente.proveedor == LLMProvider.openai

    def test_api_key_se_almacena_internamente(self):
        cliente = _cliente()
        assert cliente._api_key == "api_key_test"

    def test_modelo_se_almacena_internamente(self):
        cliente = _cliente()
        assert cliente._modelo == "modelo-test"


# ── Tests: generar_imagen default ────────────────────────────────────────────


class TestGenerarImagenDefault:
    """Pruebas para la implementacion por defecto de generar_imagen."""

    async def test_devuelve_resultado_con_error(self):
        resultado = await _cliente().generar_imagen("un gato")
        assert resultado.tuvo_error is True

    async def test_es_imagen_true(self):
        resultado = await _cliente().generar_imagen("un gato")
        assert resultado.es_imagen is True

    async def test_proveedor_correcto_en_resultado(self):
        resultado = await _cliente(LLMProvider.gemini).generar_imagen("prompt")
        assert resultado.proveedor == LLMProvider.gemini


# ── Tests: editar_imagen default ─────────────────────────────────────────────


class TestEditarImagenDefault:
    """Pruebas para la implementacion por defecto de editar_imagen.

    La implementacion base elimina el prefijo estandar y delega en generar_imagen.
    """

    async def test_delega_en_generar_imagen(self):
        resultado = await _cliente().editar_imagen(
            "Modifica la imagen adjunta aplicando el siguiente cambio: anyadir sombrero",
            imagen_base64="abc",
            imagen_mime_type="image/jpeg",
        )
        assert resultado.tuvo_error is True

    async def test_prompt_sin_prefijo_se_pasa_completo(self):
        resultado = await _cliente().editar_imagen(
            "instruccion sin prefijo estandar",
            imagen_base64="abc",
            imagen_mime_type="image/jpeg",
        )
        assert resultado.tuvo_error is True


# ── Tests: _marca_inicio y _latencia_ms ──────────────────────────────────────


class TestLatencia:
    """Pruebas para los helpers de medicion de tiempo."""

    def test_marca_inicio_devuelve_float(self):
        inicio = _cliente()._marca_inicio()
        assert isinstance(inicio, float)

    def test_latencia_ms_no_negativa(self):
        cliente = _cliente()
        inicio = cliente._marca_inicio()
        latencia = cliente._latencia_ms(inicio)
        assert latencia >= 0

    def test_latencia_ms_crece_con_el_tiempo(self):
        cliente = _cliente()
        inicio = cliente._marca_inicio()
        time.sleep(0.01)
        latencia = cliente._latencia_ms(inicio)
        assert latencia >= 10
