"""
Modulo: grok_client
Ruta:   backend/app/llm_engine/clients/grok_client.py

Descripcion:
    Cliente LLM para xAI Grok 4.3 (texto y vision) y grok-imagine-image (imagen generativa).
    La API de xAI es compatible con el protocolo de OpenAI; reutilizo
    el SDK de OpenAI apuntando al endpoint de xAI:
        https://api.x.ai/v1

    He decidido usar el SDK de OpenAI en lugar de un SDK propio de xAI porque
    xAI no tiene SDK Python oficial con soporte asincrono estable (mayo 2026).
    El protocolo de su API es identico al de OpenAI, asi que apunto el 'base_url'
    al endpoint de xAI y todo funciona sin codigo adicional. El mismo patron lo
    usa GeminiClient para el endpoint de texto de Google.

Sprint: Sprint 2
"""

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

_XAI_BASE_URL = "https://api.x.ai/v1"


class GrokClient(BaseLLMClient):
    """Cliente para xAI Grok 4.3 (texto y vision) y grok-imagine-image (imagen generativa).

    He eliminado la constante _MODELO_VISION que existia en una version anterior
    porque era identica a _MODELO_TEXTO ('grok-4.3'). A diferencia de OpenAI,
    donde DALL-E 3 y GPT-4o son modelos distintos, en xAI el mismo modelo grok-4.3
    gestiona tanto texto como vision. Mantener dos constantes iguales solo causaba
    confusion al leer el codigo.

    Atributos de clase:
        SOPORTA_IMAGEN: True. Usa grok-imagine-image para tareas de imagen generativa.
        SOPORTA_VISION: True. grok-4.3 acepta entradas multimodales (jpg/png).
    """

    SOPORTA_IMAGEN: bool = True
    SOPORTA_VISION: bool = True
    SOPORTA_EDICION_IMAGEN: bool = True
    _MODELO_TEXTO  = "grok-4.3"
    _MODELO_IMAGEN = "grok-imagine-image"
    # grok-imagine-image-quality es el modelo dedicado a edicion img2img
    # ($0.05/img). Endpoint /v1/images/edits, payload distinto al de
    # /v1/images/generations.
    _MODELO_IMAGEN_EDIT = "grok-imagine-image-quality"

    def __init__(self, api_key: str) -> None:
        """Inicializa el cliente con la clave de API de xAI.

        Args:
            api_key: Clave xai-... obtenida en console.x.ai.
        """
        super().__init__(api_key, self._MODELO_TEXTO, LLMProvider.grok)
        # He puesto timeout=120s por el mismo motivo que en OpenAIClient:
        # grok-imagine-image puede tardar mas de lo esperado, y el timeout
        # por defecto del SDK (600s) deja la conexion abierta demasiado tiempo
        # en caso de fallo silencioso del servidor de xAI.
        self._client = AsyncOpenAI(api_key=api_key, base_url=_XAI_BASE_URL, timeout=120.0)

    @staticmethod
    def _normalizar_error_api(exc: APIStatusError) -> str:
        """Extrae un mensaje de error limpio de una excepcion APIStatusError de xAI.

        He extraido esta logica a un metodo estatico porque aparecia duplicada
        en completar() y generar_imagen(). Siguiendo el mismo principio DRY que
        en OpenAIClient, centralizo aqui el parseo para que si xAI cambia
        la estructura de sus errores solo haya que actualizar este metodo.

        La API de xAI devuelve el error en el campo 'error' directamente en el body
        (sin el campo 'error.message' que usa OpenAI), por eso tengo una version
        separada en lugar de heredar la de OpenAIClient.

        xAI indica los rechazos por politica con las cadenas 'content moderation'
        o 'content_policy'. He preferido buscar en el string completo del error
        para ser mas robusto ante cambios de formato en la respuesta de la API.

        Args:
            exc: Excepcion APIStatusError lanzada por el SDK de OpenAI (proxy a xAI).

        Returns:
            Mensaje de error normalizado listo para mostrar al usuario.
        """
        raw = str(exc)
        if "content moderation" in raw.lower() or "content_policy" in raw.lower():
            return "Contenido rechazado por las politicas de seguridad de xAI (content moderation)."
        body = exc.body
        return (
            body.get("error") if isinstance(body, dict) else raw
        ) or raw

    async def completar(
        self,
        prompt: str,
        max_tokens: int = 4096,
        imagen_base64: str | None = None,
        imagen_mime_type: str | None = None,
    ) -> ResultadoLLM:
        """Envia el prompt a grok-4.3 en modo texto o vision y devuelve el resultado.

        grok-4.3 unifica texto y vision en un unico modelo, asi que uso self._modelo
        tanto para llamadas de texto como para llamadas multimodales. En versiones
        anteriores tenia una variable modelo_activo que cambiaba segun si habia imagen,
        pero como ambos valores eran identicos la he simplificado a self._modelo.

        He puesto el texto antes que la imagen en el mensaje multimodal (al contrario
        que en OpenAI donde va imagen primero). En las pruebas que hice, Grok
        parecia responder mejor a este orden, aunque la documentacion no lo especifica.

        Args:
            prompt: Texto del prompt.
            max_tokens: Limite de tokens en la respuesta.
            imagen_base64: Base64 de la imagen sin prefijo data-URI (jpg/png unicamente).
            imagen_mime_type: MIME type de la imagen (ej. image/jpeg).

        Returns:
            ResultadoLLM con todas las metricas o tuvo_error=True.
        """
        inicio = self._marca_inicio()
        try:
            if imagen_base64:
                mime = imagen_mime_type or "image/jpeg"
                contenido: list | str = [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{imagen_base64}"}},
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
            # xAI usa el formato OpenAI-compat; cached_tokens aparece bajo
            # prompt_tokens_details si el modelo lo soporta. Defensivo con
            # getattr porque la API de xAI esta en evolucion activa.
            tokens_cached = (
                getattr(getattr(respuesta.usage, "prompt_tokens_details", None),
                        "cached_tokens", 0) or 0
            )
            texto = respuesta.choices[0].message.content or ""
            if respuesta.choices[0].finish_reason == "length":
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
            return ResultadoLLM(
                proveedor=self._proveedor,
                modelo=self._modelo,
                tuvo_error=True,
                mensaje_error=self._normalizar_error_api(exc),
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
        """Genera una imagen con grok-imagine-image (modelo de imagen de xAI).

        He optado por descargar la imagen con httpx para generar la miniatura
        de inmediato, igual que en OpenAIClient. grok-imagine-image devuelve
        una URL temporal (similar a DALL-E 3), y sin miniatura el frontend
        perderia la imagen si el usuario abre el historial horas despues.

        Si la descarga falla (timeout de red, URL caducada), la miniatura queda
        en None pero la URL original sigue siendo valida para mostrar la imagen
        en el momento de la evaluacion.

        Args:
            prompt: Descripcion textual de la imagen a generar.

        Returns:
            ResultadoLLM con url_imagen o tuvo_error=True.
        """
        inicio = self._marca_inicio()
        try:
            respuesta = await self._client.images.generate(
                model=self._MODELO_IMAGEN,
                prompt=prompt,
                n=1,
            )
            latencia_ms = self._latencia_ms(inicio)
            url = respuesta.data[0].url if respuesta.data else None
            miniatura: str | None = None
            if url:
                try:
                    async with httpx.AsyncClient(timeout=30.0) as http:
                        descarga = await http.get(url)
                        descarga.raise_for_status()
                        miniatura = generar_miniatura(descarga.content)
                except Exception:
                    pass  # miniatura queda None; la URL original sigue siendo valida
            coste = calcular_coste_imagen_usd(self._proveedor)
            return ResultadoLLM(
                proveedor=self._proveedor,
                modelo=self._MODELO_IMAGEN,
                latencia_ms=latencia_ms,
                coste_usd=coste,
                tarifa_id=obtener_id_tarifa_vigente(self._proveedor),
                es_imagen=True,
                url_imagen=url,
                imagen_miniatura=miniatura,
            )
        except APIStatusError as exc:
            return ResultadoLLM(
                proveedor=self._proveedor,
                modelo=self._MODELO_IMAGEN,
                tuvo_error=True,
                mensaje_error=self._normalizar_error_api(exc),
                latencia_ms=self._latencia_ms(inicio),
                es_imagen=True,
            )
        except APIConnectionError as exc:
            return ResultadoLLM(
                proveedor=self._proveedor,
                modelo=self._MODELO_IMAGEN,
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
        """Edita una imagen con grok-imagine-image-quality (img2img nativo).

        He elegido httpx puro en lugar del SDK OpenAI porque, segun la
        documentacion de xAI a 13/05/2026, el metodo images.edit() del SDK
        de OpenAI NO es compatible con el formato de xAI (el body es distinto:
        se envia 'image' como objeto con 'url' o 'data URI' + 'type', no
        como multipart-form). Endpoint: POST /v1/images/edits.

        La imagen se envia como data-URI base64 en el campo 'image.url' con
        type='image_url', siguiendo la convencion xAI. El response devuelve
        una URL temporal que descargamos para generar la miniatura local.

        Args:
            prompt: Instruccion de edicion (que cambiar en la imagen).
            imagen_base64: Imagen de referencia en base64 sin prefijo data-URI.
            imagen_mime_type: MIME type (ej. image/jpeg, image/png).

        Returns:
            ResultadoLLM con url_imagen (URL temporal xAI) o tuvo_error=True.
        """
        inicio = self._marca_inicio()
        mime = imagen_mime_type or "image/jpeg"
        data_uri = f"data:{mime};base64,{imagen_base64}"
        try:
            async with httpx.AsyncClient(timeout=120.0) as http:
                respuesta = await http.post(
                    f"{_XAI_BASE_URL}/images/edits",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._MODELO_IMAGEN_EDIT,
                        "prompt": prompt,
                        "image": {"url": data_uri, "type": "image_url"},
                    },
                )
                respuesta.raise_for_status()
                datos = respuesta.json()

            latencia_ms = self._latencia_ms(inicio)
            items = datos.get("data") or []
            if not items:
                return ResultadoLLM(
                    proveedor=self._proveedor,
                    modelo=self._MODELO_IMAGEN_EDIT,
                    tuvo_error=True,
                    mensaje_error="grok-imagine-image-quality no devolvio imagen.",
                    latencia_ms=latencia_ms,
                    es_imagen=True,
                )

            url = items[0].get("url")
            miniatura: str | None = None
            if url:
                try:
                    async with httpx.AsyncClient(timeout=30.0) as http:
                        descarga = await http.get(url)
                        descarga.raise_for_status()
                        miniatura = generar_miniatura(descarga.content)
                except Exception:
                    pass  # miniatura queda None; la URL sigue siendo valida

            coste = calcular_coste_imagen_usd(self._proveedor, editar=True)
            return ResultadoLLM(
                proveedor=self._proveedor,
                modelo=self._MODELO_IMAGEN_EDIT,
                latencia_ms=latencia_ms,
                coste_usd=coste,
                tarifa_id=obtener_id_tarifa_vigente(self._proveedor),
                es_imagen=True,
                url_imagen=url,
                imagen_miniatura=miniatura,
            )
        except httpx.HTTPError as exc:
            return ResultadoLLM(
                proveedor=self._proveedor,
                modelo=self._MODELO_IMAGEN_EDIT,
                tuvo_error=True,
                mensaje_error=str(exc),
                latencia_ms=self._latencia_ms(inicio),
                es_imagen=True,
            )
