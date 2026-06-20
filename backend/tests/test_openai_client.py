"""
Modulo: test_openai_client
Ruta:   backend/tests/test_openai_client.py

Descripcion:
    Tests unitarios para OpenAIClient (GPT-4o y DALL-E 3).
    Se mockea el SDK de OpenAI (AsyncOpenAI) y httpx para no realizar
    llamadas reales a la API.

    Casos cubiertos:
    - completar: texto plano, vision, APIStatusError (safety/generico), APIConnectionError
    - generar_imagen: exito + miniatura, url sin miniatura, APIStatusError, APIConnectionError
    - editar_imagen: jpeg a PNG, exito con b64, APIStatusError, APIConnectionError

Sprint: Sprint 4
"""

import base64
import io
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from app.llm_engine.clients.openai_client import OpenAIClient
from app.models.enums import LLMProvider


# ── Helpers ───────────────────────────────────────────────────────────────────


def _respuesta_completar(texto: str = "respuesta ok", finish_reason: str = "stop") -> MagicMock:
    resp = MagicMock()
    resp.usage.prompt_tokens = 10
    resp.usage.completion_tokens = 20
    choice = MagicMock()
    choice.message.content = texto
    choice.finish_reason = finish_reason
    resp.choices = [choice]
    return resp


def _respuesta_imagen_url(url: str = "https://imagen.ejemplo.com/img.png") -> MagicMock:
    resp = MagicMock()
    item = MagicMock()
    item.url = url
    resp.data = [item]
    return resp


def _respuesta_editar(b64: str = "aW1hZ2VuYmFzZTY0") -> MagicMock:
    resp = MagicMock()
    item = MagicMock()
    item.b64_json = b64
    resp.data = [item]
    return resp


