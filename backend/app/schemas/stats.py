"""
Modulo: schemas/stats
Ruta:   backend/app/schemas/stats.py

Descripcion:
    DTOs Pydantic para el endpoint GET /api/v1/stats que alimenta el dashboard.
    La estructura refleja exactamente los datos que el frontend necesita para
    los 13 graficos del dashboard (ADR-016).

Sprint: Sprint 2
"""

from pydantic import BaseModel

from app.models.enums import LLMProvider, TestCategory  # noqa: F401 (re-exported)
from app.schemas.tarifa import RespuestaListaTarifas


class MetricasModelo(BaseModel):
    """Metricas medias de un modelo sobre todas sus evaluaciones."""

    proveedor: LLMProvider
    latencia_ms: float
    tokens_entrada: float
    tokens_salida: float
    tokens_por_segundo: float
    cost_usd: float
    coste_por_100_palabras: float
    palabras: float
    diversidad_lexica: float
    parrafos: float
    rating_medio: float | None
    rango_preferencia_medio: float | None
    n_evaluaciones: int
    n_puntuadas: int


class CeldaHeatmap(BaseModel):
    """Valoracion media de un modelo en una categoria concreta."""

    proveedor: LLMProvider
    categoria: TestCategory
    rating_medio: float | None
    n: int


class JaccardPar(BaseModel):
    """Similitud Jaccard media entre un par de modelos."""

    proveedor_a: LLMProvider
    proveedor_b: LLMProvider
    jaccard_medio: float
    n: int


class EvaluacionesSemana(BaseModel):
    """Conteo de evaluaciones por semana ISO para el grafico de progreso."""

    semana: str   # Formato ISO: "2026-W18"
    total: int


class MetricasImagenModelo(BaseModel):
    """Metricas medias de generacion de imagen por modelo (solo evaluaciones imagen).

    Se limita a latencia y coste porque tamaño y dimensiones no son comparables:
    OpenAI y Grok devuelven URL externa (tamaño 0) y todos los modelos generan
    1024x1024 por defecto, por lo que esas columnas no aportan informacion diferencial.
    """

    proveedor: LLMProvider
    n_evaluaciones: int
    latencia_ms: float
    cost_usd: float


class RatingImagenModelo(BaseModel):
    """Rating medio de un modelo en evaluaciones de generacion de imagen."""

    proveedor: LLMProvider
    rating_medio: float | None
    n: int


class RankingImagenModelo(BaseModel):
    """Posicion media de preferencia de un modelo en evaluaciones de imagen.

    Equivalente al ranking de resultados totales agrupados pero solo sobre
    generacion de imagen. Permite comparar si el modelo mejor posicionado en
    el ranking coincide con el mejor valorado (rating) para imagenes.
    """

    proveedor: LLMProvider
    rango_medio: float | None
    n: int


class MetricaHumanaImagenSubcat(BaseModel):
    """Valoracion y ranking medios de un modelo en una subcategoria de imagen.

    Una entrada por (subcategoria, proveedor). subcategoria es una de las cuatro
    opciones de imagen: 'generar', 'describir', 'logotipo' o 'modificar'. Permite
    al dashboard desglosar la valoracion humana por tipo de tarea de imagen y
    alternar entre valoracion media y ranking de preferencia.
    """

    subcategoria: str       # 'generar' | 'describir' | 'logotipo' | 'modificar'
    proveedor: LLMProvider
    rating_medio: float | None
    rango_medio: float | None
    n: int


class CosteImagenPorModo(BaseModel):
    """Coste medio por imagen, desglosado por proveedor y modo (generar/editar).

    Una entrada por (proveedor, modo) con datos. Permite al frontend visualizar
    la asimetria de precios entre generacion (txt2img) y edicion (img2img) en
    una grafica de barras agrupadas, dado que tras ADR-028 los precios YA NO
    son iguales (Grok cuesta 0.02 generar / 0.05 editar; Gemini 0.04 / 0.039).
    """

    proveedor: LLMProvider
    modo: str       # 'generar' | 'editar'
    n: int
    cost_usd: float


class MetricasComparativaIdioma(BaseModel):
    """Medias tecnicas de un (proveedor, idioma_prompt) en el sub-experimento ES/EN.

    Solo agrega respuestas pertenecientes a evaluaciones que tienen su
    contraparte en ingles (categorias razonamiento, creativa, concretas
    con prompt predefinido). El humano nunca valora las respuestas EN,
    asi que este DTO se queda en metricas tecnicas comparables entre
    idiomas: latencia, tokens, tok/s, coste y propiedades del texto.

    Alimenta la tarjeta 'Comparativa ES vs EN' del dashboard (ADR-029):
    cuatro proveedores en el eje X y dos series (es/en) por metrica.
    """

    proveedor: LLMProvider
    idioma_prompt: str       # 'es' | 'en'
    n_evaluaciones: int
    latencia_ms: float
    tokens_entrada: float
    tokens_salida: float
    tokens_por_segundo: float
    cost_usd: float
    coste_por_100_palabras: float
    palabras: float
    diversidad_lexica: float
    parrafos: float


class TasaRechazo(BaseModel):
    """Tasa de rechazo por politica de seguridad de un modelo LLM.

    Mide la restrictividad de cada proveedor: que porcentaje de sus
    participaciones en evaluaciones fueron bloqueadas por sus filtros de
    contenido. Es la unica metrica del dashboard que incluye sesiones
    con censura; todas las demas las excluyen para evitar sesgo.
    """

    proveedor: LLMProvider
    total_participaciones: int
    total_rechazos: int
    tasa: float


class RespuestaStats(BaseModel):
    """DTO completo devuelto por GET /api/v1/stats.

    Estructura pensada para que el frontend pueda construir los graficos
    del dashboard en una sola peticion sin hacer joins en el cliente.
    """

    total_evaluaciones: int
    total_texto_vision: int
    total_imagen_generativa: int
    total_evaluadores: int
    evaluaciones_puntuadas: int
    metricas_por_modelo: list[MetricasModelo]
    metricas_imagen_por_modelo: list[MetricasImagenModelo]
    costes_imagen_por_modo: list[CosteImagenPorModo]
    # Tarifas vigentes para que el dashboard pueda mostrar la tabla oficial
    # de precios (texto + imagen generar + imagen editar + relativos) sin
    # depender de medias historicas que arrastran tarifas antiguas.
    tarifas_vigentes: RespuestaListaTarifas
    ratings_imagen_generativa: list[RatingImagenModelo]
    ranking_imagen_generativa: list[RankingImagenModelo]
    metricas_humanas_imagen_subcategoria: list[MetricaHumanaImagenSubcat]
    heatmap: list[CeldaHeatmap]
    jaccard: list[JaccardPar]
    evaluaciones_por_semana: list[EvaluacionesSemana]
    evaluaciones_por_categoria: dict[str, int]
    tasa_rechazo: list[TasaRechazo]
    # Sub-experimento bilingue ES vs EN sobre razonamiento, creativa y
    # concretas. Lista vacia mientras no haya datos persistidos para no
    # forzar al frontend a un branch especial: la tarjeta se oculta cuando
    # comparativa_es_en esta vacia.
    comparativa_es_en: list[MetricasComparativaIdioma]
