/**
 * Modulo: historialStore
 * Ruta:   frontend/src/store/historialStore.ts
 *
 * Descripcion:
 *   Store Zustand para el historial local de sesiones de benchmark.
 *   Persiste en localStorage indexado por nickname para que cada evaluador
 *   vea solo sus propias sesiones al volver a entrar.
 *   Guarda hasta 50 sesiones por nick (las mas recientes primero).
 *
 * Sprint: Sprint 3
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { TestCategory, SessionStatus } from '@/types/benchmark'

export interface ResumenSesionLocal {
  id: number
  prompt: string
  categoria: TestCategory
  estado: SessionStatus
  created_at: string
  evaluada?: boolean
}

interface HistorialState {
  sesiones: Record<string, ResumenSesionLocal[]>
  registrar: (nick: string, sesion: ResumenSesionLocal) => void
  hidratar: (nick: string, sesionesServidor: ResumenSesionLocal[]) => void
  marcarEvaluada: (nick: string, sesionId: number) => void
  marcarSolicitudBorrado: (nick: string, sesionId: number) => void
  actualizarEstado: (nick: string, sesionId: number, estado: SessionStatus) => void
  eliminarSesion: (nick: string, sesionId: number) => void
  limpiar: (nick: string) => void
}

export const useHistorialStore = create<HistorialState>()(
  persist(
    (set) => ({
      sesiones: {},
      registrar: (nick, sesion) =>
        set((state) => ({
          sesiones: {
            ...state.sesiones,
            [nick]: [sesion, ...(state.sesiones[nick] ?? [])].slice(0, 50),
          },
        })),
      // Reemplaza el historial local con los datos frescos de BD.
      // El backend calcula el flag evaluada via subconsulta, por lo que no hace
      // falta preservar nada del localStorage: la BD es siempre la fuente de verdad.
      hidratar: (nick, sesionesServidor) =>
        set((state) => ({
          sesiones: { ...state.sesiones, [nick]: sesionesServidor },
        })),
      marcarEvaluada: (nick, sesionId) =>
        set((state) => ({
          sesiones: {
            ...state.sesiones,
            [nick]: (state.sesiones[nick] ?? []).map((s) =>
              s.id === sesionId ? { ...s, evaluada: true } : s,
            ),
          },
        })),
      marcarSolicitudBorrado: (nick, sesionId) =>
        set((state) => ({
          sesiones: {
            ...state.sesiones,
            [nick]: (state.sesiones[nick] ?? []).map((s) =>
              s.id === sesionId ? { ...s, estado: 'solicitud_borrado' as const } : s,
            ),
          },
        })),
      actualizarEstado: (nick, sesionId, estado) =>
        set((state) => ({
          sesiones: {
            ...state.sesiones,
            [nick]: (state.sesiones[nick] ?? []).map((s) =>
              s.id === sesionId ? { ...s, estado } : s,
            ),
          },
        })),
      eliminarSesion: (nick, sesionId) =>
        set((state) => ({
          sesiones: {
            ...state.sesiones,
            [nick]: (state.sesiones[nick] ?? []).filter((s) => s.id !== sesionId),
          },
        })),
      limpiar: (nick) =>
        set((state) => ({ sesiones: { ...state.sesiones, [nick]: [] } })),
    }),
    { name: 'tfg-historial' },
  ),
)
