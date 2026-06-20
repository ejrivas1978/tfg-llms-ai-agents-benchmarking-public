"""
Modulo: gemini_client
Ruta:   backend/app/llm_engine/clients/gemini_client.py

Descripcion:
    Cliente LLM para Google Gemini 2.5 Flash (texto) y gemini-2.5-flash-image
    ('Nano Banana', imagen generativa: generar y editar).

    Texto: usa el endpoint OpenAI-compatible de Google AI Studio, que permite
    reutilizar el SDK de OpenAI sin dependencias adicionales. La URL base es:
        https://generativelanguage.googleapis.com/v1beta/openai/

    Imagen: usa la REST API nativa (generateContent) directamente via httpx, ya
    que el endpoint OpenAI-compatible de Google no expone la generacion de
    imagenes. He elegido httpx en lugar de la libreria google-generativeai para
    no anadir otra dependencia al proyecto: con httpx y la clave de API basta.

Sprint: Sprint 2
"""

import base64

import httpx
from openai import APIConnectionError, APIStatusError, AsyncOpenAI

from app.llm_engine.clients.base_client import BaseLLMClient
from app.llm_engine.metricas import (
    calcular_coste_imagen_usd,
    calcular_coste_usd,
    calcular_metricas_texto,
    generar_miniatura,
    obtener_id_tarifa_vigente,
)
from app.llm_engine.resultado import ResultadoLLM
from app.models.enums import LLMProvider

_GOOGLE_OPENAI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai/"
# gemini-2.5-flash-image ('Nano Banana') se usa tanto para generar (txt2img) como
# para editar (img2img), ambos via el endpoint nativo generateContent (no esta en
# OpenAI-compat). Sustituye a Imagen 4 (imagen-4.0-generate-001:predict), cuyo
# endpoint empezo a devolver 429 RESOURCE_EXHAUSTED y 503 UNAVAILABLE de forma
# persistente el 04/06/2026 pese a estar muy por debajo de la cuota del proyecto
# (incidencia de capacidad de Google, no de facturacion). Nano Banana tiene mucho
# mas margen de rate limit (500 RPM frente a 10 de Imagen 4). Ver ADR-034.
# Pricing: 1290 tok output * $30/MTok = ~$0.039/img (1024x1024).
_IMAGEN_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta"
    "/models/gemini-2.5-flash-image:generateContent"
)
_MODELO_IMAGEN = "gemini-2.5-flash-image"
# Editar reutiliza el mismo modelo y endpoint (alias por compatibilidad con el codigo previo).
_IMAGEN_EDIT_API_URL = _IMAGEN_API_URL
_MODELO_IMAGEN_EDIT = _MODELO_IMAGEN

# Mapa de finishReason de imagen a mensaje legible.
# IMAGE_OTHER es un comodin que Google usa para errores internos no clasificados
# (capacidad del servidor, timeouts de generacion, policy triggers no identificados).
# No se puede distinguir de copyright en la respuesta; hay que reintentar con prompt diferente.
_FINISH_REASON_MSG: dict[str, str] = {
    "IMAGE_SAFETY": "Imagen bloqueada por los filtros de seguridad de Google (politica no configurable).",
    "IMAGE_PROHIBITED_CONTENT": "Contenido bloqueado: la imagen infringe la politica de uso prohibido de Google.",
    "IMAGE_OTHER": (
        "Error interno de generacion de imagen (IMAGE_OTHER). "
        "Puede ser transitorio o deberse a copyright/contenido no permitido. "
        "Intenta de nuevo con un prompt diferente."
    ),
    "SAFETY": "Prompt bloqueado por los filtros de seguridad de Google.",
    "PROHIBITED_CONTENT": "Contenido bloqueado: el prompt infringe la politica de uso prohibido de Google.",
    "RECITATION": "El modelo no pudo generar la imagen por posibles restricciones de recitacion.",
    "OTHER": (
        "Error no especificado devuelto por Google (OTHER). "
        "Intenta de nuevo o reformula el prompt."
    ),
}


