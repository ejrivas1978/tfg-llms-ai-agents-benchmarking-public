/**
 * Modulo: types/stats
 * Ruta:   frontend/src/types/stats.ts
 *
 * Descripcion:
 *   Tipos TypeScript que replican los DTOs Pydantic del endpoint
 *   GET /api/v1/stats que alimenta el dashboard de metricas.
 *
 * Sprint: Sprint 3
 */

import type { LLMProvider, TestCategory } from '@/types/benchmark'
import type { RespuestaListaTarifas } from '@/types/admin'

export interface MetricasModelo {
  proveedor: LLMProvider
  latencia_ms: number
  tokens_entrada: number
  tokens_salida: number
  tokens_por_segundo: number
  cost_usd: number
  coste_por_100_palabras: number
  palabras: number
  diversidad_lexica: number
  parrafos: number
  rating_medio: number | null
  rango_preferencia_medio: number | null
  n_evaluaciones: number
  n_puntuadas: number
}

export interface CeldaHeatmap {
  proveedor: LLMProvider
  categoria: TestCategory
  rating_medio: number | null
  n: number
}

export interface JaccardPar {
  proveedor_a: LLMProvider
  proveedor_b: LLMProvider
  jaccard_medio: number
  n: number
}

export interface EvaluacionesSemana {
  semana: string
  total: number
}

export interface MetricasImagenModelo {
  proveedor: LLMProvider
  n_evaluaciones: number
  latencia_ms: number
  cost_usd: number
}

export interface CosteImagenPorModo {
  proveedor: LLMProvider
  modo: 'generar' | 'editar'
  n: number
  cost_usd: number
}

export interface RatingImagenModelo {
  proveedor: LLMProvider
  rating_medio: number | null
  n: number
}

export interface RankingImagenModelo {
  proveedor: LLMProvider
  rango_medio: number | null
  n: number
}

export interface MetricaHumanaImagenSubcat {
  subcategoria: 'generar' | 'describir' | 'logotipo' | 'modificar'
  proveedor: LLMProvider
  rating_medio: number | null
  rango_medio: number | null
  n: number
}

export interface TasaRechazo {
  proveedor: LLMProvider
  total_participaciones: number
  total_rechazos: number
  tasa: number
}

/**
 * Medias agregadas por (proveedor, idioma_prompt) sobre el sub-experimento
 * bilingue ES vs EN (ADR-029). El backend solo incluye evaluaciones que
 * tienen al menos una respuesta EN, asi que cuando la lista esta vacia
 * significa que el sub-experimento aun no tiene datos.
 */
export interface MetricasComparativaIdioma {
  proveedor: LLMProvider
  idioma_prompt: 'es' | 'en'
  n_evaluaciones: number
  latencia_ms: number
  tokens_entrada: number
  tokens_salida: number
  tokens_por_segundo: number
  cost_usd: number
  coste_por_100_palabras: number
  palabras: number
  diversidad_lexica: number
  parrafos: number
}

export interface RespuestaStats {
  total_evaluaciones: number
  total_texto_vision: number
  total_imagen_generativa: number
  total_evaluadores: number
  evaluaciones_puntuadas: number
  metricas_por_modelo: MetricasModelo[]
  metricas_imagen_por_modelo: MetricasImagenModelo[]
  costes_imagen_por_modo: CosteImagenPorModo[]
  /** Tarifas oficiales vigentes (texto + imagen generar/editar) por proveedor */
  tarifas_vigentes: RespuestaListaTarifas
  ratings_imagen_generativa: RatingImagenModelo[]
  ranking_imagen_generativa: RankingImagenModelo[]
  metricas_humanas_imagen_subcategoria: MetricaHumanaImagenSubcat[]
  heatmap: CeldaHeatmap[]
  jaccard: JaccardPar[]
  evaluaciones_por_semana: EvaluacionesSemana[]
  evaluaciones_por_categoria: Record<string, number>
  tasa_rechazo: TasaRechazo[]
  /**
   * Sub-experimento bilingue ES vs EN (ADR-029).
   * Lista vacia mientras no haya respuestas EN persistidas; el dashboard
   * oculta la tarjeta en ese caso para no mostrar un grafico sin datos.
   */
  comparativa_es_en: MetricasComparativaIdioma[]
}