def _jpeg_bytes() -> bytes:
    img = Image.new("RGB", (20, 20), color=(200, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _jpeg_base64() -> str:
    return base64.b64encode(_jpeg_bytes()).decode()


def _png_base64() -> str:
    img = Image.new("RGB", (20, 20), color=(50, 100, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _cliente() -> OpenAIClient:
    return OpenAIClient(api_key="sk-proj-test")


# ── Tests: completar ──────────────────────────────────────────────────────────


class TestOpenAIClientCompletar:
    """Pruebas para OpenAIClient.completar."""

    async def test_texto_plano_devuelve_resultado(self):
        cliente = _cliente()
        cliente._client.chat.completions.create = AsyncMock(
            return_value=_respuesta_completar("hola mundo")
        )

        resultado = await cliente.completar("prompt")

        assert not resultado.tuvo_error
        assert resultado.texto_respuesta == "hola mundo"
        assert resultado.proveedor == LLMProvider.openai
        assert resultado.tokens_entrada == 10
        assert resultado.tokens_salida == 20

    async def test_vision_construye_contenido_multimodal(self):
        cliente = _cliente()
        mock_create = AsyncMock(return_value=_respuesta_completar("descripcion"))
        cliente._client.chat.completions.create = mock_create

        await cliente.completar("describe", imagen_base64="abc", imagen_mime_type="image/png")

        llamada = mock_create.call_args
        contenido = llamada.kwargs["messages"][0]["content"]
        assert isinstance(contenido, list)
        assert "image_url" in contenido[0]["type"]

    async def test_api_status_error_safety_devuelve_mensaje_politica(self):
        from openai import APIStatusError

        exc = APIStatusError(
            "content_policy_violation detected",
            response=MagicMock(),
            body=None,
        )
        cliente = _cliente()
        cliente._client.chat.completions.create = AsyncMock(side_effect=exc)

        resultado = await cliente.completar("prompt")

        assert resultado.tuvo_error
        assert "content_policy_violation" in resultado.mensaje_error

    async def test_api_status_error_generico_usa_body(self):
        from openai import APIStatusError

        exc = APIStatusError(
            "error generico",
            response=MagicMock(),
            body={"error": {"message": "limite de tasa excedido"}},
        )
        cliente = _cliente()
        cliente._client.chat.completions.create = AsyncMock(side_effect=exc)

        resultado = await cliente.completar("prompt")

        assert resultado.tuvo_error
        assert resultado.mensaje_error == "limite de tasa excedido"

    async def test_api_connection_error_devuelve_error(self):
        from openai import APIConnectionError

        exc = APIConnectionError.__new__(APIConnectionError)
        exc.args = ("no se puede conectar",)
        cliente = _cliente()
        cliente._client.chat.completions.create = AsyncMock(side_effect=exc)

        resultado = await cliente.completar("prompt")
        assert resultado.tuvo_error


# ── Tests: generar_imagen ─────────────────────────────────────────────────────


class TestOpenAIClientGenerarImagen:
    """Pruebas para OpenAIClient.generar_imagen."""

    async def test_imagen_exitosa_devuelve_url(self):
        cliente = _cliente()
        cliente._client.images.generate = AsyncMock(
            return_value=_respuesta_imagen_url("https://ejemplo.com/imagen.png")
        )

        mock_http = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.content = _jpeg_bytes()
        mock_resp.raise_for_status = MagicMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.get = AsyncMock(return_value=mock_resp)

        with patch("app.llm_engine.clients.openai_client.httpx.AsyncClient", return_value=mock_http):
            resultado = await cliente.generar_imagen("un paisaje nevado")

        assert not resultado.tuvo_error
        assert resultado.url_imagen == "https://ejemplo.com/imagen.png"
        assert resultado.es_imagen is True

    async def test_imagen_sin_url_no_genera_miniatura(self):
        resp = MagicMock()
        resp.data = []
        cliente = _cliente()
        cliente._client.images.generate = AsyncMock(return_value=resp)

        resultado = await cliente.generar_imagen("prompt")

        assert not resultado.tuvo_error
        assert resultado.url_imagen is None
        assert resultado.imagen_miniatura is None

    async def test_descarga_falla_pero_resultado_ok(self):
        """Falla de descarga de miniatura no debe propagar excepcion."""
        cliente = _cliente()
        cliente._client.images.generate = AsyncMock(
            return_value=_respuesta_imagen_url("https://ejemplo.com/img.png")
        )

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.get = AsyncMock(side_effect=Exception("timeout"))

        with patch("app.llm_engine.clients.openai_client.httpx.AsyncClient", return_value=mock_http):
            resultado = await cliente.generar_imagen("prompt")

        assert not resultado.tuvo_error
        assert resultado.imagen_miniatura is None

    async def test_api_status_error_safety_en_imagen(self):
        from openai import APIStatusError

        exc = APIStatusError(
            "content_policy_violation in image",
            response=MagicMock(),
            body=None,
        )
        cliente = _cliente()
        cliente._client.images.generate = AsyncMock(side_effect=exc)

        resultado = await cliente.generar_imagen("prompt")
        assert resultado.tuvo_error
        assert resultado.es_imagen is True

    async def test_api_connection_error_en_imagen(self):
        from openai import APIConnectionError

        exc = APIConnectionError.__new__(APIConnectionError)
        exc.args = ("fallo de red",)
        cliente = _cliente()
        cliente._client.images.generate = AsyncMock(side_effect=exc)

        resultado = await cliente.generar_imagen("prompt")
        assert resultado.tuvo_error
        assert resultado.es_imagen is True


# ── Tests: editar_imagen ──────────────────────────────────────────────────────


class TestOpenAIClientEditarImagen:
    """Pruebas para OpenAIClient.editar_imagen."""

    async def test_jpeg_se_convierte_a_png(self):
        """Entrada JPEG debe convertirse a PNG antes de enviar a la API."""
        b64_resultado = base64.b64encode(b"imagen_png_falsa").decode()
        cliente = _cliente()
        mock_edit = AsyncMock(return_value=_respuesta_editar(b64_resultado))
        cliente._client.images.edit = mock_edit

        with patch("app.llm_engine.clients.openai_client.generar_miniatura", return_value="miniatura_b64"):
            resultado = await cliente.editar_imagen(
                prompt="agrega un sombrero",
                imagen_base64=_jpeg_base64(),
                imagen_mime_type="image/jpeg",
            )

        llamada = mock_edit.call_args
        _, imagen_bytes, mime = llamada.kwargs["image"]
        assert mime == "image/png"
        assert not resultado.tuvo_error

    async def test_png_no_se_convierte(self):
        """Entrada PNG no debe ser reconvertida."""
        b64_resultado = base64.b64encode(b"resultado_png").decode()
        cliente = _cliente()
        mock_edit = AsyncMock(return_value=_respuesta_editar(b64_resultado))
        cliente._client.images.edit = mock_edit

        with patch("app.llm_engine.clients.openai_client.generar_miniatura", return_value=None):
            resultado = await cliente.editar_imagen(
                prompt="cambiar fondo",
                imagen_base64=_png_base64(),
                imagen_mime_type="image/png",
            )

        llamada = mock_edit.call_args
        _, _, mime = llamada.kwargs["image"]
        assert mime == "image/png"
        assert not resultado.tuvo_error

    async def test_resultado_incluye_data_uri(self):
        b64_resultado = base64.b64encode(b"bytes_resultado").decode()
        cliente = _cliente()
        cliente._client.images.edit = AsyncMock(return_value=_respuesta_editar(b64_resultado))

        with patch("app.llm_engine.clients.openai_client.generar_miniatura", return_value=None):
            resultado = await cliente.editar_imagen(
                prompt="editar",
                imagen_base64=_png_base64(),
                imagen_mime_type="image/png",
            )

        assert resultado.url_imagen.startswith("data:image/png;base64,")
        assert resultado.es_imagen is True

    async def test_sin_b64_url_imagen_es_none(self):
        resp = MagicMock()
        resp.data = []
        cliente = _cliente()
        cliente._client.images.edit = AsyncMock(return_value=resp)

        resultado = await cliente.editar_imagen("prompt", _png_base64(), "image/png")
        assert resultado.url_imagen is None
        assert not resultado.tuvo_error

    async def test_api_status_error_safety_en_edicion(self):
        from openai import APIStatusError

        exc = APIStatusError(
            "content_policy_violation",
            response=MagicMock(),
            body=None,
        )
        cliente = _cliente()
        cliente._client.images.edit = AsyncMock(side_effect=exc)

        resultado = await cliente.editar_imagen("prompt", _png_base64(), "image/png")
        assert resultado.tuvo_error
        assert resultado.es_imagen is True

    async def test_api_connection_error_en_edicion(self):
        from openai import APIConnectionError

        exc = APIConnectionError.__new__(APIConnectionError)
        exc.args = ("sin conexion",)
        cliente = _cliente()
        cliente._client.images.edit = AsyncMock(side_effect=exc)

        resultado = await cliente.editar_imagen("prompt", _png_base64(), "image/png")
        assert resultado.tuvo_error
        assert resultado.es_imagen is True

    async def test_soporta_edicion_imagen_es_true(self):
        assert OpenAIClient.SOPORTA_EDICION_IMAGEN is True
