/**
 * Componente: DashboardPage
 * Ruta:       frontend/src/pages/DashboardPage.tsx
 *
 * Descripcion:
 *   Pantalla de dashboard con 4 KPI cards, advertencia anti-sesgo y 12 graficos
 *   divididos en dos bloques: metricas de evaluacion humana y metricas automaticas.
 *   Datos reales via GET /api/v1/stats (unica peticion).
 *
 * Sprint: Sprint 3 — S3-13 a S3-16
 */

/* eslint-disable @typescript-eslint/no-explicit-any */
import type { ReactNode } from 'react'
import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  ResponsiveContainer,
  ScatterChart, Scatter, XAxis, YAxis, Tooltip, CartesianGrid,
  BarChart, Bar, Cell, Legend,
  RadarChart, PolarGrid, PolarAngleAxis, Radar,
  Line,
  PieChart, Pie,
  ComposedChart, YAxis as YAxisRight,
} from 'recharts'
import { obtenerStats } from '@/services/statsApi'
import { PROVEEDORES_LIST, proveedorColor, proveedorNombreCorto, proveedorIcono } from '@/config/llmProviders'
import { TOKENS } from '@/utils/tokens'
import type {
  RespuestaStats,
  MetricasModelo,
  MetricasImagenModelo,
  MetricasComparativaIdioma,
  TasaRechazo,
} from '@/types/stats'
import type { TarifaDTO } from '@/types/admin'
import type { LLMProvider, TestCategory } from '@/types/benchmark'

/* ── Constantes de color por modelo — derivadas del config central ─────────── */
const COLORES: Record<LLMProvider, string> = Object.fromEntries(
  PROVEEDORES_LIST.map((p) => [p, proveedorColor(p)])
) as Record<LLMProvider, string>
const NOMBRES: Record<LLMProvider, string> = Object.fromEntries(
  PROVEEDORES_LIST.map((p) => [p, proveedorNombreCorto(p)])
) as Record<LLMProvider, string>
const PROVEEDORES: LLMProvider[] = PROVEEDORES_LIST

const CATEGORIAS: TestCategory[] = [
  'razonamiento', 'codigo', 'creativa', 'concretas',
  'traduccion', 'resumen', 'imagen', 'libre',
]
const ETIQ_CAT: Record<TestCategory, string> = {
  razonamiento: 'Razonamiento',
  codigo:       'Código',
  creativa:     'Creativa',
  concretas:      'Concretas',
  traduccion:   'TRADUCCIÓN',
  resumen:      'Resumen',
  imagen:       'Visión',
  libre:        'Libre',
}
const NOMBRE_CAT: Record<string, string> = {
  razonamiento: 'Razonamiento lógico',
  codigo:       'Generación de código',
  creativa:     'Escritura creativa',
  concretas:      'Preguntas concretas',
  traduccion:   'Traducción',
  resumen:      'Resumen',
  imagen:       'Imagen',
  libre:        'Texto libre',
}

/* ── Colores para donut ──────────────────────────────────────────────────── */
const COLORES_CAT = [
  '#A855F7', '#38BDF8', '#FBBF24', '#34D399',
  '#F472B6', '#818CF8', '#FB923C', '#94A3B8',
]

/* ── Lookup nombre → color e icono (para ticks de eje X) ────────────────── */
const COLOR_POR_NOMBRE: Record<string, string> = Object.fromEntries(
  PROVEEDORES_LIST.map((p) => [NOMBRES[p], COLORES[p]])
)
const ICONO_POR_NOMBRE: Record<string, string> = Object.fromEntries(
  PROVEEDORES_LIST.map((p) => [NOMBRES[p], proveedorIcono(p)])
)

/* ── Helpers ─────────────────────────────────────────────────────────────── */
function normalizar(valores: number[]): number[] {
  const mn = Math.min(...valores)
  const mx = Math.max(...valores)
  if (mx === mn) return valores.map(() => 0.5)
  return valores.map((v) => (v - mn) / (mx - mn))
}

function colorHeatmap(val: number | null): string {
  if (val == null) return 'rgba(20,20,36,0.9)'
  const t = Math.max(0, Math.min(1, (val - 3.5) / 1.2))
  return `rgba(157,78,221,${0.12 + t * 0.65})`
}

function colorJaccard(val: number): string {
  const t = Math.max(0, Math.min(1, val))
  return `rgba(157,78,221,${0.08 + t * 0.72})`
}

/* ── Sub-componentes simples ─────────────────────────────────────────────── */
function KpiCard({
  titulo, valor, sub, color = '#9D4EDD',
}: { titulo: string; valor: string | number; sub?: string; color?: string }) {
  return (
    <div className="card px-5 py-4 flex flex-col gap-1">
      <span className="text-xs text-muted uppercase tracking-wider">{titulo}</span>
      <span className="text-3xl font-bold font-mono" style={{ color }}>{valor}</span>
      {sub && <span className="text-xs text-muted">{sub}</span>}
    </div>
  )
}

function SeccionTitulo({ label }: { label: ReactNode }) {
  // Reutiliza el mismo formato que el listado de modelos en BenchmarkPage
  // (caja morada con borde blanco roto y texto en mayusculas) para que las
  // secciones del dashboard tengan un aspecto consistente con el resto de
  // la aplicacion. El label acepta ReactNode para que algunas secciones
  // puedan inyectar spans con text-transform forzado (p. ej. mantener
  // "vs" en minuscula dentro de un titulo en mayusculas).
  return (
    <p className="text-base sm:text-xl font-semibold text-text uppercase tracking-widest mb-3 text-center
                  border border-text-alt/60 bg-primary/15 rounded-xl px-3 sm:px-5 py-2 sm:py-3">
      {label}
    </p>
  )
}

function TarjetaGrafico({
  titulo, children, className = '', fuente, descargable = true,
}: {
  titulo: string
  children: ReactNode
  className?: string
  fuente?: 'humana' | 'automatica' | 'mixta'
  /** Mostrar el boton "↓ PNG" en la cabecera. Falso para tarjetas que no
   *  contienen un grafico SVG de Recharts (ej. tablas HTML), porque el
   *  capturador busca svg.recharts-surface y caeria al primer SVG suelto
   *  de la cabecera (icono de fuente). */
  descargable?: boolean
}) {
  const refContenedor = useRef<HTMLDivElement>(null)

  function descargarPng() {
    // Los iconos de la cabecera tambien son SVGs: buscar el SVG de Recharts por su clase
    const svg = (refContenedor.current?.querySelector<SVGSVGElement>('svg.recharts-surface')
              ?? refContenedor.current?.querySelector<SVGSVGElement>('svg'))
    if (!svg) return
    const w = svg.clientWidth  || 600
    const h = svg.clientHeight || 300
    // Clon con dimensiones explicitas para que el canvas lo renderice correctamente
    const clone = svg.cloneNode(true) as SVGElement
    clone.setAttribute('width',  String(w))
    clone.setAttribute('height', String(h))
    const svgStr = new XMLSerializer().serializeToString(clone)
    const blob   = new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' })
    const url    = URL.createObjectURL(blob)
    const img    = new Image()
    img.onload = () => {
      const escala  = 2  // resolucion doble (retina)
      const canvas  = document.createElement('canvas')
      canvas.width  = w * escala
      canvas.height = h * escala
      const ctx = canvas.getContext('2d')!
      ctx.scale(escala, escala)
      ctx.fillStyle = TOKENS.surface
      ctx.fillRect(0, 0, w, h)
      ctx.drawImage(img, 0, 0, w, h)
      URL.revokeObjectURL(url)
      const a = document.createElement('a')
      a.download = `${titulo.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^\w\s-]/g, '').trim().replace(/\s+/g, '_')}.png`
      a.href = canvas.toDataURL('image/png')
      a.click()
    }
    img.src = url
  }

  return (
    <div ref={refContenedor} className={`card p-4 flex flex-col gap-3 ${className}`}>
      <div className="flex items-center gap-1.5">
        <p className="text-xs font-semibold text-muted uppercase tracking-widest flex-1">{titulo}</p>
        {fuente === 'humana' && (
          <svg width="32" height="32" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <title>Datos de evaluaciones de usuarios</title>
            <rect x="0" y="0" width="16" height="16" rx="3" fill="#FFFFFF"/>
            <path d="M1 16 L1 10 L4.5 13 L8 7.5 L11.5 13 L15 10 L15 16 Z" fill="#1A1A2E"/>
            <rect x="6.5" y="9" width="3" height="2.5" fill="#F0DEC8"/>
            <ellipse cx="8" cy="6" rx="4" ry="4.5" fill="#F0DEC8"/>
            <path d="M4 4.5 Q4 0.5 8 1 Q12 0.5 12 4.5 Q10 2.5 8 3.5 Q6 2.5 4 4.5 Z" fill="#1A1A2E"/>
            <ellipse cx="6.2" cy="5.8" rx="0.9" ry="0.8" fill="#DC2626"/>
            <ellipse cx="9.8" cy="5.8" rx="0.9" ry="0.8" fill="#DC2626"/>
            <path d="M5.5 8 Q8 9 10.5 8" stroke="#A0747A" strokeWidth="0.6" fill="none" strokeLinecap="round"/>
            <line x1="7"   y1="8"   x2="7"   y2="9.1" stroke="#FFFFFF" strokeWidth="0.8" strokeLinecap="round"/>
            <line x1="9"   y1="8"   x2="9"   y2="9.1" stroke="#FFFFFF" strokeWidth="0.8" strokeLinecap="round"/>
          </svg>
        )}
        {fuente === 'automatica' && (
          <svg width="32" height="32" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <title>Métrica automática</title>
            <line x1="8" y1="0.5" x2="8" y2="2.5" stroke="#ADADAD" strokeWidth="1.1" strokeLinecap="round"/>
            <circle cx="8" cy="0.7" r="0.9" fill="#D0D0D0"/>
            <rect x="1.5" y="2.5" width="13" height="12" rx="2.5" fill="#B8B8B8"/>
            <rect x="1.5" y="2.5" width="13" height="5" rx="2.5" fill="#D2D2D2"/>
            <rect x="2.5" y="6" width="11" height="3.5" rx="1" fill="#111827"/>
            <circle cx="6"  cy="7.75" r="1.1" fill="#FBBF24"/>
            <circle cx="10" cy="7.75" r="1.1" fill="#FBBF24"/>
            <path d="M4.5 12 Q8 14.5 11.5 12" stroke="#777" strokeWidth="1" fill="none" strokeLinecap="round"/>
          </svg>
        )}
        {/* Icono combinado: robot (automatico) + vampiro (humano) para graficos mixtos */}
        {fuente === 'mixta' && (
          <svg width="44" height="28" viewBox="0 0 34 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <title>Métrica mixta — automática y humana</title>
            {/* ── Robot (izquierda, x 0-15) ── */}
            <line x1="8" y1="0.5" x2="8" y2="2.5" stroke="#ADADAD" strokeWidth="1.1" strokeLinecap="round"/>
            <circle cx="8" cy="0.7" r="0.9" fill="#D0D0D0"/>
            <rect x="1.5" y="2.5" width="13" height="12" rx="2.5" fill="#B8B8B8"/>
            <rect x="1.5" y="2.5" width="13" height="5"  rx="2.5" fill="#D2D2D2"/>
            <rect x="2.5" y="6"   width="11" height="3.5" rx="1"  fill="#111827"/>
            <circle cx="6"  cy="7.75" r="1.1" fill="#FBBF24"/>
            <circle cx="10" cy="7.75" r="1.1" fill="#FBBF24"/>
            <path d="M4.5 12 Q8 14.5 11.5 12" stroke="#777" strokeWidth="1" fill="none" strokeLinecap="round"/>
            {/* ── Vampiro (derecha, x +18) ── */}
            <rect x="18" y="0" width="16" height="16" rx="3" fill="#FFFFFF"/>
            <path d="M19 16 L19 10 L22.5 13 L26 7.5 L29.5 13 L33 10 L33 16 Z" fill="#1A1A2E"/>
            <rect x="24.5" y="9" width="3" height="2.5" fill="#F0DEC8"/>
            <ellipse cx="26" cy="6" rx="4" ry="4.5" fill="#F0DEC8"/>
            <path d="M22 4.5 Q22 0.5 26 1 Q30 0.5 30 4.5 Q28 2.5 26 3.5 Q24 2.5 22 4.5 Z" fill="#1A1A2E"/>
            <ellipse cx="24.2" cy="5.8" rx="0.9" ry="0.8" fill="#DC2626"/>
            <ellipse cx="27.8" cy="5.8" rx="0.9" ry="0.8" fill="#DC2626"/>
            <path d="M23.5 8 Q26 9 28.5 8" stroke="#A0747A" strokeWidth="0.6" fill="none" strokeLinecap="round"/>
            <line x1="25" y1="8" x2="25" y2="9.1" stroke="#FFFFFF" strokeWidth="0.8" strokeLinecap="round"/>
            <line x1="27" y1="8" x2="27" y2="9.1" stroke="#FFFFFF" strokeWidth="0.8" strokeLinecap="round"/>
          </svg>
        )}
        {/* Boton de descarga PNG (solo si la tarjeta contiene un grafico SVG) */}
        {descargable && (
          <button
            onClick={descargarPng}
            title="Descargar gráfico como imagen PNG"
            className="flex items-center gap-1 text-[10px] font-semibold text-muted hover:text-text transition-colors px-2 py-1 rounded-lg"
            style={{ border: '1px solid rgba(255,255,255,0.18)', background: 'rgba(255,255,255,0.04)' }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.10)' }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.04)' }}
          >
            ↓ PNG
          </button>
        )}
      </div>
      {children}
    </div>
  )
}

