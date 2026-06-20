/**
 * Modulo: types/benchmark
 * Ruta:   frontend/src/types/benchmark.ts
 *
 * Descripcion:
 *   Tipos TypeScript que replican los DTOs Pydantic del backend.
 *   Fuente de verdad de los datos de benchmark en el frontend.
 *
 * Sprint: Sprint 3
 */

export type LLMProvider = 'claude' | 'openai' | 'gemini' | 'grok'

export type TestCategory =
  | 'razonamiento'
  | 'codigo'
  | 'creativa'
  | 'concretas'
  | 'traduccion'
  | 'resumen'
  | 'imagen'
  | 'libre'

export type SessionStatus = 'pendiente' | 'en_curso' | 'completada' | 'fallida' | 'solicitud_borrado'

export interface RespuestaLLM {
  id: number
  proveedor: LLMProvider
  modelo: string
  texto_respuesta: string | null
  tokens_entrada: number
  tokens_salida: number
  latencia_ms: number
  tokens_por_segundo: number
  ratio_sal_ent: number
  cost_usd: number
  coste_por_100_palabras: number
  palabras: number
  diversidad_lexica: number
  parrafos: number
  tuvo_error: boolean
  mensaje_error: string | null
  es_imagen: boolean
  url_imagen: string | null
  imagen_miniatura: string | null
  /**
   * Idioma del prompt enviado a este LLM, 'es' o 'en'.
   * Sub-experimento bilingue ES/EN (ADR-029): en categorias razonamiento,
   * creativa y concretas con prompt predefinido se generan 4 respuestas
   * adicionales con idioma_prompt='en'. En el resto siempre vale 'es'.
   * El humano solo evalua las respuestas 'es'; las 'en' alimentan la
   * tarjeta de metricas tecnicas comparativas del dashboard.
   */
  idioma_prompt: 'es' | 'en'
}

export interface SesionBenchmark {
  id: number
  nickname: string
  prompt: string
  categoria: TestCategory
  estado: SessionStatus
  similitud_jaccard_media: number | null
  created_at: string
  completed_at: string | null
  respuestas: RespuestaLLM[]
  /** Texto original de entrada en resumen autogenerado por LLM. */
  texto_entrada?: string | null
  /** True cuando texto_entrada fue generado automaticamente. */
  texto_entrada_autogenerado?: boolean
}

export interface PeticionBenchmark {
  nickname: string
  prompt: string
  categoria: TestCategory
  imagen_base64?: string | null
  imagen_mime_type?: string | null
  subcat_imagen?: string | null
  /** Etiqueta human-readable de la subcategoria seleccionada — solo para CSV admin. */
  subcategoria_csv?: string | null
  /**
   * Traduccion al ingles del prompt para el sub-experimento bilingue.
   * Solo se envia cuando la categoria es bilingue (razonamiento, creativa o
   * concretas) y la opcion elegida tiene par EN validado (todos los prompts
   * predefinidos lo tienen). Cuando esta presente, el backend lanza dos
   * rondas paralelas y persiste 4 respuestas adicionales con
   * idioma_prompt='en'.
   */
  prompt_en?: string | null
  /** Texto original de la categoria resumen si fue autogenerado por LLM. */
  texto_entrada?: string | null
  texto_entrada_autogenerado?: boolean
}
