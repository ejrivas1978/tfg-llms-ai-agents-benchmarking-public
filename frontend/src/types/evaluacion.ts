/**
 * Modulo: types/evaluacion
 * Ruta:   frontend/src/types/evaluacion.ts
 *
 * Descripcion:
 *   Tipos TypeScript que replican los DTOs Pydantic del endpoint
 *   POST /api/v1/evaluaciones del backend.
 *
 * Sprint: Sprint 3
 */

export interface PeticionEvaluacion {
  response_id: number
  nickname: string
  rating: number
  rango_preferencia: number | null
}

export interface RespuestaEvaluacion {
  id: number
  response_id: number
  nickname: string
  rating: number
  rango_preferencia: number | null
  created_at: string
}
