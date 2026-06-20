/**
 * Component/Module: usuarioStore
 * Path: frontend/src/store/usuarioStore.ts
 *
 * Descripcion:
 *   Store Zustand para la sesion del usuario web autenticado.
 *   Persiste el JWT, nick, estado y contadores de cuota en localStorage.
 *   El token caduca en 1 hora; el backend devuelve 401 al expirar,
 *   lo que dispara el logout automatico desde el interceptor de axios.
 *
 * Sprint: Sprint 4
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { EstadoUsuarioApp, RespuestaTokenUsuarioApp } from '@/types/auth'

interface UsuarioState {
  token: string | null
  nick: string | null
  estado: EstadoUsuarioApp | null
  consultasUsadas: number
  cuotaAsignada: number
  guiaVista: boolean

  login: (datos: RespuestaTokenUsuarioApp) => void
  logout: () => void
  actualizarCuota: (usadas: number, asignadas: number) => void
  actualizarEstado: (estado: EstadoUsuarioApp) => void
  marcarGuiaVista: () => void
}

export const useUsuarioStore = create<UsuarioState>()(
  persist(
    (set) => ({
      token: null,
      nick: null,
      estado: null,
      consultasUsadas: 0,
      cuotaAsignada: 0,
      guiaVista: false,

      login: (datos) =>
        set({
          token: datos.access_token,
          nick: datos.nick,
          estado: datos.estado,
          consultasUsadas: datos.consultas_usadas,
          cuotaAsignada: datos.cuota_asignada,
          guiaVista: datos.guia_vista,
        }),

      logout: () =>
        set({
          token: null,
          nick: null,
          estado: null,
          consultasUsadas: 0,
          cuotaAsignada: 0,
          guiaVista: false,
        }),

      actualizarCuota: (usadas, asignadas) =>
        set({ consultasUsadas: usadas, cuotaAsignada: asignadas }),

      actualizarEstado: (estado) => set({ estado }),

      marcarGuiaVista: () => set({ guiaVista: true }),
    }),
    { name: 'tfg-usuario' },
  ),
)
