"""
Modulo: claude_client
Ruta:   backend/app/llm_engine/clients/claude_client.py

Descripcion:
    Cliente LLM para Anthropic Claude Sonnet 4.6.
    Usa el SDK oficial de Anthropic (anthropic>=0.40).
    Claude no soporta imagen generativa en este estudio (ADR-011):
    las tareas de imagen se ejecutan solo con los otros tres modelos.

    He decidido usar el SDK oficial de Anthropic en lugar del endpoint
    compatible con OpenAI (que Anthropic tambien expone) porque la API
    nativa usa 'input_tokens'/'output_tokens', mientras que el endpoint
    de compatibilidad usa 'prompt_tokens'/'completion_tokens'. Usar el SDK
    nativo me da type hints correctos sin tener que hacer mapeos manuales.

Sprint: Sprint 2
"""

from anthropic import APIConnectionError, APIStatusError, AsyncAnthropic

from app.llm_engine.clients.base_client import BaseLLMClient
from app.llm_engine.metricas import (
    calcular_coste_usd,
    calcular_metricas_texto,
    obtener_id_tarifa_vigente,
)
from app.llm_engine.resultado import ResultadoLLM
from app.models.enums import LLMProvider


class ClaudeClient(BaseLLMClient):
    """Cliente para Anthropic Claude Sonnet 4.6.

    He marcado SOPORTA_IMAGEN=False porque Claude no participa en imagen generativa
    segun la decision de diseno del TFG (ADR-011). El razonamiento es que Anthropic
    no tiene un modelo de imagen generativa equivalente a DALL-E 3 o Imagen 4, asi
    que incluirlo forzaria una comparacion asimetrica. Si en el futuro Anthropic
    lanza un modelo de imagen, bastaria con cambiar este flag y sobreescribir
    generar_imagen() sin tocar el runner ni el servicio.

    Claude si soporta vision (descripcion de imagenes) a traves de completar()
    con imagen_base64, que se usa en las categorias de vision multimodal.

    Atributos de clase:
        SOPORTA_IMAGEN: False. Claude no participa en imagen generativa (ADR-011).
    """

    SOPORTA_IMAGEN: bool = False
    _MODELO_DEFAULT = "claude-sonnet-4-6"

    def __init__(self, api_key: str) -> None:
        """Inicializa el cliente con la clave de API de Anthropic.

        Args:
            api_key: Clave sk-ant-api03-... obtenida en console.anthropic.com.
        """
        super().__init__(api_key, self._MODELO_DEFAULT, LLMProvider.claude)
        # No he puesto timeout explicito aqui a diferencia de OpenAIClient y GrokClient.
        # El SDK de Anthropic tiene un default de 600s para texto, que es aceptable
        # porque Claude solo hace llamadas de texto/vision, sin generacion de imagenes
        # que son las que tienden a bloquearse mas tiempo. Si en el futuro se detecta
        # el mismo problema de bloqueos indefinidos, se puede pasar timeout=120.0 aqui.
        self._client = AsyncAnthropic(api_key=api_key)

    async def completar(
        self,
        prompt: str,
        max_tokens: int = 4096,
        imagen_base64: str | None = None,
        imagen_mime_type: str | None = None,
    ) -> ResultadoLLM:
        """Envia el prompt a Claude y devuelve el resultado con metricas.

        El formato multimodal de Anthropic es diferente al de OpenAI/Grok:
        la imagen va dentro de un objeto 'source' con tipo 'base64', en lugar
        de una data-URI en un campo 'image_url'. He puesto la imagen primero
        porque la documentacion de Anthropic recomienda ese orden para que
        el modelo procese el contexto visual antes de leer la pregunta.

        Args:
            prompt: Texto del prompt.
            max_tokens: Limite de tokens en la respuesta.
            imagen_base64: Imagen en base64 para llamadas de vision multimodal.
            imagen_mime_type: MIME type de la imagen (ej. image/jpeg).

        Returns:
            ResultadoLLM con todas las metricas calculadas o tuvo_error=True.
        """
        inicio = self._marca_inicio()
        try:
            if imagen_base64:
                # Formato de imagen de Anthropic: 'source' con 'type': 'base64'.
                # He puesto imagen primero y texto despues siguiendo la recomendacion
                # de Anthropic de procesar primero el contexto visual.
                contenido: list | str = [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": imagen_mime_type or "image/jpeg",
                            "data": imagen_base64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ]
            else:
                contenido = prompt
            respuesta = await self._client.messages.create(
                model=self._modelo,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": contenido}],
            )
            latencia_ms = self._latencia_ms(inicio)
            # Anthropic usa input_tokens/output_tokens (no prompt_tokens/completion_tokens):
            # es la razon principal por la que uso el SDK nativo en lugar del endpoint
            # de compatibilidad con OpenAI.
            tokens_entrada = respuesta.usage.input_tokens
            tokens_salida = respuesta.usage.output_tokens
            # cache_read_input_tokens es opcional en el SDK de Anthropic:
            # solo aparece cuando el prompt entra por el path de prompt-caching
            # (cabecera anthropic-beta=prompt-caching-2024-07-31 o equivalente).
            # En este benchmark NO usamos prompt caching, asi que sera 0 casi
            # siempre, pero lo capturamos por si el SDK lo activa por su cuenta
            # en alguna version futura.
            tokens_cached = getattr(respuesta.usage, "cache_read_input_tokens", 0) or 0
            texto = respuesta.content[0].text if respuesta.content else ""
            # Anthropic usa stop_reason='max_tokens' cuando la respuesta se corta por limite.
            if respuesta.stop_reason == "max_tokens":
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
            # Anthropic no tiene un codigo de error unico para contenido bloqueado:
            # puede aparecer como 'content filtering', 'output blocked', 'safety system'
            # o variantes segun la version de la API. He preferido buscar varias palabras
            # clave en el mensaje en lugar de depender de un codigo concreto, para ser
            # mas robusto ante futuros cambios de Anthropic en la nomenclatura.
            raw = str(exc)
            body = exc.body
            msg_api = (
                (body.get("error") or {}).get("message")
                if isinstance(body, dict) and isinstance(body.get("error"), dict)
                else None
            ) or raw
            _SAFETY_KW = ("content filtering", "safety classifier", "output blocked",
                          "filtered", "safety system", "content_policy")
            if any(kw in msg_api.lower() for kw in _SAFETY_KW):
                mensaje = "Contenido rechazado por las politicas de seguridad de Anthropic."
            else:
                mensaje = msg_api
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
