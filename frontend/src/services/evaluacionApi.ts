/**
 * Modulo: services/evaluacionApi
 * Ruta:   frontend/src/services/evaluacionApi.ts
 *
 * Descripcion:
 *   Capa de acceso a la API del backend para el recurso evaluacion.
 *   Usa axios con baseURL relativa; el proxy de Vite enruta /api a :8000.
 *
 * Sprint: Sprint 3
 */

import axios from 'axios'
import type { PeticionEvaluacion, RespuestaEvaluacion } from '@/types/evaluacion'

const api = axios.create({ baseURL: '/api/v1' })

export async function crearEvaluacion(
  peticion: PeticionEvaluacion,
): Promise<RespuestaEvaluacion> {
  const { data } = await api.post<RespuestaEvaluacion>('/evaluaciones', peticion)
  return data
}

export async function obtenerEvaluacionesPorEvaluacion(
  evaluacionId: number,
): Promise<RespuestaEvaluacion[]> {
  const { data } = await api.get<RespuestaEvaluacion[]>(`/evaluaciones/evaluacion/${evaluacionId}`)
  return data
}
