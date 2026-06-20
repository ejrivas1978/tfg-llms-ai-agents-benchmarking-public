/**
 * Modulo: services/authApi
 * Ruta:   frontend/src/services/authApi.ts
 *
 * Descripcion:
 *   Capa de acceso a los endpoints de autenticacion del backend.
 *   Solo el administrador utiliza JWT; los usuarios regulares son anonimos.
 *
 * Sprint: Sprint 3
 */

import axios from 'axios'
import type { PeticionLogin, RespuestaToken } from '@/types/auth'

const api = axios.create({ baseURL: '/api/v1' })

export async function loginAdmin(peticion: PeticionLogin): Promise<RespuestaToken> {
  const { data } = await api.post<RespuestaToken>('/auth/login', peticion)
  return data
}
