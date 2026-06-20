/**
 * Componente: BtnAmpliar
 * Ruta:       frontend/src/components/shared/BtnAmpliar.tsx
 *
 * Descripcion:
 *   Boton con borde blanco brillante y sombra purpura al hover.
 *   Usado para acciones de ampliar imagen o mapa mental en EvalViewModal y TablaAdmin.
 *
 * Sprint: Sprint 3
 */

import { useState } from 'react'
import type { ReactNode } from 'react'

interface Props {
  children: ReactNode
  onClick:  () => void
}

export default function BtnAmpliar({ children, onClick }: Props) {
  const [hov, setHov] = useState(false)
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      className="text-[11px] font-semibold px-3 py-1 rounded-lg transition-all duration-150 flex items-center gap-1"
      style={{
        border:     `1.5px solid ${hov ? 'rgba(255,255,255,1)' : 'rgba(255,255,255,0.6)'}`,
        background: hov ? 'rgba(255,255,255,0.10)' : 'rgba(255,255,255,0.04)',
        color:      hov ? '#FFFFFF' : 'rgba(255,255,255,0.75)',
        boxShadow:  hov
          ? '0 0 10px rgba(255,255,255,0.45), 0 0 22px rgba(157,78,221,0.35)'
          : '0 0 5px rgba(255,255,255,0.15)',
      }}
    >
      {children}
    </button>
  )
}
