/**
 * Componente: VisorImagen
 * Ruta:       frontend/src/components/shared/VisorImagen.tsx
 *
 * Descripcion:
 *   Lightbox reutilizable para imagenes con zoom toggle, arrastre y descarga opcional.
 *   - Clic en la imagen: alterna zoom completo / ajustado a ventana.
 *   - Doble clic: cierra el lightbox.
 *   - Clic fuera de la imagen: cierra el lightbox.
 *   - Prop onDescargar opcional: muestra boton de descarga.
 *
 * Usado por: BenchmarkCard, EvalViewModal
 * Sprint: Sprint 3
 */

import { useState, useEffect } from 'react'
import type { ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { TOKENS } from '@/utils/tokens'

interface Props {
  src:          string
  fallbackSrc?: string
  onClose:      () => void
  onDescargar?: () => void
}

function BtnLightbox({
  color = '#C4B5FD',
  children,
  onClick,
}: {
  color?:    string
  children:  ReactNode
  onClick:   () => void
}) {
  const [hov, setHov] = useState(false)
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      className="text-[11px] font-semibold py-1.5 px-2.5 rounded-lg flex items-center
                 justify-center gap-1 transition-all duration-150 whitespace-nowrap"
      style={{
        color:      hov ? TOKENS.surface : color,
        background: hov ? color     : `${color}25`,
        border:     `1px solid ${color}${hov ? '' : '70'}`,
      }}
    >
      {children}
    </button>
  )
}

export default function VisorImagen({ src, fallbackSrc, onClose, onDescargar }: Props) {
  const [zoom,    setZoom]    = useState(false)
  const [imgSrc,  setImgSrc]  = useState(src)

  useEffect(() => { setImgSrc(src) }, [src])

  return createPortal(
    <div
      className="fixed inset-0 z-[9999] flex flex-col items-center justify-center p-6"
      style={{ background: 'rgba(0,0,0,0.92)', backdropFilter: 'blur(8px)' }}
      onClick={onClose}
    >
      <div
        className="rounded-xl"
        style={{
          maxWidth:  '90vw',
          maxHeight: '80vh',
          overflow:  zoom ? 'auto' : 'hidden',
          cursor:    zoom ? 'zoom-out' : 'zoom-in',
        }}
        onClick={(e) => { e.stopPropagation(); setZoom((v) => !v) }}
        onDoubleClick={(e) => { e.stopPropagation(); onClose() }}
      >
        <img
          src={imgSrc}
          alt="Imagen ampliada"
          draggable={false}
          style={{
            display:    'block',
            maxWidth:   zoom ? 'none' : '88vw',
            maxHeight:  zoom ? 'none' : '76vh',
            userSelect: 'none',
          }}
          onError={() => { if (fallbackSrc) setImgSrc(fallbackSrc) }}
        />
      </div>

      <p className="text-[11px] text-muted mt-2 mb-3 select-none">
        {zoom
          ? 'Clic para reducir · arrastra para desplazarte'
          : 'Clic en la imagen para hacer zoom · doble clic para cerrar'}
      </p>

      <div className="flex gap-3" onClick={(e) => e.stopPropagation()}>
        <BtnLightbox color="#818CF8" onClick={() => setZoom((v) => !v)}>
          {zoom ? '⊖ Reducir' : '⊕ Zoom'}
        </BtnLightbox>
        {onDescargar && (
          <BtnLightbox color="#34D399" onClick={onDescargar}>↓ Descargar</BtnLightbox>
        )}
        <BtnLightbox color="#F87171" onClick={onClose}>✕ Cerrar</BtnLightbox>
      </div>
    </div>,
    document.body,
  )
}
