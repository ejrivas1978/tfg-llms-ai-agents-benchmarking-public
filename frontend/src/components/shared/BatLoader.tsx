/**
 * Componente: BatLoader
 * Ruta:       frontend/src/components/shared/BatLoader.tsx
 *
 * Descripcion:
 *   Pantalla de carga con un murcielago animado dentro de una esfera gris.
 *   Mientras isLoading es true el murcielago flota y las alas aletean.
 *   Cuando isLoading pasa a false, el murcielago gira una vez por cada modelo
 *   completado (secuencialmente) y al terminar llama a onComplete.
 *
 *   Las gotas de los colmillos nacen como sangre y se transforman a mitad de
 *   trayecto en el icono del LLM correspondiente (metafora: vampiros de
 *   informacion). Las salpicaduras al girar muestran una mezcla aleatoria de
 *   gotas de sangre e iconos LLM.
 *
 * Sprint: Sprint 3 / Sprint 4
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import './BatLoader.css'

export interface ModeloCarga {
  nombre: string
  color: string
  sinSoporte?: boolean
}

type EstadoModelo = 'esperando' | 'respondiendo' | 'completado' | 'no_soportado'

interface Props {
  modelos: ModeloCarga[]
  isLoading: boolean
  onComplete?: () => void
}

/* ── Iconos LLM en miniatura (letra + color de marca) ────────────────────── */
const LLM_MINI = [
  { letra: 'G', color: '#EF4444' },  // Gemini
  { letra: 'X', color: '#4DB8FF' },  // Grok
  { letra: 'G', color: '#10D9A0' },  // GPT-4o
  { letra: 'C', color: '#E8956D' },  // Claude
]

function aleatorioLLM(): number { return Math.floor(Math.random() * 4) }

/* Posiciones y delays de las gotas de los dos colmillos */
const TODAS_GOTAS = [
  { cx: 121, delay: '0s' },
  { cx: 121, delay: '-0.87s' },
  { cx: 121, delay: '-1.73s' },
  { cx: 138, delay: '-0.43s' },
  { cx: 138, delay: '-1.30s' },
  { cx: 138, delay: '-2.16s' },
]

/* Posiciones, forma y delay de cada marca de salpicadura */
interface SplatterPos {
  cx: number; cy: number
  rx: number; ry: number  // rx === ry → circulo; en otro caso elipse
  rot?: string; fill: string; delay: string
}
const SPLATTER_POS: SplatterPos[] = [
  { cx: 55,  cy: 98,  rx: 6,   ry: 14,  rot: 'rotate(12,55,98)',    fill: '#990000', delay: '0.04s' },
  { cx: 268, cy: 88,  rx: 7,   ry: 12,  rot: 'rotate(-12,268,88)',  fill: '#aa0000', delay: '0.09s' },
  { cx: 38,  cy: 162, rx: 5,   ry: 17,  rot: 'rotate(3,38,162)',    fill: '#880000', delay: '0.02s' },
  { cx: 284, cy: 172, rx: 5,   ry: 16,  rot: 'rotate(-4,284,172)',  fill: '#990000', delay: '0.07s' },
  { cx: 75,  cy: 258, rx: 8,   ry: 12,  rot: 'rotate(22,75,258)',   fill: '#aa0000', delay: '0.12s' },
  { cx: 250, cy: 250, rx: 8,   ry: 13,  rot: 'rotate(-18,250,250)', fill: '#880000', delay: '0.05s' },
  { cx: 150, cy: 36,  rx: 14,  ry: 7,   rot: 'rotate(5,150,36)',    fill: '#990000', delay: '0.08s' },
  { cx: 170, cy: 284, rx: 12,  ry: 7,   rot: 'rotate(-5,170,284)',  fill: '#aa0000', delay: '0.03s' },
  { cx: 220, cy: 108, rx: 7,   ry: 11,  rot: 'rotate(-10,220,108)', fill: '#880000', delay: '0.10s' },
  { cx: 98,  cy: 215, rx: 8,   ry: 11,  rot: 'rotate(18,98,215)',   fill: '#990000', delay: '0.06s' },
  { cx: 42,  cy: 82,  rx: 3.5, ry: 3.5,                             fill: '#aa0000', delay: '0.13s' },
  { cx: 278, cy: 74,  rx: 3,   ry: 3,                               fill: '#880000', delay: '0.01s' },
]