/* ── Selector lateral de graficos ─────────────────────────────────────────
 *
 * Sustituye a una rejilla de TarjetaGrafico cuando hay 5+ graficos en una
 * misma seccion: a la izquierda se ve un listado de botones con todas las
 * opciones, a la derecha la grafica seleccionada. Solo se renderiza una
 * tarjeta a la vez para reducir la carga cognitiva del dashboard.
 *
 * Cada opcion define su titulo, fuente (humana/automatica/mixta) y un
 * render() que devuelve el cuerpo de la TarjetaGrafico (con descripciones,
 * notas al pie y todo lo que tenga el chart). El selector solo se encarga
 * del layout y del estado de seleccion.
 */
interface OpcionGrafico {
  id: string
  /** Texto del boton lateral. Conciso (max ~32 chars). */
  label: string
  /** Titulo grande dentro de la TarjetaGrafico. */
  titulo: string
  fuente: 'humana' | 'automatica' | 'mixta'
  render: () => ReactNode
}

function SelectorGraficos({
  opciones, defaultId, horizontal = false,
}: {
  opciones: OpcionGrafico[]
  defaultId: string
  /** true = botones en una fila repartida a lo ancho, encima de la grafica.
   *  false (def) = columna lateral de 240px a la izquierda de la grafica. */
  horizontal?: boolean
}) {
  const [seleccionado, setSeleccionado] = useState<string>(defaultId)
  const actual = opciones.find((o) => o.id === seleccionado) ?? opciones[0]

  const botones = (
    <div className={horizontal ? 'flex gap-2 flex-wrap sm:flex-nowrap' : 'flex flex-col gap-1.5'}>
      {opciones.map((o) => {
        const activo = o.id === actual.id
        return (
          <button
            key={o.id}
            type="button"
            onClick={() => setSeleccionado(o.id)}
            className={
              'text-[11px] font-semibold uppercase tracking-wider px-3 rounded-md border-2 '
              + 'transition-all duration-150 cursor-pointer leading-snug '
              + (horizontal
                ? 'flex-1 min-w-[120px] text-center py-5 flex items-center justify-center'
                : 'text-left py-2')
            }
            style={{
              color: activo ? '#0F0F1C' : TOKENS.textAlt,
              background: activo ? TOKENS.textAlt : 'rgba(157,78,221,0.10)',
              borderColor: TOKENS.textAlt,
              // Sombra brillante al estar activo: halo blanco roto + brillo
              // violeta exterior para resaltar visualmente la seleccion del
              // selector frente al fondo oscuro del dashboard.
              boxShadow: activo
                ? '0 0 20px rgba(245,245,240,0.90), 0 0 36px rgba(157,78,221,0.55), 0 2px 8px rgba(0,0,0,0.55)'
                : '0 0 4px rgba(245,245,240,0.18)',
              transform: activo ? (horizontal ? 'translateY(-2px)' : 'translateX(2px)') : undefined,
            }}
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )

  if (horizontal) {
    return (
      <div className="flex flex-col gap-4">
        {botones}
        <TarjetaGrafico titulo={actual.titulo} fuente={actual.fuente}>
          {actual.render()}
        </TarjetaGrafico>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr] gap-4">
      {botones}
      <TarjetaGrafico titulo={actual.titulo} fuente={actual.fuente}>
        {actual.render()}
      </TarjetaGrafico>
    </div>
  )
}

/* ── Tooltip compartido con indicador de modelo ganador ───────────────────── */
function TooltipEstrella({
  active, payload, label, labelMejor,
}: {
  active?: boolean
  payload?: { name: string; value: number; color: string; payload: { esMejor?: boolean } }[]
  label?: string
  labelMejor: string
}) {
  if (!active || !payload?.length) return null
  const esMejor = payload[0]?.payload?.esMejor === true
  return (
    <div className="card px-3 py-2 text-xs space-y-0.5">
      {label && <p className="text-muted">{label}</p>}
      {payload.map((p) => (
        <div key={p.name} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full flex-shrink-0 inline-block" style={{ background: p.color }} />
          <span className="text-muted">{p.name}:</span>
          <span className="font-mono font-bold text-text">{p.value}</span>
        </div>
      ))}
      {esMejor && <p className="text-yellow-400 font-semibold mt-1">★ {labelMejor}</p>}
    </div>
  )
}

/* ── Tick de eje X con icono y color del modelo ──────────────────────────── */
function TickColorModelo(props: any) {
  const { x, y, payload } = props as { x: number; y: number; payload: { value: string } }
  const color = COLOR_POR_NOMBRE[payload.value] ?? '#A0A0C0'
  const icono = ICONO_POR_NOMBRE[payload.value]
  return (
    <g>
      <text x={x} y={y} dy={13} textAnchor="middle" fontSize={11} fontWeight={600} fill={color}>
        {payload.value}
      </text>
      {icono && (
        <image x={x - 9} y={y + 18} width={18} height={18} href={icono} />
      )}
    </g>
  )
}

/* ── Helper: ★ encima de la barra ganadora ───────────────────────────────── */
function etiquetaEstrella(mejorIdx: number, color: string) {
  return function EtiquetaLabel(props: any) {
    const { x, y, width, index } = props as { x: number; y: number; width: number; index: number }
    if (index !== mejorIdx) return <g />
    const cx = x + width / 2
    const cy = y - 22
    return (
      <g>
        <circle cx={cx} cy={cy} r={16} fill="none"
                stroke={color} strokeWidth={1.5} strokeDasharray="5 3" opacity={0.9} />
        <text x={cx} y={cy} textAnchor="middle" dominantBaseline="middle" fontSize={20} fill={color}>★</text>
      </g>
    )
  }
}

/* ── Scatter: latencia vs coste ──────────────────────────────────────────── */
function GraficoScatter({ metricas }: { metricas: MetricasModelo[] }) {
  // Mejor eficiencia: menor distancia euclidiana normalizada al origen (0 lat, 0 coste)
  const latencias = metricas.map((m) => m.latencia_ms)
  const costes    = metricas.map((m) => m.cost_usd)
  const minLat = Math.min(...latencias), maxLat = Math.max(...latencias)
  const minCos = Math.min(...costes),    maxCos = Math.max(...costes)
  const distNorm = (m: MetricasModelo) => {
    const lN = maxLat > minLat ? (m.latencia_ms - minLat) / (maxLat - minLat) : 0
    const cN = maxCos > minCos ? (m.cost_usd    - minCos) / (maxCos - minCos) : 0
    return lN * lN + cN * cN
  }
  const mejorProveedor = metricas.reduce((best, m) =>
    distNorm(m) < distNorm(best) ? m : best
  ).proveedor

  const renderPunto = (proveedor: LLMProvider) => (props: any) => {
    const { cx, cy } = props
    const esMejor = proveedor === mejorProveedor
    const color   = COLORES[proveedor]
    return (
      <g>
        {esMejor && (
          <circle cx={cx} cy={cy} r={17} fill="none"
                  stroke={color} strokeWidth={1.5} strokeDasharray="4 3" opacity={0.75} />
        )}
        <circle cx={cx} cy={cy} r={10} fill={color} />
        {esMejor && (
          <text x={cx} y={cy - 22} textAnchor="middle" fontSize={13} fill={color}>★</text>
        )}
      </g>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <ScatterChart margin={{ top: 22, right: 20, bottom: 20, left: 10 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={TOKENS.border} />
        <XAxis
          type="number" dataKey="coste" name="Coste"
          label={{ value: 'Coste (USD)', position: 'insideBottom', offset: -10, fill: '#6B7099', fontSize: 11 }}
          tick={{ fill: '#6B7099', fontSize: 10 }}
          tickFormatter={(v: number) => `$${v.toFixed(8)}`}
        />
        <YAxis
          type="number" dataKey="latencia" name="Latencia"
          label={{ value: 'Latencia (ms)', angle: -90, position: 'insideLeft', fill: '#6B7099', fontSize: 11 }}
          tick={{ fill: '#6B7099', fontSize: 10 }}
        />
        <Tooltip
          cursor={{ strokeDasharray: '3 3' }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null
            const d = payload[0].payload as { proveedor: string; latencia: number; coste: number }
            const esMejor = d.proveedor === mejorProveedor
            return (
              <div className="card px-3 py-2 text-xs space-y-0.5">
                <p className="font-bold flex items-center gap-1.5"
                   style={{ color: COLORES[d.proveedor as LLMProvider] }}>
                  {NOMBRES[d.proveedor as LLMProvider]}
                  {esMejor && (
                    <span className="text-yellow-400 font-normal">★ Mejor eficiencia</span>
                  )}
                </p>
                <p className="text-muted">Latencia: <span className="text-text font-mono">{d.latencia.toFixed(0)} ms</span></p>
                <p className="text-muted">Coste: <span className="text-text font-mono">${d.coste.toFixed(8)}</span></p>
              </div>
            )
          }}
        />
        {metricas.map((m) => (
          <Scatter
            key={m.proveedor}
            name={NOMBRES[m.proveedor]}
            data={[{ proveedor: m.proveedor, latencia: m.latencia_ms, coste: m.cost_usd }]}
            fill={COLORES[m.proveedor]}
            shape={renderPunto(m.proveedor)}
          />
        ))}
      </ScatterChart>
    </ResponsiveContainer>
  )
}

/* ── Barras: rating medio por modelo ─────────────────────────────────────── */
function GraficoRating({ metricas }: { metricas: MetricasModelo[] }) {
  const datos = metricas.map((m) => ({
    nombre: NOMBRES[m.proveedor],
    rating: m.rating_medio ?? 0,
    proveedor: m.proveedor,
  })).sort((a, b) => b.rating - a.rating)
  const mejorIdx = datos.reduce((bi, d, i) => d.rating > datos[bi].rating ? i : bi, 0)
  const datosConFlag = datos.map((d, i) => ({ ...d, esMejor: i === mejorIdx }))
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={datosConFlag} margin={{ top: 44, right: 10, bottom: 10, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={TOKENS.border} vertical={false} />
        <XAxis dataKey="nombre" tick={<TickColorModelo />} height={46} />
        <YAxis domain={[0, 5]} tick={{ fill: '#6B7099', fontSize: 10 }} />
        <Tooltip content={(p: any) => <TooltipEstrella {...p} labelMejor="Mejor valorado por los evaluadores" />} />
        <Bar dataKey="rating" name="Valoración" radius={[4, 4, 0, 0]}
             label={etiquetaEstrella(mejorIdx, COLORES[datos[mejorIdx].proveedor])}>
          {datosConFlag.map((d) => (
            <Cell key={d.proveedor} fill={COLORES[d.proveedor]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

/* ── Barras: ranking medio de preferencia ────────────────────────────────── */
function GraficoRanking({ metricas }: { metricas: MetricasModelo[] }) {
  const datos = metricas
    .filter((m) => m.rango_preferencia_medio != null)
    .map((m) => ({
      nombre:    NOMBRES[m.proveedor],
      rango:     +(m.rango_preferencia_medio!).toFixed(2),
      proveedor: m.proveedor,
    }))
    .sort((a, b) => b.rango - a.rango)

  if (datos.length === 0) {
    return (
      <p className="text-xs text-muted italic text-center py-8">
        Sin datos de ranking todavía. Completa evaluaciones con la sección de preferencia.
      </p>
    )
  }

  const mejorIdx     = datos.reduce((bi, d, i) => d.rango < datos[bi].rango ? i : bi, 0)
  const datosConFlag = datos.map((d, i) => ({ ...d, esMejor: i === mejorIdx }))

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={datosConFlag} margin={{ top: 44, right: 10, bottom: 10, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={TOKENS.border} vertical={false} />
        <XAxis dataKey="nombre" tick={<TickColorModelo />} height={46} />
        <YAxis
          domain={[0, 4.5]}
          tick={{ fill: '#6B7099', fontSize: 10 }}
          tickFormatter={(v: number) => `#${v.toFixed(0)}`}
        />
        <Tooltip content={(p: any) => <TooltipEstrella {...p} labelMejor="Modelo más preferido" />} />
        <Bar dataKey="rango" name="Rango medio" radius={[4, 4, 0, 0]}
             label={etiquetaEstrella(mejorIdx, COLORES[datos[mejorIdx].proveedor])}>
          {datosConFlag.map((d) => (
            <Cell key={d.proveedor} fill={COLORES[d.proveedor]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

/* ── Heatmap: modelo × categoria ─────────────────────────────────────────── */
function GraficoHeatmap({ celdas }: { celdas: RespuestaStats['heatmap'] }) {
  const mapa = new Map<string, number | null>()
  celdas.forEach((c) => mapa.set(`${c.proveedor}|${c.categoria}`, c.rating_medio))

  return (
    <div className="overflow-x-auto">
      <div className="grid" style={{ gridTemplateColumns: `80px repeat(${CATEGORIAS.length}, 1fr)`, minWidth: 520 }}>
        {/* Cabecera */}
        <div />
        {CATEGORIAS.map((cat) => (
          <div key={cat} className="text-center text-[9px] text-muted uppercase py-1 px-0.5 font-semibold tracking-wide">
            {ETIQ_CAT[cat]}
          </div>
        ))}
        {/* Filas por modelo */}
        {PROVEEDORES.map((prov) => (
          <>
            <div key={`lbl-${prov}`}
                 className="text-[11px] font-semibold py-2 pr-2 flex items-center"
                 style={{ color: COLORES[prov] }}>
              {NOMBRES[prov]}
            </div>
            {CATEGORIAS.map((cat) => {
              const val = mapa.get(`${prov}|${cat}`) ?? null
              return (
                <div key={`${prov}|${cat}`}
                     className="m-0.5 rounded text-center text-[10px] font-mono font-bold py-2.5 flex items-center justify-center transition-colors"
                     style={{
                       background: colorHeatmap(val),
                       color: val != null ? '#E2DEFF' : '#3A3A5A',
                     }}
                     title={`${NOMBRES[prov]} · ${cat} · ${val != null ? val.toFixed(2) : 'sin datos'}`}>
                  {val != null ? val.toFixed(1) : '–'}
                </div>
              )
            })}
          </>
        ))}
      </div>
      <p className="text-[9px] text-muted mt-2">
        Escala de color: 3.5 (tenue) → 4.7 (intenso). Celdas "–" sin datos suficientes.
      </p>
    </div>
  )
}

/* ── Radar: perfil tecnico normalizado ──────────────────────────────────── */
function GraficoRadar({ metricas }: { metricas: MetricasModelo[] }) {
  const velocidades   = metricas.map((m) => m.tokens_por_segundo)
  const ratings       = metricas.map((m) => m.rating_medio ?? 0)
  const costes        = metricas.map((m) => m.cost_usd)
  const diversidades  = metricas.map((m) => m.diversidad_lexica)
  const palabras      = metricas.map((m) => m.palabras)

  const normVel  = normalizar(velocidades)
  const normRat  = normalizar(ratings)
  const normEfi  = normalizar(costes.map((c) => -c))
  const normDiv  = normalizar(diversidades)
  const normCon  = normalizar(palabras.map((p) => -p))

  const ejes = ['Velocidad', 'Calidad', 'Eficiencia', 'Riqueza', 'Concision']
  const datos = ejes.map((eje, i) => {
    const entrada: Record<string, string | number> = { eje }
    metricas.forEach((m, mi) => {
      const vals = [normVel, normRat, normEfi, normDiv, normCon]
      entrada[m.proveedor] = +(vals[i][mi] * 100).toFixed(1)
    })
    return entrada
  })

  return (
    <ResponsiveContainer width="100%" height={220}>
      <RadarChart data={datos} cx="50%" cy="50%" outerRadius="70%">
        <PolarGrid stroke={TOKENS.border} />
        <PolarAngleAxis dataKey="eje" tick={{ fill: '#6B7099', fontSize: 10 }} />
        {PROVEEDORES.map((prov) => (
          <Radar
            key={prov}
            name={NOMBRES[prov]}
            dataKey={prov}
            stroke={COLORES[prov]}
            fill={COLORES[prov]}
            fillOpacity={0.15}
            strokeWidth={1.5}
          />
        ))}
        <Legend iconSize={8} wrapperStyle={{ fontSize: 10 }} />
      </RadarChart>
    </ResponsiveContainer>
  )
}

/* ── Donut: distribucion por categoria ───────────────────────────────────── */
function GraficoDonut({ porCategoria }: { porCategoria: Record<string, number> }) {
  const datos = Object.entries(porCategoria)
    .filter(([, v]) => v > 0)
    .map(([name, value], i) => ({ name: NOMBRE_CAT[name] ?? name, value, color: COLORES_CAT[i % COLORES_CAT.length] }))

  return (
    <ResponsiveContainer width="100%" height={180}>
      <PieChart>
        <Pie
          data={datos} dataKey="value" nameKey="name"
          cx="50%" cy="50%" innerRadius={45} outerRadius={70}
          paddingAngle={2}
        >
          {datos.map((d, i) => (
            <Cell key={i} fill={d.color} />
          ))}
        </Pie>
        <Tooltip
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null
            const d = payload[0]
            return (
              <div className="card px-3 py-2 text-xs">
                <span style={{ color: d.payload.color as string }}>{d.name}</span>
                {': '}
                <span className="font-mono font-bold text-text">{d.value as number}</span>
              </div>
            )
          }}
        />
        <Legend iconSize={8} wrapperStyle={{ fontSize: 10 }} />
      </PieChart>
    </ResponsiveContainer>
  )
}

/* ── Barras: latencia media por modelo ───────────────────────────────────── */
function GraficoLatencia({ metricas }: { metricas: MetricasModelo[] }) {
  const datos = metricas.map((m) => ({
    nombre: NOMBRES[m.proveedor],
    latencia: +m.latencia_ms.toFixed(0),
    proveedor: m.proveedor,
  })).sort((a, b) => b.latencia - a.latencia)
  const mejorIdx     = datos.reduce((bi, d, i) => d.latencia < datos[bi].latencia ? i : bi, 0)
  const datosConFlag = datos.map((d, i) => ({ ...d, esMejor: i === mejorIdx }))
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={datosConFlag} margin={{ top: 44, right: 10, bottom: 10, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={TOKENS.border} vertical={false} />
        <XAxis dataKey="nombre" tick={<TickColorModelo />} height={46} />
        <YAxis tick={{ fill: '#6B7099', fontSize: 10 }} unit=" ms" />
        <Tooltip content={(p: any) => <TooltipEstrella {...p} labelMejor="Modelo más rápido en texto" />} />
        <Bar dataKey="latencia" name="Latencia (ms)" radius={[4, 4, 0, 0]}
             label={etiquetaEstrella(mejorIdx, COLORES[datos[mejorIdx].proveedor])}>
          {datosConFlag.map((d) => (
            <Cell key={d.proveedor} fill={COLORES[d.proveedor]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

/* ── Tokens entrada o salida (toggle) ─────────────────────────────────────
 *
 * Sigue el mismo patron que GraficoTokensIdioma de la comparativa bilingue:
 * dos botones encima eligen si se muestra el consumo de tokens de entrada
 * o de salida, y la grafica solo pinta una metrica a la vez. Mostrar las
 * dos apiladas hacia mezclar dos ejes que no son comparables 1-a-1 (el
 * prompt fija la entrada, el modelo decide la salida) y dificultaba ver
 * quien es realmente "mas barato" en cada dimension.
 */
function GraficoTokens({ metricas }: { metricas: MetricasModelo[] }) {
  const [tipo, setTipo] = useState<'entrada' | 'salida'>('entrada')
  const campo = tipo === 'entrada' ? 'tokens_entrada' : 'tokens_salida'

  const datos = metricas.map((m) => ({
    nombre: NOMBRES[m.proveedor],
    valor: +m[campo].toFixed(0),
    proveedor: m.proveedor,
  })).sort((a, b) => b.valor - a.valor)
  const mejorIdx     = datos.reduce((bi, d, i) => d.valor < datos[bi].valor ? i : bi, 0)
  const datosConFlag = datos.map((d, i) => ({ ...d, esMejor: i === mejorIdx }))
  const labelMejor   = tipo === 'entrada'
    ? 'Menor consumo de tokens de entrada'
    : 'Menor consumo de tokens de salida'

  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-2 justify-center flex-wrap">
        {(['entrada', 'salida'] as const).map((t) => {
          const activo = tipo === t
          return (
            <button
              key={t}
              type="button"
              onClick={() => setTipo(t)}
              className="text-[10px] font-bold uppercase tracking-wider px-3 py-1.5 rounded-md border-2 transition-all duration-150 cursor-pointer"
              style={{
                color: activo ? '#0F0F1C' : TOKENS.textAlt,
                background: activo ? TOKENS.textAlt : 'rgba(157,78,221,0.10)',
                borderColor: TOKENS.textAlt,
                boxShadow: activo
                  ? '0 0 12px rgba(245,245,240,0.55), 0 2px 6px rgba(0,0,0,0.45)'
                  : '0 0 4px rgba(245,245,240,0.20)',
              }}
            >
              Mostrar tokens {t}
            </button>
          )
        })}
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={datosConFlag} margin={{ top: 44, right: 10, bottom: 10, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={TOKENS.border} vertical={false} />
          <XAxis dataKey="nombre" tick={<TickColorModelo />} height={46} />
          <YAxis tick={{ fill: '#6B7099', fontSize: 10 }} />
          <Tooltip content={(p: any) => <TooltipEstrella {...p} labelMejor={labelMejor} />} />
          <Bar dataKey="valor" name={tipo === 'entrada' ? 'Tokens entrada' : 'Tokens salida'} radius={[4, 4, 0, 0]}
               label={etiquetaEstrella(mejorIdx, COLORES[datos[mejorIdx].proveedor])}>
            {datosConFlag.map((d) => (
              <Cell key={d.proveedor} fill={COLORES[d.proveedor]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

/* ── Barras: velocidad tok/s ─────────────────────────────────────────────── */
function GraficoTokPS({ metricas }: { metricas: MetricasModelo[] }) {
  const datos = metricas.map((m) => ({
    nombre: NOMBRES[m.proveedor],
    tokps: +m.tokens_por_segundo.toFixed(1),
    proveedor: m.proveedor,
  })).sort((a, b) => b.tokps - a.tokps)
  const mejorIdx     = datos.reduce((bi, d, i) => d.tokps > datos[bi].tokps ? i : bi, 0)
  const datosConFlag = datos.map((d, i) => ({ ...d, esMejor: i === mejorIdx }))
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={datosConFlag} margin={{ top: 44, right: 10, bottom: 10, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={TOKENS.border} vertical={false} />
        <XAxis dataKey="nombre" tick={<TickColorModelo />} height={46} />
        <YAxis tick={{ fill: '#6B7099', fontSize: 10 }} unit=" t/s" />
        <Tooltip content={(p: any) => <TooltipEstrella {...p} labelMejor="Mayor velocidad de generación" />} />
        <Bar dataKey="tokps" name="Tok/s" radius={[4, 4, 0, 0]}
             label={etiquetaEstrella(mejorIdx, COLORES[datos[mejorIdx].proveedor])}>
          {datosConFlag.map((d) => (
            <Cell key={d.proveedor} fill={COLORES[d.proveedor]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

/* ── Barras: coste medio por respuesta (USD) ────────────────────────────── */
function GraficoCosteRespuesta({ metricas }: { metricas: MetricasModelo[] }) {
  const datos = metricas.map((m) => ({
    nombre: NOMBRES[m.proveedor],
    coste: +m.cost_usd.toFixed(8),
    proveedor: m.proveedor,
  })).sort((a, b) => b.coste - a.coste)
  const mejorIdx     = datos.reduce((bi, d, i) => d.coste < datos[bi].coste ? i : bi, 0)
  const datosConFlag = datos.map((d, i) => ({ ...d, esMejor: i === mejorIdx }))
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={datosConFlag} margin={{ top: 44, right: 10, bottom: 10, left: 10 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={TOKENS.border} vertical={false} />
        <XAxis dataKey="nombre" tick={<TickColorModelo />} height={46} />
        <YAxis tick={{ fill: '#6B7099', fontSize: 10 }} tickFormatter={(v: number) => `$${v.toFixed(8)}`} />
        <Tooltip content={(p: any) => <TooltipEstrella {...p} labelMejor="Coste medio por respuesta más bajo" />} />
        <Bar dataKey="coste" name="$/respuesta (media)" radius={[4, 4, 0, 0]}
             label={etiquetaEstrella(mejorIdx, COLORES[datos[mejorIdx].proveedor])}>
          {datosConFlag.map((d) => (
            <Cell key={d.proveedor} fill={COLORES[d.proveedor]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

/* ── Barras: coste por 100 palabras ─────────────────────────────────────── */
function GraficoCostePalabras({ metricas }: { metricas: MetricasModelo[] }) {
  const datos = metricas.map((m) => ({
    nombre: NOMBRES[m.proveedor],
    coste: +m.coste_por_100_palabras.toFixed(8),
    proveedor: m.proveedor,
  })).sort((a, b) => b.coste - a.coste)
  const mejorIdx     = datos.reduce((bi, d, i) => d.coste < datos[bi].coste ? i : bi, 0)
  const datosConFlag = datos.map((d, i) => ({ ...d, esMejor: i === mejorIdx }))
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={datosConFlag} margin={{ top: 44, right: 10, bottom: 10, left: 10 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={TOKENS.border} vertical={false} />
        <XAxis dataKey="nombre" tick={<TickColorModelo />} height={46} />
        <YAxis tick={{ fill: '#6B7099', fontSize: 10 }} tickFormatter={(v: number) => `$${v.toFixed(8)}`} />
        <Tooltip content={(p: any) => <TooltipEstrella {...p} labelMejor="Mejor relación precio/palabras" />} />
        <Bar dataKey="coste" name="$/100 palabras" radius={[4, 4, 0, 0]}
             label={etiquetaEstrella(mejorIdx, COLORES[datos[mejorIdx].proveedor])}>
          {datosConFlag.map((d) => (
            <Cell key={d.proveedor} fill={COLORES[d.proveedor]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

/* ── Combo: longitud y diversidad lexica ─────────────────────────────────── */
function GraficoLongitudDiversidad({ metricas }: { metricas: MetricasModelo[] }) {
  const datosBase = metricas.map((m) => ({
    nombre:     NOMBRES[m.proveedor],
    palabras:   +m.palabras.toFixed(0),
    diversidad: +(m.diversidad_lexica * 100).toFixed(1),
    proveedor:  m.proveedor,
  }))

  const mejorPalabrasIdx   = datosBase.reduce((bi, d, i) => d.palabras   > datosBase[bi].palabras   ? i : bi, 0)
  const mejorDiversidadIdx = datosBase.reduce((bi, d, i) => d.diversidad > datosBase[bi].diversidad ? i : bi, 0)

  const datos = datosBase.map((d, i) => ({
    ...d,
    esMejorPalabras:   i === mejorPalabrasIdx,
    esMejorDiversidad: i === mejorDiversidadIdx,
  }))

  // Dot personalizado para la linea de diversidad: estrella en el maximo
  const dotDiversidad = (props: any) => {
    const { cx, cy, index } = props as { cx: number; cy: number; index: number }
    if (index === mejorDiversidadIdx) {
      return (
        <g key={`dot-div-${index}`}>
          <circle cx={cx} cy={cy} r={16} fill="none"
                  stroke="#FBBF24" strokeWidth={1.5} strokeDasharray="5 3" opacity={0.9} />
          <text x={cx} y={cy} textAnchor="middle" dominantBaseline="middle" fontSize={20} fill="#FBBF24">★</text>
        </g>
      )
    }
    return <circle key={`dot-${index}`} cx={cx} cy={cy} r={5} fill="#FBBF24" stroke="#1C1305" strokeWidth={1} />
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <ComposedChart data={datos} margin={{ top: 44, right: 30, bottom: 10, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={TOKENS.border} vertical={false} />
        <XAxis dataKey="nombre" tick={<TickColorModelo />} height={46} />
        <YAxis yAxisId="left" tick={{ fill: '#6B7099', fontSize: 10 }} unit=" pal" />
        <YAxisRight yAxisId="right" orientation="right"
          tick={{ fill: '#FBBF24', fontSize: 10 }} unit="%" tickLine={false}
          axisLine={false} domain={[0, 100]} />
        <Tooltip
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null
            const d = payload[0]?.payload as typeof datos[0]
            return (
              <div className="card px-3 py-2 text-xs space-y-0.5">
                <p className="font-bold" style={{ color: COLORES[d.proveedor] }}>{d.nombre}</p>
                <p className="text-muted">Palabras: <span className="text-text font-mono">{d.palabras}</span></p>
                <p className="text-muted">Diversidad léxica: <span className="text-text font-mono">{d.diversidad} %</span></p>
                {d.esMejorPalabras   && <p className="text-yellow-400 font-semibold mt-1">★ Respuesta más extensa</p>}
                {d.esMejorDiversidad && <p className="text-yellow-400 font-semibold mt-1">★ Vocabulario más rico</p>}
              </div>
            )
          }}
        />
        <Bar yAxisId="left" dataKey="palabras" name="Palabras" radius={[4, 4, 0, 0]}
             label={etiquetaEstrella(mejorPalabrasIdx, COLORES[datos[mejorPalabrasIdx].proveedor])}>
          {datos.map((d) => (
            <Cell key={d.proveedor} fill={COLORES[d.proveedor]} fillOpacity={0.8} />
          ))}
        </Bar>
        <Line
          yAxisId="right" type="monotone" dataKey="diversidad" name="Diversidad (%)"
          stroke="#FBBF24" strokeWidth={2} strokeDasharray="5 3"
          dot={dotDiversidad}
        />
      </ComposedChart>
    </ResponsiveContainer>
  )
}

/* ── Matriz Jaccard 4×4 ──────────────────────────────────────────────────── */
function MatrizJaccard({ pares }: { pares: RespuestaStats['jaccard'] }) {
  const mapa = new Map<string, number>()
  pares.forEach((p) => {
    mapa.set(`${p.proveedor_a}|${p.proveedor_b}`, p.jaccard_medio)
    mapa.set(`${p.proveedor_b}|${p.proveedor_a}`, p.jaccard_medio)
  })

  return (
    <div>
      <div className="grid" style={{ gridTemplateColumns: `64px repeat(4, 1fr)` }}>
        <div />
        {PROVEEDORES.map((p) => (
          <div key={p} className="flex items-center justify-center gap-1 text-[10px] font-bold py-1.5"
               style={{ color: COLORES[p] }}>
            <img src={proveedorIcono(p)} alt={NOMBRES[p]} className="w-3.5 h-3.5 rounded flex-shrink-0" />
            {NOMBRES[p]}
          </div>
        ))}
        {PROVEEDORES.map((pA) => (
          <>
            <div key={`lbl-${pA}`}
                 className="text-[10px] font-bold flex items-center gap-1 pr-2"
                 style={{ color: COLORES[pA] }}>
              <img src={proveedorIcono(pA)} alt={NOMBRES[pA]} className="w-3.5 h-3.5 rounded flex-shrink-0" />
              {NOMBRES[pA]}
            </div>
            {PROVEEDORES.map((pB) => {
              const val = pA === pB ? 1 : (mapa.get(`${pA}|${pB}`) ?? 0)
              return (
                <div key={`${pA}|${pB}`}
                     className="m-0.5 rounded text-center text-[11px] font-mono font-bold py-3 flex items-center justify-center"
                     style={{
                       background: colorJaccard(val),
                       color: pA === pB ? '#FFFFFF' : '#C4B5FD',
                     }}
                     title={`${NOMBRES[pA]} vs ${NOMBRES[pB]}: ${val.toFixed(3)}`}>
                  {val.toFixed(2)}
                </div>
              )
            })}
          </>
        ))}
      </div>
      <p className="text-[9px] text-muted mt-2">
        Indice de Jaccard medio sobre bigramas de texto. Diagonal = 1 (modelo vs si mismo).
        Valores bajos indican perspectivas distintas.
      </p>
    </div>
  )
}

/* ── Barras: latencia de generacion de imagen ────────────────────────────── */
function GraficoImagenLatencia({ metricas }: { metricas: MetricasImagenModelo[] }) {
  const datos = metricas
    .filter((m) => m.proveedor !== 'claude')
    .map((m) => ({
      nombre:    NOMBRES[m.proveedor],
      latencia:  +m.latencia_ms.toFixed(0),
      proveedor: m.proveedor,
    })).sort((a, b) => b.latencia - a.latencia)
  const mejorIdx     = datos.reduce((bi, d, i) => d.latencia < datos[bi].latencia ? i : bi, 0)
  const datosConFlag = datos.map((d, i) => ({ ...d, esMejor: i === mejorIdx }))
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={datosConFlag} margin={{ top: 44, right: 10, bottom: 10, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={TOKENS.border} vertical={false} />
        <XAxis dataKey="nombre" tick={<TickColorModelo />} height={46} />
        <YAxis tick={{ fill: '#6B7099', fontSize: 10 }} unit=" ms" />
        <Tooltip content={(p: any) => <TooltipEstrella {...p} labelMejor="Generación de imagen más rápida" />} />
        <Bar dataKey="latencia" name="Latencia (ms)" radius={[4, 4, 0, 0]}
             label={etiquetaEstrella(mejorIdx, COLORES[datos[mejorIdx].proveedor])}>
          {datosConFlag.map((d) => (
            <Cell key={d.proveedor} fill={COLORES[d.proveedor]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

/* ── Tabla resumen: tarifas oficiales vigentes (texto + imagen) ──────────── */

// Modelos exactos invocados por cada cliente segun la columna. Las 3
// columnas de texto (entrada/salida/cacheado) usan el mismo modelo de
// texto del proveedor; imagen generar / editar usan modelos distintos.
const MODELOS_POR_PROVEEDOR: Record<LLMProvider, {
  texto: string | null
  imagenGenerar: string | null
  imagenEditar: string | null
}> = {
  claude: { texto: 'claude-sonnet-4-6', imagenGenerar: null,                       imagenEditar: null                          },
  openai: { texto: 'gpt-4o',            imagenGenerar: 'gpt-image-1 (medium)',     imagenEditar: 'gpt-image-1 (medium)'        },
  gemini: { texto: 'gemini-2.5-flash',  imagenGenerar: 'gemini-2.5-flash-image',   imagenEditar: 'gemini-2.5-flash-image'      },
  grok:   { texto: 'grok-4.3',          imagenGenerar: 'grok-imagine-image',       imagenEditar: 'grok-imagine-image-quality'  },
}

function TablaCostesVigentes({ tarifas }: { tarifas: TarifaDTO[] }) {
  const filas = [...tarifas].sort((a, b) => a.proveedor.localeCompare(b.proveedor))
  const fmt = (v: number | string | null | undefined) => {
    if (v == null) return '—'
    const n = typeof v === 'string' ? parseFloat(v) : v
    if (!Number.isFinite(n)) return '—'
    // 8 decimales y recorte de ceros sobrantes (incluido el punto si queda
    // pelado): 3.00000000 -> "3", 0.04000000 -> "0.04", 0.039 -> "0.039".
    return `$${n.toFixed(8).replace(/\.?0+$/, '')}`
  }
  // Celda con chip del modelo (color + contorno del proveedor) sobre el precio.
  const celda = (
    modelo: string | null,
    valor: number | string | null | undefined,
    color: string,
  ) => (
    <div className="leading-tight flex flex-col items-end gap-1">
      {modelo && (
        <span
          className="text-[11px] font-medium px-1.5 py-0.5 rounded whitespace-nowrap"
          style={{
            color,
            background: `${color}15`,
            border: `1px solid ${color}40`,
          }}
        >
          {modelo}
        </span>
      )}
      <span className="font-mono">{fmt(valor)}</span>
    </div>
  )
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs min-w-[1080px]">
        <thead>
          <tr className="text-[10px] uppercase tracking-wide text-muted border-b border-border">
            <th className="text-left  py-2 px-2">Proveedor</th>
            <th className="text-right py-2 px-2">Entrada $/Millon de tokens</th>
            <th className="text-right py-2 px-2">Salida $/Millon de tokens</th>
            <th className="text-right py-2 px-2">Cacheado $/Millon de tokens</th>
            <th className="text-right py-2 px-2">Img gen $/img</th>
            <th className="text-right py-2 px-2">Img edit $/img</th>
            <th className="text-right py-2 px-2">Rel. ent.</th>
            <th className="text-right py-2 px-2">Rel. sal.</th>
          </tr>
        </thead>
        <tbody>
          {filas.map((t) => {
            const m = MODELOS_POR_PROVEEDOR[t.proveedor]
            const c = COLORES[t.proveedor]
            return (
              <tr key={t.proveedor} className="border-b border-border hover:bg-primary-l/30">
                <td className="py-2 px-2">
                  <span className="text-[11px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full whitespace-nowrap"
                        style={{
                          color:      c,
                          background: `${c}20`,
                          border:     `1px solid ${c}50`,
                        }}>
                    {NOMBRES[t.proveedor]}
                  </span>
                </td>
                <td className="py-2 px-2 text-right">{celda(m.texto,         t.precio_entrada_usd_por_mtoken,          c)}</td>
                <td className="py-2 px-2 text-right">{celda(m.texto,         t.precio_salida_usd_por_mtoken,           c)}</td>
                <td className="py-2 px-2 text-right">{celda(m.texto,         t.precio_entrada_cacheado_usd_por_mtoken, c)}</td>
                <td className="py-2 px-2 text-right">{celda(m.imagenGenerar, t.precio_imagen_generar_usd_por_imagen,   c)}</td>
                <td className="py-2 px-2 text-right">{celda(m.imagenEditar,  t.precio_imagen_editar_usd_por_imagen,    c)}</td>
                <td className="py-2 px-2 text-right font-mono">{t.coste_relativo_entrada.toFixed(1)}x</td>
                <td className="py-2 px-2 text-right font-mono">{t.coste_relativo_salida.toFixed(1)}x</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

/* ── Barras: valoracion media por modelo — evaluaciones de generacion de imagen ── */
function GraficoImagenRating({ ratings }: { ratings: RespuestaStats['ratings_imagen_generativa'] }) {
  const datos = ratings
    .filter((r) => r.proveedor !== 'claude' && r.rating_medio != null)
    .map((r) => ({
      nombre:    NOMBRES[r.proveedor],
      rating:    +(r.rating_medio!).toFixed(2),
      proveedor: r.proveedor,
    }))
    .sort((a, b) => b.rating - a.rating)

  if (datos.length === 0) {
    return (
      <p className="text-xs text-muted italic text-center py-8">
        Sin valoraciones de imagen todavía. Completa evaluaciones de generación de imagen.
      </p>
    )
  }

  const mejorIdx     = datos.reduce((bi, d, i) => d.rating > datos[bi].rating ? i : bi, 0)
  const datosConFlag = datos.map((d, i) => ({ ...d, esMejor: i === mejorIdx }))

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={datosConFlag} margin={{ top: 44, right: 10, bottom: 10, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={TOKENS.border} vertical={false} />
        <XAxis dataKey="nombre" tick={<TickColorModelo />} height={46} />
        <YAxis domain={[0, 5]} tick={{ fill: '#6B7099', fontSize: 10 }} />
        <Tooltip content={(p: any) => <TooltipEstrella {...p} labelMejor="Modelo mejor valorado en la categoría de imágenes" />} />
        <Bar dataKey="rating" name="Valoración" radius={[4, 4, 0, 0]}
             label={etiquetaEstrella(mejorIdx, COLORES[datos[mejorIdx].proveedor])}>
          {datosConFlag.map((d) => (
            <Cell key={d.proveedor} fill={COLORES[d.proveedor]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}


/* ── Barras: ranking medio de preferencia en imagen ──────────────────────── */
function GraficoImagenRanking({ ranking }: { ranking: RespuestaStats['ranking_imagen_generativa'] }) {
  const datos = ranking
    .filter((r) => r.proveedor !== 'claude' && r.rango_medio != null)
    .map((r) => ({
      nombre:    NOMBRES[r.proveedor],
      rango:     +(r.rango_medio!).toFixed(2),
      proveedor: r.proveedor,
    }))
    .sort((a, b) => b.rango - a.rango)

  if (datos.length === 0) {
    return (
      <p className="text-xs text-muted italic text-center py-8">
        Sin datos de ranking de imagen todavía. Completa evaluaciones de generación de imagen con la sección de preferencia.
      </p>
    )
  }

  const mejorIdx     = datos.reduce((bi, d, i) => d.rango < datos[bi].rango ? i : bi, 0)
  const datosConFlag = datos.map((d, i) => ({ ...d, esMejor: i === mejorIdx }))

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={datosConFlag} margin={{ top: 44, right: 10, bottom: 10, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={TOKENS.border} vertical={false} />
        <XAxis dataKey="nombre" tick={<TickColorModelo />} height={46} />
        <YAxis
          domain={[0, 3.5]}
          tick={{ fill: '#6B7099', fontSize: 10 }}
          tickFormatter={(v: number) => `#${v.toFixed(0)}`}
        />
        <Tooltip content={(p: any) => <TooltipEstrella {...p} labelMejor="Modelo más preferido en imágenes" />} />
        <Bar dataKey="rango" name="Rango medio" radius={[4, 4, 0, 0]}
             label={etiquetaEstrella(mejorIdx, COLORES[datos[mejorIdx].proveedor])}>
          {datosConFlag.map((d) => (
            <Cell key={d.proveedor} fill={COLORES[d.proveedor]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}


/* ── Imagen por subcategoria: toggle valoracion/ranking por modelo ───────── */
/* Misma idea que GraficoTokensIdioma (toggle interno) pero para las metricas
 * humanas de una opcion de imagen concreta (generar/describir/logotipo/modificar).
 * Filtra las filas a esa subcategoria y muestra valoracion media (mayor mejor)
 * o ranking de preferencia (menor mejor) por modelo. */
function GraficoImagenSubcatHumana({
  filas, subcategoria,
}: {
  filas: RespuestaStats['metricas_humanas_imagen_subcategoria']
  subcategoria: 'generar' | 'describir' | 'logotipo' | 'modificar'
}) {
  const [metrica, setMetrica] = useState<'valoracion' | 'ranking'>('valoracion')
  const esRating = metrica === 'valoracion'

  const datos = filas
    .filter((f) => f.subcategoria === subcategoria)
    .filter((f) => (esRating ? f.rating_medio != null : f.rango_medio != null))
    .map((f) => ({
      nombre:    NOMBRES[f.proveedor],
      valor:     +((esRating ? f.rating_medio! : f.rango_medio!)).toFixed(2),
      proveedor: f.proveedor,
    }))
    .sort((a, b) => b.valor - a.valor)

  const mejorIdx = datos.length === 0 ? 0 : datos.reduce(
    (bi, d, i) => ((esRating ? d.valor > datos[bi].valor : d.valor < datos[bi].valor) ? i : bi), 0)
  const datosConFlag = datos.map((d, i) => ({ ...d, esMejor: i === mejorIdx }))

  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-2 justify-center flex-wrap">
        {([['valoracion', 'Valoración media'], ['ranking', 'Ranking de preferencia']] as const).map(([m, txt]) => {
          const activo = metrica === m
          return (
            <button
              key={m}
              type="button"
              onClick={() => setMetrica(m)}
              className="text-[10px] font-bold uppercase tracking-wider px-3 py-1.5 rounded-md border-2 transition-all duration-150 cursor-pointer"
              style={{
                color: activo ? '#0F0F1C' : TOKENS.textAlt,
                background: activo ? TOKENS.textAlt : 'rgba(157,78,221,0.10)',
                borderColor: TOKENS.textAlt,
                boxShadow: activo
                  ? '0 0 12px rgba(245,245,240,0.55), 0 2px 6px rgba(0,0,0,0.45)'
                  : '0 0 4px rgba(245,245,240,0.20)',
              }}
            >
              {txt}
            </button>
          )
        })}
      </div>

      {datos.length === 0 ? (
        <p className="text-xs text-muted italic text-center py-8">
          Sin datos de {esRating ? 'valoración' : 'ranking'} para esta opción todavía.
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={datosConFlag} margin={{ top: 44, right: 10, bottom: 10, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={TOKENS.border} vertical={false} />
            <XAxis dataKey="nombre" tick={<TickColorModelo />} height={46} />
            <YAxis
              domain={esRating ? [0, 5] : [0, 4.5]}
              tick={{ fill: '#6B7099', fontSize: 10 }}
              tickFormatter={esRating ? undefined : (v: number) => `#${v.toFixed(0)}`}
            />
            <Tooltip content={(p: any) => (
              <TooltipEstrella {...p} labelMejor={esRating ? 'Modelo mejor valorado' : 'Modelo más preferido'} />
            )} />
            <Bar dataKey="valor" name={esRating ? 'Valoración' : 'Rango medio'} radius={[4, 4, 0, 0]}
                 label={etiquetaEstrella(mejorIdx, COLORES[datos[mejorIdx].proveedor])}>
              {datosConFlag.map((d) => (
                <Cell key={d.proveedor} fill={COLORES[d.proveedor]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}


/* ── Barras: tasa de rechazo por politica de seguridad ───────────────────── */
function GraficoRestrictividad({ tasas }: { tasas: TasaRechazo[] }) {
  const tasasFiltradas = tasas.filter((t) => t.proveedor !== 'claude')

  if (tasasFiltradas.length === 0) {
    return (
      <p className="text-xs text-muted italic text-center py-8">
        Sin datos de evaluaciones de imagen todavía.
      </p>
    )
  }

  const datos = tasasFiltradas.map((t) => ({
    nombre:     NOMBRES[t.proveedor],
    tasa:       +(t.tasa * 100).toFixed(1),
    rechazos:   t.total_rechazos,
    total:      t.total_participaciones,
    proveedor:  t.proveedor,
  })).sort((a, b) => b.tasa - a.tasa)

  const masRestrictivo = datos[0]?.proveedor
  // El mas laxo es el que menos rechazos tiene (ultimo tras ordenar descendente)
  const masLaxoIdx = datos.length - 1

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={datos} margin={{ top: 44, right: 10, bottom: 10, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={TOKENS.border} vertical={false} />
        <XAxis dataKey="nombre" tick={<TickColorModelo />} height={46} />
        <YAxis tick={{ fill: '#6B7099', fontSize: 10 }} unit=" %" domain={[0, 100]} />
        <Tooltip
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null
            const d = payload[0].payload as typeof datos[0]
            return (
              <div className="card px-3 py-2 text-xs space-y-0.5">
                <p className="font-bold" style={{ color: COLORES[d.proveedor] }}>
                  {NOMBRES[d.proveedor]}
                  {d.proveedor === masRestrictivo && d.tasa > 0 && (
                    <span className="ml-2 text-red-400 font-normal">▲ Más restrictivo</span>
                  )}
                </p>
                <p className="text-muted">Tasa: <span className="text-text font-mono">{d.tasa} %</span></p>
                <p className="text-muted">Rechazos: <span className="text-text font-mono">{d.rechazos} / {d.total}</span></p>
                {d.proveedor === datos[masLaxoIdx]?.proveedor && (
                  <p className="text-yellow-400 font-semibold mt-1">★ Más laxo en políticas</p>
                )}
              </div>
            )
          }}
        />
        <Bar dataKey="tasa" name="Tasa de rechazo (%)" radius={[4, 4, 0, 0]}
             label={etiquetaEstrella(masLaxoIdx, COLORES[datos[masLaxoIdx]?.proveedor])}>
          {datos.map((d) => (
            <Cell key={d.proveedor} fill={COLORES[d.proveedor]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

/* ── Barras agrupadas ES vs EN del sub-experimento bilingue (ADR-029) ─────
 *
 * Renderiza cuatro mini-graficos, uno por metrica tecnica comparable entre
 * idiomas (latencia, velocidad, coste, longitud). Cada mini-grafico tiene
 * los 4 proveedores en el eje X y dos barras por proveedor: la ES con el
 * color saturado del LLM y la EN con el mismo color difuminado al 35 %.
 *
 * El componente espera datos preagrupados por (proveedor, idioma) tal y como
 * los devuelve LLMResponseRepository.medias_comparativa_es_en(). Si la lista
 * llega vacia, el grafico no se renderiza (la tarjeta padre ya lo oculta).
 */
function GraficoComparativaIdioma({
  filas, metrica, unidad, formato, mejorEs = 'min',
}: {
  filas: MetricasComparativaIdioma[]
  metrica: keyof Pick<
    MetricasComparativaIdioma,
    'latencia_ms' | 'tokens_por_segundo' | 'cost_usd' | 'palabras' | 'coste_por_100_palabras' | 'tokens_entrada' | 'tokens_salida'
  >
  unidad?: string
  formato?: (v: number) => string
  /**
   * Direccion "favorable para ES":
   * - 'min': lo bueno es que ES sea MAS PEQUENO que EN (latencia, costes, tokens)
   * - 'max': lo bueno es que ES sea MAS GRANDE que EN (velocidad tok/s)
   * Determina si el badge por proveedor lleva borde verde (favorable) o rojo
   * (desfavorable) cuando se compara ES con EN.
   */
  mejorEs?: 'min' | 'max'
}) {
  // Metricas monetarias usan 8 decimales (coherente con NUMERIC(12,8) de la BD
  // y con el resto del dashboard). Las demas con 2 decimales basta.
  const esMetricaMonetaria = metrica === 'cost_usd' || metrica === 'coste_por_100_palabras'
  const datos = PROVEEDORES.map((p) => {
    const filaEs = filas.find((f) => f.proveedor === p && f.idioma_prompt === 'es')
    const filaEn = filas.find((f) => f.proveedor === p && f.idioma_prompt === 'en')
    return {
      nombre: NOMBRES[p],
      proveedor: p,
      es: filaEs ? +Number(filaEs[metrica]).toFixed(esMetricaMonetaria ? 8 : 2) : 0,
      en: filaEn ? +Number(filaEn[metrica]).toFixed(esMetricaMonetaria ? 8 : 2) : 0,
    }
  })

  // Badges con el % de diferencia EN vs ES por proveedor.
  // Signo positivo = EN es mayor que ES; negativo = EN es menor.
  // Verde si ES sale favorecido (segun mejorEs); rojo en caso contrario;
  // gris si los dos valores son iguales o si falta uno de los dos.
  const diffs = datos.map((d) => {
    if (d.es === 0 || d.en === 0) return { ...d, pct: null as number | null, color: '#6B7099' }
    const pct = ((d.en - d.es) / d.es) * 100
    // Si mejorEs='min' (menor=mejor), ES es favorable cuando es MAS PEQUENO,
    // es decir cuando d.es < d.en, que equivale a pct > 0 (EN mayor que ES).
    // Si mejorEs='max' (mayor=mejor), ES es favorable cuando d.es > d.en,
    // es decir pct < 0 (EN menor que ES).
    const favorableEs = mejorEs === 'min' ? pct > 0 : pct < 0
    const igual = Math.abs(pct) < 0.05
    const color = igual ? '#6B7099' : favorableEs ? '#10D9A0' : '#EF4444'
    return { ...d, pct, color }
  })

  return (
    <div className="flex flex-col gap-2">
      {/* Fila de badges por proveedor con el % de variacion EN respecto a ES.
          Borde verde si ES sale favorable (mas barato / mas rapido segun la
          metrica); rojo si EN gana; gris si no hay datos suficientes. El
          numero siempre representa "cuanto cambia EN respecto a ES":
          +10 % = EN consume / cuesta / tarda 10 % mas que ES. */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 px-1">
        {diffs.map((d) => (
          <div
            key={d.proveedor}
            className="flex flex-col items-center justify-center rounded-md py-1 px-1.5 text-center"
            style={{
              border: `2px solid ${d.color}`,
              background: `${d.color}10`,
              boxShadow: d.pct !== null && Math.abs(d.pct) >= 0.05
                ? `0 0 8px ${d.color}55`
                : undefined,
            }}
            title={
              d.pct === null
                ? 'Sin datos para comparar'
                : d.color === '#10D9A0'
                  ? 'ES es favorable frente a EN para esta metrica'
                  : d.color === '#EF4444'
                    ? 'EN es favorable frente a ES para esta metrica'
                    : 'ES y EN dan practicamente el mismo valor'
            }
          >
            <span className="text-[9px] font-bold uppercase tracking-wider leading-none"
                  style={{ color: COLORES[d.proveedor] }}>
              {NOMBRES[d.proveedor]}
            </span>
            <span className="text-[12px] font-mono font-bold leading-tight mt-0.5" style={{ color: d.color }}>
              {d.pct === null
                ? '—'
                : `${d.pct > 0 ? '+' : ''}${d.pct.toFixed(1)} %`}
            </span>
          </div>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={datos} margin={{ top: 18, right: 10, bottom: 10, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={TOKENS.border} vertical={false} />
          <XAxis dataKey="nombre" tick={<TickColorModelo />} height={46} />
          <YAxis
            tick={{ fill: '#6B7099', fontSize: 10 }}
            unit={unidad}
            tickFormatter={formato as any}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const d = payload[0].payload as typeof datos[0]
              const fmt = formato ?? ((v: number) => String(v))
              return (
                <div className="card px-3 py-2 text-xs space-y-0.5">
                  <p className="font-bold" style={{ color: COLORES[d.proveedor] }}>
                    {NOMBRES[d.proveedor]}
                  </p>
                  <p className="text-muted">
                    ES: <span className="text-text font-mono">{fmt(d.es)}{unidad ?? ''}</span>
                  </p>
                  <p className="text-muted">
                    EN: <span className="text-text font-mono">{fmt(d.en)}{unidad ?? ''}</span>
                  </p>
                  {d.es > 0 && (
                    <p className="text-muted">
                      Diferencia: <span className="text-text font-mono">
                        {(((d.en - d.es) / d.es) * 100).toFixed(1)} %
                      </span>
                    </p>
                  )}
                </div>
              )
            }}
          />
          <Legend iconSize={8} wrapperStyle={{ fontSize: 10 }} />
          <Bar dataKey="es" name="Castellano" radius={[2, 2, 0, 0]}>
            {datos.map((d) => <Cell key={d.proveedor} fill={COLORES[d.proveedor]} />)}
          </Bar>
          <Bar dataKey="en" name="Inglés" radius={[2, 2, 0, 0]}>
            {datos.map((d) => <Cell key={d.proveedor} fill={COLORES[d.proveedor]} fillOpacity={0.35} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

/* ── Tokens entrada o salida, ES vs EN, con toggle (ADR-029) ──────────────
 *
 * Renderiza una sola metrica (tokens_entrada o tokens_salida) en barras
 * agrupadas ES vs EN. El usuario alterna entre las dos vistas mediante dos
 * botones encima del grafico. Por defecto se muestra ENTRADA, porque es la
 * que representa el coste fijo del prompt (ahi es donde el cambio de idioma
 * mas se nota); SALIDA depende de cuanto decida generar el modelo.
 *
 * Apilar las dos metricas en una unica vista resultaba ilegible con 4
 * barras (ES entrada, ES salida, EN entrada, EN salida) por proveedor; el
 * toggle deja siempre 2 barras claras por proveedor.
 */
function GraficoTokensIdioma({ filas }: { filas: MetricasComparativaIdioma[] }) {
  const [tipo, setTipo] = useState<'entrada' | 'salida'>('entrada')
  const metrica = tipo === 'entrada' ? 'tokens_entrada' : 'tokens_salida'

  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-2 justify-center flex-wrap">
        {(['entrada', 'salida'] as const).map((t) => {
          const activo = tipo === t
          return (
            <button
              key={t}
              type="button"
              onClick={() => setTipo(t)}
              className="text-[10px] font-bold uppercase tracking-wider px-3 py-1.5 rounded-md border-2 transition-all duration-150 cursor-pointer"
              style={{
                color: activo ? '#0F0F1C' : TOKENS.textAlt,
                background: activo ? TOKENS.textAlt : 'rgba(157,78,221,0.10)',
                borderColor: TOKENS.textAlt,
                boxShadow: activo
                  ? '0 0 12px rgba(245,245,240,0.55), 0 2px 6px rgba(0,0,0,0.45)'
                  : '0 0 4px rgba(245,245,240,0.20)',
              }}
            >
              Mostrar tokens {t}
            </button>
          )
        })}
      </div>
      <GraficoComparativaIdioma
        filas={filas}
        metrica={metrica}
        formato={(v) => v.toFixed(0)}
      />
    </div>
  )
}

/* ── Datos para el modal de leyenda ─────────────────────────────────────── */
const VARIABLES_HUMANA = [
  { nombre: 'Valoración (1–5 ★)',      desc: 'Puntuación asignada por el usuario con estrellas a cada respuesta del modelo.' },
  { nombre: 'Ranking de preferencia',  desc: 'Posición ordinal (1.º, 2.º…) establecida por el usuario mediante drag-and-drop. Menor valor = más preferido.' },
  { nombre: 'Valoración media',        desc: 'Media aritmética de todas las valoraciones recibidas por un modelo en una categoría o en el global.' },
  { nombre: 'Ranking medio',           desc: 'Media de las posiciones ordinales asignadas. Barras más bajas en el gráfico indican mayor preferencia.' },
  { nombre: 'Heatmap modelo × categoría', desc: 'Cruce de la valoración media por modelo y categoría para detectar fortalezas y debilidades específicas.' },
]

const VARIABLES_AUTOMATICA = [
  { nombre: 'Latencia (ms)',           desc: 'Tiempo transcurrido desde el envío del prompt hasta recibir la respuesta completa del modelo.' },
  { nombre: 'Tokens de entrada',       desc: 'Número de tokens del prompt enviado al modelo. Influye directamente en el coste.' },
  { nombre: 'Tokens de salida',        desc: 'Número de tokens generados en la respuesta. Determina la longitud y parte del coste.' },
  { nombre: 'Velocidad (tok/s)',       desc: 'Tokens generados por segundo (tokens_salida / latencia). Mayor valor indica mayor rapidez.' },
  { nombre: 'Coste estimado (USD)',    desc: 'Coste calculado según el pricing público de cada proveedor aplicado a los tokens de entrada y salida.' },
  { nombre: 'Longitud (palabras)',     desc: 'Número de palabras en la respuesta. Permite comparar la extensión típica de cada modelo.' },
  { nombre: 'Diversidad léxica (TTR)', desc: 'Ratio Type-Token: porcentaje de palabras únicas sobre el total. Mayor valor = vocabulario más variado.' },
  { nombre: 'Similitud Jaccard',       desc: 'Índice de Jaccard sobre bigramas entre pares de modelos. Mide cuánto se parecen sus respuestas (0 = totalmente distintas, 1 = idénticas).' },
  { nombre: 'Tasa de rechazo (%)',     desc: 'Porcentaje de prompts rechazados por la política de contenido del modelo. Solo relevante en generación de imagen.' },
  { nombre: 'Latencia imagen (ms)',    desc: 'Tiempo de generación de una imagen. Medido igual que la latencia de texto pero para el endpoint de imagen.' },
]

/* ── Modal de detalle de icono ───────────────────────────────────────────── */
function ModalIcono({ tipo, onClose }: { tipo: 'humana' | 'automatica'; onClose: () => void }) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  const esHumana  = tipo === 'humana'
  const variables = esHumana ? VARIABLES_HUMANA : VARIABLES_AUTOMATICA
  const titulo    = esHumana ? 'Datos de evaluaciones de usuarios' : 'Métricas automáticas'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
         style={{ background: 'rgba(0,0,0,0.7)' }}
         onClick={onClose}>
      <div className="relative w-full max-w-md rounded-card border border-border shadow-card-lg overflow-hidden bg-surface"
           onClick={(e) => e.stopPropagation()}>

        {/* Cabecera */}
        <div className="flex items-center gap-4 px-5 py-4 border-b border-border">
          {esHumana ? (
            <svg width="64" height="64" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" className="flex-shrink-0">
              <rect x="0" y="0" width="16" height="16" rx="3" fill="#FFFFFF"/>
              <path d="M1 16 L1 10 L4.5 13 L8 7.5 L11.5 13 L15 10 L15 16 Z" fill="#1A1A2E"/>
              <rect x="6.5" y="9" width="3" height="2.5" fill="#F0DEC8"/>
              <ellipse cx="8" cy="6" rx="4" ry="4.5" fill="#F0DEC8"/>
              <path d="M4 4.5 Q4 0.5 8 1 Q12 0.5 12 4.5 Q10 2.5 8 3.5 Q6 2.5 4 4.5 Z" fill="#1A1A2E"/>
              <ellipse cx="6.2" cy="5.8" rx="0.9" ry="0.8" fill="#DC2626"/>
              <ellipse cx="9.8" cy="5.8" rx="0.9" ry="0.8" fill="#DC2626"/>
              <path d="M5.5 8 Q8 9 10.5 8" stroke="#A0747A" strokeWidth="0.6" fill="none" strokeLinecap="round"/>
              <line x1="7" y1="8" x2="7" y2="9.1" stroke="#FFFFFF" strokeWidth="0.8" strokeLinecap="round"/>
              <line x1="9" y1="8" x2="9" y2="9.1" stroke="#FFFFFF" strokeWidth="0.8" strokeLinecap="round"/>
            </svg>
          ) : (
            <svg width="64" height="64" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" className="flex-shrink-0">
              <line x1="8" y1="0.5" x2="8" y2="2.5" stroke="#ADADAD" strokeWidth="1.1" strokeLinecap="round"/>
              <circle cx="8" cy="0.7" r="0.9" fill="#D0D0D0"/>
              <rect x="1.5" y="2.5" width="13" height="12" rx="2.5" fill="#B8B8B8"/>
              <rect x="1.5" y="2.5" width="13" height="5" rx="2.5" fill="#D2D2D2"/>
              <rect x="2.5" y="6" width="11" height="3.5" rx="1" fill="#111827"/>
              <circle cx="6"  cy="7.75" r="1.1" fill="#FBBF24"/>
              <circle cx="10" cy="7.75" r="1.1" fill="#FBBF24"/>
              <path d="M4.5 12 Q8 14.5 11.5 12" stroke="#777" strokeWidth="1" fill="none" strokeLinecap="round"/>
            </svg>
          )}
          <div className="min-w-0">
            <p className="text-sm font-semibold">{titulo}</p>
            <p className="text-xs text-muted mt-0.5">
              {esHumana ? 'Variables aportadas por los evaluadores' : 'Variables calculadas automáticamente por el sistema'}
            </p>
          </div>
          <button onClick={onClose}
                  className="ml-auto text-muted hover:text-text transition-colors text-lg leading-none flex-shrink-0">
            ✕
          </button>
        </div>

        {/* Lista de variables */}
        <div className="px-5 py-4 space-y-3 max-h-[60vh] overflow-y-auto">
          {variables.map((v) => (
            <div key={v.nombre} className="flex gap-2.5">
              <span className="text-primary mt-0.5 flex-shrink-0">▸</span>
              <div>
                <span className="text-xs font-semibold text-text">{v.nombre}</span>
                <span className="text-xs text-muted"> — {v.desc}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

/* ── Pagina principal ────────────────────────────────────────────────────── */
export default function DashboardPage() {
  const [modalIcono, setModalIcono] = useState<'humana' | 'automatica' | null>(null)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['stats'],
    queryFn: obtenerStats,
    staleTime: 30_000,
    retry: 1,
  })

  if (isLoading) {
    return (
      <div className="max-w-[1200px] mx-auto space-y-4">
        <div className="card px-4 py-3 text-sm text-muted animate-pulse">Cargando estadísticas…</div>
        <div className="grid grid-cols-4 gap-4">
          {[0,1,2,3].map((i) => (
            <div key={i} className="card h-24 animate-pulse bg-surface" />
          ))}
        </div>
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="max-w-[1200px] mx-auto">
        <div className="card px-5 py-4 text-sm text-red-400 text-center">
          No se pudo cargar el dashboard. Comprueba que el backend esta activo.
        </div>
      </div>
    )
  }

  if (data.metricas_por_modelo.length === 0) {
    return (
      <div className="max-w-[1200px] mx-auto">
        <div className="card flex flex-col items-center justify-center py-20 gap-4 text-center">
          <span style={{ fontSize: 72, lineHeight: 1 }}>📊</span>
          <p className="text-lg font-semibold text-text">Sin datos todavía</p>
          <p className="text-sm text-muted leading-relaxed max-w-sm">
            El estudio no tiene ninguna evaluación completada.
            Ejecuta la primera comparativa para empezar a ver resultados en el dashboard.
          </p>
          <Link to="/benchmark" className="btn-primary mt-2">
            Crear primera valoración
          </Link>
        </div>
      </div>
    )
  }

  const pctPuntuadas = data.total_evaluaciones > 0
    ? Math.round((data.evaluaciones_puntuadas / data.total_evaluaciones) * 100)
    : 0

  const catMasUsada = Object.entries(data.evaluaciones_por_categoria)
    .sort((a, b) => b[1] - a[1])[0]?.[0] ?? '—'

  return (
    <>
    <div className="max-w-[1200px] mx-auto space-y-6">

      {/* Leyenda de iconos */}
      <div className="flex items-center gap-6 px-4 py-2.5 rounded-xl border border-border text-xs text-muted"
           style={{ background: TOKENS.depth, overflow: 'visible' }}>
        <span className="font-semibold uppercase tracking-widest text-[10px]">Leyenda</span>
        <button className="relative flex items-center gap-2 select-none group px-3 py-2 rounded-xl transition-all duration-150"
                style={{ background: 'rgba(157,78,221,0.10)', border: '1.5px solid rgba(255,255,255,0.75)', cursor: 'pointer', boxShadow: '0 0 8px rgba(255,255,255,0.25), 0 0 18px rgba(157,78,221,0.3)' }}
                onMouseEnter={(e) => { const b = e.currentTarget as HTMLButtonElement; b.style.background = 'rgba(157,78,221,0.22)'; b.style.borderColor = 'rgba(255,255,255,1)'; b.style.boxShadow = '0 0 12px rgba(255,255,255,0.5), 0 0 28px rgba(157,78,221,0.55)' }}
                onMouseLeave={(e) => { const b = e.currentTarget as HTMLButtonElement; b.style.background = 'rgba(157,78,221,0.10)'; b.style.borderColor = 'rgba(255,255,255,0.75)'; b.style.boxShadow = '0 0 8px rgba(255,255,255,0.25), 0 0 18px rgba(157,78,221,0.3)' }}
                onClick={() => setModalIcono('humana')}>
          {/* Burbuja tooltip */}
          <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2.5 pointer-events-none
                          opacity-0 group-hover:opacity-100 transition-opacity duration-200 z-20">
            <div className="text-xs font-semibold whitespace-nowrap px-3 py-2 rounded-lg"
                 style={{ background: TOKENS.border, border: '1px solid rgba(157,78,221,0.6)', color: TOKENS.textLight }}>
              Hazme clic para ver el listado de las variables analizadas.
            </div>
            <div className="absolute left-1/2 -translate-x-1/2 -bottom-1.5"
                 style={{ width: 0, height: 0, borderLeft: '6px solid transparent',
                          borderRight: '6px solid transparent', borderTop: '6px solid rgba(157,78,221,0.5)' }} />
          </div>
          <svg width="32" height="32" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="0" y="0" width="16" height="16" rx="3" fill="#FFFFFF"/>
            <path d="M1 16 L1 10 L4.5 13 L8 7.5 L11.5 13 L15 10 L15 16 Z" fill="#1A1A2E"/>
            <rect x="6.5" y="9" width="3" height="2.5" fill="#F0DEC8"/>
            <ellipse cx="8" cy="6" rx="4" ry="4.5" fill="#F0DEC8"/>
            <path d="M4 4.5 Q4 0.5 8 1 Q12 0.5 12 4.5 Q10 2.5 8 3.5 Q6 2.5 4 4.5 Z" fill="#1A1A2E"/>
            <ellipse cx="6.2" cy="5.8" rx="0.9" ry="0.8" fill="#DC2626"/>
            <ellipse cx="9.8" cy="5.8" rx="0.9" ry="0.8" fill="#DC2626"/>
            <path d="M5.5 8 Q8 9 10.5 8" stroke="#A0747A" strokeWidth="0.6" fill="none" strokeLinecap="round"/>
            <line x1="7" y1="8" x2="7" y2="9.1" stroke="#FFFFFF" strokeWidth="0.8" strokeLinecap="round"/>
            <line x1="9" y1="8" x2="9" y2="9.1" stroke="#FFFFFF" strokeWidth="0.8" strokeLinecap="round"/>
          </svg>
          <span>Gráfico basado en <strong className="text-text">valoraciones de usuarios</strong></span>
        </button>
        <button className="relative flex items-center gap-2 select-none group px-3 py-2 rounded-xl transition-all duration-150"
                style={{ background: 'rgba(157,78,221,0.10)', border: '1.5px solid rgba(255,255,255,0.75)', cursor: 'pointer', boxShadow: '0 0 8px rgba(255,255,255,0.25), 0 0 18px rgba(157,78,221,0.3)' }}
                onMouseEnter={(e) => { const b = e.currentTarget as HTMLButtonElement; b.style.background = 'rgba(157,78,221,0.22)'; b.style.borderColor = 'rgba(255,255,255,1)'; b.style.boxShadow = '0 0 12px rgba(255,255,255,0.5), 0 0 28px rgba(157,78,221,0.55)' }}
                onMouseLeave={(e) => { const b = e.currentTarget as HTMLButtonElement; b.style.background = 'rgba(157,78,221,0.10)'; b.style.borderColor = 'rgba(255,255,255,0.75)'; b.style.boxShadow = '0 0 8px rgba(255,255,255,0.25), 0 0 18px rgba(157,78,221,0.3)' }}
                onClick={() => setModalIcono('automatica')}>
          {/* Burbuja tooltip */}
          <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2.5 pointer-events-none
                          opacity-0 group-hover:opacity-100 transition-opacity duration-200 z-20">
            <div className="text-xs font-semibold whitespace-nowrap px-3 py-2 rounded-lg"
                 style={{ background: TOKENS.border, border: '1px solid rgba(157,78,221,0.6)', color: TOKENS.textLight }}>
              Hazme clic para ver el listado de las variables analizadas.
            </div>
            <div className="absolute left-1/2 -translate-x-1/2 -bottom-1.5"
                 style={{ width: 0, height: 0, borderLeft: '6px solid transparent',
                          borderRight: '6px solid transparent', borderTop: '6px solid rgba(157,78,221,0.5)' }} />
          </div>
          <svg width="32" height="32" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <line x1="8" y1="0.5" x2="8" y2="2.5" stroke="#ADADAD" strokeWidth="1.1" strokeLinecap="round"/>
            <circle cx="8" cy="0.7" r="0.9" fill="#D0D0D0"/>
            <rect x="1.5" y="2.5" width="13" height="12" rx="2.5" fill="#B8B8B8"/>
            <rect x="1.5" y="2.5" width="13" height="5" rx="2.5" fill="#D2D2D2"/>
            <rect x="2.5" y="6" width="11" height="3.5" rx="1" fill="#111827"/>
            <circle cx="6"  cy="7.75" r="1.1" fill="#FBBF24"/>
            <circle cx="10" cy="7.75" r="1.1" fill="#FBBF24"/>
            <path d="M4.5 12 Q8 14.5 11.5 12" stroke="#777" strokeWidth="1" fill="none" strokeLinecap="round"/>
          </svg>
          <span>Gráfico basado en <strong className="text-text">métricas automáticas</strong></span>
        </button>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <KpiCard titulo="Evaluaciones totales" valor={data.total_evaluaciones}
                 sub={`${data.total_texto_vision} texto/visión · ${data.total_imagen_generativa} Generación de Imagen`} />
        <KpiCard titulo="Evaluadores únicos"   valor={data.total_evaluadores}    sub="nicks distintos" />
        <KpiCard titulo="Con puntuación"       valor={`${pctPuntuadas} %`}
                 color={pctPuntuadas < 50 ? '#FBBF24' : '#34D399'}
                 sub={`${data.evaluaciones_puntuadas} evaluaciones puntuadas`} />
        <KpiCard titulo="Categoría más usada"  valor={NOMBRE_CAT[catMasUsada] ?? catMasUsada} color="#34D399"
                 sub={`${data.evaluaciones_por_categoria[catMasUsada] ?? 0} evaluaciones`} />
      </div>

      {/* ── Tabla de tarifas vigentes (referencia de costes) ── */}
      {/* Titulo dinamico de la tabla de precios. La fecha sale de la fila
          mas reciente de tarifas_llm (actualizado_en MAX entre los items
          vigentes), asi el dashboard refleja siempre el ultimo cambio
          aprobado por el admin sin depender de fechas hardcoded. */}
      <SeccionTitulo
        label={(() => {
          const items = data.tarifas_vigentes.items
          if (items.length === 0) return 'Tarifa de precios vigentes'
          const ultima = items.reduce((max, t) =>
            new Date(t.actualizado_en) > new Date(max.actualizado_en) ? t : max,
          )
          // dd/mm/aaaa en local — formato natural para la audiencia espanola.
          const fecha = new Date(ultima.actualizado_en).toLocaleDateString('es-ES', {
            day: '2-digit', month: '2-digit', year: 'numeric',
          })
          return `Tarifa de precios vigentes a fecha ${fecha}`
        })()}
      />

      <TarjetaGrafico titulo="Tarifas oficiales vigentes — texto e imagen" fuente="humana" descargable={false}>
        <TablaCostesVigentes tarifas={data.tarifas_vigentes.items} />
        <p className="text-[9px] text-muted">
          Tabla en vivo desde <span className="font-mono">tarifas_llm</span> (auditoría 13/05/2026).
          Texto en USD por millón de tokens; imagen en USD por imagen 1024×1024.
          Rel. ent. y Rel. sal. = ratio frente al proveedor más barato de cada columna.
        </p>
      </TarjetaGrafico>

      {/* ── Separador: a partir de aqui el dashboard pasa de tarifas de
          referencia a las metricas agregadas de las evaluaciones reales. ── */}
      <SeccionTitulo label="Resultados totales agrupados" />

      {/* ── Bloque 1: evaluacion humana ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <TarjetaGrafico titulo="Scatter: latencia vs coste por comparación" fuente="automatica">
          <GraficoScatter metricas={data.metricas_por_modelo} />
          <p className="text-xs text-muted">
            Esquina inferior izquierda = rápido y barato.
            <span className="text-yellow-400 ml-1">★</span> modelo con mejor eficiencia relativa (distancia normalizada mínima al origen).
          </p>
        </TarjetaGrafico>

        <TarjetaGrafico titulo="Valoración media por modelo (1–5)" fuente="humana">
          <GraficoRating metricas={data.metricas_por_modelo} />
        </TarjetaGrafico>
      </div>

      <TarjetaGrafico titulo="Ranking de preferencia medio por modelo" fuente="humana">
        <GraficoRanking metricas={data.metricas_por_modelo} />
        <p className="text-xs text-muted">
          Posición ordinal media según el drag-and-drop del evaluador. #1 = modelo más preferido.
          Barras más bajas indican mayor preferencia.
        </p>
      </TarjetaGrafico>

      <TarjetaGrafico titulo="Heatmap valoración media · modelo × categoría" fuente="humana">
        <GraficoHeatmap celdas={data.heatmap} />
      </TarjetaGrafico>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <TarjetaGrafico titulo="Radar: perfil técnico normalizado" fuente="mixta">
          <GraficoRadar metricas={data.metricas_por_modelo} />
        </TarjetaGrafico>

        <TarjetaGrafico titulo="Distribución por categoría" fuente="humana">
          <GraficoDonut porCategoria={data.evaluaciones_por_categoria} />
        </TarjetaGrafico>
      </div>

      {/* ── Separador ── */}
      <SeccionTitulo label="Métricas automáticas — independientes del evaluador (solo sesiones de texto)" />

      {/* Selector lateral: una sola grafica visible. Por defecto se arranca
          en "Coste por 100 palabras" porque es la metrica mas comparativa
          entre modelos cuando se normaliza por volumen.
          El orden de las primeras 6 opciones coincide 1-a-1 con el selector
          de "Comparativa ES vs EN" para que las dos secciones queden
          visualmente alineadas. Jaccard cierra solo aqui (la comparativa
          bilingue no la incluye porque cruzar dos idiomas no aporta). */}
      <SelectorGraficos
        defaultId="coste_palabras"
        opciones={[
          {
            id: 'coste_palabras',
            label: 'Coste por 100 palabras',
            titulo: 'Coste por 100 palabras generadas',
            fuente: 'automatica',
            render: () => <GraficoCostePalabras metricas={data.metricas_por_modelo} />,
          },
          {
            id: 'latencia',
            label: 'Latencia media (ms)',
            titulo: 'Latencia media por modelo (ms)',
            fuente: 'automatica',
            render: () => <GraficoLatencia metricas={data.metricas_por_modelo} />,
          },
          {
            id: 'tokps',
            label: 'Velocidad (tok/s)',
            titulo: 'Velocidad de generación (tokens por segundo)',
            fuente: 'automatica',
            render: () => <GraficoTokPS metricas={data.metricas_por_modelo} />,
          },
          {
            id: 'coste_respuesta',
            label: 'Coste por respuesta',
            titulo: 'Coste medio por respuesta (USD)',
            fuente: 'automatica',
            render: () => <GraficoCosteRespuesta metricas={data.metricas_por_modelo} />,
          },
          {
            id: 'tokens',
            label: 'Tokens entrada / salida',
            titulo: 'Tokens de entrada y salida por modelo',
            fuente: 'automatica',
            render: () => (
              <>
                <GraficoTokens metricas={data.metricas_por_modelo} />
                <p className="text-[9px] text-muted">
                  Alterna entre tokens de entrada (volumen del prompt enviado) y de salida (longitud
                  que decide cada modelo). <span className="text-yellow-400">★</span> menor consumo
                  en la dimensión seleccionada.
                </p>
              </>
            ),
          },
          {
            id: 'longitud_diversidad',
            label: 'Longitud y diversidad léxica',
            titulo: 'Longitud media y diversidad léxica',
            fuente: 'automatica',
            render: () => (
              <>
                <GraficoLongitudDiversidad metricas={data.metricas_por_modelo} />
                <p className="text-[11px] text-muted leading-snug">
                  Barras = longitud media de la respuesta (palabras) ·
                  Línea amarilla = porcentaje de vocabulario único (TTR): a mayor valor, más variado el vocabulario del modelo.
                </p>
              </>
            ),
          },
          {
            id: 'jaccard',
            label: 'Similitud Jaccard',
            titulo: 'Matriz de similitud Jaccard entre modelos',
            fuente: 'automatica',
            render: () => <MatrizJaccard pares={data.jaccard} />,
          },
        ]}
      />

      {/* ── Tarjeta sub-experimento bilingue ES vs EN (ADR-029) ──
          Solo aparece cuando hay al menos un (proveedor, idioma=en) en la
          BD; en proyectos nuevos sin datos bilingues, la tarjeta se oculta
          completa para no dejar un grafico vacio en el dashboard. */}
      {data.comparativa_es_en.length > 0 && (
        <>
          <SeccionTitulo
            label={
              <>
                🌐 Métricas automáticas — Comparativa prompt Español(ES){' '}
                <span className="lowercase">vs</span> Inglés(EN)
              </>
            }
          />

          <div className="rounded-card px-4 py-3 text-sm space-y-2"
               style={{ background: 'rgba(157,78,221,0.08)', border: '1px solid rgba(157,78,221,0.28)' }}>
            <p className="text-[#C0BCDC] leading-snug text-xs">
              <span className="font-bold">Sub-experimento controlado:</span>{' '}
              en <strong>Razonamiento lógico</strong>, <strong>Escritura creativa</strong>,{' '}
              <strong>Preguntas concretas</strong> y <strong>Generación de código</strong> el prompt
              se envía a la vez en castellano y en su traducción inglesa validada. El usuario solo
              valora las respuestas en castellano; las inglesas alimentan esta comparativa de métricas automáticas.
            </p>
            <p className="text-[#C0BCDC] leading-snug text-xs flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="font-bold">Color del %:</span>
              <span className="inline-flex items-center gap-1.5">
                <span className="inline-block w-3 h-3 rounded-sm"
                      style={{ background: '#10D9A010', border: '2px solid #10D9A0' }} />
                <span>verde = ES sale favorable</span>
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="inline-block w-3 h-3 rounded-sm"
                      style={{ background: '#EF444410', border: '2px solid #EF4444' }} />
                <span>rojo = EN sale favorable</span>
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="inline-block w-3 h-3 rounded-sm"
                      style={{ background: '#6B709910', border: '2px solid #6B7099' }} />
                <span>gris = sin diferencia o sin datos</span>
              </span>
            </p>
          </div>

          {/* Mismo patron y mismo orden que el selector de "Metricas
              automaticas" para que las dos secciones queden alineadas fila
              a fila (excepto la ultima fila: aqui acaba en Longitud, alli
              acaba en Longitud + diversidad y luego Jaccard). */}
          <SelectorGraficos
            defaultId="coste_palabras_bilingue"
            opciones={[
              {
                id: 'coste_palabras_bilingue',
                label: 'Coste por 100 palabras',
                titulo: 'Coste por 100 palabras ES vs EN (USD)',
                fuente: 'automatica',
                render: () => (
                  <>
                    <GraficoComparativaIdioma
                      filas={data.comparativa_es_en}
                      metrica="coste_por_100_palabras"
                      formato={(v) => `$${v.toFixed(8)}`}
                    />
                    <p className="text-[10px] text-muted leading-snug">
                      Normalizacion por volumen: revela si un modelo es mas caro en uno de los dos idiomas
                      cuando se ajusta por la longitud real de la respuesta.
                    </p>
                  </>
                ),
              },
              {
                id: 'latencia_bilingue',
                label: 'Latencia media (ms)',
                titulo: 'Latencia media ES vs EN (ms)',
                fuente: 'automatica',
                render: () => (
                  <GraficoComparativaIdioma
                    filas={data.comparativa_es_en}
                    metrica="latencia_ms"
                    unidad=" ms"
                    formato={(v) => v.toFixed(0)}
                  />
                ),
              },
              {
                id: 'tokps_bilingue',
                label: 'Velocidad (tok/s)',
                titulo: 'Velocidad de generación ES vs EN (tok/s)',
                fuente: 'automatica',
                render: () => (
                  <GraficoComparativaIdioma
                    filas={data.comparativa_es_en}
                    metrica="tokens_por_segundo"
                    unidad=" t/s"
                    formato={(v) => v.toFixed(1)}
                    // En tok/s lo bueno para ES es ser MAS RAPIDO que EN,
                    // asi que invertimos la convencion 'min' por defecto.
                    mejorEs="max"
                  />
                ),
              },
              {
                id: 'coste_respuesta_bilingue',
                label: 'Coste por respuesta',
                titulo: 'Coste por respuesta ES vs EN (USD)',
                fuente: 'automatica',
                render: () => (
                  <GraficoComparativaIdioma
                    filas={data.comparativa_es_en}
                    metrica="cost_usd"
                    formato={(v) => `$${v.toFixed(8)}`}
                  />
                ),
              },
              {
                id: 'tokens_bilingue',
                label: 'Tokens entrada / salida',
                titulo: 'Tokens de entrada y salida por modelo ES vs EN',
                fuente: 'automatica',
                render: () => (
                  <>
                    <GraficoTokensIdioma filas={data.comparativa_es_en} />
                    <p className="text-[10px] text-muted leading-snug">
                      Alterna entre tokens de entrada (volumen del prompt traducido) y de salida (longitud
                      que decide cada modelo). Las dos barras de cada proveedor son ES y EN: comparar su
                      diferencia revela donde el cambio de idioma encarece o reduce la factura.
                    </p>
                  </>
                ),
              },
              {
                id: 'palabras_bilingue',
                label: 'Longitud (palabras)',
                titulo: 'Longitud de la respuesta ES vs EN (palabras)',
                fuente: 'automatica',
                render: () => (
                  <GraficoComparativaIdioma
                    filas={data.comparativa_es_en}
                    metrica="palabras"
                    formato={(v) => v.toFixed(0)}
                  />
                ),
              },
            ]}
          />
        </>
      )}

      {/* ── Bloque 3: generacion de imagenes (solo si hay datos) ── */}
      {data.metricas_imagen_por_modelo.length > 0 && (
        <>
          <SeccionTitulo label="Generación de imágenes — OpenAI · Gemini · Grok" />

          <div className="rounded-card px-4 py-3 text-sm"
               style={{ background: 'rgba(77,184,255,0.06)', border: '1px solid rgba(77,184,255,0.2)' }}>
            <p className="text-[#4DB8FF] leading-snug text-xs">
              <span className="font-bold">Solo modelos con soporte de generación de imagen:</span>{' '}
              Claude no genera ni edita imágenes en este estudio. Las métricas comparativas automáticas son la
              latencia y el coste por imagen. El coste se cobra a la tarifa vigente en la tabla de tarifas cuando
              se ejecuta cada llamada, distinguiendo entre generación (txt2img) y edición (img2img).
              Para consultar los precios exactos de cada modelo, ver la{' '}
              <span className="font-semibold">tabla &laquo;Tarifas oficiales vigentes&raquo;</span> al inicio del dashboard.
              El tamaño de archivo y las dimensiones se descartan porque la mayoría de proveedores devuelven URL
              externa y todos generan 1024×1024 por defecto, así que no aportan información diferencial.
              Se incluye además la valoración media por evaluador y la tasa de rechazo por política de contenido,
              relevante exclusivamente en imagen generativa.
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <TarjetaGrafico titulo="Latencia media de generación de imagen (ms)" fuente="automatica">
              <GraficoImagenLatencia metricas={data.metricas_imagen_por_modelo} />
            </TarjetaGrafico>

            <TarjetaGrafico titulo="Valoración media por modelo — evaluaciones de imagen (1–5)" fuente="humana">
              <GraficoImagenRating ratings={data.ratings_imagen_generativa} />
              <p className="text-[9px] text-muted">
                Media de las puntuaciones de todas las evaluaciones relacionadas con la categoría de imágenes.
              </p>
            </TarjetaGrafico>

            <TarjetaGrafico titulo="Ranking de preferencia medio por modelo — evaluaciones de imagen" fuente="humana">
              <GraficoImagenRanking ranking={data.ranking_imagen_generativa} />
              <p className="text-[9px] text-muted">
                Posición ordinal media (1.º = más preferido) al ordenar las imágenes de una misma
                evaluación. Menor es mejor. Comparada con la valoración, permite ver si el mejor
                posicionado en el ranking coincide con el mejor puntuado.
              </p>
            </TarjetaGrafico>

            <TarjetaGrafico titulo="Tasa de rechazo por política de contenido — imagen (%)" fuente="automatica">
              <div className="relative">
                {/* Fondo simbolico: senal de prohibicion difuminada, enviada al fondo (z-0)
                    para que se entienda de un vistazo que la grafica mide contenido bloqueado. */}
                <div aria-hidden className="pointer-events-none absolute inset-0 z-0 flex items-center justify-center overflow-hidden">
                  <svg viewBox="0 0 100 100" fill="none" stroke="#EF4444" strokeWidth="9"
                       className="h-56 w-56 opacity-[0.26] blur-[2px]">
                    <circle cx="50" cy="50" r="40" />
                    <line x1="21.7" y1="21.7" x2="78.3" y2="78.3" strokeLinecap="round" />
                  </svg>
                </div>
                {/* La grafica va por encima del fondo (z-10). */}
                <div className="relative z-10">
                  <GraficoRestrictividad tasas={data.tasa_rechazo} />
                </div>
              </div>
              <p className="text-[9px] text-muted">
                Porcentaje de evaluaciones de imagen (generar, logotipo, modificar) en las que cada modelo
                rechazó el prompt por su política de contenido. Estas evaluaciones quedan marcadas como
                fallidas y están excluidas de todas las demás métricas del dashboard.
                El denominador incluye evaluaciones de imagen completadas y fallidas.
              </p>
            </TarjetaGrafico>
          </div>

          <p className="text-xs text-muted">
            Detalle por tipo de imagen: elige una de las cuatro opciones y alterna entre valoración
            media y ranking de preferencia para ver si el modelo mejor posicionado en el ranking
            coincide con el mejor puntuado en cada tarea.
          </p>
          <SelectorGraficos
            defaultId="generar"
            horizontal
            opciones={[
              {
                id: 'generar', label: 'Generar imagen', fuente: 'humana',
                titulo: 'Imagen · Generar — valoración / ranking por modelo',
                render: () => (
                  <>
                    <GraficoImagenSubcatHumana
                      filas={data.metricas_humanas_imagen_subcategoria} subcategoria="generar" />
                    <p className="text-[9px] text-muted">
                      Imágenes creadas desde texto (txt2img). Tres proveedores (Claude excluido).
                    </p>
                  </>
                ),
              },
              {
                id: 'describir', label: 'Describir imagen', fuente: 'humana',
                titulo: 'Imagen · Describir — valoración / ranking por modelo',
                render: () => (
                  <>
                    <GraficoImagenSubcatHumana
                      filas={data.metricas_humanas_imagen_subcategoria} subcategoria="describir" />
                    <p className="text-[9px] text-muted">
                      Visión multimodal sobre una imagen subida. Incluye a Claude (los cuatro modelos).
                    </p>
                  </>
                ),
              },
              {
                id: 'logotipo', label: 'Logotipo', fuente: 'humana',
                titulo: 'Imagen · Logotipo — valoración / ranking por modelo',
                render: () => (
                  <>
                    <GraficoImagenSubcatHumana
                      filas={data.metricas_humanas_imagen_subcategoria} subcategoria="logotipo" />
                    <p className="text-[9px] text-muted">
                      Diseño de logotipo desde texto. Tres proveedores (Claude excluido).
                    </p>
                  </>
                ),
              },
              {
                id: 'modificar', label: 'Modificar imagen', fuente: 'humana',
                titulo: 'Imagen · Modificar — valoración / ranking por modelo',
                render: () => (
                  <>
                    <GraficoImagenSubcatHumana
                      filas={data.metricas_humanas_imagen_subcategoria} subcategoria="modificar" />
                    <p className="text-[9px] text-muted">
                      Edición de una imagen de referencia (img2img). Tres proveedores (Claude excluido).
                    </p>
                  </>
                ),
              },
            ]}
          />
        </>
      )}

    </div>

    {modalIcono && (
      <ModalIcono tipo={modalIcono} onClose={() => setModalIcono(null)} />
    )}
    </>
  )
}
