/**
 * Componente: ToastContainer
 * Ruta:       frontend/src/components/shared/Toast.tsx
 *
 * Descripcion:
 *   Contenedor fijo en la esquina inferior derecha que renderiza los
 *   toasts del store. Se incluye una sola vez en Layout.tsx.
 *   Cada toast muestra un icono segun su tipo y un boton de cierre manual.
 *
 * Sprint: Sprint 3
 */

import { useToastStore } from '@/store/toastStore'
import type { Toast } from '@/store/toastStore'

const ICONO: Record<Toast['tipo'], string> = {
  exito: '✓',
  error: '✕',
  info:  'ℹ',
}

const COLOR: Record<Toast['tipo'], string> = {
  exito: 'border-green-500 bg-green-500/10 text-green-400',
  error: 'border-red-500  bg-red-500/10  text-red-400',
  info:  'border-primary  bg-primary/10  text-primary',
}

export default function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts)
  const quitar = useToastStore((s) => s.quitar)

  if (toasts.length === 0) return null

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2 items-end pointer-events-none">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`flex items-center gap-2.5 px-4 py-2.5 rounded-card border text-sm
                      shadow-card-lg pointer-events-auto animate-fade-in ${COLOR[t.tipo]}`}
          style={{ minWidth: '220px', maxWidth: '340px' }}
        >
          <span className="font-bold flex-shrink-0">{ICONO[t.tipo]}</span>
          <span className="flex-1">{t.mensaje}</span>
          <button
            className="flex-shrink-0 opacity-60 hover:opacity-100 transition-opacity ml-1"
            onClick={() => quitar(t.id)}
            aria-label="Cerrar"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  )
}
