"""
Modulo: runner
Ruta:   backend/app/llm_engine/runner.py

Descripcion:
    Orquestador de llamadas paralelas a los cuatro LLMs.
    Ejecuta todos los clientes en paralelo con asyncio.gather y
    return_exceptions=True para que el fallo de un proveedor no
    cancele las llamadas a los demas.

    DECISION(ADR-004): asyncio.gather con return_exceptions=True.
    DECISION(ADR-011): Seleccion automatica de clientes segun la categoria.
        - Texto: los 4 modelos (Claude, GPT-4o, Gemini, Grok).
        - Vision multimodal: solo clientes con SOPORTA_VISION=True.
        - Imagen generativa: solo los 3 con SOPORTA_IMAGEN=True (Claude excluido).
        - Edicion de imagen: clientes con SOPORTA_IMAGEN=True (SOPORTA_EDICION solo OpenAI).

Sprint: Sprint 2
"""

import asyncio
import logging

from app.llm_engine.clients.base_client import BaseLLMClient
from app.llm_engine.resultado import ResultadoLLM

logger = logging.getLogger(__name__)


async def ejecutar_benchmark(
    clientes: list[BaseLLMClient],
    prompt: str,
    es_imagen: bool = False,
    max_tokens: int = 4096,
    imagen_base64: str | None = None,
    imagen_mime_type: str | None = None,
    idioma_prompt: str = 'es',
) -> list[ResultadoLLM]:
    """Ejecuta todos los clientes en paralelo y devuelve sus resultados.

    He organizado la logica en cuatro ramas mutuamente excluyentes usando
    la combinacion de es_imagen e imagen_base64:

    1. es_imagen=True + imagen_base64 presente → edicion de imagen:
       el usuario subio una imagen y pide modificarla. Los clientes con
       SOPORTA_EDICION_IMAGEN usan su API nativa; el resto generan desde texto.

    2. imagen_base64 presente (es_imagen=False) → vision multimodal:
       el usuario subio una imagen para que los LLMs la describan o analicen.
       Solo participan los clientes con SOPORTA_VISION=True.

    3. es_imagen=True (imagen_base64 ausente) → imagen generativa desde texto:
       el usuario pide generar una imagen a partir de un prompt de texto.
       Solo participan los clientes con SOPORTA_IMAGEN=True (Claude excluido).

    4. Sin imagen → texto puro: todos los clientes participan.

    He elegido asyncio.gather con return_exceptions=True en lugar de
    asyncio.gather sin ese flag porque si un proveedor falla con una excepcion
    no capturada, el gather sin el flag cancelaria el resto de tareas en vuelo.
    Con return_exceptions=True, los errores llegan como objetos Exception en
    la lista de resultados y los convierto a ResultadoLLM(tuvo_error=True).

    Args:
        clientes: Lista de instancias BaseLLMClient a ejecutar.
        prompt: Texto del prompt o descripcion de la imagen.
        es_imagen: True para rutas de imagen generativa o edicion de imagen.
        max_tokens: Limite de tokens (ignorado en tareas de imagen generativa).
        imagen_base64: Base64 de la imagen subida para vision o edicion.
        imagen_mime_type: MIME type de la imagen subida.

    Returns:
        Lista de ResultadoLLM, uno por cliente activo, en el mismo orden.
        Los errores estan encapsulados en ResultadoLLM.tuvo_error=True.
    """
    if es_imagen and imagen_base64:
        # Edicion de imagen: solo los clientes con soporte de imagen participan.
        # Los que tienen SOPORTA_EDICION_IMAGEN=True (OpenAI) usan su API nativa;
        # el resto (Gemini, Grok) delegan en generar_imagen() con solo el prompt.
        clientes_activos = [c for c in clientes if c.SOPORTA_IMAGEN]
        tareas = [
            c.editar_imagen(prompt, imagen_base64, imagen_mime_type or "image/jpeg")
            for c in clientes_activos
        ]
    elif imagen_base64:
        # Vision multimodal: imagen de referencia para describir o analizar.
        # Claude, GPT-4o, Gemini y Grok soportan vision; todos tienen SOPORTA_VISION=True.
        clientes_activos = [c for c in clientes if c.SOPORTA_VISION]
        tareas = [
            c.completar(prompt, max_tokens=max_tokens, imagen_base64=imagen_base64, imagen_mime_type=imagen_mime_type)
            for c in clientes_activos
        ]
    elif es_imagen:
        # Imagen generativa desde texto: DALL-E 3, Imagen 4 y grok-imagine-image.
        # Claude no tiene modelo de imagen generativa (ADR-011), por eso se excluye.
        clientes_activos = [c for c in clientes if c.SOPORTA_IMAGEN]
        tareas = [c.generar_imagen(prompt) for c in clientes_activos]
    else:
        # Texto puro: todos los clientes participan sin filtro.
        clientes_activos = clientes
        tareas = [c.completar(prompt, max_tokens=max_tokens) for c in clientes_activos]

    resultados_raw = await asyncio.gather(*tareas, return_exceptions=True)

    resultados: list[ResultadoLLM] = []
    for cliente, raw in zip(clientes_activos, resultados_raw):
        if isinstance(raw, ResultadoLLM):
            # Etiquetar la respuesta con el idioma del prompt enviado.
            # Necesario para que el persister (LLMResponseRepository) y los
            # agregados del dashboard (medias por idioma) puedan filtrar
            # por (proveedor, idioma) sin JOINs adicionales.
            raw.idioma_prompt = idioma_prompt
            resultados.append(raw)
        else:
            # Excepcion no capturada dentro del cliente (bug en el cliente, no error de API).
            # Los errores de API deberian haberse capturado dentro de cada metodo del cliente.
            # Si llegamos aqui es que hay un bug que escapo al try/except interno,
            # y lo convierto a ResultadoLLM para no romper la respuesta al frontend.
            logger.error("Excepcion inesperada en %s: %s", cliente.proveedor, raw)
            resultados.append(
                ResultadoLLM(
                    proveedor=cliente.proveedor,
                    modelo=getattr(cliente, "_modelo", "desconocido"),
                    tuvo_error=True,
                    mensaje_error=f"Error interno: {raw}",
                    es_imagen=es_imagen,
                    idioma_prompt=idioma_prompt,
                )
            )
    return resultados


