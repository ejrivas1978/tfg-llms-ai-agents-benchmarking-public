"""
Modulo: services.stats_service
Ruta:   backend/app/services/stats_service.py

Descripcion:
    Capa de servicio para la agregacion de estadisticas del dashboard.
    Combina datos de los tres repositorios en el DTO RespuestaStats que
    alimenta los 13 graficos del dashboard (ADR-016).

    Calculo de similitud Jaccard entre pares de proveedores:
        Se cargan todos los textos de respuesta sin error desde la BD y se
        calculan los pares en Python. Esto evita logica compleja en SQL y
        es suficientemente rapido para el volumen de un estudio TFG (~500 evaluaciones).

    DECISION(ADR-003): Toda la logica de agregacion reside en el Service.
    DECISION(ADR-016): El dashboard separa metricas humanas de metricas automaticas.

Dependencias:
    - app.llm_engine.metricas
    - app.models.enums
    - app.repositories.benchmark_evaluacion_repository
    - app.repositories.llm_response_repository
    - app.repositories.user_evaluation_repository
    - app.schemas.stats

Sprint: Sprint 2
"""

import logging
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm_engine.metricas import jaccard_bigramas
from app.models.enums import LLMProvider
from app.repositories.benchmark_evaluacion_repository import BenchmarkEvaluacionRepository
from app.repositories.llm_response_repository import LLMResponseRepository
from app.repositories.user_evaluation_repository import UserEvaluationRepository
from app.schemas.stats import (
    CeldaHeatmap,
    CosteImagenPorModo,
    EvaluacionesSemana,
    JaccardPar,
    MetricasComparativaIdioma,
    MetricaHumanaImagenSubcat,
    MetricasImagenModelo,
    MetricasModelo,
    RankingImagenModelo,
    RatingImagenModelo,
    RespuestaStats,
    TasaRechazo,
)
from app.services.tarifa_service import TarifaService

logger = logging.getLogger(__name__)


def _prov_valor(raw: object) -> str:
    """Extrae el valor canonico de un campo provider devuelto por SQLAlchemy.

    En Python 3.12+ str() sobre un enum mixto (str, Enum) devuelve
    'LLMProvider.claude' en lugar de 'claude'. Esta funcion normaliza
    ambos casos para que LLMProvider(valor) siempre funcione.
    """
    if isinstance(raw, LLMProvider):
        return raw.value
    return str(raw)


