"""
Modulo: test_gemini_client
Ruta:   backend/tests/test_gemini_client.py

Descripcion:
    Tests unitarios para GeminiClient.
    Se mockea el SDK de OpenAI (AsyncOpenAI en modo compat Google) y httpx
    para las llamadas de imagen generativa (gemini-2.5-flash-image, generateContent).

    Casos cubiertos:
    - completar: texto, vision, content_filter finish_reason, APIStatusError (safety),
      APIConnectionError
    - generar_imagen: exito con inlineData, sin candidates (bloqueo de prompt),
      candidato sin imagen (finishReason), httpx.HTTPError

Sprint: Sprint 4
"""

import base64
import io
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from app.llm_engine.clients.gemini_client import GeminiClient
from app.models.enums import LLMProvider


# ── Helpers ───────────────────────────────────────────────────────────────────


def _respuesta_completar(
    texto: str = "respuesta gemini",
    finish_reason: str = "stop",
) -> MagicMock:
    resp = MagicMock()
    resp.usage.prompt_tokens = 15
    resp.usage.completion_tokens = 25
    choice = MagicMock()
    choice.message.content = texto
    choice.finish_reason = finish_reason
    resp.choices = [choice]
    return resp


def _png_b64() -> str:
    img = Image.new("RGB", (10, 10), color=(80, 160, 240))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _cliente() -> GeminiClient:
    return GeminiClient(api_key="AIzaSy-test")


# ── Tests: completar ──────────────────────────────────────────────────────────


class TestGeminiClientCompletar:
    """Pruebas para GeminiClient.completar."""

    async def test_texto_plano_devuelve_resultado(self):
        cliente = _cliente()
        cliente._client.chat.completions.create = AsyncMock(
            return_value=_respuesta_completar("hola desde gemini")
        )

        resultado = await cliente.completar("prompt de prueba")

        assert not resultado.tuvo_error
        assert resultado.texto_respuesta == "hola desde gemini"
        assert resultado.proveedor == LLMProvider.gemini
        assert resultado.tokens_entrada == 15
        assert resultado.tokens_salida == 25

    async def test_vision_construye_contenido_multimodal(self):
        cliente = _cliente()
        mock_create = AsyncMock(return_value=_respuesta_completar("descripcion de imagen"))
        cliente._client.chat.completions.create = mock_create

        await cliente.completar("describe", imagen_base64="xyz", imagen_mime_type="image/png")

        llamada = mock_create.call_args
        contenido = llamada.kwargs["messages"][0]["content"]
        assert isinstance(contenido, list)
        assert contenido[0]["type"] == "image_url"

    async def test_content_filter_devuelve_error_seguridad(self):
        """Cuando finish_reason == content_filter debe retornar ResultadoLLM con tuvo_error."""
        cliente = _cliente()
        cliente._client.chat.completions.create = AsyncMock(
            return_value=_respuesta_completar(finish_reason="content_filter")
        )

        resultado = await cliente.completar("prompt")

        assert resultado.tuvo_error
        assert "Google" in resultado.mensaje_error

    async def test_api_status_error_safety_detecta_keywords(self):
        from openai import APIStatusError

        exc = APIStatusError(
            "unsafe content violat",
            response=MagicMock(),
            body=None,
        )
        cliente = _cliente()
        cliente._client.chat.completions.create = AsyncMock(side_effect=exc)

        resultado = await cliente.completar("prompt")

        assert resultado.tuvo_error
        assert "Google" in resultado.mensaje_error

    async def test_api_status_error_generico_usa_body(self):
        from openai import APIStatusError

        exc = APIStatusError(
            "error generico",
            response=MagicMock(),
            body={"error": {"message": "clave invalida"}},
        )
        cliente = _cliente()
        cliente._client.chat.completions.create = AsyncMock(side_effect=exc)

        resultado = await cliente.completar("prompt")

        assert resultado.tuvo_error
        assert resultado.mensaje_error == "clave invalida"

    async def test_api_connection_error_devuelve_error(self):
        from openai import APIConnectionError

        exc = APIConnectionError.__new__(APIConnectionError)
        exc.args = ("fallo conexion google",)
        cliente = _cliente()
        cliente._client.chat.completions.create = AsyncMock(side_effect=exc)

        resultado = await cliente.completar("prompt")
        assert resultado.tuvo_error


