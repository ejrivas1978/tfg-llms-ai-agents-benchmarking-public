/**
 * Modulo: services/adminApi
 * Ruta:   frontend/src/services/adminApi.ts
 *
 * Descripcion:
 *   Capa de acceso a la API del backend para los endpoints de administracion.
 *   Todas las funciones requieren el JWT del administrador en la cabecera.
 *
 * Sprint: Sprint 3
 */

import axios from 'axios'
import type {
  LLMProveedor,
  PeticionActualizarTarifa,
  RespuestaHistorialTarifa,
  RespuestaListaEvaluaciones,
  RespuestaListaTarifas,
  RespuestaListaUsuarios,
} from '@/types/admin'
import type { RespuestaUsuarioApp } from '@/types/auth'
import type { TestCategory, SessionStatus } from '@/types/benchmark'
import { useAdminStore } from '@/store/adminStore'

export interface FiltrosAdmin {
  nick?:        string
  categoria?:   TestCategory
  prompt?:      string
  estado?:      SessionStatus
  valoracion?:  'valorada' | 'sin_valorar'
  fechaDesde?:  string
  fechaHasta?:  string
}

const api = axios.create({ baseURL: '/api/v1' })

// Cierra la sesion automaticamente cuando el backend devuelve 401 (token expirado).
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAdminStore.getState().clearToken()
    }
    return Promise.reject(error)
  },
)

const bearer = (token: string) => ({ Authorization: `Bearer ${token}` })

/**
 * Convierte un valor de input <type="datetime-local"> ("2026-05-09T10:30")
 * o de <type="date"> ("2026-05-09") a ISO 8601 UTC ("2026-05-09T08:30:00.000Z")
 * para que el backend (que almacena created_at en UTC) lo compare correctamente
 * con la zona horaria local del navegador.
 *
 * Si el valor es vacio o invalido, devuelve undefined para que el filtro se
 * omita en la query.
 */
function aIsoUtc(valorLocal: string | undefined): string | undefined {
  if (!valorLocal) return undefined
  const fecha = new Date(valorLocal)
  if (isNaN(fecha.getTime())) return undefined
  return fecha.toISOString()
}

export async function listarEvaluacionesAdmin(
  token: string,
  pagina = 1,
  limite = 10,
  filtros?: FiltrosAdmin,
): Promise<RespuestaListaEvaluaciones> {
  const params: Record<string, string | number> = { pagina, limite }
  if (filtros?.nick)       params['nick']        = filtros.nick
  if (filtros?.categoria)  params['categoria']   = filtros.categoria
  if (filtros?.prompt)     params['prompt']      = filtros.prompt
  if (filtros?.estado)     params['estado']      = filtros.estado
  if (filtros?.valoracion) params['valoracion']  = filtros.valoracion
  const fechaDesdeIso = aIsoUtc(filtros?.fechaDesde)
  const fechaHastaIso = aIsoUtc(filtros?.fechaHasta)
  if (fechaDesdeIso) params['fecha_desde'] = fechaDesdeIso
  if (fechaHastaIso) params['fecha_hasta'] = fechaHastaIso

  const { data } = await api.get<RespuestaListaEvaluaciones>('/admin/evaluaciones', {
    headers: bearer(token),
    params,
  })
  return data
}

export async function eliminarEvaluacion(token: string, id: number): Promise<void> {
  await api.delete(`/admin/evaluaciones/${id}`, { headers: bearer(token) })
}

export async function rechazarBorradoEvaluacion(token: string, id: number): Promise<void> {
  await api.post(`/admin/evaluaciones/${id}/rechazar-borrado`, null, { headers: bearer(token) })
}

/**
 * Descarga el CSV con todas las evaluaciones que cumplen los filtros activos.
 * Devuelve el Blob para que el componente decida como dispararlo (anchor + click).
 * El backend marca el Content-Disposition con un nombre que incluye timestamp.
 */
export async function exportarEvaluacionesCsvAdmin(
  token: string,
  filtros?: FiltrosAdmin,
): Promise<{ blob: Blob; nombre: string }> {
  const params: Record<string, string> = {}
  if (filtros?.nick)       params['nick']        = filtros.nick
  if (filtros?.categoria)  params['categoria']   = filtros.categoria
  if (filtros?.prompt)     params['prompt']      = filtros.prompt
  if (filtros?.estado)     params['estado']      = filtros.estado
  if (filtros?.valoracion) params['valoracion']  = filtros.valoracion
  const fechaDesdeIso = aIsoUtc(filtros?.fechaDesde)
  const fechaHastaIso = aIsoUtc(filtros?.fechaHasta)
  if (fechaDesdeIso) params['fecha_desde'] = fechaDesdeIso
  if (fechaHastaIso) params['fecha_hasta'] = fechaHastaIso

  const respuesta = await api.get<Blob>('/admin/evaluaciones/exportar-csv', {
    headers: bearer(token),
    params,
    responseType: 'blob',
  })

  // Extraemos el filename del Content-Disposition; si falla, fallback con timestamp local.
  const disposition = respuesta.headers['content-disposition'] as string | undefined
  const match = disposition?.match(/filename="?([^";]+)"?/i)
  const ahora = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
  const nombre = match?.[1] ?? `benchmark-export-${ahora}.csv`
  return { blob: respuesta.data, nombre }
}

