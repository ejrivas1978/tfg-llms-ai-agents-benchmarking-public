"""
Modulo: schemas/benchmark
Ruta:   backend/app/schemas/benchmark.py

Descripcion:
    DTOs Pydantic para los endpoints de benchmark.
    Separan la representacion HTTP de los modelos ORM internos.

Sprint: Sprint 2
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import LLMProvider, SessionStatus, TestCategory


class PeticionBenchmark(BaseModel):
    """Cuerpo de la peticion POST /api/v1/benchmarks/run.

    Atributos:
        nickname: Alias del evaluador (anonimo, sin cuenta).
        prompt: Texto que se enviara a todos los LLMs.
        categoria: Categoria del prompt para el dashboard.
    """

    nickname: str = Field(..., min_length=1, max_length=100)
    prompt: str = Field(..., min_length=1, max_length=65000)
    categoria: TestCategory
    imagen_base64: str | None = Field(None)
    imagen_mime_type: str | None = Field(None)
    # Subcategoria de imagen: 'generar' | 'describir' | 'logotipo' | 'modificar' | None
    # Cuando es 'describir' se usa completar() en todos los modelos (incluyendo Claude),
    # no generar_imagen(). Permite analisis vision tanto con URL como con fichero subido.
    subcat_imagen: str | None = Field(None)
    # Subcategoria human-readable solo para el CSV de admin. No afecta a runner
    # ni metricas. Frontend la calcula a partir de la opcion seleccionada.
    subcategoria_csv: str | None = Field(None, max_length=150)
    # Traduccion al ingles del prompt para la comparativa bilingue ES/EN.
    # Solo se rellena cuando categoria in (razonamiento, creativa, concretas)
    # Y el prompt elegido es predefinido (tiene su par EN validado). Si esta
    # presente, el backend lanza una segunda ronda con este prompt y persiste
    # 4 respuestas adicionales con idioma_prompt='en'.
    prompt_en: str | None = Field(None, max_length=65000)
    # Texto de entrada original (sin prefijo de instruccion) para la categoria resumen.
    # Solo se envia cuando el texto fue generado automaticamente por el LLM.
    texto_entrada: str | None = Field(None, max_length=65000)
    texto_entrada_autogenerado: bool = Field(False)


class RespuestaLLMDTO(BaseModel):
    """DTO para una respuesta individual de un LLM dentro de una sesion."""

    id: int
    proveedor: LLMProvider
    modelo: str
    texto_respuesta: str | None
    tokens_entrada: int
    tokens_salida: int
    latencia_ms: int
    tokens_por_segundo: float
    ratio_sal_ent: float
    cost_usd: float
    coste_por_100_palabras: float
    palabras: int
    diversidad_lexica: float
    parrafos: int
    tuvo_error: bool
    mensaje_error: str | None
    es_imagen: bool
    url_imagen: str | None
    imagen_miniatura: str | None
    # Idioma del prompt enviado a este LLM ('es' o 'en'). En categorias no
    # bilingues siempre es 'es'. El frontend lo usa para agrupar las 8 cards
    # de comparativa: 4 ES con controles de evaluacion y 4 EN bajo boton.
    idioma_prompt: str = "es"

    model_config = {"from_attributes": True}


class RespuestaBenchmark(BaseModel):
    """DTO de respuesta para POST /run y GET /{id}.

    Atributos:
        id: Identificador de la sesion.
        nickname: Alias del evaluador.
        prompt: Texto del prompt original.
        categoria: Categoria del benchmark.
        estado: Estado de la sesion (completada, fallida...).
        similitud_jaccard_media: Similitud media entre respuestas de texto.
        created_at: Momento de creacion.
        completed_at: Momento de finalizacion (None si aun en curso).
        respuestas: Lista de respuestas de cada LLM.
    """

    id: int
    nickname: str
    prompt: str
    categoria: TestCategory
    estado: SessionStatus
    similitud_jaccard_media: float | None
    created_at: datetime
    completed_at: datetime | None
    respuestas: list[RespuestaLLMDTO]
    texto_entrada: str | None = None
    texto_entrada_autogenerado: bool = False

    model_config = {"from_attributes": True}


class ResumenEvaluacionAdmin(BaseModel):
    """DTO ligero para el listado paginado de evaluaciones en el panel de administracion.

    No incluye las respuestas LLM para reducir el tamano de la respuesta.

    Atributos:
        evaluada: True si la comparativa tiene al menos una evaluacion de usuario.
    """

    id: int
    nickname: str
    prompt: str
    categoria: TestCategory
    estado: SessionStatus
    similitud_jaccard_media: float | None
    created_at: datetime
    completed_at: datetime | None
    evaluada: bool


class RespuestaListaEvaluaciones(BaseModel):
    """DTO de respuesta para GET /admin/evaluaciones (lista paginada).

    Atributos:
        items: Listado de evaluaciones en la pagina actual.
        total: Total de evaluaciones en la base de datos (para calcular paginas).
        pagina: Numero de pagina actual (basado en 1).
        paginas: Total de paginas disponibles.
    """

    items: list[ResumenEvaluacionAdmin]
    total: int
    pagina: int
    paginas: int


class RespuestaTextoEjemplo(BaseModel):
    """DTO de respuesta para GET /benchmarks/texto-ejemplo.

    Atributos:
        texto: Texto en castellano generado por el LLM (~300 palabras).
        palabras: Numero de palabras del texto devuelto.
        proveedor: Nombre del proveedor LLM que genero el texto.
    """

    texto: str
    palabras: int
    proveedor: str


class ResumenEvaluacionUsuario(BaseModel):
    """DTO ligero para GET /usuarios/mis-evaluaciones.

    Solo incluye los campos necesarios para renderizar el historial del usuario
    sin cargar las respuestas LLM completas. Construido manualmente en el router
    (el ORM usa category/status; el DTO expone categoria/estado).
    """

    id: int
    prompt: str
    categoria: TestCategory
    estado: SessionStatus
    created_at: datetime
    evaluada: bool