# ── Tests: generar_imagen ─────────────────────────────────────────────────────


class TestGeminiClientGenerarImagen:
    """Pruebas para GeminiClient.generar_imagen via gemini-2.5-flash-image (generateContent)."""

    def _mock_http_exito(self, b64: str = None) -> MagicMock:
        b64_imagen = b64 or _png_b64()
        mock_http = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        # generateContent devuelve candidates[].content.parts[]; una part de texto
        # (que debemos ignorar) y otra con inlineData (la imagen en base64).
        mock_resp.json = MagicMock(
            return_value={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": "Aqui tienes la imagen"},
                                {"inlineData": {"data": b64_imagen, "mimeType": "image/png"}},
                            ]
                        }
                    }
                ]
            }
        )
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(return_value=mock_resp)
        return mock_http

    async def test_imagen_exitosa_devuelve_data_uri(self):
        cliente = _cliente()
        mock_http = self._mock_http_exito()

        with patch("app.llm_engine.clients.gemini_client.httpx.AsyncClient", return_value=mock_http):
            resultado = await cliente.generar_imagen("un gato espacial")

        assert not resultado.tuvo_error
        assert resultado.url_imagen.startswith("data:image/png;base64,")
        assert resultado.modelo == "gemini-2.5-flash-image"
        assert resultado.es_imagen is True

    async def test_sin_candidates_bloqueo_prompt(self):
        """HTTP 200 sin candidates = prompt bloqueado; usa blockReason si esta."""
        cliente = _cliente()
        mock_http = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value={"promptFeedback": {"blockReason": "SAFETY"}})
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(return_value=mock_resp)

        with patch("app.llm_engine.clients.gemini_client.httpx.AsyncClient", return_value=mock_http):
            resultado = await cliente.generar_imagen("prompt bloqueado")

        assert resultado.tuvo_error
        assert resultado.es_imagen is True
        assert "SAFETY" in resultado.mensaje_error

    async def test_sin_candidates_sin_motivo_usa_mensaje_default(self):
        """HTTP 200 sin candidates ni promptFeedback usa mensaje generico."""
        cliente = _cliente()
        mock_http = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value={})
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(return_value=mock_resp)

        with patch("app.llm_engine.clients.gemini_client.httpx.AsyncClient", return_value=mock_http):
            resultado = await cliente.generar_imagen("prompt")

        assert resultado.tuvo_error
        assert resultado.mensaje_error is not None

    async def test_candidate_sin_imagen_usa_finish_reason(self):
        """Hay candidato pero ninguna part trae inlineData = bloqueo a nivel de imagen."""
        cliente = _cliente()
        mock_http = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(
            return_value={
                "candidates": [
                    {
                        "content": {"parts": [{"text": "No puedo generar eso"}]},
                        "finishReason": "PROHIBITED_CONTENT",
                    }
                ]
            }
        )
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(return_value=mock_resp)

        with patch("app.llm_engine.clients.gemini_client.httpx.AsyncClient", return_value=mock_http):
            resultado = await cliente.generar_imagen("prompt")

        assert resultado.tuvo_error
        assert "PROHIBITED_CONTENT" in resultado.mensaje_error

    async def test_httpx_error_devuelve_error(self):
        import httpx

        cliente = _cliente()
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(side_effect=httpx.ConnectError("no host"))

        with patch("app.llm_engine.clients.gemini_client.httpx.AsyncClient", return_value=mock_http):
            resultado = await cliente.generar_imagen("prompt")

        assert resultado.tuvo_error
        assert resultado.es_imagen is True

    async def test_soporta_imagen_es_true(self):
        assert GeminiClient.SOPORTA_IMAGEN is True
