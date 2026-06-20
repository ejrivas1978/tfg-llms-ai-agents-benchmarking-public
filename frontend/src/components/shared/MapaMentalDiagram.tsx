/**
 * Componente: MapaMentalDiagram
 * Ruta:       frontend/src/components/shared/MapaMentalDiagram.tsx
 *
 * Descripcion:
 *   Renderiza un diagrama Mermaid (mindmap, flowchart, etc.) como SVG.
 *   Expone el SVG generado al padre via onSvgReady para permitir zoom y descarga.
 *
 * Sprint: Sprint 3
 */

import mermaid from 'mermaid'
import { useEffect, useState } from 'react'

mermaid.initialize({
  startOnLoad: false,
  theme:       'dark',
  themeVariables: {
    darkMode:            true,
    background:          '#0F0F1C',
    primaryColor:        '#5C2D9E',
    primaryTextColor:    '#FFFFFF',
    primaryBorderColor:  '#9D4EDD',
    lineColor:           '#8080B0',
    textColor:           '#E2E8F0',
    // Colores de relleno de los nodos del mapa mental (niveles 0-7)
    fillType0:           '#5C2D9E',   // violeta
    fillType1:           '#0E7A58',   // verde esmeralda
    fillType2:           '#1E4A9E',   // azul
    fillType3:           '#9E2060',   // rosa fucsia
    fillType4:           '#7A4818',   // naranja tostado
    fillType5:           '#0E6A8A',   // cian
    fillType6:           '#4A7A18',   // verde lima
    fillType7:           '#7A1E7A',   // púrpura oscuro claro
  },
})

let _contador = 0

interface Props {
  codigo:      string
  onSvgReady?: (svg: string) => void
  /** 'miniatura': altura fija + clase mermaid-thumbnail (por defecto). 'completo': tamaño natural del SVG. */
  modo?:       'miniatura' | 'completo'
}

export default function MapaMentalDiagram({ codigo, onSvgReady, modo = 'miniatura' }: Props) {
  const [svg,   setSvg]   = useState<string>('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setSvg('')
    setError(null)
    const id = `mermaid-${++_contador}`
    mermaid.render(id, codigo)
      .then(({ svg }) => {
        setSvg(svg)
        onSvgReady?.(svg)
      })
      .catch((e) => setError(String(e)))
  }, [codigo])

  if (error) {
    return (
      <div className="p-3 rounded-lg border border-red-500/30 bg-red-500/10">
        <p className="text-xs text-red-400 font-mono whitespace-pre-wrap">{error}</p>
        <p className="text-[10px] text-muted mt-1">El modelo generó sintaxis de diagrama incorrecta.</p>
      </div>
    )
  }

  if (!svg) {
    return (
      <div className="flex items-center justify-center h-32 text-muted text-xs">
        Renderizando diagrama…
      </div>
    )
  }

  if (modo === 'completo') {
    return (
      <div
        className="w-full overflow-auto flex items-start justify-center py-2"
        dangerouslySetInnerHTML={{ __html: svg }}
      />
    )
  }

  return (
    <div
      className="mermaid-thumbnail w-full h-full overflow-hidden flex items-center justify-center"
      style={{ minHeight: 0 }}
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}
