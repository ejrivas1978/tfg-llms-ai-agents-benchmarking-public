"""
Modulo: openai_client
Ruta:   backend/app/llm_engine/clients/openai_client.py

Descripcion:
    Cliente LLM para OpenAI GPT-4o (texto y vision) y DALL-E 3 / gpt-image-1 (imagen).
    Usa el SDK oficial de OpenAI (openai>=1.54).

    He decidido mantener tres modelos distintos para OpenAI porque cada uno tiene
    una API diferente: gpt-4o para texto/vision via chat.completions, dall-e-3 para
    generacion de imagen via images.generate, y gpt-image-1 para edicion imagen-a-imagen
    via images.edit. No hay un modelo "todo-en-uno" como en Grok.

    DECISION de timeout: he puesto 120s en el constructor de AsyncOpenAI porque en las
    primeras pruebas el servidor se quedaba bloqueado indefinidamente esperando respuesta
    de gpt-image-1. El timeout por defecto del SDK es 600s, lo que en la practica
    significa que el proceso nunca cancela la llamada si algo va mal.

Sprint: Sprint 2
"""

import base64 as b64_mod
import io

import httpx
from openai import APIConnectionError, APIStatusError, AsyncOpenAI
from PIL import Image

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


class OpenAIClient(BaseLLMClient):
    """Cliente para OpenAI GPT-4o y DALL-E 3.

    He marcado SOPORTA_IMAGEN=True porque OpenAI tiene tres APIs de imagen:
    DALL-E 3 para generacion desde texto, gpt-image-1 para edicion con imagen
    de referencia, y GPT-4o para descripcion (vision). El runner usa este flag
    para incluir o excluir el cliente en cada tipo de tarea.

    Atributos de clase:
        SOPORTA_IMAGEN: True. Usa DALL-E 3 para tareas de imagen generativa.
        SOPORTA_EDICION_IMAGEN: True. Usa gpt-image-1 con edicion real sin mascara.
    """

    SOPORTA_IMAGEN: bool = True
    SOPORTA_EDICION_IMAGEN: bool = True
    _MODELO_TEXTO   = "gpt-4o"
    # DALL-E 3 fue retirado por OpenAI 13/05/2026 (HTTP 400
    # "model does not exist"). Migrado a gpt-image-1 con quality="medium"
    # (~$0.07/img) para mantener calidad equivalente a Imagen 4 standard
    # de Gemini y permitir comparativa de rating humano manzana-con-manzana.
    # gpt-image-1 atiende AMBOS caminos (generar y editar) cambiando el
    # endpoint (images.generate vs images.edit), pero con prompting distinto.
    _MODELO_IMAGEN  = "gpt-image-1"
    _MODELO_EDICION = "gpt-image-1"
    # Quality fijo "medium": comparable a Imagen 4 standard en aesthetic /
    # prompt-adherence segun comparativas oficiales (Artificial Analysis).
    # "low" producir�a imagenes visiblemente peores y sesgaria el rating
    # humano contra OpenAI sin reflejar su capacidad real.
    _CALIDAD_IMAGEN = "medium"

    def __init__(self, api_key: str) -> None:
        """Inicializa el cliente con la clave de API de OpenAI.

        Args:
            api_key: Clave sk-proj-... obtenida en platform.openai.com.
        """
        super().__init__(api_key, self._MODELO_TEXTO, LLMProvider.openai)
        # He puesto timeout=120s para evitar bloqueos indefinidos:
        # gpt-image-1 y grok-imagine-image pueden tardar mas de lo esperado,
        # y el timeout por defecto del SDK (600s) es demasiado largo para una
        # aplicacion web donde el usuario esta esperando una respuesta.
        self._client = AsyncOpenAI(api_key=api_key, timeout=120.0)

    @staticmethod
    def _normalizar_error_api(exc: APIStatusError) -> str:
        """Extrae un mensaje de error limpio de una excepcion APIStatusError de OpenAI.

        He extraido esta logica a un metodo estatico porque exactamente el mismo bloque
        de codigo aparecia tres veces (en completar, generar_imagen y editar_imagen).
        Es el principio DRY: si cambia la estructura del error de la API de OpenAI,
        solo hay que actualizar este metodo y no buscar todos los sitios donde esta repetido.

        La API de OpenAI devuelve un campo 'error.message' dentro del body JSON cuando
        el error es un 4xx. Si el body no tiene ese formato (por ejemplo, un error de
        red), usamos la representacion en string de la excepcion completa.

        Args:
            exc: Excepcion APIStatusError lanzada por el SDK de OpenAI.

        Returns:
            Mensaje de error normalizado listo para mostrar al usuario.
        """
        raw = str(exc)
        # Deteccion de rechazo por politica de contenido:
        # 'content_policy_violation' es el codigo que OpenAI devuelve en el campo
        # 'error.code' del body. 'safety system' aparece a veces en el mensaje.
        # He preferido buscar en el string completo del error para no depender
        # de la estructura exacta del body, que puede variar segun la version de la API.
        if "content_policy_violation" in raw or "safety system" in raw:
            return "Contenido rechazado por las politicas de seguridad de OpenAI (content_policy_violation)."
        body = exc.body
        return (
            body.get("error", {}).get("message")  # type: ignore[union-attr]
            if isinstance(body, dict) else raw
        ) or raw

    async def completar(
        self,
        prompt: str,
        max_tokens: int = 4096,
        imagen_base64: str | None = None,
        imagen_mime_type: str | None = None,
    ) -> ResultadoLLM:
        """Envia el prompt a GPT-4o y devuelve el resultado con metricas.

        Si se proporcionan imagen_base64 e imagen_mime_type, construye un mensaje
        multimodal en formato OpenAI (image_url con data-URI). GPT-4o acepta tanto
        texto puro como mensajes multimodales con el mismo modelo.

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
                # Formato multimodal de OpenAI: el contenido del mensaje es una lista
                # con un objeto image_url y un texto. La imagen va como data-URI
                # (data:mime;base64,datos). He puesto la imagen primero y el texto despues
                # porque en las pruebas GPT-4o responde mejor con ese orden.
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
            # OpenAI expone los hits de cache en prompt_tokens_details.cached_tokens
            # desde finales de 2024. Defensivo: si el modelo o version del SDK no
            # incluye el campo, lo tratamos como 0 cached.
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
        """Genera una imagen con DALL-E 3 a partir del prompt.

        He migrado de DALL-E 3 a gpt-image-1 el 13/05/2026 porque OpenAI
        retiro DALL-E 3 del API (HTTP 400: "model 'dall-e-3' does not exist").
        gpt-image-1 con quality="medium" produce imagenes de calidad
        comparable a Imagen 4 standard de Gemini segun comparativas
        independientes (Artificial Analysis, Notes by Lex), permitiendo
        comparativa de rating humano equilibrada.

        A diferencia de DALL-E 3 (que devolvia URL temporal), gpt-image-1
        devuelve la imagen como base64 directamente en data[0].b64_json,
        igual que el endpoint de edicion. Construimos data-URI para
        que el frontend la muestre sin caducidad ni endpoint proxy.

        Args:
            prompt: Descripcion textual de la imagen a generar.

        Returns:
            ResultadoLLM con url_imagen (data-URI base64) y coste fijo,
            o tuvo_error=True.
        """
        inicio = self._marca_inicio()
        try:
            respuesta = await self._client.images.generate(
                model=self._MODELO_IMAGEN,
                prompt=prompt,
                n=1,
                size="1024x1024",
                quality=self._CALIDAD_IMAGEN,
            )
            latencia_ms = self._latencia_ms(inicio)
            b64_resultado = respuesta.data[0].b64_json if respuesta.data else None
            url_imagen: str | None = None
            miniatura: str | None = None
            if b64_resultado:
                # Data-URI para mostrar sin endpoint proxy ni caducidad.
                url_imagen = f"data:image/png;base64,{b64_resultado}"
                miniatura = generar_miniatura(b64_mod.b64decode(b64_resultado))
            coste = calcular_coste_imagen_usd(self._proveedor)
            return ResultadoLLM(
                proveedor=self._proveedor,
                modelo=self._MODELO_IMAGEN,
                latencia_ms=latencia_ms,
                coste_usd=coste,
                tarifa_id=obtener_id_tarifa_vigente(self._proveedor),
                es_imagen=True,
                url_imagen=url_imagen,
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
        """Edita una imagen con gpt-image-1 aplicando las instrucciones del prompt.

        He elegido gpt-image-1 aqui en lugar de DALL-E 3 porque es el unico modelo
        de OpenAI que acepta una imagen de entrada para edicion real. DALL-E 3 solo
        genera desde texto. gpt-image-1 via images.edit() no requiere mascara, lo que
        simplifica mucho el flujo: solo necesito la imagen y el prompt de instruccion.

        Conversion JPEG a PNG: gpt-image-1 requiere PNG como formato de entrada.
        Si el usuario sube un JPEG, la API puede fallar en silencio (devuelve una imagen
        generada ignorando la referencia) o lanzar un error. He preferido hacer la
        conversion automatica con Pillow en lugar de obligar al usuario a subir PNG.
        La conversion usa RGBA para mantener el canal alfa si existe.

        La respuesta viene en base64 (b64_json), no como URL, a diferencia de DALL-E 3.
        Esto es mejor para nuestro caso porque la imagen no expira.

        Args:
            prompt: Instruccion de modificacion.
            imagen_base64: Imagen de entrada en base64 sin prefijo data-URI.
            imagen_mime_type: MIME type de la imagen (ej. image/jpeg).

        Returns:
            ResultadoLLM con url_imagen como data-URI base64 o tuvo_error=True.
        """
        inicio = self._marca_inicio()
        try:
            try:
                imagen_bytes = b64_mod.b64decode(imagen_base64)
                # gpt-image-1 requiere PNG; si viene JPEG lo convierto aqui
                # para evitar errores silenciosos en la API
                if "jpeg" in imagen_mime_type or "jpg" in imagen_mime_type:
                    img = Image.open(io.BytesIO(imagen_bytes))
                    buf = io.BytesIO()
                    img.convert("RGBA").save(buf, format="PNG")
                    imagen_bytes = buf.getvalue()
                    imagen_mime_type = "image/png"
            except Exception as exc_conv:
                return ResultadoLLM(
                    proveedor=self._proveedor,
                    modelo=self._MODELO_EDICION,
                    tuvo_error=True,
                    mensaje_error=f"Error al procesar la imagen de entrada: {exc_conv}",
                    latencia_ms=self._latencia_ms(inicio),
                    es_imagen=True,
                )
            respuesta = await self._client.images.edit(
                model=self._MODELO_EDICION,
                image=("image.png", imagen_bytes, "image/png"),
                prompt=prompt,
                n=1,
            )
            latencia_ms = self._latencia_ms(inicio)
            b64_resultado = respuesta.data[0].b64_json if respuesta.data else None
            url_imagen: str | None = None
            miniatura: str | None = None
            if b64_resultado:
                # Construyo una data-URI para que el frontend pueda mostrar la imagen
                # directamente sin necesidad de un endpoint proxy (a diferencia de
                # DALL-E 3 que devuelve una URL temporal que expira)
                url_imagen = f"data:image/png;base64,{b64_resultado}"
                miniatura = generar_miniatura(b64_mod.b64decode(b64_resultado))
            coste = calcular_coste_imagen_usd(self._proveedor, editar=True)
            return ResultadoLLM(
                proveedor=self._proveedor,
                modelo=self._MODELO_EDICION,
                latencia_ms=latencia_ms,
                coste_usd=coste,
                tarifa_id=obtener_id_tarifa_vigente(self._proveedor),
                es_imagen=True,
                url_imagen=url_imagen,
                imagen_miniatura=miniatura,
            )
        except APIStatusError as exc:
            return ResultadoLLM(
                proveedor=self._proveedor,
                modelo=self._MODELO_EDICION,
                tuvo_error=True,
                mensaje_error=self._normalizar_error_api(exc),
                latencia_ms=self._latencia_ms(inicio),
                es_imagen=True,
            )
        except APIConnectionError as exc:
            return ResultadoLLM(
                proveedor=self._proveedor,
                modelo=self._MODELO_EDICION,
                tuvo_error=True,
                mensaje_error=str(exc),
                latencia_ms=self._latencia_ms(inicio),
                es_imagen=True,
            )
