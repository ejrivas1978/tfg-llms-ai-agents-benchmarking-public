"""
Modulo: test_claude_client
Ruta:   backend/tests/test_claude_client.py

Descripcion:
    Tests unitarios para ClaudeClient.
    Se mockea el SDK de Anthropic (AsyncAnthropic) para no realizar
    llamadas reales a la API.

    Casos cubiertos:
    - completar: texto plano, vision multimodal, APIStatusError (safety),
      APIStatusError (error generico), APIConnectionError

Sprint: Sprint 4
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.llm_engine.clients.claude_client import ClaudeClient
from app.models.enums import LLMProvider


# ── Helpers ───────────────────────────────────────────────────────────────────


def _respuesta_ok(texto: str = "respuesta de prueba") -> MagicMock:
    resp = MagicMock()
    resp.usage.input_tokens = 10
    resp.usage.output_tokens = 20
    resp.content = [SimpleNamespace(text=texto)]
    return resp


def _cliente() -> ClaudeClient:
    return ClaudeClient(api_key="sk-ant-test")


# ── Tests: completar ──────────────────────────────────────────────────────────


class TestClaudeClientCompletar:
    """Pruebas para ClaudeClient.completar."""

    async def test_texto_plano_devuelve_resultado(self):
        cliente = _cliente()
        cliente._client.messages.create = AsyncMock(return_value=_respuesta_ok("hola mundo"))

        resultado = await cliente.completar("prompt de prueba")

        assert not resultado.tuvo_error
        assert resultado.texto_respuesta == "hola mundo"
        assert resultado.proveedor == LLMProvider.claude
        assert resultado.tokens_entrada == 10
        assert resultado.tokens_salida == 20

    async def test_vision_construye_contenido_multimodal(self):
        cliente = _cliente()
        mock_create = AsyncMock(return_value=_respuesta_ok("descripcion imagen"))
        cliente._client.messages.create = mock_create

        resultado = await cliente.completar(
            prompt="describe esto",
            imagen_base64="abc123",
            imagen_mime_type="image/jpeg",
        )

        assert not resultado.tuvo_error
        llamada = mock_create.call_args
        contenido = llamada.kwargs["messages"][0]["content"]
        assert isinstance(contenido, list)
        assert contenido[0]["type"] == "image"
        assert contenido[0]["source"]["data"] == "abc123"

    async def test_content_empty_devuelve_texto_vacio(self):
        resp = MagicMock()
        resp.usage.input_tokens = 5
        resp.usage.output_tokens = 0
        resp.content = []
        cliente = _cliente()
        cliente._client.messages.create = AsyncMock(return_value=resp)

        resultado = await cliente.completar("pregunta")
        assert resultado.texto_respuesta == ""
        assert not resultado.tuvo_error

    async def test_api_status_error_safety_devuelve_error_seguridad(self):
        from anthropic import APIStatusError

        exc = APIStatusError(
            "content filtering violation",
            response=MagicMock(),
            body={"error": {"message": "content filtering applied"}},
        )
        cliente = _cliente()
        cliente._client.messages.create = AsyncMock(side_effect=exc)

        resultado = await cliente.completar("prompt")

        assert resultado.tuvo_error
        assert "seguridad" in resultado.mensaje_error.lower() or "Anthropic" in resultado.mensaje_error

    async def test_api_status_error_generico_usa_mensaje_body(self):
        from anthropic import APIStatusError

        exc = APIStatusError(
            "error de API",
            response=MagicMock(),
            body={"error": {"message": "cuota excedida"}},
        )
        cliente = _cliente()
        cliente._client.messages.create = AsyncMock(side_effect=exc)

        resultado = await cliente.completar("prompt")

        assert resultado.tuvo_error
        assert resultado.mensaje_error == "cuota excedida"

    async def test_api_status_error_body_no_dict_usa_raw(self):
        from anthropic import APIStatusError

        exc = APIStatusError(
            "error plano sin body dict",
            response=MagicMock(),
            body=None,
        )
        cliente = _cliente()
        cliente._client.messages.create = AsyncMock(side_effect=exc)

        resultado = await cliente.completar("prompt")

        assert resultado.tuvo_error
        assert resultado.mensaje_error is not None

    async def test_api_connection_error_devuelve_error_conexion(self):
        from anthropic import APIConnectionError

        exc = APIConnectionError.__new__(APIConnectionError)
        exc.args = ("Fallo de conexion",)
        cliente = _cliente()
        cliente._client.messages.create = AsyncMock(side_effect=exc)

        resultado = await cliente.completar("prompt")

        assert resultado.tuvo_error

    async def test_resultado_incluye_metricas_calculadas(self):
        resp = MagicMock()
        resp.usage.input_tokens = 100
        resp.usage.output_tokens = 200
        resp.content = [SimpleNamespace(text="alfa beta gamma alfa")]
        cliente = _cliente()
        cliente._client.messages.create = AsyncMock(return_value=resp)

        resultado = await cliente.completar("analiza esto")

        assert resultado.palabras == 4
        assert resultado.coste_usd > 0
        assert resultado.latencia_ms >= 0

    async def test_proveedor_es_claude(self):
        cliente = _cliente()
        cliente._client.messages.create = AsyncMock(return_value=_respuesta_ok())

        resultado = await cliente.completar("test")
        assert resultado.proveedor == LLMProvider.claude

    async def test_soporta_imagen_es_false(self):
        assert ClaudeClient.SOPORTA_IMAGEN is False
