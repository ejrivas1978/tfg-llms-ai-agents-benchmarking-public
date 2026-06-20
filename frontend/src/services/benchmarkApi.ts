/**
 * Modulo: services/benchmarkApi
 * Ruta:   frontend/src/services/benchmarkApi.ts
 *
 * Descripcion:
 *   Capa de acceso a la API del backend para el recurso benchmark.
 *   Usa axios con baseURL relativa; el proxy de Vite enruta /api a :8000.
 *
 * Sprint: Sprint 3
 */

import axios from 'axios'
import type { SesionBenchmark, PeticionBenchmark } from '@/types/benchmark'
import { useUsuarioStore } from '@/store/usuarioStore'
import { useAdminStore } from '@/store/adminStore'

const api = axios.create({ baseURL: '/api/v1' })

// Inyecta el JWT del usuario web o del administrador en cada peticion
api.interceptors.request.use((config) => {
  const tokenUsuario = useUsuarioStore.getState().token
  const tokenAdmin = useAdminStore.getState().token
  const token = tokenUsuario ?? tokenAdmin
  if (token) {
    config.headers = config.headers ?? {}
    config.headers['Authorization'] = `Bearer ${token}`
  }
  return config
})

// Limpia la sesion cuando el backend responde 401 (token caducado o invalido)
api.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error.response?.status === 401) {
      useUsuarioStore.getState().logout()
      useAdminStore.getState().clearToken()
    }
    return Promise.reject(error)
  },
)

export async function ejecutarBenchmark(
  peticion: PeticionBenchmark,
): Promise<SesionBenchmark> {
  const { data } = await api.post<SesionBenchmark>('/benchmarks/run', peticion)
  return data
}

export async function obtenerEvaluacion(id: number): Promise<SesionBenchmark> {
  const { data } = await api.get<SesionBenchmark>(`/benchmarks/${id}`)
  return data
}

export interface TextoEjemplo {
  texto: string
  palabras: number
  proveedor: string
}

export async function generarTextoEjemplo(proveedor?: string): Promise<TextoEjemplo> {
  const params = proveedor ? { proveedor } : undefined
  const { data } = await api.get<TextoEjemplo>('/benchmarks/texto-ejemplo', { params })
  return data
}

/** Solicita al administrador el borrado de una evaluacion propia. */
export async function solicitarBorradoEvaluacion(evaluacionId: number): Promise<void> {
  await api.post(`/usuarios/evaluaciones/${evaluacionId}/solicitar-borrado`)
}

/** Carga el historial de un evaluador desde BD sin necesitar JWT activo. */
export async function obtenerHistorialPorNick(nick: string): Promise<import('@/store/historialStore').ResumenSesionLocal[]> {
  const { data } = await api.get<import('@/store/historialStore').ResumenSesionLocal[]>(
    `/benchmarks/historial/${encodeURIComponent(nick)}`,
  )
  return data
}