class StatsService:
    """Capa de servicio para la agregacion de estadisticas del dashboard.

    Combina las consultas de los tres repositorios y realiza los calculos
    de enriquecimiento (Jaccard por pares, merge de ratings) en Python.

    Atributos:
        _db: Sesion asincrona SQLAlchemy inyectada via dependencia FastAPI.
        _benchmark_repo: Repositorio de BenchmarkEvaluacion.
        _respuesta_repo: Repositorio de LLMResponse.
        _eval_repo: Repositorio de UserEvaluation.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Inicializa el servicio con sus repositorios.

        Args:
            db: AsyncSession proporcionada por la dependencia get_db de FastAPI.
        """
        self._db = db
        self._benchmark_repo = BenchmarkEvaluacionRepository(db)
        self._respuesta_repo = LLMResponseRepository(db)
        self._eval_repo = UserEvaluationRepository(db)

    async def obtener(self) -> RespuestaStats:
        """Agrega todas las estadisticas para el dashboard en una sola llamada.

        Ejecuta las consultas de repositorio de forma secuencial (SQLAlchemy
        async no permite ejecutarlas en paralelo sobre la misma sesion) y
        combina los resultados en el DTO RespuestaStats.

        Returns:
            RespuestaStats con todos los datos necesarios para los 13 graficos.
        """
        total_evaluaciones       = await self._benchmark_repo.contar_evaluaciones()
        total_imagen_generativa  = await self._benchmark_repo.contar_evaluaciones_imagen_generativa()
        total_evaluadores        = await self._benchmark_repo.contar_evaluadores()
        evaluaciones_puntuadas   = await self._benchmark_repo.contar_evaluaciones_puntuadas()

        medias_llm       = await self._respuesta_repo.medias_por_proveedor()
        medias_imagen    = await self._respuesta_repo.medias_imagen_por_proveedor()
        costes_img_modo  = await self._respuesta_repo.costes_imagen_por_proveedor_y_modo()
        tarifas_vigentes = await TarifaService(self._db).listar_con_relativos()
        ratings_prov  = await self._eval_repo.ratings_por_proveedor()
        ranking_prov  = await self._eval_repo.ranking_medio_por_proveedor()
        ratings_cat        = await self._eval_repo.ratings_por_proveedor_y_categoria()
        ratings_img_raw    = await self._eval_repo.ratings_generacion_imagen_por_proveedor()
        ranking_img_raw    = await self._eval_repo.ranking_generacion_imagen_por_proveedor()
        humanas_img_subcat = await self._eval_repo.metricas_humanas_imagen_por_subcategoria()
        rechazo_raw        = await self._eval_repo.tasa_rechazo_por_proveedor()

        textos = await self._respuesta_repo.textos_por_evaluacion_y_proveedor()
        comparativa_raw = await self._respuesta_repo.medias_comparativa_es_en()

        semanas_raw = await self._benchmark_repo.evaluaciones_por_semana()
        por_categoria = await self._benchmark_repo.evaluaciones_por_categoria()

        metricas_por_modelo        = self._combinar_metricas(medias_llm, ratings_prov, ranking_prov)
        metricas_imagen_por_modelo = self._construir_metricas_imagen(medias_imagen)
        costes_imagen_por_modo     = self._construir_costes_imagen_por_modo(costes_img_modo)
        ratings_imagen_generativa  = self._construir_ratings_imagen(ratings_img_raw)
        ranking_imagen_generativa  = self._construir_ranking_imagen(ranking_img_raw)
        metricas_humanas_imagen_subcategoria = self._construir_humanas_imagen_subcat(humanas_img_subcat)
        heatmap                    = self._construir_heatmap(ratings_cat)
        jaccard                    = self._calcular_pares_jaccard(textos)
        tasa_rechazo               = self._construir_tasa_rechazo(rechazo_raw)
        comparativa_es_en          = self._construir_comparativa_es_en(comparativa_raw)
        por_semana = [
            EvaluacionesSemana(semana=r["semana"], total=r["total"]) for r in semanas_raw
        ]

        return RespuestaStats(
            total_evaluaciones=total_evaluaciones,
            total_texto_vision=total_evaluaciones - total_imagen_generativa,
            total_imagen_generativa=total_imagen_generativa,
            total_evaluadores=total_evaluadores,
            evaluaciones_puntuadas=evaluaciones_puntuadas,
            metricas_por_modelo=metricas_por_modelo,
            metricas_imagen_por_modelo=metricas_imagen_por_modelo,
            costes_imagen_por_modo=costes_imagen_por_modo,
            tarifas_vigentes=tarifas_vigentes,
            ratings_imagen_generativa=ratings_imagen_generativa,
            ranking_imagen_generativa=ranking_imagen_generativa,
            metricas_humanas_imagen_subcategoria=metricas_humanas_imagen_subcategoria,
            heatmap=heatmap,
            jaccard=jaccard,
            evaluaciones_por_semana=por_semana,
            evaluaciones_por_categoria=por_categoria,
            tasa_rechazo=tasa_rechazo,
            comparativa_es_en=comparativa_es_en,
        )

    def _combinar_metricas(
        self,
        medias_llm: list[dict],
        ratings_prov: list[dict],
        ranking_prov: list[dict],
    ) -> list[MetricasModelo]:
        """Combina metricas LLM con ratings y rankings de preferencia de usuario.

        El join se realiza en Python sobre la clave 'provider'.
        Los proveedores sin valoraciones obtienen rating_medio=None, rango_preferencia_medio=None.

        Args:
            medias_llm: Salida de LLMResponseRepository.medias_por_proveedor().
            ratings_prov: Salida de UserEvaluationRepository.ratings_por_proveedor().
            ranking_prov: Salida de UserEvaluationRepository.ranking_medio_por_proveedor().

        Returns:
            Lista de MetricasModelo ordenada por proveedor.
        """
        indice_ratings: dict[str, dict] = {r["provider"]: r for r in ratings_prov}
        indice_ranking: dict[str, dict] = {r["provider"]: r for r in ranking_prov}

        resultado = []
        for fila in medias_llm:
            prov = _prov_valor(fila["provider"])
            rating_info  = indice_ratings.get(prov, {})
            ranking_info = indice_ranking.get(prov, {})
            resultado.append(
                MetricasModelo(
                    proveedor=LLMProvider(prov),
                    latencia_ms=float(fila["latencia_ms"] or 0),
                    tokens_entrada=float(fila["tokens_entrada"] or 0),
                    tokens_salida=float(fila["tokens_salida"] or 0),
                    tokens_por_segundo=float(fila["tokens_por_segundo"] or 0),
                    cost_usd=float(fila["cost_usd"] or 0),
                    coste_por_100_palabras=float(fila["coste_por_100_palabras"] or 0),
                    palabras=float(fila["palabras"] or 0),
                    diversidad_lexica=float(fila["diversidad_lexica"] or 0),
                    parrafos=float(fila["parrafos"] or 0),
                    rating_medio=float(rating_info["rating_medio"]) if rating_info.get("rating_medio") else None,
                    rango_preferencia_medio=float(ranking_info["rango_medio"]) if ranking_info.get("rango_medio") else None,
                    n_evaluaciones=int(fila["n"]),
                    n_puntuadas=int(rating_info.get("n_puntuadas", 0)),
                )
            )
        return sorted(resultado, key=lambda m: m.proveedor.value)

    def _construir_heatmap(self, ratings_cat: list[dict]) -> list[CeldaHeatmap]:
        """Convierte los datos brutos del repositorio en celdas de heatmap.

        Args:
            ratings_cat: Salida de UserEvaluationRepository.ratings_por_proveedor_y_categoria().

        Returns:
            Lista de CeldaHeatmap ordenada por (proveedor, categoria).
        """
        celdas = [
            CeldaHeatmap(
                proveedor=LLMProvider(_prov_valor(fila["provider"])),
                categoria=fila["categoria"],
                rating_medio=float(fila["rating_medio"]) if fila.get("rating_medio") else None,
                n=int(fila["n"]),
            )
            for fila in ratings_cat
        ]
        return sorted(celdas, key=lambda c: (c.proveedor.value, c.categoria.value))

    def _construir_metricas_imagen(self, medias: list[dict]) -> list[MetricasImagenModelo]:
        """Construye la lista de metricas de imagen por proveedor.

        Args:
            medias: Salida de LLMResponseRepository.medias_imagen_por_proveedor().

        Returns:
            Lista de MetricasImagenModelo ordenada por proveedor.
        """
        resultado = []
        for fila in medias:
            resultado.append(
                MetricasImagenModelo(
                    proveedor=LLMProvider(_prov_valor(fila["provider"])),
                    n_evaluaciones=int(fila["n"]),
                    latencia_ms=float(fila["latencia_ms"] or 0),
                    cost_usd=float(fila["cost_usd"] or 0),
                )
            )
        return sorted(resultado, key=lambda m: m.proveedor.value)

    def _construir_costes_imagen_por_modo(
        self, filas: list[dict]
    ) -> list[CosteImagenPorModo]:
        """Construye el desglose de coste medio por (proveedor, modo).

        Ordena por proveedor y dentro de cada proveedor pone 'generar' antes
        de 'editar' para que la grafica de barras agrupadas mantenga ese
        orden visual consistente entre proveedores.

        Args:
            filas: Salida de LLMResponseRepository.costes_imagen_por_proveedor_y_modo().

        Returns:
            Lista de CosteImagenPorModo ordenada por (proveedor, modo).
        """
        items = [
            CosteImagenPorModo(
                proveedor=LLMProvider(_prov_valor(fila["provider"])),
                modo=str(fila["modo"]),
                n=int(fila["n"]),
                cost_usd=float(fila["cost_usd"] or 0),
            )
            for fila in filas
        ]
        # Orden: proveedor alfabetico, luego 'generar' antes que 'editar'.
        orden_modo = {"generar": 0, "editar": 1}
        return sorted(
            items, key=lambda c: (c.proveedor.value, orden_modo.get(c.modo, 9))
        )

    def _construir_ratings_imagen(self, ratings_raw: list[dict]) -> list[RatingImagenModelo]:
        """Construye la lista de ratings de generacion de imagen por proveedor.

        Args:
            ratings_raw: Salida de UserEvaluationRepository.ratings_generacion_imagen_por_proveedor().

        Returns:
            Lista de RatingImagenModelo ordenada por proveedor.
        """
        return sorted(
            [
                RatingImagenModelo(
                    proveedor=LLMProvider(_prov_valor(fila["provider"])),
                    rating_medio=float(fila["rating_medio"]) if fila.get("rating_medio") else None,
                    n=int(fila["n"]),
                )
                for fila in ratings_raw
            ],
            key=lambda r: r.proveedor.value,
        )

    def _construir_ranking_imagen(self, ranking_raw: list[dict]) -> list[RankingImagenModelo]:
        """Construye la lista de ranking de preferencia de imagen por proveedor.

        Args:
            ranking_raw: Salida de UserEvaluationRepository.ranking_generacion_imagen_por_proveedor().

        Returns:
            Lista de RankingImagenModelo ordenada por proveedor.
        """
        return sorted(
            [
                RankingImagenModelo(
                    proveedor=LLMProvider(_prov_valor(fila["provider"])),
                    rango_medio=float(fila["rango_medio"]) if fila.get("rango_medio") else None,
                    n=int(fila["n"]),
                )
                for fila in ranking_raw
            ],
            key=lambda r: r.proveedor.value,
        )

    def _construir_humanas_imagen_subcat(
        self, filas_raw: list[dict]
    ) -> list[MetricaHumanaImagenSubcat]:
        """Construye las metricas humanas (rating + ranking) por subcategoria de imagen.

        Args:
            filas_raw: Salida de
                UserEvaluationRepository.metricas_humanas_imagen_por_subcategoria().

        Returns:
            Lista de MetricaHumanaImagenSubcat ordenada por (subcategoria, proveedor).
        """
        return sorted(
            [
                MetricaHumanaImagenSubcat(
                    subcategoria=str(fila["subcategoria"]),
                    proveedor=LLMProvider(_prov_valor(fila["provider"])),
                    rating_medio=float(fila["rating_medio"]) if fila.get("rating_medio") is not None else None,
                    rango_medio=float(fila["rango_medio"]) if fila.get("rango_medio") is not None else None,
                    n=int(fila["n"]),
                )
                for fila in filas_raw
            ],
            key=lambda m: (m.subcategoria, m.proveedor.value),
        )

    def _construir_comparativa_es_en(
        self, comparativa_raw: list[dict]
    ) -> list[MetricasComparativaIdioma]:
        """Construye la lista de medias agrupadas por (proveedor, idioma) para la comparativa.

        Acepta idioma_prompt='es' o 'en'; el frontend agrupa por proveedor y
        pinta dos barras por metrica (ES vs EN). Orden estable: por proveedor
        alfabetico y dentro de cada proveedor ES antes que EN para que las
        graficas de barras agrupadas tengan colocacion consistente.

        Args:
            comparativa_raw: Salida de LLMResponseRepository.medias_comparativa_es_en().

        Returns:
            Lista de MetricasComparativaIdioma ordenada por (proveedor, idioma).
        """
        items: list[MetricasComparativaIdioma] = []
        for fila in comparativa_raw:
            idioma = str(fila["idioma_prompt"])
            items.append(
                MetricasComparativaIdioma(
                    proveedor=LLMProvider(_prov_valor(fila["provider"])),
                    idioma_prompt=idioma,
                    n_evaluaciones=int(fila["n"]),
                    latencia_ms=float(fila["latencia_ms"] or 0),
                    tokens_entrada=float(fila["tokens_entrada"] or 0),
                    tokens_salida=float(fila["tokens_salida"] or 0),
                    tokens_por_segundo=float(fila["tokens_por_segundo"] or 0),
                    cost_usd=float(fila["cost_usd"] or 0),
                    coste_por_100_palabras=float(fila["coste_por_100_palabras"] or 0),
                    palabras=float(fila["palabras"] or 0),
                    diversidad_lexica=float(fila["diversidad_lexica"] or 0),
                    parrafos=float(fila["parrafos"] or 0),
                )
            )
        orden_idioma = {"es": 0, "en": 1}
        return sorted(
            items,
            key=lambda m: (m.proveedor.value, orden_idioma.get(m.idioma_prompt, 9)),
        )

    def _construir_tasa_rechazo(self, rechazo_raw: list[dict]) -> list[TasaRechazo]:
        """Construye la lista de tasas de rechazo por proveedor.

        Args:
            rechazo_raw: Salida de UserEvaluationRepository.tasa_rechazo_por_proveedor().

        Returns:
            Lista de TasaRechazo ordenada por proveedor.
        """
        resultado = []
        for fila in rechazo_raw:
            total = int(fila["total"])
            rechazos = int(fila["rechazos"] or 0)
            resultado.append(
                TasaRechazo(
                    proveedor=LLMProvider(_prov_valor(fila["provider"])),
                    total_participaciones=total,
                    total_rechazos=rechazos,
                    tasa=round(rechazos / total, 4) if total > 0 else 0.0,
                )
            )
        return sorted(resultado, key=lambda t: t.proveedor.value)

    def _calcular_pares_jaccard(self, textos: list[dict]) -> list[JaccardPar]:
        """Calcula la similitud Jaccard media entre todos los pares de proveedores.

        Agrupa los textos por evaluacion y calcula el Jaccard de bigramas para
        cada par (proveedor_a, proveedor_b) en las evaluaciones donde ambos
        esten presentes. Los pares se indexan en orden alfabetico para evitar
        duplicados (claude-openai y openai-claude son el mismo par).

        Args:
            textos: Salida de LLMResponseRepository.textos_por_evaluacion_y_proveedor().

        Returns:
            Lista de JaccardPar ordenada por (proveedor_a, proveedor_b).
        """
        # Agrupa {evaluacion_id: {provider: response_text}}
        por_evaluacion: dict[int, dict[str, str]] = defaultdict(dict)
        for fila in textos:
            texto = fila.get("response_text") or ""
            if texto.strip():
                por_evaluacion[fila["evaluacion_id"]][_prov_valor(fila["provider"])] = texto

        # Acumula similitudes por par de proveedores
        acumulados: dict[tuple[str, str], list[float]] = defaultdict(list)
        for proveedores_textos in por_evaluacion.values():
            provs = sorted(proveedores_textos.keys())
            for i, pa in enumerate(provs):
                for pb in provs[i + 1:]:
                    j = jaccard_bigramas(proveedores_textos[pa], proveedores_textos[pb])
                    acumulados[(pa, pb)].append(j)

        if not acumulados:
            return []

        return sorted(
            [
                JaccardPar(
                    proveedor_a=LLMProvider(pa),
                    proveedor_b=LLMProvider(pb),
                    jaccard_medio=round(sum(vals) / len(vals), 4),
                    n=len(vals),
                )
                for (pa, pb), vals in acumulados.items()
            ],
            key=lambda jp: (jp.proveedor_a.value, jp.proveedor_b.value),
        )