export async function eliminarTodasLasEvaluaciones(
  token: string,
): Promise<{ eliminadas: number }> {
  const { data } = await api.delete<{ eliminadas: number }>('/admin/evaluaciones', {
    headers: bearer(token),
  })
  return data
}

// ── Gestion de usuarios ──────────────────────────────────────────────────

export async function listarUsuariosAdmin(token: string): Promise<RespuestaListaUsuarios> {
  const { data } = await api.get<RespuestaListaUsuarios>('/admin/usuarios', {
    headers: bearer(token),
  })
  return data
}

export async function concederAccesoAdmin(
  token: string,
  id: number,
  cuota: number,
): Promise<RespuestaUsuarioApp> {
  const { data } = await api.post<RespuestaUsuarioApp>(
    `/admin/usuarios/${id}/conceder-acceso`,
    { cuota },
    { headers: bearer(token) },
  )
  return data
}

export async function ampliarConsultasAdmin(
  token: string,
  id: number,
  tokens_adicionales: number,
): Promise<RespuestaUsuarioApp> {
  const { data } = await api.post<RespuestaUsuarioApp>(
    `/admin/usuarios/${id}/ampliar-tokens`,
    { tokens_adicionales },
    { headers: bearer(token) },
  )
  return data
}

export async function resetearEvaluacionesUsuario(
  token: string,
  id: number,
  nueva_cuota: number,
): Promise<{ usuario: RespuestaUsuarioApp; evaluaciones_eliminadas: number }> {
  const { data } = await api.post<{ usuario: RespuestaUsuarioApp; evaluaciones_eliminadas: number }>(
    `/admin/usuarios/${id}/resetear-evaluaciones`,
    { nueva_cuota },
    { headers: bearer(token) },
  )
  return data
}

export async function eliminarUsuarioAdmin(
  token: string,
  id: number,
): Promise<{ evaluaciones_eliminadas: number }> {
  const { data } = await api.delete<{ evaluaciones_eliminadas: number }>(
    `/admin/usuarios/${id}`,
    { headers: bearer(token) },
  )
  return data
}

export async function marcarGuiaVistaAdmin(
  token: string,
  id: number,
): Promise<RespuestaUsuarioApp> {
  const { data } = await api.post<RespuestaUsuarioApp>(
    `/admin/usuarios/${id}/marcar-guia-vista`,
    {},
    { headers: bearer(token) },
  )
  return data
}

export async function resetearGuiaUsuario(
  token: string,
  id: number,
): Promise<RespuestaUsuarioApp> {
  const { data } = await api.post<RespuestaUsuarioApp>(
    `/admin/usuarios/${id}/resetear-guia`,
    {},
    { headers: bearer(token) },
  )
  return data
}

export async function promoverAdminUsuario(
  token: string,
  id: number,
  email: string,
): Promise<RespuestaUsuarioApp> {
  const { data } = await api.post<RespuestaUsuarioApp>(
    `/admin/usuarios/${id}/promover-admin`,
    { email },
    { headers: bearer(token) },
  )
  return data
}

export async function quitarAdminUsuario(
  token: string,
  id: number,
): Promise<RespuestaUsuarioApp> {
  const { data } = await api.post<RespuestaUsuarioApp>(
    `/admin/usuarios/${id}/quitar-admin`,
    {},
    { headers: bearer(token) },
  )
  return data
}

// ── Gestion de tarifas LLM ──────────────────────────────────────────────

export async function listarTarifasAdmin(token: string): Promise<RespuestaListaTarifas> {
  const { data } = await api.get<RespuestaListaTarifas>('/admin/tarifas', {
    headers: bearer(token),
  })
  return data
}

export async function actualizarTarifaAdmin(
  token: string,
  proveedor: LLMProveedor,
  peticion: PeticionActualizarTarifa,
): Promise<RespuestaListaTarifas> {
  const { data } = await api.put<RespuestaListaTarifas>(
    `/admin/tarifas/${proveedor}`,
    peticion,
    { headers: bearer(token) },
  )
  return data
}

export async function historialTarifaAdmin(
  token: string,
  proveedor: LLMProveedor,
): Promise<RespuestaHistorialTarifa> {
  const { data } = await api.get<RespuestaHistorialTarifa>(
    `/admin/tarifas/${proveedor}/historial`,
    { headers: bearer(token) },
  )
  return data
}
