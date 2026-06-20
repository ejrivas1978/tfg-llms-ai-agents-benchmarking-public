"""
Modulo: resultado
Ruta:   backend/app/llm_engine/resultado.py

Descripcion:
    Dataclass inmutable que representa el resultado de una llamada a un LLM.
    Es el contrato de datos entre los clientes LLM y el runner/service:
    cualquier cliente devuelve siempre un ResultadoLLM, tanto si tuvo exito
    como si fallo, para que asyncio.gather no descarte ningun resultado.

Sprint: Sprint 2
"""

from dataclasses import dataclass

from app.llm_engine.sanitizar_error import sanitizar_mensaje_error
from app.models.enums import LLMProvider


@dataclass
class ResultadoLLM:
    """Resultado de una llamada a un proveedor LLM con todas las metricas calculadas.

    Atributos:
        proveedor: Identificador del proveedor (LLMProvider enum).
        modelo: Nombre exacto del modelo usado (ej: claude-3-5-sonnet-20241022).
        texto_respuesta: Texto generado. None si tuvo_error es True.
        tokens_entrada: Tokens del prompt segun la API del proveedor.
        tokens_salida: Tokens del completado segun la API.
        latencia_ms: Tiempo total de la llamada en milisegundos.
        tuvo_error: True si la llamada a la API fallo.
        mensaje_error: Descripcion del error. None si tuvo exito.
        tokens_por_segundo: tokens_salida / (latencia_ms / 1000).
        ratio_sal_ent: tokens_salida / tokens_entrada.
        coste_usd: Coste estimado segun precios del proveedor.
        coste_por_100_palabras: coste_usd / palabras * 100.
        palabras: Numero de palabras en texto_respuesta.
        diversidad_lexica: Type-token ratio (palabras unicas / palabras totales).
        parrafos: Numero de parrafos no vacios en texto_respuesta.
        es_imagen: True para tareas de imagen generativa (metricas de texto = 0).
        url_imagen: URL de la imagen generada. None para tareas de texto.
        imagen_miniatura: Miniatura JPEG en base64 (200x200 px). None si no aplica o fallo.
    """

    proveedor: LLMProvider
    modelo: str
    texto_respuesta: str | None = None
    tokens_entrada: int = 0
    tokens_salida: int = 0
    # Tokens del prompt servidos desde cache (cache hit). Lo expone cada API
    # de forma distinta y los clientes lo capturan defensivamente con getattr;
    # cuando la API no lo devuelve queda en 0 y el coste se calcula al precio
    # estandar de entrada sin descuento.
    tokens_entrada_cacheados: int = 0
    latencia_ms: int = 0
    tuvo_error: bool = False
    mensaje_error: str | None = None
    tokens_por_segundo: float = 0.0
    ratio_sal_ent: float = 0.0
    coste_usd: float = 0.0
    coste_por_100_palabras: float = 0.0
    palabras: int = 0
    diversidad_lexica: float = 0.0
    parrafos: int = 0
    es_imagen: bool = False
    url_imagen: str | None = None
    imagen_miniatura: str | None = None
    # ID de la fila tarifas_llm vigente al hacer la llamada. Se copia en
    # llm_responses.tarifa_id al persistir, para que cada respuesta quede
    # ligada a la version exacta de tarifa con la que se cobro su coste_usd.
    # None si el cache de precios aun no se ha hidratado desde BD.
    tarifa_id: int | None = None
    # Idioma del prompt que se envio al LLM ('es' o 'en'). En categorias
    # bilingues el runner lanza 2 rondas; cada ronda etiqueta sus 4
    # respuestas con el idioma correspondiente.
    idioma_prompt: str = 'es'

    def __post_init__(self) -> None:
        """Redacta credenciales del mensaje_error como ultima linea de defensa.

        Centralizar la sanitizacion aqui evita que un cliente nuevo (o un
        cambio en uno existente) olvide aplicarla y filtre la API key a
        BD/CSV. Cualquier ResultadoLLM creado en cualquier punto del codigo
        pasa por aqui.
        """
        self.mensaje_error = sanitizar_mensaje_error(self.mensaje_error)