def construir_clientes(
    anthropic_key: str | None,
    openai_key: str | None,
    google_key: str | None,
    xai_key: str | None,
) -> list[BaseLLMClient]:
    """Construye la lista de clientes activos a partir de las claves disponibles.

    He puesto los imports dentro del cuerpo de la funcion en lugar de a nivel
    de modulo para evitar imports circulares: los clientes importan desde
    app.models.enums, que a su vez podria ser importado por otros modulos
    que importan runner. Al poner los imports aqui, solo se ejecutan cuando
    se llama a esta funcion, no al importar el modulo.

    Un cliente se omite sin error si su clave es None o vacia. Esto me permite
    arrancar en desarrollo con solo algunas APIs configuradas (por ejemplo,
    solo con la clave de Claude mientras las otras estan en tramite).

    Args:
        anthropic_key: Clave de Anthropic (Claude Sonnet 4.6).
        openai_key: Clave de OpenAI (GPT-4o + DALL-E 3 + gpt-image-1).
        google_key: Clave de Google AI (Gemini 2.5 Flash + Imagen 4).
        xai_key: Clave de xAI (Grok 4.3 + grok-imagine-image).

    Returns:
        Lista de BaseLLMClient instanciados y listos para usar.
    """
    from app.llm_engine.clients.claude_client import ClaudeClient
    from app.llm_engine.clients.gemini_client import GeminiClient
    from app.llm_engine.clients.grok_client import GrokClient
    from app.llm_engine.clients.openai_client import OpenAIClient

    clientes: list[BaseLLMClient] = []
    if anthropic_key:
        clientes.append(ClaudeClient(anthropic_key))
    if openai_key:
        clientes.append(OpenAIClient(openai_key))
    if google_key:
        clientes.append(GeminiClient(google_key))
    if xai_key:
        clientes.append(GrokClient(xai_key))
    return clientes
