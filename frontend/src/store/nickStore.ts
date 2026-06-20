/**
 * Component/Module: nickStore
 * Path: frontend/src/store/nickStore.ts
 *
 * Descripcion:
 *   Store Zustand para el nickname del evaluador activo.
 *   Persiste en localStorage para sobrevivir recargas de pagina.
 *
 *   Tras la unificacion ADR-027 cualquier usuario regular puede ser
 *   promovido a administrador, asi que el discriminador "soy admin?"
 *   no puede ser nick=='admin' literal. esAdmin() consulta el
 *   adminStore: si hay token administrativo activo, la sesion es admin
 *   independientemente del nick concreto.
 *
 * Sprint: Sprint 3 (revisado Sprint 4)
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { useAdminStore } from '@/store/adminStore'

interface NickState {
  nick: string
  setNick: (nick: string) => void
  clearNick: () => void
  esAdmin: () => boolean
}

export const useNickStore = create<NickState>()(
  persist(
    (set) => ({
      nick: '',
      setNick: (nick) => set({ nick: nick.trim() }),
      clearNick: () => set({ nick: '' }),
      // Sesion administrativa = existe token en adminStore. Se actualiza
      // automaticamente al promover/degradar y al cerrar sesion admin.
      esAdmin: () => useAdminStore.getState().token !== null,
    }),
    { name: 'tfg-nick' },
  ),
)
