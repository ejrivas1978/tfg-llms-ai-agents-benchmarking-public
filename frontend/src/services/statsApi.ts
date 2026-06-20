/**
 * Modulo: services/statsApi
 * Ruta:   frontend/src/services/statsApi.ts
 *
 * Descripcion:
 *   Capa de acceso a la API del backend para el recurso stats.
 *   Usa la misma instancia axios con proxy Vite /api -> :8000.
 *
 * Sprint: Sprint 3
 */

import axios from 'axios'
import type { RespuestaStats } from '@/types/stats'

const api = axios.create({ baseURL: '/api/v1' })

export async function obtenerStats(): Promise<RespuestaStats> {
  const { data } = await api.get<RespuestaStats>('/stats')
  return data
}