def _mensaje_finish_reason(razon: str) -> str:
    """Devuelve un mensaje descriptivo para el finishReason de la API de imagen de Gemini."""
    return _FINISH_REASON_MSG.get(
        razon,
        f"gemini-2.5-flash-image no devolvio imagen (finishReason={razon!r}).",
    )


class GeminiClient(BaseLLMClient):
    """Cliente para Google Gemini 2.5 Flash y gemini-2.5-flash-image (Nano Banana).

    He separado el cliente en dos transportes: AsyncOpenAI para texto/vision
    y httpx para imagen generativa. Esta decision la tome porque el endpoint
    OpenAI-compatible de Google no expone la API de imagen; solo expone chat
    completions. Para imagen he tenido que usar la REST API nativa de Google,
    que devuelve la imagen en base64 directamente en el body (sin URL temporal
    como DALL-E 3 o grok-imagine-image).

    Atributos de clase:
        SOPORTA_IMAGEN: True. Usa gemini-2.5-flash-image para generar y editar.
    """

    SOPORTA_IMAGEN: bool = True
    SOPORTA_EDICION_IMAGEN: bool = True
    _MODELO_TEXTO = "gemini-2.5-flash"

    def __init__(self, api_key: str) -> None:
        """Inicializa el cliente con la clave de API de Google AI Studio.

        Args:
            api_key: Clave AIzaSy-... obtenida en aistudio.google.com.
        """
        super().__init__(api_key, self._MODELO_TEXTO, LLMProvider.gemini)
        # He guardado _api_key en el padre (BaseLLMClient) pero la necesito
        # tambien aqui para pasarla como parametro de query en la REST API de Imagen 4.
        # El SDK de OpenAI la pasa en el encabezado Authorization, pero la REST API
        # de Google espera la clave como parametro ?key=... en la URL.
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=_GOOGLE_OPENAI_BASE,
        )

    async def completar(
        self,
        prompt: str,
        max_tokens: int = 4096,
        imagen_base64: str | None = None,
        imagen_mime_type: str | None = None,
    ) -> ResultadoLLM:
        """Envia el prompt a Gemini 2.5 Flash y devuelve el resultado con metricas.

        He detectado que Gemini puede devolver finish_reason='content_filter'
        cuando el contenido esta bloqueado, en lugar de lanzar una excepcion.
        Por eso compruebo ese campo antes de intentar acceder al texto de respuesta.
        Si no lo hiciera, obtendria un mensaje de respuesta vacio o un error críptico.

        El formato de imagen multimodal es el mismo que OpenAI (image_url con data-URI)
        porque uso el endpoint de compatibilidad de Google, que traduce ese formato
        internamente. He colocado imagen antes del texto igual que en OpenAIClient.

        Args:
            prompt: Texto del prompt.
            max_tokens: Limite de tokens en la respuesta.
            imagen_base64: Imagen en base64 para llamadas de vision multimodal.
            imagen_mime_type: MIME type de la imagen (ej. image/jpeg).

        Returns:
            ResultadoLLM con todas las metricas o tuvo_error=True.
        """
        inicio = self._marca_inicio()
        try:
            if imagen_base64:
                contenido: list | str = [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{imagen_mime_type or 'image/jpeg'};base64,{imagen_base64}"
                        },
                    },
                    {"type": "text", "text": prompt},
                ]
            else:
                contenido = prompt
            respuesta = await self._client.chat.completions.create(
                model=self._modelo,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": contenido}],
            )
            latencia_ms = self._latencia_ms(inicio)
            tokens_entrada = respuesta.usage.prompt_tokens
            tokens_salida = respuesta.usage.completion_tokens
            # El endpoint compat-OpenAI de Google reenvia cached_tokens cuando
            # el modelo soporta context caching y el prompt sobrepasa el umbral
            # minimo (~32k tokens en Gemini Flash). En este benchmark con prompts
            # cortos casi siempre sera 0; defensivo con getattr por si el SDK
            # no reenvia el campo.
            tokens_cached = (
                getattr(getattr(respuesta.usage, "prompt_tokens_details", None),
                        "cached_tokens", 0) or 0
            )
            # Gemini puede devolver finish_reason='content_filter' sin lanzar excepcion:
            # en ese caso choices[0].message.content seria None o vacio, y el usuario
            # veria una respuesta en blanco. Lo detecto aqui y lo convierto en error
            # con mensaje descriptivo.
            finish_reason = respuesta.choices[0].finish_reason
            if finish_reason == "content_filter":
                return ResultadoLLM(
                    proveedor=self._proveedor,
                    modelo=self._modelo,
                    tuvo_error=True,
                    mensaje_error="Contenido bloqueado por los filtros de seguridad de Google.",
                    latencia_ms=self._latencia_ms(inicio),
                )
            texto = respuesta.choices[0].message.content or ""
            # Si el modelo paró por limite de tokens la respuesta llega cortada en silencio.
            # Añadimos un aviso al final del texto para que el evaluador lo sepa.
            if finish_reason == "length":
                texto += "\n\n⚠️ [Respuesta truncada — limite de tokens alcanzado]"
            coste = calcular_coste_usd(
                self._proveedor, tokens_entrada, tokens_salida, tokens_cached
            )
            metricas = calcular_metricas_texto(texto, tokens_entrada, tokens_salida, latencia_ms, coste)
            return ResultadoLLM(
                proveedor=self._proveedor,
                modelo=self._modelo,
                texto_respuesta=texto,
                tokens_entrada=tokens_entrada,
                tokens_salida=tokens_salida,
                tokens_entrada_cacheados=tokens_cached,
                latencia_ms=latencia_ms,
                coste_usd=coste,
                tarifa_id=obtener_id_tarifa_vigente(self._proveedor),
                **metricas,
            )
        except APIStatusError as exc:
            raw = str(exc)
            _SAFETY_KW = ("safety", "content_policy", "unsafe", "violat", "filtered")
            if any(kw in raw.lower() for kw in _SAFETY_KW):
                mensaje = "Contenido bloqueado por los filtros de seguridad de Google."
            else:
                body = exc.body
                mensaje = (
                    (body.get("error") or {}).get("message")
                    if isinstance(body, dict) and isinstance(body.get("error"), dict)
                    else raw
                ) or raw
            return ResultadoLLM(
                proveedor=self._proveedor,
                modelo=self._modelo,
                tuvo_error=True,
                mensaje_error=mensaje,
                latencia_ms=self._latencia_ms(inicio),
            )
        except APIConnectionError as exc:
            return ResultadoLLM(
                proveedor=self._proveedor,
                modelo=self._modelo,
                tuvo_error=True,
                mensaje_error=str(exc),
                latencia_ms=self._latencia_ms(inicio),
            )

    async def generar_imagen(self, prompt: str) -> ResultadoLLM:
        """Genera una imagen desde texto con gemini-2.5-flash-image (Nano Banana).

        Antes esta tarea la hacia Imagen 4 (imagen-4.0-generate-001) via el endpoint
        :predict, pero ese modelo empezo a devolver 429 RESOURCE_EXHAUSTED y 503
        UNAVAILABLE de forma persistente el 04/06/2026 pese a estar muy por debajo de
        la cuota del proyecto (incidencia de capacidad de Google). Nano Banana usa el
        endpoint generateContent, acepta un prompt de solo texto pidiendo IMAGE en
        responseModalities y tiene mucho mas margen de rate limit. Es el mismo modelo
        que ya usaba editar_imagen. Ver ADR-034.

        La respuesta trae candidates[0].content.parts[], donde una part lleva el texto
        del modelo y otra el inlineData con la imagen en base64. Itero las parts hasta
        dar con la primera que contenga imagen y descarto el texto.

        Args:
            prompt: Descripcion textual de la imagen a generar.

        Returns:
            ResultadoLLM con url_imagen codificada como data-URI base64 o tuvo_error=True.
        """
        inicio = self._marca_inicio()
        try:
            async with httpx.AsyncClient(timeout=90.0) as http:
                respuesta = await http.post(
                    _IMAGEN_API_URL,
                    # Google AI espera la clave como parametro de query, no en Authorization
                    params={"key": self._api_key},
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
                    },
                )
                respuesta.raise_for_status()
                datos = respuesta.json()

            latencia_ms = self._latencia_ms(inicio)

            # Caso 1: bloqueo a nivel de prompt. Google no devuelve candidatos y a veces
            # informa el motivo en promptFeedback.blockReason.
            candidatos = datos.get("candidates") or []
            if not candidatos:
                motivo = (datos.get("promptFeedback") or {}).get("blockReason")
                return ResultadoLLM(
                    proveedor=self._proveedor,
                    modelo=_MODELO_IMAGEN,
                    tuvo_error=True,
                    mensaje_error=(
                        f"gemini-2.5-flash-image no devolvio imagen (blockReason={motivo!r})."
                        if motivo
                        else "gemini-2.5-flash-image no devolvio candidatos (posible bloqueo de seguridad)."
                    ),
                    latencia_ms=latencia_ms,
                    es_imagen=True,
                )

            # La imagen viene en una part con inlineData; otra part puede traer texto.
            partes = candidatos[0].get("content", {}).get("parts", [])
            b64: str | None = None
            mime = "image/png"
            for parte in partes:
                inline = parte.get("inlineData") or parte.get("inline_data")
                if inline and inline.get("data"):
                    b64 = inline["data"]
                    mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
                    break

            # Caso 2: bloqueo a nivel de imagen (hay candidato pero sin inlineData).
            # El motivo suele venir en finishReason (ej. SAFETY, IMAGE_OTHER, IMAGE_SAFETY).
            if not b64:
                razon = candidatos[0].get("finishReason", "")
                return ResultadoLLM(
                    proveedor=self._proveedor,
                    modelo=_MODELO_IMAGEN,
                    tuvo_error=True,
                    mensaje_error=_mensaje_finish_reason(razon),
                    latencia_ms=latencia_ms,
                    es_imagen=True,
                )

            # Imagen generada correctamente: construyo data-URI para que el frontend
            # la pueda mostrar directamente sin endpoint proxy. Como la imagen ya viene
            # en base64, no necesito una segunda peticion HTTP a diferencia de los
            # clientes que reciben URLs temporales (OpenAI, Grok).
            url_imagen = f"data:{mime};base64,{b64}"
            miniatura = generar_miniatura(base64.b64decode(b64))
            coste = calcular_coste_imagen_usd(self._proveedor)
            return ResultadoLLM(
                proveedor=self._proveedor,
                modelo=_MODELO_IMAGEN,
                latencia_ms=latencia_ms,
                coste_usd=coste,
                tarifa_id=obtener_id_tarifa_vigente(self._proveedor),
                es_imagen=True,
                url_imagen=url_imagen,
                imagen_miniatura=miniatura,
            )
        except httpx.HTTPError as exc:
            return ResultadoLLM(
                proveedor=self._proveedor,
                modelo=_MODELO_IMAGEN,
                tuvo_error=True,
                mensaje_error=str(exc),
                latencia_ms=self._latencia_ms(inicio),
                es_imagen=True,
            )

    async def editar_imagen(
        self,
        prompt: str,
        imagen_base64: str,
        imagen_mime_type: str,
    ) -> ResultadoLLM:
        """Edita una imagen con gemini-2.5-flash-image (Nano Banana).

        He elegido el endpoint nativo generateContent en lugar del de
        OpenAI-compatible porque este ultimo no expone gemini-2.5-flash-image
        para tareas img2img a fecha 13/05/2026. La estructura de peticion es
        la del SDK genai: 'contents' con 'parts' que combinan texto + inline_data
        (la imagen base64). Se pide explicitamente IMAGE en responseModalities.

        Args:
            prompt: Instruccion de edicion (que cambiar en la imagen).
            imagen_base64: Imagen de referencia en base64 sin prefijo data-URI.
            imagen_mime_type: MIME type (ej. image/jpeg, image/png).

        Returns:
            ResultadoLLM con url_imagen data-URI o tuvo_error=True.
        """
        inicio = self._marca_inicio()
        try:
            async with httpx.AsyncClient(timeout=60.0) as http:
                respuesta = await http.post(
                    _IMAGEN_EDIT_API_URL,
                    params={"key": self._api_key},
                    json={
                        "contents": [{
                            "parts": [
                                {"text": prompt},
                                {
                                    "inline_data": {
                                        "mime_type": imagen_mime_type or "image/jpeg",
                                        "data": imagen_base64,
                                    },
                                },
                            ],
                        }],
                        "generationConfig": {
                            "responseModalities": ["TEXT", "IMAGE"],
                        },
                    },
                )
                respuesta.raise_for_status()
                datos = respuesta.json()

            latencia_ms = self._latencia_ms(inicio)

            # Estructura de respuesta: candidates[0].content.parts[] donde cada
            # part puede ser texto o inlineData con la imagen base64. Iteramos
            # hasta encontrar la primera part con inlineData.
            candidatos = datos.get("candidates") or []
            if not candidatos:
                return ResultadoLLM(
                    proveedor=self._proveedor,
                    modelo=_MODELO_IMAGEN_EDIT,
                    tuvo_error=True,
                    mensaje_error="gemini-2.5-flash-image no devolvio candidatos (posible bloqueo de seguridad).",
                    latencia_ms=latencia_ms,
                    es_imagen=True,
                )

            partes = candidatos[0].get("content", {}).get("parts", [])
            b64_resultado: str | None = None
            mime_resultado = "image/png"
            for parte in partes:
                inline = parte.get("inlineData") or parte.get("inline_data")
                if inline and inline.get("data"):
                    b64_resultado = inline["data"]
                    mime_resultado = inline.get("mimeType") or inline.get("mime_type") or "image/png"
                    break

            if not b64_resultado:
                razon_finalizacion = candidatos[0].get("finishReason", "")
                return ResultadoLLM(
                    proveedor=self._proveedor,
                    modelo=_MODELO_IMAGEN_EDIT,
                    tuvo_error=True,
                    mensaje_error=_mensaje_finish_reason(razon_finalizacion),
                    latencia_ms=latencia_ms,
                    es_imagen=True,
                )

            url_imagen = f"data:{mime_resultado};base64,{b64_resultado}"
            miniatura = generar_miniatura(base64.b64decode(b64_resultado))
            coste = calcular_coste_imagen_usd(self._proveedor, editar=True)
            return ResultadoLLM(
                proveedor=self._proveedor,
                modelo=_MODELO_IMAGEN_EDIT,
                latencia_ms=latencia_ms,
                coste_usd=coste,
                tarifa_id=obtener_id_tarifa_vigente(self._proveedor),
                es_imagen=True,
                url_imagen=url_imagen,
                imagen_miniatura=miniatura,
            )
        except httpx.HTTPError as exc:
            return ResultadoLLM(
                proveedor=self._proveedor,
                modelo=_MODELO_IMAGEN_EDIT,
                tuvo_error=True,
                mensaje_error=str(exc),
                latencia_ms=self._latencia_ms(inicio),
                es_imagen=True,
            )
