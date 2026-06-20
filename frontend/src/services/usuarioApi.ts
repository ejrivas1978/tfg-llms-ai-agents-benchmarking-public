/**
 * Modulo: services/usuarioApi
 * Ruta:   frontend/src/services/usuarioApi.ts
 *
 * Descripcion:
 *   Capa de acceso a los endpoints de autenticacion y gestion de usuarios web.
 *   El interceptor de respuesta detecta 401 y limpia la sesion local para
 *   forzar el re-login cuando el JWT caduca.
 *
 * Sprint: Sprint 4
 */
import axios from 'axios'
import type {
  PeticionRegistro,
  PeticionLoginUsuario,
  PeticionRegenerarContrasena,
  RespuestaTokenUsuarioApp,
  RespuestaUsuarioApp,
} from '@/types/auth'
import type { ResumenSesionLocal } from '@/store/historialStore'
import { useUsuarioStore } from '@/store/usuarioStore'

const api = axios.create({ baseURL: '/api/v1' })

// Limpia la sesion cuando el backend responde 401 (token caducado)
api.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error.response?.status === 401) {
      useUsuarioStore.getState().logout()
    }
    return Promise.reject(error)
  },
)

export async function verificarNick(nick: string): Promise<{ existe: boolean }> {
  const { data } = await api.get<{ existe: boolean }>(`/usuarios/verificar/${encodeURIComponent(nick)}`)
  return data
}

export async function registrarUsuario(
  peticion: PeticionRegistro,
): Promise<RespuestaUsuarioApp> {
  const { data } = await api.post<RespuestaUsuarioApp>('/usuarios/registrar', peticion)
  return data
}

export async function loginUsuario(
  peticion: PeticionLoginUsuario,
): Promise<RespuestaTokenUsuarioApp> {
  const { data } = await api.post<RespuestaTokenUsuarioApp>('/usuarios/login', peticion)
  return data
}

export async function regenerarContrasena(
  peticion: PeticionRegenerarContrasena,
): Promise<RespuestaUsuarioApp> {
  const { data } = await api.post<RespuestaUsuarioApp>('/usuarios/regenerar-contrasena', peticion)
  return data
}

export async function solicitarMasTokens(token: string): Promise<RespuestaUsuarioApp> {
  const { data } = await api.post<RespuestaUsuarioApp>(
    '/usuarios/solicitar-mas-tokens',
    {},
    { headers: { Authorization: `Bearer ${token}` } },
  )
  return data
}

export async function marcarGuiaVista(token: string): Promise<RespuestaUsuarioApp> {
  const { data } = await api.patch<RespuestaUsuarioApp>(
    '/usuarios/marcar-guia-vista',
    {},
    { headers: { Authorization: `Bearer ${token}` } },
  )
  return data
}

export async function obtenerPerfilUsuario(token: string): Promise<RespuestaUsuarioApp> {
  const { data } = await api.get<RespuestaUsuarioApp>(
    '/usuarios/me',
    { headers: { Authorization: `Bearer ${token}` } },
  )
  return data
}

export async function obtenerMisEvaluaciones(token: string): Promise<ResumenSesionLocal[]> {
  const { data } = await api.get<ResumenSesionLocal[]>(
    '/usuarios/mis-evaluaciones',
    { headers: { Authorization: `Bearer ${token}` } },
  )
  return data
}
