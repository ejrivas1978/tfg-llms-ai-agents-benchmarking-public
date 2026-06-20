"""
Modulo: llm_response_repository
Ruta:   backend/app/repositories/llm_response_repository.py

Descripcion:
    Repository para LLMResponse. Encapsula la persistencia de las respuestas
    LLM y las consultas de agregacion para el dashboard.

Sprint: Sprint 2
"""

import sqlalchemy as sa
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.llm_engine.resultado import ResultadoLLM
from app.models.benchmark_evaluacion import BenchmarkEvaluacion
from app.models.enums import SessionStatus
from app.models.llm_response import LLMResponse


class LLMResponseRepository:
    """Repositorio de operaciones de base de datos para LLMResponse."""

    def __init__(self, db: AsyncSession) -> None:
        """Inicializa el repositorio con la sesion de base de datos.

        Args:
            db: Sesion asincrona de SQLAlchemy.
        """
        self._db = db

    async def crear_desde_resultado(
        self,
        evaluacion_id: int,
        resultado: ResultadoLLM,
    ) -> LLMResponse:
        """Persiste un ResultadoLLM como LLMResponse en la base de datos.

        Convierte el dataclass del motor LLM al modelo ORM, mapeando
        todos los campos incluyendo las metricas calculadas.

        Args:
            evaluacion_id: ID de la BenchmarkEvaluacion padre.
            resultado: ResultadoLLM devuelto por el cliente LLM.

        Returns:
            Instancia de LLMResponse persistida y refrescada.
        """
        respuesta = LLMResponse(
            evaluacion_id=evaluacion_id,
            provider=resultado.proveedor,
            model_name=resultado.modelo,
            response_text=resultado.url_imagen if resultado.es_imagen else resultado.texto_respuesta,
            input_tokens=resultado.tokens_entrada,
            output_tokens=resultado.tokens_salida,
            input_tokens_cached=resultado.tokens_entrada_cacheados,
            latency_ms=resultado.latencia_ms,
            tokens_por_segundo=resultado.tokens_por_segundo,
            ratio_sal_ent=resultado.ratio_sal_ent,
            cost_usd=resultado.coste_usd,
            coste_por_100_palabras=resultado.coste_por_100_palabras,
            palabras=resultado.palabras,
            diversidad_lexica=resultado.diversidad_lexica,
            parrafos=resultado.parrafos,
            tuvo_error=resultado.tuvo_error,
            error_message=resultado.mensaje_error,
            imagen_miniatura=resultado.imagen_miniatura,
            # FK a la version de tarifa vigente al hacer la llamada. None si el
            # cache no estaba hidratado o el cliente fallo antes de calcular coste.
            tarifa_id=resultado.tarifa_id,
            # Idioma del prompt enviado a este LLM ('es' o 'en'). En categorias
            # bilingues cada evaluacion produce 4 filas con 'es' y 4 con 'en'.
            idioma_prompt=resultado.idioma_prompt,
        )
        self._db.add(respuesta)
        await self._db.flush()
        await self._db.refresh(respuesta)
        return respuesta

    async def obtener_por_id(self, response_id: int) -> LLMResponse | None:
        """Obtiene una LLMResponse con su evaluacion padre cargada.

        Args:
            response_id: ID de la respuesta LLM.

        Returns:
            LLMResponse con relacion benchmark cargada, o None si no existe.
        """
        resultado = await self._db.execute(
            select(LLMResponse)
            .where(LLMResponse.id == response_id)
            .options(selectinload(LLMResponse.benchmark))
        )
        return resultado.scalar_one_or_none()

    async def textos_por_evaluacion_y_proveedor(self) -> list[dict]:
        """Devuelve los textos de respuesta de evaluaciones de texto completadas (excluye imagen).

        Usado por StatsService para calcular la similitud Jaccard media
        entre pares de proveedores. Las evaluaciones de imagen se excluyen porque
        su response_text es una URL o data-URI, no texto comparable.
        Solo evaluaciones completadas para no incluir datos en transito.

        Filtra a idioma_prompt='es' porque el Jaccard agregado del dashboard
        compara proveedores sobre el corpus que el humano evalua (castellano).
        Las respuestas EN de la comparativa bilingue se agregan aparte en
        textos_por_evaluacion_y_proveedor_por_idioma() para no mezclar
        vocabularios de dos idiomas en un mismo conjunto.

        Returns:
            Lista de dicts con evaluacion_id, provider y response_text.
        """
        resultado = await self._db.execute(
            select(
                LLMResponse.evaluacion_id,
                LLMResponse.provider,
                LLMResponse.response_text,
            )
            .join(BenchmarkEvaluacion, LLMResponse.evaluacion_id == BenchmarkEvaluacion.id)
            .where(
                LLMResponse.tuvo_error.is_(False),
                LLMResponse.response_text.is_not(None),
                LLMResponse.idioma_prompt == "es",
                BenchmarkEvaluacion.status == SessionStatus.completada,
                BenchmarkEvaluacion.es_generacion_imagen.is_(False),
            )
        )
        return [row._asdict() for row in resultado.all()]

    async def medias_imagen_por_proveedor(self) -> list[dict]:
        """Devuelve las medias de metricas de imagen agrupadas por proveedor.

        Solo incluye evaluaciones de categoria imagen completadas y sin error.

        Returns:
            Lista de dicts con proveedor, n, latencia_ms y cost_usd.
        """
        resultado = await self._db.execute(
            select(
                LLMResponse.provider,
                func.count(LLMResponse.id).label("n"),
                func.avg(LLMResponse.latency_ms).label("latencia_ms"),
                func.avg(LLMResponse.cost_usd).label("cost_usd"),
            )
            .join(BenchmarkEvaluacion, LLMResponse.evaluacion_id == BenchmarkEvaluacion.id)
            .where(
                LLMResponse.tuvo_error.is_(False),
                BenchmarkEvaluacion.status == SessionStatus.completada,
                BenchmarkEvaluacion.es_generacion_imagen.is_(True),
            )
            .group_by(LLMResponse.provider)
        )
        return [row._asdict() for row in resultado.all()]

    # Subcategoria que corresponde a edicion img2img. El resto de subcategorias
    # de imagen (generar, logotipo) son generacion txt2img.
    _SUBCATEGORIA_EDICION_IMAGEN = "modificar"

    async def costes_imagen_por_proveedor_y_modo(self) -> list[dict]:
        """Coste medio por imagen agrupado por proveedor y por modo (generar/editar).

        Una fila por (proveedor, modo) con datos. El modo se deriva de la
        subcategoria de la evaluacion ('modificar' = editar; 'generar' y
        'logotipo' = generar), no del model_name: desde que un mismo modelo
        sirve para generar y editar (p. ej. gemini-2.5-flash-image y gpt-image-1),
        el nombre del modelo ya no distingue el modo.

        Limita el ambito a respuestas de evaluaciones de imagen completadas
        sin error, igual que medias_imagen_por_proveedor() para mantener
        coherencia entre las dos graficas del bloque imagen.

        Returns:
            Lista de dicts con proveedor, modo ('generar' o 'editar'),
            n y cost_usd (media).
        """
        modo = sa.case(
            (
                BenchmarkEvaluacion.subcategoria_csv == self._SUBCATEGORIA_EDICION_IMAGEN,
                "editar",
            ),
            else_="generar",
        ).label("modo")
        resultado = await self._db.execute(
            select(
                LLMResponse.provider,
                modo,
                func.count(LLMResponse.id).label("n"),
                func.avg(LLMResponse.cost_usd).label("cost_usd"),
            )
            .join(BenchmarkEvaluacion, LLMResponse.evaluacion_id == BenchmarkEvaluacion.id)
            .where(
                LLMResponse.tuvo_error.is_(False),
                BenchmarkEvaluacion.status == SessionStatus.completada,
                BenchmarkEvaluacion.es_generacion_imagen.is_(True),
            )
            .group_by(LLMResponse.provider, modo)
        )
        return [row._asdict() for row in resultado.all()]

    async def medias_por_proveedor(self) -> list[dict]:
        """Devuelve las medias de metricas de texto agrupadas por proveedor.

        Excluye evaluaciones de imagen para evitar sesgar las medias con los ceros
        de metricas no aplicables (palabras=0, tok/s=0, diversidad=0, etc.).
        Solo evaluaciones completadas para no incluir datos en transito.
        Las metricas del dashboard reflejan exclusivamente el rendimiento en texto.

        Filtra a idioma_prompt='es' para que las medias del dashboard global
        sigan reflejando el corpus principal del estudio (las respuestas EN de
        la comparativa bilingue son un sub-experimento controlado y se agregan
        aparte en medias_comparativa_es_en()).

        Returns:
            Lista de diccionarios con proveedor y medias de metricas de texto.
        """
        resultado = await self._db.execute(
            select(
                LLMResponse.provider,
                func.count(LLMResponse.id).label("n"),
                func.avg(LLMResponse.latency_ms).label("latencia_ms"),
                func.avg(LLMResponse.input_tokens).label("tokens_entrada"),
                func.avg(LLMResponse.output_tokens).label("tokens_salida"),
                func.avg(LLMResponse.tokens_por_segundo).label("tokens_por_segundo"),
                func.avg(LLMResponse.cost_usd).label("cost_usd"),
                func.avg(LLMResponse.coste_por_100_palabras).label("coste_por_100_palabras"),
                func.avg(LLMResponse.palabras).label("palabras"),
                func.avg(LLMResponse.diversidad_lexica).label("diversidad_lexica"),
                func.avg(LLMResponse.parrafos).label("parrafos"),
            )
            .join(BenchmarkEvaluacion, LLMResponse.evaluacion_id == BenchmarkEvaluacion.id)
            .where(
                LLMResponse.tuvo_error.is_(False),
                LLMResponse.idioma_prompt == "es",
                BenchmarkEvaluacion.status == SessionStatus.completada,
                BenchmarkEvaluacion.es_generacion_imagen.is_(False),
            )
            .group_by(LLMResponse.provider)
        )
        return [row._asdict() for row in resultado.all()]

    async def medias_comparativa_es_en(self) -> list[dict]:
        """Medias por (proveedor, idioma_prompt) sobre la comparativa bilingue.

        Restringido a las evaluaciones que tienen al menos una respuesta EN
        (esto identifica el sub-experimento bilingue sin necesidad de
        filtrar por categoria). Para cada par (proveedor, idioma) devuelve
        n y la media de las metricas tecnicas comparables: latencia, tokens
        entrada/salida, tok/s, coste, palabras, diversidad lexica.

        Pensado para la tarjeta 'Comparativa ES vs EN' del dashboard:
        permite renderizar barras agrupadas con cuatro proveedores en X y
        dos series (ES, EN) por metrica.

        Returns:
            Lista de dicts con proveedor, idioma_prompt y medias agregadas.
        """
        # Subconsulta: evaluaciones con al menos una respuesta EN.
        # Equivale a identificar las evaluaciones del sub-experimento bilingue
        # sin acoplarnos al enum TestCategory desde el repository.
        evaluaciones_bilingues = (
            select(LLMResponse.evaluacion_id)
            .where(LLMResponse.idioma_prompt == "en")
            .distinct()
            .scalar_subquery()
        )
        resultado = await self._db.execute(
            select(
                LLMResponse.provider,
                LLMResponse.idioma_prompt,
                func.count(LLMResponse.id).label("n"),
                func.avg(LLMResponse.latency_ms).label("latencia_ms"),
                func.avg(LLMResponse.input_tokens).label("tokens_entrada"),
                func.avg(LLMResponse.output_tokens).label("tokens_salida"),
                func.avg(LLMResponse.tokens_por_segundo).label("tokens_por_segundo"),
                func.avg(LLMResponse.cost_usd).label("cost_usd"),
                func.avg(LLMResponse.coste_por_100_palabras).label("coste_por_100_palabras"),
                func.avg(LLMResponse.palabras).label("palabras"),
                func.avg(LLMResponse.diversidad_lexica).label("diversidad_lexica"),
                func.avg(LLMResponse.parrafos).label("parrafos"),
            )
            .join(BenchmarkEvaluacion, LLMResponse.evaluacion_id == BenchmarkEvaluacion.id)
            .where(
                LLMResponse.tuvo_error.is_(False),
                BenchmarkEvaluacion.status == SessionStatus.completada,
                BenchmarkEvaluacion.es_generacion_imagen.is_(False),
                LLMResponse.evaluacion_id.in_(evaluaciones_bilingues),
            )
            .group_by(LLMResponse.provider, LLMResponse.idioma_prompt)
        )
        return [row._asdict() for row in resultado.all()]
