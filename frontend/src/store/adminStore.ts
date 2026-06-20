/**
 * Modulo: adminStore
 * Ruta:   frontend/src/store/adminStore.ts
 *
 * Descripcion:
 *   Store Zustand para la sesion autenticada del administrador.
 *   El token JWT se persiste en sessionStorage: sobrevive a recargas de pagina
 *   pero se elimina al cerrar la pestana, lo que es suficiente para uso de admin.
 *
 * Sprint: Sprint 3
 */

import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

interface AdminState {
  token: string | null
  /**
   * True si el admin actual es el root del sistema (es_root=true en BD,
   * el seeded en el despliegue). Los admins promovidos tienen esRoot=false
   * y la UI les oculta los botones de promover/quitar admin.
   */
  esRoot: boolean
  setSession: (token: string, esRoot: boolean) => void
  clearToken: () => void
}

export const useAdminStore = create<AdminState>()(
  persist(
    (set) => ({
      token: null,
      esRoot: false,
      setSession: (token, esRoot) => set({ token, esRoot }),
      clearToken: () => set({ token: null, esRoot: false }),
    }),
    {
      name:    'admin-session',
      storage: createJSONStorage(() => sessionStorage),
    },
  ),
)
