/**
 * Modulo: toastStore
 * Ruta:   frontend/src/store/toastStore.ts
 *
 * Descripcion:
 *   Store Zustand en memoria (sin persistencia) para notificaciones
 *   tipo toast. Cada toast se auto-elimina a los 4 segundos.
 *
 * Sprint: Sprint 3
 */

import { create } from 'zustand'

export interface Toast {
  id: number
  mensaje: string
  tipo: 'exito' | 'error' | 'info'
}

interface ToastState {
  toasts: Toast[]
  mostrar: (mensaje: string, tipo?: Toast['tipo']) => void
  quitar: (id: number) => void
}

let _nextId = 1

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],

  mostrar: (mensaje, tipo = 'info') => {
    const id = _nextId++
    set((state) => ({ toasts: [...state.toasts, { id, mensaje, tipo }] }))
    setTimeout(() => {
      set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }))
    }, 4000)
  },

  quitar: (id) =>
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),
}))
