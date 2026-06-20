/**
 * Modulo: types/admin
 * Ruta:   frontend/src/types/admin.ts
 *
 * Descripcion:
 *   Tipos TypeScript que replican los DTOs Pydantic del panel de administracion.
 *
 * Sprint: Sprint 3 / Sprint 4
 */

import type { TestCategory, SessionStatus, LLMProvider } from '@/types/benchmark'
import type { RespuestaUsuarioApp } from '@/types/auth'

export interface RespuestaListaUsuarios {
  items: RespuestaUsuarioApp[]
  total: number
}

export interface ResumenEvaluacionAdmin {
  id: number
  nickname: string
  prompt: string
  categoria: TestCategory
  estado: SessionStatus
  similitud_jaccard_media: number | null
  created_at: string
  completed_at: string | null
  evaluada: boolean
}

export interface RespuestaListaEvaluaciones {
  items: ResumenEvaluacionAdmin[]
  total: number
  pagina: number
  paginas: number
}

/* ── Tarifas LLM ──────────────────────────────────────────────────────── */

/** Alias de LLMProvider para contextos de administracion (tarifas, stats). */
export type LLMProveedor = LLMProvider

/**
 * Tarifa vigente con los dos costes relativos calculados en el backend.
 * El backend devuelve los relativos para no duplicar la formula en cliente,
 * pero el frontend tambien puede recalcularlos cuando hay cambios sin
 * guardar (al editar el input antes de pulsar Guardar).
 */
export interface TarifaDTO {
  id: number
  proveedor: LLMProveedor
  precio_entrada_usd_por_mtoken: number
  precio_salida_usd_por_mtoken:  number
  /** null = sin descuento configurado para tokens cacheados */
  precio_entrada_cacheado_usd_por_mtoken: number | null
  /** null = el proveedor no soporta generación de imagen */
  precio_imagen_generar_usd_por_imagen: number | null
  /** null = el proveedor no soporta edición de imagen */
  precio_imagen_editar_usd_por_imagen: number | null
  coste_relativo_entrada:        number
  coste_relativo_salida:         number
  vigente: boolean
  actualizado_en:  string
  actualizado_por: string | null
}

export interface RespuestaListaTarifas {
  items: TarifaDTO[]
  baseline_entrada_usd_por_mtoken: number
  baseline_salida_usd_por_mtoken:  number
}

export interface PeticionActualizarTarifa {
  precio_entrada_usd_por_mtoken: number
  precio_salida_usd_por_mtoken:  number
  /** Omitir o null = sin descuento de cache; positivo = se aplica si la API devuelve cached_tokens */
  precio_entrada_cacheado_usd_por_mtoken?: number | null
  /** Omitir o null = el proveedor no genera imágenes (Claude) */
  precio_imagen_generar_usd_por_imagen?: number | null
  /** Omitir o null = el proveedor no edita imágenes nativamente */
  precio_imagen_editar_usd_por_imagen?: number | null
}

/** Una version (vigente o historica) en el historial de tarifas de un proveedor. */
export interface HistorialTarifaItem {
  id: number
  proveedor: LLMProveedor
  precio_entrada_usd_por_mtoken: number
  precio_salida_usd_por_mtoken:  number
  precio_entrada_cacheado_usd_por_mtoken: number | null
  precio_imagen_generar_usd_por_imagen: number | null
  precio_imagen_editar_usd_por_imagen: number | null
  vigente: boolean
  actualizado_en:  string
  actualizado_por: string | null
}

export interface RespuestaHistorialTarifa {
  proveedor: LLMProveedor
  items: HistorialTarifaItem[]
}
