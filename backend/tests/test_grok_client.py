"""
Modulo: test_grok_client
Ruta:   backend/tests/test_grok_client.py

Descripcion:
    Tests unitarios para GrokClient (xAI Grok 4.3).
    Se mockea el SDK de OpenAI (AsyncOpenAI apuntando a xAI) y httpx
    para la descarga de miniatura en generacion de imagen.

    Casos cubiertos:
    - completar: texto plano, vision multimodal, APIStatusError (content moderation),
      APIStatusError (generico), APIConnectionError
    - generar_imagen: exito + miniatura, sin url, APIStatusError, APIConnectionError

Sprint: Sprint 4
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.llm_engine.clients.grok_client import GrokClient
from app.models.enums import LLMProvider


# ── Helpers ───────────────────────────────────────────────────────────────────


def _respuesta_completar(texto: str = "respuesta grok") -> MagicMock:
    resp = MagicMock()
    resp.usage.prompt_tokens = 12
    resp.usage.completion_tokens = 18
    choice = MagicMock()
    choice.message.content = texto
    choice.finish_reason = "stop"
    resp.choices = [choice]
    return resp


def _respuesta_imagen(url: str = "https://imagen.xai.com/grok.png") -> MagicMock:
    resp = MagicMock()
    item = MagicMock()
    item.url = url
    resp.data = [item]
    return resp


def _cliente() -> GrokClient:
    return GrokClient(api_key="xai-test-key")


# ── Tests: completar ──────────────────────────────────────────────────────────


class TestGrokClientCompletar:
    """Pruebas para GrokClient.completar."""

    async def test_texto_plano_devuelve_resultado(self):
        cliente = _cliente()
        cliente._client.chat.completions.create = AsyncMock(
            return_value=_respuesta_completar("hola desde grok")
        )

        resultado = await cliente.completar("pregunta de prueba")

        assert not resultado.tuvo_error
        assert resultado.texto_respuesta == "hola desde grok"
        assert resultado.proveedor == LLMProvider.grok
        assert resultado.tokens_entrada == 12
        assert resultado.tokens_salida == 18

    async def test_vision_construye_contenido_multimodal(self):
        """En modo vision, el contenido debe ser una lista con text primero e image_url segundo."""
        cliente = _cliente()
        mock_create = AsyncMock(return_value=_respuesta_completar("descripcion"))
        cliente._client.chat.completions.create = mock_create

        await cliente.completar("describe esto", imagen_base64="abc", imagen_mime_type="image/jpeg")

        llamada = mock_create.call_args
        contenido = llamada.kwargs["messages"][0]["content"]
        assert isinstance(contenido, list)
        tipos = [item["type"] for item in contenido]
        assert "text" in tipos
        assert "image_url" in tipos

    async def test_vision_usa_modelo_texto(self):
        """Con imagen, grok-4.3 unifica texto y vision: se usa _MODELO_TEXTO."""
        cliente = _cliente()
        mock_create = AsyncMock(return_value=_respuesta_completar())
        cliente._client.chat.completions.create = mock_create

        await cliente.completar("prompt", imagen_base64="data", imagen_mime_type="image/jpeg")

        llamada = mock_create.call_args
        assert llamada.kwargs["model"] == GrokClient._MODELO_TEXTO

    async def test_texto_usa_modelo_texto(self):
        cliente = _cliente()
        mock_create = AsyncMock(return_value=_respuesta_completar())
        cliente._client.chat.completions.create = mock_create

        await cliente.completar("prompt sin imagen")

        llamada = mock_create.call_args
        assert llamada.kwargs["model"] == GrokClient._MODELO_TEXTO

    async def test_api_status_error_content_moderation(self):
        from openai import APIStatusError

        exc = APIStatusError(
            "content moderation triggered",
            response=MagicMock(),
            body=None,
        )
        cliente = _cliente()
        cliente._client.chat.completions.create = AsyncMock(side_effect=exc)

        resultado = await cliente.completar("prompt")

        assert resultado.tuvo_error
        assert "xAI" in resultado.mensaje_error

    async def test_api_status_error_generico_usa_body(self):
        from openai import APIStatusError

        exc = APIStatusError(
            "error",
            response=MagicMock(),
            body={"error": "credencial invalida"},
        )
        cliente = _cliente()
        cliente._client.chat.completions.create = AsyncMock(side_effect=exc)

        resultado = await cliente.completar("prompt")

        assert resultado.tuvo_error
        assert resultado.mensaje_error == "credencial invalida"

    async def test_api_connection_error_devuelve_error(self):
        from openai import APIConnectionError

        exc = APIConnectionError.__new__(APIConnectionError)
        exc.args = ("fallo xai",)
        cliente = _cliente()
        cliente._client.chat.completions.create = AsyncMock(side_effect=exc)

        resultado = await cliente.completar("prompt")
        assert resultado.tuvo_error


# ── Tests: generar_imagen ─────────────────────────────────────────────────────


class TestGrokClientGenerarImagen:
    """Pruebas para GrokClient.generar_imagen."""

    async def test_imagen_exitosa_devuelve_url(self):
        import io
        from PIL import Image

        img_bytes = io.BytesIO()
        Image.new("RGB", (20, 20), (255, 0, 0)).save(img_bytes, format="JPEG")
        jpeg_content = img_bytes.getvalue()

        cliente = _cliente()
        cliente._client.images.generate = AsyncMock(
            return_value=_respuesta_imagen("https://xai.com/img.png")
        )

        mock_http = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.content = jpeg_content
        mock_resp.raise_for_status = MagicMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.get = AsyncMock(return_value=mock_resp)

        with patch("app.llm_engine.clients.grok_client.httpx.AsyncClient", return_value=mock_http):
            resultado = await cliente.generar_imagen("una nebulosa")

        assert not resultado.tuvo_error
        assert resultado.url_imagen == "https://xai.com/img.png"
        assert resultado.es_imagen is True

    async def test_imagen_sin_url_devuelve_ok_sin_miniatura(self):
        resp = MagicMock()
        resp.data = []
        cliente = _cliente()
        cliente._client.images.generate = AsyncMock(return_value=resp)

        resultado = await cliente.generar_imagen("prompt")

        assert not resultado.tuvo_error
        assert resultado.url_imagen is None
        assert resultado.imagen_miniatura is None

    async def test_descarga_falla_silenciosamente(self):
        cliente = _cliente()
        cliente._client.images.generate = AsyncMock(
            return_value=_respuesta_imagen("https://xai.com/img.png")
        )

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.get = AsyncMock(side_effect=Exception("timeout"))

        with patch("app.llm_engine.clients.grok_client.httpx.AsyncClient", return_value=mock_http):
            resultado = await cliente.generar_imagen("prompt")

        assert not resultado.tuvo_error
        assert resultado.imagen_miniatura is None

    async def test_api_status_error_safety(self):
        from openai import APIStatusError

        exc = APIStatusError(
            "content moderation applied",
            response=MagicMock(),
            body=None,
        )
        cliente = _cliente()
        cliente._client.images.generate = AsyncMock(side_effect=exc)

        resultado = await cliente.generar_imagen("prompt")
        assert resultado.tuvo_error
        assert resultado.es_imagen is True

    async def test_api_connection_error(self):
        from openai import APIConnectionError

        exc = APIConnectionError.__new__(APIConnectionError)
        exc.args = ("sin red",)
        cliente = _cliente()
        cliente._client.images.generate = AsyncMock(side_effect=exc)

        resultado = await cliente.generar_imagen("prompt")
        assert resultado.tuvo_error
        assert resultado.es_imagen is True

    async def test_soporta_imagen_y_vision(self):
        assert GrokClient.SOPORTA_IMAGEN is True
        assert GrokClient.SOPORTA_VISION is True