export default function BatLoader({ modelos, isLoading, onComplete }: Props) {
  const batRef        = useRef<HTMLDivElement>(null)
  const splatterRef   = useRef<HTMLDivElement>(null)
  const terminadoRef  = useRef(false)
  const modelosRef    = useRef(modelos)
  const onCompleteRef = useRef(onComplete)

  useEffect(() => { modelosRef.current = modelos })
  useEffect(() => { onCompleteRef.current = onComplete })

  const [estados,      setEstados]      = useState<EstadoModelo[]>(
    modelos.map((m) => (m.sinSoporte ? 'no_soportado' : 'respondiendo')),
  )
  const [toastTexto,   setToastTexto]   = useState('')
  const [toastVisible, setToastVisible] = useState(false)

  // Icono LLM asignado a cada una de las 6 gotas; se rota cada 5.2 s
  const [iconosGotas, setIconosGotas] = useState<number[]>(() =>
    Array.from({ length: 6 }, aleatorioLLM)
  )
  // Para cada salpicadura: null = gota de sangre, numero = indice LLM_MINI
  const [iconosSplatter, setIconosSplatter] = useState<(number | null)[]>(
    Array(12).fill(null)
  )

  // Cicla los iconos de las gotas cada 5.2 s (dos ciclos de animacion completos)
  useEffect(() => {
    const t = setInterval(
      () => setIconosGotas(Array.from({ length: 6 }, aleatorioLLM)),
      5200,
    )
    return () => clearInterval(t)
  }, [])

  const triggerSpin = useCallback(() => {
    const el = batRef.current
    if (!el) return
    el.classList.remove('bat-spinning')
    void el.offsetWidth   // fuerza reflow para reiniciar la animacion CSS
    el.classList.add('bat-spinning')

    const sp = splatterRef.current
    if (sp) {
      sp.classList.remove('bat-splattering')
      void sp.offsetWidth
      sp.classList.add('bat-splattering')
    }

    // ~55% de las salpicaduras se convierten en iconos LLM aleatorios
    setIconosSplatter(
      Array.from({ length: 12 }, () =>
        Math.random() < 0.55 ? aleatorioLLM() : null
      )
    )
  }, [])

  // Solo depende de isLoading: evita que re-renders del padre cancelen los timers
  useEffect(() => {
    if (isLoading || terminadoRef.current) return
    terminadoRef.current = true

    const lista  = modelosRef.current
    const timers: ReturnType<typeof setTimeout>[] = []

    let spinIdx = 0
    lista.forEach((modelo, idx) => {
      if (modelo.sinSoporte) return

      const offset = spinIdx * 1100
      spinIdx++

      timers.push(setTimeout(() => {
        triggerSpin()
        setToastTexto(`${modelo.nombre} completado ✓`)
        setToastVisible(true)
      }, offset))

      timers.push(setTimeout(() => {
        setToastVisible(false)
        batRef.current?.classList.remove('bat-spinning')
        setEstados((prev) => prev.map((e, i) => (i === idx ? 'completado' : e)))
      }, offset + 900))
    })

    timers.push(setTimeout(() => {
      onCompleteRef.current?.()
    }, spinIdx * 1100 + 200))

    return () => timers.forEach(clearTimeout)
  }, [isLoading, triggerSpin])

  return (
    <div className="bat-loader-wrap">

      {/* Esfera con el murcielago */}
      <div className="bat-sphere">
        <div ref={batRef} className="bat-hover">
          <svg width="260" height="220" viewBox="0 0 260 220" fill="none" xmlns="http://www.w3.org/2000/svg">

            {/* Ala izquierda */}
            <g className="wing-left">
              <path d="M96 88 C82 73 54 52 12 48 C26 44 42 34 50 42 C54 30 64 27 72 38 C76 28 85 26 91 35 C93 28 100 26 103 34 L103 84 Z" fill="#000000"/>
              <line x1="96" y1="84" x2="12"  y2="48" stroke="#1a1a1a" strokeWidth="0.8"/>
              <line x1="96" y1="84" x2="50"  y2="42" stroke="#1a1a1a" strokeWidth="0.8"/>
              <line x1="96" y1="84" x2="72"  y2="38" stroke="#1a1a1a" strokeWidth="0.8"/>
              <line x1="96" y1="84" x2="91"  y2="35" stroke="#1a1a1a" strokeWidth="0.8"/>
              <line x1="96" y1="84" x2="103" y2="34" stroke="#1a1a1a" strokeWidth="0.8"/>
            </g>

            {/* Ala derecha */}
            <g className="wing-right">
              <path d="M164 88 C178 73 206 52 248 48 C234 44 218 34 210 42 C206 30 196 27 188 38 C184 28 175 26 169 35 C167 28 160 26 157 34 L157 84 Z" fill="#000000"/>
              <line x1="164" y1="84" x2="248" y2="48" stroke="#1a1a1a" strokeWidth="0.8"/>
              <line x1="164" y1="84" x2="210" y2="42" stroke="#1a1a1a" strokeWidth="0.8"/>
              <line x1="164" y1="84" x2="188" y2="38" stroke="#1a1a1a" strokeWidth="0.8"/>
              <line x1="164" y1="84" x2="169" y2="35" stroke="#1a1a1a" strokeWidth="0.8"/>
              <line x1="164" y1="84" x2="157" y2="34" stroke="#1a1a1a" strokeWidth="0.8"/>
            </g>

            {/* Cuerpo */}
            <ellipse cx="130" cy="120" rx="26" ry="38" fill="#000000"/>
            <ellipse cx="130" cy="80"  rx="26" ry="24" fill="#000000"/>

            {/* Orejas */}
            <polygon points="107,66 100,38 116,58" fill="#000000"/>
            <polygon points="108,64 102,44 114,58" fill="#141414"/>
            <polygon points="153,66 160,38 144,58" fill="#000000"/>
            <polygon points="152,64 158,44 146,58" fill="#141414"/>

            {/* Ojos con parpadeo */}
            <g className="eyes-blink" style={{ transformOrigin: '130px 79px' }}>
              <ellipse cx="120" cy="79" rx="6"   ry="6"   fill="#ffffff"/>
              <ellipse cx="140" cy="79" rx="6"   ry="6"   fill="#ffffff"/>
              <ellipse cx="121" cy="80" rx="3.5" ry="3.5" fill="#cc0000"/>
              <ellipse cx="141" cy="80" rx="3.5" ry="3.5" fill="#cc0000"/>
              <ellipse cx="121.5" cy="79" rx="1.5" ry="1.5" fill="#000"/>
              <ellipse cx="141.5" cy="79" rx="1.5" ry="1.5" fill="#000"/>
            </g>

            {/* Boca y colmillos */}
            <path d="M126 87 C128 90 132 90 134 87" stroke="#444" strokeWidth="1" fill="none" strokeLinecap="round"/>
            <path d="M118 93 C124 101 136 101 142 93" stroke="#555" strokeWidth="1.3" fill="none" strokeLinecap="round"/>
            <path d="M122 95 L125 95 L122.5 100 L121 100 Z" fill="#ffffff"/>
            <path d="M121 100 L122.5 100 L120 105 Z"        fill="#cc0000"/>
            <path d="M138 95 L141 95 L138.5 100 L137 100 Z" fill="#ffffff"/>
            <path d="M137 100 L138.5 100 L136 105 Z"        fill="#cc0000"/>

            {/* Gotas: nacen como sangre y se transforman en icono LLM a mitad de trayecto */}
            {TODAS_GOTAS.map((gota, i) => {
              const llm = LLM_MINI[iconosGotas[i]]
              return (
                <g key={i}>
                  {/* Fase sangre: visible entre 12 % y 50 % del ciclo */}
                  <ellipse
                    className="bat-drop-blood"
                    cx={gota.cx} cy={106} rx={2} ry={3.5} fill="#cc0000"
                    style={{ animationDelay: gota.delay }}
                  />
                  {/* Fase icono LLM: aparece en el cruce (38-50 %) y sigue cayendo */}
                  <g className="bat-drop-icon" style={{ animationDelay: gota.delay }}>
                    <circle cx={gota.cx} cy={106} r={5} fill={llm.color}/>
                    <text
                      x={gota.cx} y={106}
                      textAnchor="middle"
                      dominantBaseline="central"
                      fontSize={6}
                      fill="white"
                      fontWeight="bold"
                      style={{ fontFamily: 'Helvetica, Arial, sans-serif', pointerEvents: 'none' }}
                    >
                      {llm.letra}
                    </text>
                  </g>
                </g>
              )
            })}

            {/* Patas */}
            <path d="M118 155 C114 163 110 167 108 172" stroke="#1a1a1a" strokeWidth="4" strokeLinecap="round"/>
            <path d="M142 155 C146 163 150 167 152 172" stroke="#1a1a1a" strokeWidth="4" strokeLinecap="round"/>
            <path d="M108 172 L104 177 M108 172 L108 178 M108 172 L112 177" stroke="#1a1a1a" strokeWidth="1.5" strokeLinecap="round"/>
            <path d="M152 172 L148 177 M152 172 L152 178 M152 172 L156 177" stroke="#1a1a1a" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        </div>

        {/* Salpicaduras al girar: mezcla aleatoria de sangre e iconos LLM */}
        <div ref={splatterRef} className="bat-splatter">
          <svg width="320" height="320" viewBox="0 0 320 320" fill="none">
            {SPLATTER_POS.map((pos, i) => {
              const iconIdx = iconosSplatter[i]

              if (iconIdx !== null) {
                // Esta posicion muestra un icono LLM en lugar de sangre
                const llm = LLM_MINI[iconIdx]
                return (
                  <g
                    key={i}
                    className="bat-splatter-mark"
                    style={{ animationDelay: pos.delay }}
                  >
                    <circle cx={pos.cx} cy={pos.cy} r={9} fill={llm.color}/>
                    <text
                      x={pos.cx} y={pos.cy}
                      textAnchor="middle"
                      dominantBaseline="central"
                      fontSize={9}
                      fill="white"
                      fontWeight="bold"
                      style={{ fontFamily: 'Helvetica, Arial, sans-serif', pointerEvents: 'none' }}
                    >
                      {llm.letra}
                    </text>
                  </g>
                )
              }

              // Gota de sangre (circulo si rx === ry, elipse en caso contrario)
              if (pos.rx === pos.ry) {
                return (
                  <circle
                    key={i}
                    className="bat-splatter-mark"
                    cx={pos.cx} cy={pos.cy} r={pos.rx}
                    fill={pos.fill}
                    style={{ animationDelay: pos.delay }}
                  />
                )
              }
              return (
                <ellipse
                  key={i}
                  className="bat-splatter-mark"
                  cx={pos.cx} cy={pos.cy} rx={pos.rx} ry={pos.ry}
                  fill={pos.fill}
                  transform={pos.rot}
                  style={{ animationDelay: pos.delay }}
                />
              )
            })}
          </svg>
        </div>

        {/* Toast de modelo completado */}
        <div className={`bat-toast ${toastVisible ? 'show' : ''}`}>
          {toastTexto}
        </div>
      </div>

      {/* Lista de modelos con su estado */}
      <div className="bat-model-list">
        {modelos.map((modelo, idx) => {
          const estado = estados[idx]
          return (
            <div key={modelo.nombre} className={`bat-model-row${estado === 'completado' ? ' done-row' : ''}`}>
              <div className={`bat-dot ${
                estado === 'completado'   ? 'done'    :
                estado === 'no_soportado' ? 'waiting' :
                estado === 'respondiendo' ? 'running' : 'waiting'
              }`} />
              <span style={{
                color: estado === 'completado'   ? '#ccc' :
                       estado === 'no_soportado' ? '#555' : modelo.color,
              }}>
                {modelo.nombre}
                {estado === 'no_soportado' && <span style={{ color: '#555' }}> — no soportado</span>}
                {estado === 'respondiendo' && <span style={{ color: '#888' }}> — respondiendo...</span>}
                {estado === 'esperando'    && <span style={{ color: '#888' }}> — en cola</span>}
                {estado === 'completado'   && <span style={{ color: '#888' }}> — completado</span>}
              </span>
              <span className={`bat-checkmark${estado === 'completado' ? ' visible' : ''}`}>✓</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
