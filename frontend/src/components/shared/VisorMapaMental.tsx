/**
 * Componente: VisorMapaMental
 * Ruta:       frontend/src/components/shared/VisorMapaMental.tsx
 *
 * Descripcion:
 *   Lightbox reutilizable para diagramas de mapa mental con zoom, arrastre y descarga opcional.
 *   - Gestiona internamente zoom, cursor y logica de drag/pan.
 *   - Preprocesa el SVG recibido eliminando width/height fijos para que escale al 100%.
 *   - Clic fuera o doble clic: cierra el visor.
 *   - Prop onDescargar opcional: muestra boton de descarga PNG.
 *
 * Usado por: BenchmarkCard, EvalViewModal, TablaAdmin
 * Sprint: Sprint 3
 */

import { useState, useRef } from 'react'
import type { ReactNode, MouseEvent } from 'react'
import { createPortal } from 'react-dom'
import { TOKENS } from '@/utils/tokens'

interface Props {
  svg:          string
  onClose:      () => void
  onDescargar?: () => void
}

function BtnZoom({
  color = '#C4B5FD',
  children,
  onClick,
}: {
  color?:   string
  children: ReactNode
  onClick:  () => void
}) {
  const [hov, setHov] = useState(false)
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      className="text-xs px-3 py-1.5 rounded-lg font-semibold transition-all duration-150"
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

export default function VisorMapaMental({ svg, onClose, onDescargar }: Props) {
  const [zoom,   setZoom]   = useState(1)
  const [cursor, setCursor] = useState<'grab' | 'grabbing'>('grab')

  const scrollRef      = useRef<HTMLDivElement>(null)
  const arrastrando    = useRef(false)
  const origenArrastre = useRef({ x: 0, y: 0, sl: 0, st: 0 })

  const svgProcesado = svg
    .replace(/(\s)width="[^"]*"/, '')
    .replace(/(\s)height="[^"]*"/, '')
    .replace(/max-width:[^;";]+;?\s*/g, '')

  const iniciarArrastre = (e: MouseEvent) => {
    if (!scrollRef.current) return
    arrastrando.current = true
    setCursor('grabbing')
    origenArrastre.current = {
      x:  e.clientX,
      y:  e.clientY,
      sl: scrollRef.current.scrollLeft,
      st: scrollRef.current.scrollTop,
    }
  }
  const moverArrastre = (e: MouseEvent) => {
    if (!arrastrando.current || !scrollRef.current) return
    e.preventDefault()
    scrollRef.current.scrollLeft = origenArrastre.current.sl - (e.clientX - origenArrastre.current.x)
    scrollRef.current.scrollTop  = origenArrastre.current.st - (e.clientY - origenArrastre.current.y)
  }
  const terminarArrastre = () => { arrastrando.current = false; setCursor('grab') }

  return createPortal(
    <div
      className="fixed inset-0 z-[9999] flex flex-col items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.92)', backdropFilter: 'blur(8px)' }}
      onDoubleClick={onClose}
    >
      <div
        ref={scrollRef}
        className="rounded-xl overflow-auto select-none"
        style={{
          width:     '90vw',
          maxHeight: '75vh',
          background: TOKENS.surface,
          border:    '1px solid rgba(157,78,221,0.4)',
          cursor,
        }}
        onDoubleClick={(e) => { e.stopPropagation(); onClose() }}
        onClick={(e) => e.stopPropagation()}
        onMouseDown={iniciarArrastre}
        onMouseMove={moverArrastre}
        onMouseUp={terminarArrastre}
        onMouseLeave={terminarArrastre}
        onWheel={(e) => {
          e.stopPropagation()
          setZoom((z) => Math.min(4, Math.max(0.5, z - e.deltaY * 0.001)))
        }}
      >
        <div
          style={{
            transform:       `scale(${zoom})`,
            transformOrigin: 'top left',
            transition:      arrastrando.current ? 'none' : 'transform 0.15s',
            padding:         '16px',
          }}
          dangerouslySetInnerHTML={{ __html: svgProcesado }}
        />
      </div>

      <div className="flex items-center gap-3 mt-3" onClick={(e) => e.stopPropagation()}>
        <BtnZoom onClick={() => setZoom((z) => Math.min(4, z + 0.25))}>⊕ +</BtnZoom>
        <span className="text-xs text-muted font-mono w-14 text-center select-none">
          {Math.round(zoom * 100)}%
        </span>
        <BtnZoom onClick={() => setZoom((z) => Math.max(0.5, z - 0.25))}>⊖ −</BtnZoom>
        <BtnZoom onClick={() => setZoom(1)}>↺ Reset</BtnZoom>
        {onDescargar && (
          <BtnZoom color="#34D399" onClick={onDescargar}>↓ PNG</BtnZoom>
        )}
        <BtnZoom color="#F87171" onClick={onClose}>✕ Cerrar</BtnZoom>
      </div>

      <p className="text-[10px] text-muted mt-1.5 select-none">
        Arrastra · rueda para zoom · doble clic para cerrar
      </p>
    </div>,
    document.body,
  )
}
