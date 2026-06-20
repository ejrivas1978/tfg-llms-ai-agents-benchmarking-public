/**
 * Componente: BenchmarkPage
 * Ruta:       frontend/src/pages/BenchmarkPage.tsx
 *
 * Descripcion:
 *   Pantalla principal de ejecucion de benchmarks.
 *   Vista "formulario": grid de categorias + prompt + chips LLM + enviar.
 *   Vista "resultados": respuestas de los 4 modelos + tabla AutoStats +
 *     seccion de evaluacion inline (estrellas + ranking DnD) + barra inferior.
 *
 *   Subcomponente AutoStats: tabla comparativa que lee los valores calculados
 *   por el backend (latencia_ms, tokens_por_segundo, cost_usd, etc.) y añade
 *   unicamente la comparacion cruzada entre proveedores (badges ganador/peor).
 *   No recalcula ningun metrica: toda la aritmetica viene en RespuestaLLM.
 *
 * Sprint: Sprint 3 — S3-05
 */

import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { DndContext, closestCenter, useSensor, useSensors, PointerSensor, TouchSensor, useDraggable, useDroppable, type DragEndEvent } from '@dnd-kit/core'
import { useHistorialStore } from '@/store/historialStore'
import { useUsuarioStore } from '@/store/usuarioStore'
import { useNickStore } from '@/store/nickStore'
import { useAdminStore } from '@/store/adminStore'
import BenchmarkCard from '@/components/benchmark/BenchmarkCard'
import StarRating from '@/components/evaluation/StarRating'
import BatLoader from '@/components/shared/BatLoader'
import SubcatPanel, { esCategoriaBilingue } from '@/components/benchmark/SubcatPanel'
import ConfirmModal from '@/components/shared/ConfirmModal'
import { ejecutarBenchmark } from '@/services/benchmarkApi'
import { crearEvaluacion } from '@/services/evaluacionApi'
import { solicitarMasTokens, marcarGuiaVista as marcarGuiaVistaApi } from '@/services/usuarioApi'
import type { SesionBenchmark, TestCategory, LLMProvider, RespuestaLLM } from '@/types/benchmark'
import type { PeticionEvaluacion } from '@/types/evaluacion'
import { LLM_PROVIDERS_CONFIG, PROVEEDORES_LIST } from '@/config/llmProviders'
import { TOKENS } from '@/utils/tokens'
import OnboardingGuide from '@/components/shared/OnboardingGuide'
import axios from 'axios'

/* ── Detector de rechazo por politica de seguridad ────────────────────── */
function esCensura(r: { tuvo_error: boolean; mensaje_error?: string | null }): boolean {
  if (!r.tuvo_error || !r.mensaje_error) return false
  const m = r.mensaje_error.toLowerCase()
  return m.includes('content_policy') || m.includes('politicas de seguridad') ||
         m.includes('filtros de seguridad') || m.includes('safety system')
}

/* ── Datos de categorias ───────────────────────────────────────────────── */
const CATEGORIAS_DATA = [
  { valor: 'razonamiento' as TestCategory, etiqueta: 'Razonamiento lógico',  desc: 'Problemas de lógica',         icon: '🧩', color: '#A855F7', colorL: '#1A0D2E' },
  { valor: 'codigo'       as TestCategory, etiqueta: 'Generación de código', desc: 'Retos de programación',       icon: '💻', color: '#38BDF8', colorL: '#06141F' },
  { valor: 'creativa'     as TestCategory, etiqueta: 'Escritura creativa',   desc: 'Desafíos de escritura',       icon: '✍️', color: TOKENS.cat3, colorL: '#1C1305' },
  { valor: 'concretas'    as TestCategory, etiqueta: 'Preguntas concretas',  desc: 'Preguntas de respuesta exacta', icon: '🔍', color: TOKENS.cat4, colorL: '#041A10' },
  { valor: 'traduccion'   as TestCategory, etiqueta: 'Traducción',           desc: 'Tu texto, cualquier idioma',  icon: '🌐', color: '#F472B6', colorL: '#20071A' },
  { valor: 'resumen'      as TestCategory, etiqueta: 'Resumen',              desc: 'Resume cualquier texto',      icon: '📄', color: TOKENS.cat6, colorL: '#0C0D24' },
  { valor: 'imagen'       as TestCategory, etiqueta: 'Imagen',               desc: 'Analizar o generar imágenes', icon: '🖼️', color: TOKENS.errorText, colorL: '#1F0505' },
  { valor: 'libre'        as TestCategory, etiqueta: 'Texto libre',          desc: 'Escribe tu propio prompt',    icon: '💬', color: '#94A3B8', colorL: '#0D0E18' },
]

/* ── Datos de proveedores LLM — derivados del config central ──────────── */
const PROVEEDORES_CHIPS = PROVEEDORES_LIST.map((id) => ({ ...LLM_PROVIDERS_CONFIG[id], id }))
const PROVEEDORES_ORDER: LLMProvider[] = PROVEEDORES_LIST

/* ── Subcomponente: tarjeta de categoria ───────────────────────────────── */
interface CatCardProps {
  dato: (typeof CATEGORIAS_DATA)[0]
  seleccionado: boolean
  onClick: () => void
}

function CatCard({ dato, seleccionado, onClick }: CatCardProps) {
  const [hovering, setHovering] = useState(false)
  const hov = hovering && !seleccionado
  // ADR-029: marcar visualmente las tres categorias bilingues ES/EN antes de
  // que el usuario las elija, para que sepa que su evaluacion lanzara dos
  // rondas en paralelo (una en castellano y otra en ingles).
  const bilingue = esCategoriaBilingue(dato.valor)
  return (
    <button
      type="button"
      onClick={onClick}
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
      className="relative text-left rounded-card p-4 border-2 transition-all duration-150 w-full"
      style={{
        backgroundColor: seleccionado ? dato.colorL : hov ? dato.colorL : dato.colorL + '99',
        borderColor:     seleccionado ? dato.color  : hov ? dato.color : dato.color + '55',
        transform:       seleccionado ? 'translateY(-2px)' : hov ? 'translateY(-3px)' : undefined,
        boxShadow:       seleccionado ? '0 4px 20px rgba(0,0,0,.4)' : hov ? `0 8px 28px ${dato.color}55` : undefined,
      }}
    >
      {bilingue && (
        <div className="absolute top-2 right-2 z-10 group/badge">
          <span
            className="inline-flex items-center gap-0.5 text-[10px] font-bold tracking-wider
                       px-1.5 py-0.5 rounded-md border cursor-help select-none whitespace-nowrap"
            style={{
              color: TOKENS.textAlt,
              borderColor: TOKENS.textAlt,
              background: 'rgba(0,0,0,0.35)',
              boxShadow: '0 0 8px rgba(245,245,240,0.55), 0 2px 6px rgba(0,0,0,0.45)',
            }}
          >
            🌐 ES/EN
          </span>
          {/* Tooltip explicativo — aparece al pasar el raton sobre el badge.
              Posicionado absoluto a la derecha para no salirse en columnas
              estrechas; pointer-events-none para que no estorbe al clic. */}
          <div
            className="absolute right-0 top-full mt-1.5 w-56 pointer-events-none
                       opacity-0 group-hover/badge:opacity-100 transition-opacity duration-150 z-20"
          >
            <div
              className="text-[10.5px] leading-snug font-normal px-2.5 py-2 rounded-lg text-left normal-case"
              style={{
                background: TOKENS.border,
                border: `1px solid ${TOKENS.textAlt}`,
                color: TOKENS.textLight,
                boxShadow: '0 4px 18px rgba(0,0,0,0.65), 0 0 6px rgba(245,245,240,0.25)',
              }}
            >
              Categoría bilingüe ES/EN: el prompt se envía a los cuatro modelos en castellano y en inglés en paralelo. Solo se valoran las respuestas en castellano; las inglesas alimentan la comparativa automática del dashboard.
            </div>
          </div>
        </div>
      )}
      <div className="w-10 h-10 rounded-xl flex items-center justify-center text-xl mb-2.5"
           style={{ backgroundColor: seleccionado || hov ? dato.color : dato.color + '30' }}>
        {dato.icon}
      </div>
      <div className="font-semibold text-sm leading-snug text-text">{dato.etiqueta}</div>
      <div className="text-xs mt-0.5 leading-snug text-muted">{dato.desc}</div>
    </button>
  )
}

/* ── Subcomponente: tabla comparativa de metricas ──────────────────────── */
// fn: accede al campo ya calculado por el backend en RespuestaLLM (sin recalcular)
// mejor: direccion para asignar el badge ganador/peor (unico calculo frontend)
const METRICAS_AUTO: {
  label: string
  icono: string
  fn: (r: RespuestaLLM) => number | null
  fmt: (v: number) => string
  mejor: 'min' | 'max' | 'none'
  soloTexto?: boolean
  soloImagen?: boolean
}[] = [
  { label: 'Latencia',     icono: '⏱️', fn: (r) => r.latencia_ms,              fmt: (v) => `${v} ms`,                mejor: 'min'  },
  { label: 'Tok/s',        icono: '⚡',  fn: (r) => r.tokens_por_segundo,       fmt: (v) => v.toFixed(1),             mejor: 'max',  soloTexto: true },
  { label: 'Coste',        icono: '💰',  fn: (r) => r.cost_usd,                 fmt: (v) => `$${v.toFixed(8)}`,       mejor: 'min',  soloTexto: true },
  { label: 'Palabras',     icono: '📝',  fn: (r) => r.palabras,                 fmt: (v) => v.toString(),             mejor: 'none', soloTexto: true },
  { label: 'Sal/Ent',      icono: '↕️',  fn: (r) => r.ratio_sal_ent,            fmt: (v) => v.toFixed(2),             mejor: 'max',  soloTexto: true },
  { label: 'Div. léxica',  icono: '🔤',  fn: (r) => r.diversidad_lexica,        fmt: (v) => `${(v*100).toFixed(0)}%`, mejor: 'max',  soloTexto: true },
  { label: 'Párrafos',     icono: '¶',   fn: (r) => r.parrafos,                 fmt: (v) => v.toString(),             mejor: 'none', soloTexto: true },
  { label: '¢/100 pal.',   icono: '🏷️',  fn: (r) => r.coste_por_100_palabras,   fmt: (v) => `$${v.toFixed(8)}`,       mejor: 'min',  soloTexto: true },
]

function AutoStats({ respuestas }: { respuestas: RespuestaLLM[] }) {
  const validas = respuestas.filter((r) => !r.tuvo_error)
  if (validas.length < 2) return null

  const provEnTabla = PROVEEDORES_ORDER.filter((prov) =>
    validas.some((r) => r.proveedor === prov)
  )

  return (
    <div className="card overflow-hidden">

      {/* Título */}
      <p className="text-base sm:text-xl font-semibold text-text uppercase tracking-widest mx-4 mt-4 mb-3 text-center
                     border border-text-alt/60 bg-primary/15 rounded-xl px-3 sm:px-5 py-2 sm:py-3">
        Comparación automática de métricas
      </p>

      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse min-w-[640px]">

          {/* Cabecera: fondo oscuro + borde inferior morado para separarse del cuerpo */}
          <thead>
            <tr style={{ background: '#06060F', borderBottom: '2px solid rgba(157,78,221,0.45)' }}>
              <th className="px-4 py-3 text-left text-[10px] font-bold text-muted uppercase tracking-widest"
                  style={{ borderRight: '1px solid rgba(157,78,221,0.25)', minWidth: '7rem' }}>
                <span className="flex items-center gap-1.5">
                  <svg width="18" height="18" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ flexShrink: 0 }}>
                    <title>Métrica automática</title>
                    <line x1="8" y1="0.5" x2="8" y2="2.5" stroke="#ADADAD" strokeWidth="1.1" strokeLinecap="round"/>
                    <circle cx="8" cy="0.7" r="0.9" fill="#D0D0D0"/>
                    <rect x="1.5" y="2.5" width="13" height="12" rx="2.5" fill="#B8B8B8"/>
                    <rect x="1.5" y="2.5" width="13" height="5" rx="2.5" fill="#D2D2D2"/>
                    <rect x="2.5" y="6" width="11" height="3.5" rx="1" fill="#111827"/>
                    <circle cx="6"  cy="7.75" r="1.1" fill={TOKENS.cat3}/>
                    <circle cx="10" cy="7.75" r="1.1" fill={TOKENS.cat3}/>
                    <path d="M4.5 12 Q8 14.5 11.5 12" stroke="#777" strokeWidth="1" fill="none" strokeLinecap="round"/>
                  </svg>
                  Métrica
                </span>
              </th>
              {provEnTabla.map((prov) => {
                const chip = PROVEEDORES_CHIPS.find((c) => c.id === prov)!
                return (
                  <th key={prov} className="px-4 py-3 text-center">
                    <div className="flex flex-col items-center gap-1.5">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                           style={{ background: chip.color + '22', border: `1px solid ${chip.color}55` }}>
                        <img src={chip.icono} alt={chip.nombre} className="w-[18px] h-[18px] rounded" />
                      </div>
                      <span className="font-bold text-[11px] leading-tight whitespace-nowrap"
                            style={{ color: chip.color }}>
                        {chip.nombre}
                      </span>
                    </div>
                  </th>
                )
              })}
            </tr>
          </thead>

          {/* Cuerpo: filas alternas + columna métrica diferenciada */}
          <tbody>
            {METRICAS_AUTO.map((metrica, rowIdx) => {
              const vals = provEnTabla.map((prov) => {
                const r = validas.find((x) => x.proveedor === prov)
                if (!r) return null
                if (metrica.soloTexto  && r.es_imagen)  return null
                if (metrica.soloImagen && !r.es_imagen) return null
                return metrica.fn(r)
              })
              const nums = vals.filter((v): v is number => v !== null)
              if (nums.length === 0) return null
              const maxV = Math.max(...nums)
              const minV = Math.min(...nums)
              const hayVariacion = minV !== maxV
              const filaBg = rowIdx % 2 === 0
                ? 'rgba(157,78,221,0.07)'
                : 'rgba(0,0,0,0.32)'

              return (
                <tr key={metrica.label}
                    className="hover:bg-primary-l/30 transition-colors"
                    style={{ background: filaBg }}>
                  {/* Columna métrica: fondo propio + icono + borde derecho = "cabecera de fila" */}
                  <td className="px-4 py-2.5 font-semibold text-text"
                      style={{ borderRight: '1px solid rgba(157,78,221,0.25)', background: 'rgba(0,0,0,0.30)' }}>
                    <span className="flex items-center gap-2">
                      <span className="text-[13px] leading-none flex-shrink-0">{metrica.icono}</span>
                      {metrica.label}
                    </span>
                  </td>
                  {provEnTabla.map((prov, i) => {
                    const val = vals[i]
                    if (val === null) {
                      return <td key={prov} className="px-4 py-2.5 text-center text-muted">—</td>
                    }
                    const esGanador = hayVariacion && metrica.mejor !== 'none' && (
                      (metrica.mejor === 'min' && val === minV) ||
                      (metrica.mejor === 'max' && val === maxV)
                    )
                    const esPeor = hayVariacion && metrica.mejor !== 'none' && nums.length > 1 && (
                      (metrica.mejor === 'min' && val === maxV) ||
                      (metrica.mejor === 'max' && val === minV)
                    )
                    return (
                      <td key={prov} className="px-4 py-2.5 text-center">
                        <div className="flex flex-col items-center gap-0.5">
                          <span className="font-mono font-bold"
                                style={{ color: esGanador ? TOKENS.cat4 : esPeor ? TOKENS.errorText : '#C4B5FD' }}>
                            {metrica.fmt(val)}
                          </span>
                          {esGanador && (
                            <span className="text-[9px] font-bold text-green-400 bg-green-400/10 px-1.5 rounded-full">
                              ⚡ mejor
                            </span>
                          )}
                          {esPeor && (
                            <span className="text-[9px] font-bold text-red-400 bg-red-400/10 px-1.5 rounded-full">
                              🐢 peor
                            </span>
                          )}
                        </div>
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="text-[9px] text-muted px-4 pb-3 pt-1">
        Verde = mejor valor · Rojo = peor valor · Solo métricas con dirección clara (latencia, coste, velocidad, diversidad)
      </p>
    </div>
  )
}

/* ── Subcomponente: chip arrastrable de LLM (sin posicion intrinseca) ── */
interface LLMChipProps {
  id: number
  nombre: string
  color: string
  icono: string
  disabled: boolean
}

function DraggableLLMChip({ id, nombre, color, icono, disabled, fullSize = false }: LLMChipProps & { fullSize?: boolean }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({ id: `chip-${id}`, disabled })

  const style = transform
    ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`, opacity: isDragging ? 0.45 : 1 }
    : { opacity: isDragging ? 0.45 : 1 }

  return (
    <div ref={setNodeRef} style={style} className={fullSize ? 'w-full h-full' : ''}>
      <button
        {...attributes}
        {...listeners}
        type="button"
        disabled={disabled}
        style={{ touchAction: 'none', borderColor: fullSize ? 'transparent' : color }}
        className={`w-full ${fullSize ? 'h-full border-0' : 'rounded-[10px] border-2'} py-2.5 px-2 text-center
                   cursor-grab active:cursor-grabbing select-none transition-colors
                   focus:outline-none`}
      >
        <span className="flex items-center justify-center gap-1.5">
          <img src={icono} alt={nombre} className="w-[18px] h-[18px] rounded flex-shrink-0" />
          <span className="text-[13px] font-semibold leading-snug" style={{ color }}>
            {nombre.split(/[\s-]/)[0]}
          </span>
        </span>
      </button>
    </div>
  )
}

/* ── Subcomponente: slot numerado droppable ── */
interface SlotProps {
  posicion: number
  ocupante: { id: number; nombre: string; color: string; icono: string } | null
  disabled: boolean
}

function DroppableSlot({ posicion, ocupante, disabled }: SlotProps) {
  const { setNodeRef, isOver } = useDroppable({ id: `slot-${posicion - 1}` })

  return (
    <div className="flex flex-col items-center">
      <span className="block text-[22px] font-extrabold text-muted leading-none mb-1.5">
        {posicion}º
      </span>
      <div
        ref={setNodeRef}
        className={`w-full rounded-[10px] border-2 ${ocupante ? 'border-solid border-border' : 'border-dashed border-[#D6D3CA]'}
                    ${isOver ? 'bg-primary-l/60' : ''}
                    min-h-[64px] flex items-stretch transition-colors`}
        style={ocupante
          ? { borderColor: ocupante.color, backgroundColor: `${ocupante.color}1A` }
          : undefined}
      >
        {ocupante && (
          <DraggableLLMChip
            id={ocupante.id}
            nombre={ocupante.nombre}
            color={ocupante.color}
            icono={ocupante.icono}
            disabled={disabled}
            fullSize
          />
        )}
      </div>
    </div>
  )
}

/* ── Subcomponente: pool droppable para devolver chips no asignados ── */
function DroppablePool({ children }: { children: React.ReactNode }) {
  const { setNodeRef, isOver } = useDroppable({ id: 'pool' })
  return (
    <div
      ref={setNodeRef}
      className={`rounded-[10px] border-2 border-dashed border-[#D6D3CA] p-3 min-h-[64px]
                  flex flex-wrap gap-2 items-center justify-center transition-colors
                  ${isOver ? 'bg-primary-l/40' : ''}`}
    >
      {children}
    </div>
  )
}

/* ── Pagina principal ──────────────────────────────────────────────────── */
export default function BenchmarkPage() {
  const nickUsuario        = useUsuarioStore((s) => s.nick)
  const tokenAdmin         = useAdminStore((s) => s.token)
  const guiaVista          = useUsuarioStore((s) => s.guiaVista)
  const marcarGuiaVistaStore = useUsuarioStore((s) => s.marcarGuiaVista)
  // nickStore persiste el nick del actor actual independientemente del rol.
  // Tras la unificacion ADR-027 los admins promovidos conservan su nick
  // original (ej. 'defkorn'), por lo que no podemos asumir 'admin' literal
  // cuando hay tokenAdmin.
  const nickActor          = useNickStore((s) => s.nick)
  const nick = nickUsuario || nickActor || (tokenAdmin ? 'admin' : '')

  // Cuota del usuario web (el admin no tiene cuota)
  const esUsuarioWeb    = useUsuarioStore((s) => s.token !== null)
  const consultasUsadas = useUsuarioStore((s) => s.consultasUsadas)
  const cuotaAsignada   = useUsuarioStore((s) => s.cuotaAsignada)
  const actualizarCuota = useUsuarioStore((s) => s.actualizarCuota)
  const actualizarEstado = useUsuarioStore((s) => s.actualizarEstado)
  const estadoUsuario   = useUsuarioStore((s) => s.estado)
  const tokenUsuario    = useUsuarioStore((s) => s.token)

  const cuotaAgotada = esUsuarioWeb && consultasUsadas >= cuotaAsignada && cuotaAsignada > 0

  // Bloqueo por evaluacion pendiente: solo para usuarios web (el admin no tiene restriccion)
  const sesionesHistorial    = useHistorialStore((s) => s.sesiones[nick] ?? [])
  const evaluacionPendiente  = esUsuarioWeb && !tokenAdmin
    ? (sesionesHistorial.find((s) => s.estado === 'completada' && !s.evaluada) ?? null)
    : null

  const navigate  = useNavigate()
  const registrar      = useHistorialStore((s) => s.registrar)
  const marcarEvaluada = useHistorialStore((s) => s.marcarEvaluada)

  const [forzarGuia, setForzarGuia] = useState(false)

  // La guia se muestra si el usuario web no la ha visto aun, o si el admin la fuerza
  const mostrarGuia = forzarGuia || (!!(tokenUsuario && !guiaVista))

  const handleCerrarGuia = async () => {
    if (forzarGuia) {
      setForzarGuia(false)
      return
    }
    // Cierre normal: marcar en store y en base de datos
    marcarGuiaVistaStore()
    if (tokenUsuario) {
      marcarGuiaVistaApi(tokenUsuario).catch(() => {})
    }
  }
  const [solicitandoConsultas, setSolicitandoConsultas] = useState(false)
  const [consultasSolicitadas, setConsultasSolicitadas] = useState(false)

  const [prompt,           setPrompt]           = useState('')
  // Traduccion al ingles del prompt cuando la categoria pertenece al
  // sub-experimento bilingue (ADR-029). Vale null fuera de ese sub-experimento
  // o mientras no se haya elegido todavia una opcion predefinida.
  const [promptEn,         setPromptEn]         = useState<string | null>(null)
  const [promptReadonly,   setPromptReadonly]   = useState(false)
  const [categoria,        setCategoria]        = useState<TestCategory | null>(null)
  const haSeleccionadoCategoria = categoria !== null

  // Refs para auto-scroll a los pasos 2 y 3 conforme avanza el usuario
  const subcatRef     = useRef<HTMLDivElement>(null)
  const tercerPasoRef = useRef<HTMLDivElement>(null)

  // Auto-scroll al SubcatPanel cuando se selecciona una categoria
  useEffect(() => {
    if (categoria !== null) {
      requestAnimationFrame(() => {
        subcatRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      })
    }
  }, [categoria])

  // Auto-scroll al TERCER PASO cuando aparece el bloque del prompt
  const tercerPasoVisible = categoria === 'libre' || (categoria !== null && prompt.length > 0)
  useEffect(() => {
    if (tercerPasoVisible) {
      requestAnimationFrame(() => {
        tercerPasoRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      })
    }
  }, [tercerPasoVisible])
  const [mostrarAlertaPendiente, setMostrarAlertaPendiente] = useState(false)
  const [mostrarAlertaCuota, setMostrarAlertaCuota] = useState(false)
  const [evaluacion,           setEvaluacion]           = useState<SesionBenchmark | null>(null)
  const [vista,            setVista]            = useState<'formulario' | 'resultados'>('formulario')
  const [modelosInactivos,  setModelosInactivos]  = useState<LLMProvider[]>([])
  const [modelosSinSoporte, setModelosSinSoporte] = useState<LLMProvider[]>([])
  const [imagenBase64,     setImagenBase64]     = useState<string | null>(null)
  const [imagenMimeType,   setImagenMimeType]   = useState<string | null>(null)
  const [subcatImagen,     setSubcatImagen]     = useState<string | null>(null)
  const [subcategoriaCsv,       setSubcategoriaCsv]       = useState<string | null>(null)
  const [textoEntrada,          setTextoEntrada]          = useState<string | null>(null)
  const [textoEntradaAutoGen,   setTextoEntradaAutoGen]   = useState(false)

  // Estado de evaluacion inline
  // orden: array de slots (1º, 2º, 3º, 4º). Cada posicion contiene el id del LLM
  // asignado o null si esta vacia. El humano arrastra los chips del pool a los
  // slots para construir el ranking sin sesgo de orden inicial.
  const [orden,   setOrden]   = useState<(number | null)[]>([])
  const [ratings, setRatings] = useState<Record<number, number>>({})

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(TouchSensor, { activationConstraint: { distance: 5 } }),
  )
  const [evalGuardada,    setEvalGuardada]    = useState(false)
  const [showLoader,      setShowLoader]      = useState(false)
  const [verTextoOriginalResultados,     setVerTextoOriginalResultados]     = useState(false)
  const [ampliadoTextoOriginalResultados, setAmpliadoTextoOriginalResultados] = useState(false)

  const cambiarCategoria = (cat: TestCategory) => {
    setCategoria(cat)
    setPrompt('')
    setPromptEn(null)
    setPromptReadonly(false)
    setModelosInactivos([])
    setModelosSinSoporte([])
    setImagenBase64(null)
    setImagenMimeType(null)
    setSubcatImagen(null)
    setSubcategoriaCsv(null)
    setTextoEntrada(null)
    setTextoEntradaAutoGen(false)
  }

  const pedirMasConsultas = async () => {
    if (!tokenUsuario) return
    setSolicitandoConsultas(true)
    try {
      await solicitarMasTokens(tokenUsuario)
      actualizarEstado('pendiente_ampliar_tokens')
      setConsultasSolicitadas(true)
    } finally {
      setSolicitandoConsultas(false)
    }
  }

  // Inicializa el estado de evaluacion cuando llegan los resultados de una nueva evaluacion
  useEffect(() => {
    if (!evaluacion) return
    // ADR-029: las respuestas EN del sub-experimento bilingue se ignoran a
    // efectos de inicializar ratings y slots. Solo las ES son evaluables;
    // las EN se renderizan bajo el acordeon de cada tarjeta sin entrar al
    // sistema de puntuacion ni al ranking.
    const respuestasEs = evaluacion.respuestas.filter((r) => r.idioma_prompt === 'es')
    const initR: Record<number, number> = {}
    respuestasEs.forEach((r) => {
      initR[r.id] = r.tuvo_error ? 1 : 0
    })
    setRatings(initR)
    // Slots vacios: el humano debe arrastrar cada LLM desde el pool a un slot
    // numerado. Asi se elimina cualquier orden inicial que pueda sesgar la
    // valoracion (anteriormente se barajaba pero seguian apareciendo posicionados).
    const respValidas = respuestasEs.filter((r) => !r.tuvo_error)
    setOrden(new Array(respValidas.length).fill(null))
    setEvalGuardada(false)
  }, [evaluacion])

  const mutacion = useMutation({
    mutationFn: () => ejecutarBenchmark({
      nickname: nick,
      prompt,
      categoria: categoria ?? 'libre',
      imagen_base64:    imagenBase64    ?? undefined,
      imagen_mime_type: imagenMimeType  ?? undefined,
      subcat_imagen:    subcatImagen    ?? undefined,
      subcategoria_csv: subcategoriaCsv ?? undefined,
      // Sub-experimento bilingue: solo se envia el par EN cuando categoria
      // bilingue + opcion predefinida elegida. El backend lo usa para lanzar
      // una segunda ronda paralela y persistir 4 respuestas EN adicionales.
      prompt_en:        promptEn        ?? undefined,
      texto_entrada:              textoEntradaAutoGen ? (textoEntrada ?? undefined) : undefined,
      texto_entrada_autogenerado: textoEntradaAutoGen || undefined,
    }),
    onSuccess: (data) => {
      setEvaluacion(data)
      registrar(nick, {
        id:         data.id,
        prompt:     data.prompt,
        categoria:  data.categoria,
        estado:     data.estado,
        created_at: data.created_at,
      })
      // Incrementar contador local solo si la comparacion se completo con exito
      if (esUsuarioWeb && data.estado === 'completada') {
        actualizarCuota(consultasUsadas + 1, cuotaAsignada)
      }
    },
  })

  // Activar el loader en cuanto isPending sea true (garantiza que isLoading=true al montar BatLoader)
  useEffect(() => {
    if (mutacion.isPending) setShowLoader(true)
  }, [mutacion.isPending])

  const evalMutacion = useMutation({
    mutationFn: async () => {
      if (!evaluacion) return
      // orden: array de slots, cada uno con el id del LLM asignado por el humano.
      // El indice del array = posicion 1º, 2º, 3º, 4º. Nulls no deberian llegar
      // aqui porque puedeGuardar exige rankingCompleto.
      let rangoExitosa = 0
      const peticiones: PeticionEvaluacion[] = []
      for (const id of orden) {
        if (id === null) continue
        const r = evaluacion.respuestas.find((x) => x.id === id)
        if (!r) continue
        const esFallida = r.tuvo_error
        if (!esFallida) rangoExitosa++
        peticiones.push({
          response_id:       id,
          nickname:          nick,
          rating:            ratings[id] ?? 1,
          rango_preferencia: esFallida ? null : rangoExitosa,
        })
      }
      for (const p of peticiones) {
        await crearEvaluacion(p)
      }
    },
    onSuccess: () => {
      if (evaluacion) marcarEvaluada(nick, evaluacion.id)
      setEvalGuardada(true)
    },
  })

  const onDragEnd = ({ active, over }: DragEndEvent) => {
    if (!over) return
    const chipId = Number(active.id.toString().replace('chip-', ''))
    const dest   = over.id.toString()

    setOrden((prev) => {
      const next = [...prev]
      const from = next.indexOf(chipId)

      if (dest === 'pool') {
        if (from !== -1) next[from] = null
        return next
      }
      const to = Number(dest.replace('slot-', ''))
      if (Number.isNaN(to)) return prev

      const ocupante = next[to]
      if (from === -1) {
        // Venia del pool. Si habia ocupante, vuelve al pool (se pierde su slot).
        next[to] = chipId
      } else {
        // Venia de un slot. Swap aunque el destino este vacio.
        next[from] = ocupante
        next[to]   = chipId
      }
      return next
    })
  }

  if (!nick) return null

  const catActual          = CATEGORIAS_DATA.find((c) => c.valor === categoria)
  // Para "modificar imagen" la imagen adjunta es obligatoria ademas del prompt
  const faltaImagenModificar = subcatImagen === 'modificar' && !imagenBase64
  const puedeEnviar = prompt.trim().length >= 10 && !mutacion.isPending && !cuotaAgotada && !evaluacionPendiente && !faltaImagenModificar

  const lanzarNuevo = () => {
    setEvaluacion(null)
    mutacion.reset()
    evalMutacion.reset()
    setPrompt('')
    setPromptEn(null)
    setPromptReadonly(false)
    setModelosInactivos([])
    setModelosSinSoporte([])
    setShowLoader(false)
    // Reset al estado inicial del formulario: sin categoria seleccionada,
    // para que solo aparezca el PRIMER PASO destacado.
    setCategoria(null)
    setSubcatImagen(null)
    setSubcategoriaCsv(null)
    setImagenBase64(null)
    setImagenMimeType(null)
    setVista('formulario')
  }

  /* ── Vista: resultados ── */
  if (vista === 'resultados') {
    // Sesion fallida = censura de politica o error de imagen en al menos un LLM
    const esFallida = evaluacion?.estado === 'fallida'

    // idsValidos: ids de los slots que estan ocupados por LLMs activos y sin error.
    // Para puntuaciones usamos las respuestas validas (no las del pool), porque
    // el rating se asigna al puntuar en la grid superior, no en el ranking.
    //
    // ADR-029: en el sub-experimento bilingue ES/EN cada evaluacion produce 8
    // respuestas (4 ES + 4 EN), pero el humano solo puntua y ordena las ES;
    // las EN viajan aparte para metricas comparativas automaticas. Filtrar
    // aqui por idioma_prompt='es' garantiza que rating y ranking solo
    // contemplen las 4 cuyo numero es estable entre categorias bilingues y
    // no bilingues, sin afectar al resto de pantallas.
    const respuestasEs = (evaluacion?.respuestas ?? []).filter(
      (r) => r.idioma_prompt === 'es',
    )
    const respuestasEn = (evaluacion?.respuestas ?? []).filter(
      (r) => r.idioma_prompt === 'en',
    )
    // Distingue el motivo del fallo: censura de politica vs error tecnico de imagen
    const hayCensura = respuestasEs.some(esCensura)
    const respuestasValidas = respuestasEs.filter(
      (r) => !r.tuvo_error && !modelosInactivos.includes(r.proveedor),
    )
    const todosConRating  = respuestasValidas.length > 0
      && respuestasValidas.every((r) => (ratings[r.id] ?? 0) >= 1)
    // Pool: LLMs validos que aun no estan asignados a ningun slot.
    const idsEnSlots = new Set(orden.filter((s): s is number => s !== null))
    const pool       = respuestasValidas.filter((r) => !idsEnSlots.has(r.id))
    const rankingCompleto = orden.length > 0 && orden.every((s) => s !== null)
    const puedeGuardar    = todosConRating && rankingCompleto

    return (
      <div className="max-w-[1200px] mx-auto space-y-5">

        {/* Cabecera de resultados */}
        <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4">
          <div className="flex-1 flex items-center gap-3 px-4 py-3 rounded-xl border border-text-alt/60 bg-primary/15">
            <p className="text-sm text-white line-clamp-1">
              <span className="font-medium">Prompt enviado: </span>{evaluacion?.prompt ?? prompt}
            </p>
          </div>
          <button className="btn-primary whitespace-nowrap w-full sm:w-auto sm:flex-shrink-0" onClick={lanzarNuevo}>
            + Nueva Comparativa
          </button>
        </div>

        {/* Grid 4 columnas — respuestas de los modelos */}
        <div>
          <p className="text-base sm:text-xl font-semibold text-text uppercase tracking-widest mb-3 text-center
                         border border-text-alt/60 bg-primary/15 rounded-xl px-3 sm:px-5 py-2 sm:py-3">
            Respuestas de los modelos
          </p>

          {/* Acordeón texto autogenerado — solo visible en evaluaciones de resumen con texto autogenerado */}
          {evaluacion?.texto_entrada_autogenerado && evaluacion.texto_entrada && (
            <div
              className="mb-4 rounded-lg border overflow-hidden transition-all duration-150
                         hover:border-text-alt/60 hover:shadow-[0_0_22px_6px_rgba(245,245,240,0.75)]"
              style={{ background: TOKENS.depth, borderColor: 'rgba(245,245,240,0.2)' }}
            >
              <button
                type="button"
                className="w-full flex items-center justify-between px-3 py-2.5 text-xs font-semibold"
                style={{ color: TOKENS.cat6 }}
                onClick={() => setVerTextoOriginalResultados((v) => !v)}
              >
                <span className="flex items-center gap-1.5">
                  <span>✨</span>
                  Ver texto original generado automáticamente
                </span>
                <span className="ml-2 flex-shrink-0 text-[10px]">{verTextoOriginalResultados ? '▲' : '▼'}</span>
              </button>
              {verTextoOriginalResultados && (
                <div className="px-3 pb-3 border-t border-[#F5F5F0]/10">
                  <p
                    className="text-xs text-text leading-relaxed whitespace-pre-wrap mt-2 overflow-hidden cursor-pointer"
                    style={{ maxHeight: ampliadoTextoOriginalResultados ? undefined : '120px' }}
                    onDoubleClick={() => setAmpliadoTextoOriginalResultados((v) => !v)}
                    title={ampliadoTextoOriginalResultados ? 'Doble clic para contraer' : 'Doble clic para ampliar'}
                  >
                    {evaluacion.texto_entrada}
                  </p>
                  <button
                    type="button"
                    className="text-[11px] mt-1.5 transition-colors hover:opacity-80"
                    style={{ color: TOKENS.cat6 }}
                    onClick={() => setAmpliadoTextoOriginalResultados((v) => !v)}
                  >
                    {ampliadoTextoOriginalResultados ? '▲ Contraer' : '▼ Ampliar · doble clic'}
                  </button>
                </div>
              )}
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            {PROVEEDORES_ORDER
              .filter((proveedor) => !modelosInactivos.includes(proveedor))
              .map((proveedor) => {
                // ADR-029: la tarjeta principal siempre es la respuesta ES
                // (la que se evalua). La EN, si existe, viaja en respuestaEn
                // para renderizarse bajo el acordeon dentro de la misma card.
                const respuesta   = respuestasEs.find((r) => r.proveedor === proveedor)
                const respuestaEn = respuestasEn.find((r) => r.proveedor === proveedor)
                return (
                  <BenchmarkCard
                    key={proveedor}
                    proveedor={proveedor}
                    respuesta={respuesta}
                    respuestaEn={respuestaEn}
                    cargando={false}
                  />
                )
              })}
          </div>
        </div>

        {/* Tabla comparativa de metricas automaticas.
            La tabla se construye solo sobre las respuestas ES para mantener
            equivalencia con la comparativa humana. Las metricas EN del
            sub-experimento bilingue se publican aparte en el dashboard. */}
        {evaluacion && !showLoader && (
          <AutoStats respuestas={respuestasEs.filter((r) => !modelosInactivos.includes(r.proveedor))} />
        )}

        {/* Seccion de evaluacion inline */}
        {evaluacion && !showLoader && (
          <div className="card px-5 py-5 space-y-5">

            {/* Titulo */}
            <div>
              <p className="text-base sm:text-xl font-semibold text-text uppercase tracking-widest mb-3 text-center
                             border border-text-alt/60 bg-primary/15 rounded-xl px-3 sm:px-5 py-2 sm:py-3
                             flex items-center justify-center gap-2">
                CUARTO PASO: Evalúa las respuestas
                <svg width="22" height="22" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ flexShrink: 0 }}>
                  <title>Evaluacion humana</title>
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
              </p>
              <p className="text-xs text-muted">
                Valora cada respuesta y ordénalas de mejor a peor arrastrando las fichas.
              </p>
            </div>

            {/* ── Sesion fallida: censura de politica o error de imagen ── */}
            {esFallida ? (
              <div className="space-y-4">
                <div className="rounded-lg border border-red-500/30 px-4 py-3 flex items-start gap-3"
                     style={{ background: 'rgba(239,68,68,0.06)' }}>
                  <span className="text-red-400 text-base flex-shrink-0">
                    {hayCensura ? '🚫' : '⚠️'}
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-red-400 mb-1">
                      {hayCensura
                        ? 'Evaluación bloqueada por política de contenido'
                        : 'Error en la generación de imagen'}
                    </p>
                    <p className="text-xs text-red-300 leading-snug">
                      {hayCensura
                        ? 'Uno o más modelos rechazaron el prompt por su política de seguridad. La evaluación ha sido registrada automáticamente como fallida y no computará en las métricas de calidad del dashboard. Solo aparecerá en la gráfica de restrictividad por modelo.'
                        : 'Uno o más modelos no pudieron generar la imagen (puede ser un error transitorio, de capacidad o de copyright). La evaluación se ha marcado como fallida para evitar sesgo: valorar solo los modelos que sí respondieron no sería una comparativa justa.'}
                    </p>
                  </div>
                </div>

                {/* Lista de modelos con su estado */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
                  {PROVEEDORES_ORDER.map((prov) => {
                    const r    = respuestasEs.find((x) => x.proveedor === prov)
                    const chip = PROVEEDORES_CHIPS.find((c) => c.id === prov)!
                    if (!r || modelosInactivos.includes(prov)) return null
                    const censurado  = esCensura(r)
                    const conError   = r.tuvo_error && !censurado
                    return (
                      <div key={prov}
                           className="rounded-[10px] border p-3.5 text-center"
                           style={{
                             background:  censurado ? 'rgba(239,68,68,0.06)' : conError ? 'rgba(251,146,60,0.06)' : TOKENS.depth,
                             borderColor: censurado ? 'rgba(239,68,68,0.35)' : conError ? 'rgba(251,146,60,0.35)' : '#1C1C32',
                           }}>
                        <p className="text-[13px] font-semibold mb-2"
                           style={{ color: chip.color, textDecoration: (censurado || conError) ? 'line-through' : 'none' }}>
                          {chip.nombre}
                        </p>
                        {censurado ? (
                          <p className="text-[11px] text-red-400 font-semibold">🚫 Politica de seguridad</p>
                        ) : conError ? (
                          <p className="text-[11px] text-orange-400 font-semibold">⚠ Error de generacion</p>
                        ) : (
                          <p className="text-[11px] text-green-400">✓ Respondio</p>
                        )}
                      </div>
                    )
                  })}
                </div>

                <div className="flex justify-end pt-1">
                  <button className="btn-ghost text-sm"
                          onClick={() => {
                            if (['generar', 'logotipo', 'modificar'].includes(subcatImagen ?? '')) {
                              setEvaluacion(null)
                              setPrompt('')
                              setCategoria(null)
                              setSubcatImagen(null)
                              setSubcategoriaCsv(null)
                              setImagenBase64(null)
                              setImagenMimeType(null)
                              setVista('formulario')
                            } else {
                              navigate('/historial')
                            }
                          }}>
                    {['generar', 'logotipo', 'modificar'].includes(subcatImagen ?? '')
                      ? 'Intentar con otro prompt →'
                      : 'Cerrar y volver al menu →'}
                  </button>
                </div>
              </div>
            ) : !evalGuardada ? (
              <>
                <p className="text-base sm:text-xl font-semibold text-text uppercase tracking-widest mb-3 text-center
                               border border-text-alt/60 bg-primary/15 rounded-xl px-3 sm:px-5 py-2 sm:py-3
                               flex items-center justify-center gap-2">
                  Puntuación
                  {todosConRating
                    ? <span className="text-green-400 font-bold">✓</span>
                    : <span className="text-yellow-400 font-bold">*</span>
                  }
                </p>
                {/* Cajitas de valoracion — grid 4 columnas */}
                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3.5">
                  {PROVEEDORES_ORDER.map((prov) => {
                    const r    = respuestasEs.find((x) => x.proveedor === prov)
                    const chip = PROVEEDORES_CHIPS.find((c) => c.id === prov)!
                    if (!r || modelosInactivos.includes(prov)) return null

                    if (r.tuvo_error) {
                      return (
                        <div key={prov}
                             className="rounded-[10px] border p-3.5 text-center opacity-40"
                             style={{ background: TOKENS.depth, borderColor: TOKENS.border }}>
                          <p className="text-[13px] font-semibold mb-2 line-through"
                             style={{ color: chip.color }}>
                            {chip.nombre}
                          </p>
                          <p className="text-xs text-red-400">Error técnico</p>
                        </div>
                      )
                    }

                    const valorado = (ratings[r.id] ?? 0) > 0
                    return (
                      <div key={prov}
                           className={`rounded-[10px] border-[1.5px] p-3.5 text-center transition-colors ${!valorado ? 'animate-pulse-strong' : ''}`}
                           style={{
                             borderColor: valorado ? chip.color + 'AA' : '#1C1C32',
                             background:  valorado ? chip.color + '12' : TOKENS.depth,
                           }}>
                        <p className="text-[13px] font-semibold mb-2.5" style={{ color: chip.color }}>
                          {chip.nombre}
                        </p>
                        <StarRating
                          valor={ratings[r.id] ?? 0}
                          onChange={(v) => setRatings((p) => ({ ...p, [r.id]: v }))}
                          disabled={evalMutacion.isPending}
                        />
                      </div>
                    )
                  })}
                </div>

                {/* Ranking: slots numerados arriba + pool de chips abajo */}
                <div className="space-y-3">
                  <p className="text-base sm:text-xl font-semibold text-text uppercase tracking-widest mb-3 text-center
                                 border border-text-alt/60 bg-primary/15 rounded-xl px-3 sm:px-5 py-2 sm:py-3
                                 flex items-center justify-center gap-2">
                    🏆 Ranking de preferencia (arrastra cada modelo a un puesto)
                    {!rankingCompleto && (
                      <span className="text-yellow-400 font-bold text-xs">*</span>
                    )}
                    {rankingCompleto && (
                      <span className="text-green-400 text-xs">✓</span>
                    )}
                  </p>
                  <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
                    {/* Slots numerados (1º, 2º, 3º, 4º) */}
                    <div className={`grid grid-cols-2 ${orden.length === 3 ? 'sm:grid-cols-3' : 'sm:grid-cols-4'} gap-2 ${!rankingCompleto ? 'animate-pulse-strong' : ''}`}>
                      {orden.map((slotId, idx) => {
                        const r    = slotId !== null ? evaluacion.respuestas.find((x) => x.id === slotId) : null
                        const chip = r ? PROVEEDORES_CHIPS.find((c) => c.id === r.proveedor) : null
                        const ocupante = (slotId !== null && chip) ? {
                          id: slotId, nombre: chip.nombre, color: chip.color, icono: chip.icono,
                        } : null
                        return (
                          <DroppableSlot
                            key={idx}
                            posicion={idx + 1}
                            ocupante={ocupante}
                            disabled={evalMutacion.isPending}
                          />
                        )
                      })}
                    </div>

                    {/* Pool de LLMs sin asignar */}
                    {pool.length > 0 && (
                      <div className="space-y-1.5">
                        <p className="text-[11px] text-muted text-center uppercase tracking-wider">
                          Arrastra cada modelo a uno de los puestos
                        </p>
                        <DroppablePool>
                          {pool.map((r) => {
                            const chip = PROVEEDORES_CHIPS.find((c) => c.id === r.proveedor)
                            if (!chip) return null
                            return (
                              <div key={r.id} className="w-[130px] sm:w-[150px]">
                                <DraggableLLMChip
                                  id={r.id}
                                  nombre={chip.nombre}
                                  color={chip.color}
                                  icono={chip.icono}
                                  disabled={evalMutacion.isPending}
                                />
                              </div>
                            )
                          })}
                        </DroppablePool>
                      </div>
                    )}
                  </DndContext>
                </div>

                {/* Pie con validacion y boton guardar */}
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pt-1">
                  <div className="space-y-0.5">
                    {!todosConRating && (
                      <p className="text-xs text-yellow-400">
                        Puntua con estrellas todas las respuestas para poder guardar.
                      </p>
                    )}
                    {todosConRating && !rankingCompleto && (
                      <p className="text-xs text-yellow-400">
                        Coloca cada modelo en uno de los puestos del ranking.
                      </p>
                    )}
                    {evalMutacion.isError && (
                      <p className="text-xs text-red-400">
                        Error al guardar. Comprueba que el backend esta activo.
                      </p>
                    )}
                  </div>
                  <button
                    className={`btn-primary ${puedeGuardar && !evalMutacion.isPending ? 'animate-pulse-strong' : ''}`}
                    onClick={() => evalMutacion.mutate()}
                    disabled={!puedeGuardar || evalMutacion.isPending}
                  >
                    {evalMutacion.isPending ? 'Guardando…' : 'Guardar evaluación'}
                  </button>
                </div>
              </>
            ) : (
              <div className="flex items-center justify-between gap-4">
                <p className="text-sm text-green-400 font-medium">
                  ✓ Evaluacion guardada correctamente
                </p>
                <div className="flex items-center gap-3">
                  <button
                    className="btn-primary text-sm"
                    onClick={() => {
                      lanzarNuevo()
                      window.scrollTo({ top: 0, behavior: 'smooth' })
                    }}
                  >
                    + Nueva Comparativa
                  </button>
                  <button className="btn-ghost text-sm" onClick={() => navigate('/historial')}>
                    Ver historial →
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Barra de informacion de evaluacion */}
        {evaluacion && !showLoader && (
          <div className="card px-5 py-3 flex flex-wrap items-center gap-4 text-sm">
            <span>
              <span className="text-muted">Evaluacion #</span>
              <span className="font-mono font-semibold">{evaluacion.id}</span>
            </span>
            <span>
              <span className="text-muted">Jaccard: </span>
              <span className="font-mono font-semibold">
                {evaluacion.similitud_jaccard_media != null
                  ? `${(evaluacion.similitud_jaccard_media * 100).toFixed(1)} %`
                  : 'N/A'}
              </span>
            </span>
            <span className="text-xs text-muted">{evaluacion.estado}</span>
          </div>
        )}

        {mutacion.isError && (() => {
          const st = axios.isAxiosError(mutacion.error)
            ? mutacion.error.response?.status
            : null
          return (
            <p className="text-sm text-red-400 text-center">
              {st === 401
                ? 'Sesión expirada. Recarga la página para volver a iniciar sesión.'
                : 'Error al conectar con el servidor. Comprueba que el backend está activo.'}
            </p>
          )
        })()}
      </div>
    )
  }

  /* ── Vista: formulario ── */
  return (
    <>
    <OnboardingGuide visible={mostrarGuia} onCerrar={handleCerrarGuia} />
    <div className="max-w-[1100px] mx-auto space-y-8">

      {/* Cabecera */}
      <div className="relative">
        <div className="flex flex-col items-center text-center">
          <img src="/logo-tfg.png" alt="Logo TFG" className="h-28 sm:h-44 w-auto mb-4" />
          <h2 className="text-xl sm:text-3xl font-bold mb-2">
            Bienvenido al comparador de modelos
          </h2>
          <p className="text-sm sm:text-base text-muted animate-pulse-strong">
            Los parpadeos te ayudarán a guiarte en los pasos a seguir.
          </p>
        </div>

        <div className="static sm:absolute sm:top-0 sm:right-0 mt-3 sm:mt-0
                         flex flex-wrap items-start justify-center sm:justify-end gap-3">
          {/* Boton solo visible para admin: relanza la guia de bienvenida */}
          {tokenAdmin && (
            <button
              onClick={() => setForzarGuia(true)}
              className="btn-ghost text-xs flex items-center gap-1.5 flex-shrink-0"
              title="Revisar guía de bienvenida"
            >
              👁 Ver guía de bienvenida
            </button>
          )}

          {/* Contador de cuota — solo para usuarios web */}
          {esUsuarioWeb && cuotaAsignada > 0 && (
            <div className={`rounded-xl border px-4 py-3 text-sm flex-shrink-0 ${
              cuotaAgotada
                ? 'border-red-500/40 bg-red-900/20'
                : consultasUsadas >= cuotaAsignada * 0.8
                  ? 'border-yellow-500/40 bg-yellow-900/20'
                  : 'border-border bg-card'
            }`}>
              <p className="text-xs text-muted mb-1 font-semibold uppercase tracking-wider">
                Consultas
              </p>
              <p className={`font-mono font-bold text-lg leading-none ${
                cuotaAgotada ? 'text-red-400' : 'text-text'
              }`}>
                {consultasUsadas}
                <span className="text-muted font-normal text-sm"> / {cuotaAsignada}</span>
              </p>
              {cuotaAgotada && (
                <p className="text-[11px] text-red-400 mt-1">Cuota agotada</p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Banner de cuota agotada con boton de solicitud */}
      {cuotaAgotada && (
        <div className="rounded-xl border border-red-500/30 bg-red-900/10 px-5 py-4 flex items-center justify-between gap-4 flex-wrap">
          <div>
            <p className="text-sm font-semibold text-red-400 mb-1">
              Has agotado tu cuota de consultas
            </p>
            {!(consultasSolicitadas || estadoUsuario === 'pendiente_ampliar_tokens') && (
              <p className="text-xs text-red-300/80">
                Solicita al administrador que amplie tus consultas para seguir comparando.
              </p>
            )}
          </div>
          {!(consultasSolicitadas || estadoUsuario === 'pendiente_ampliar_tokens') ? (
            <button
              className="btn-primary flex-shrink-0 bg-red-600 hover:bg-red-500 border-red-500"
              onClick={pedirMasConsultas}
              disabled={solicitandoConsultas}
            >
              {solicitandoConsultas ? 'Enviando solicitud…' : 'SOLICITAR MAS CONSULTAS'}
            </button>
          ) : (
            <p className="text-sm text-green-400 font-medium flex-shrink-0">
              ✓ Pendiente de ampliación de cuota por el administrador.
            </p>
          )}
        </div>
      )}

      {/* Banner de evaluacion pendiente */}
      {evaluacionPendiente && (
        <div className="rounded-xl border border-yellow-500/30 px-5 py-4
                         flex items-center justify-between gap-4 flex-wrap"
             style={{ background: 'rgba(251,191,36,0.06)' }}>
          <div>
            <p className="text-sm font-semibold text-yellow-400 mb-1">
              ⏳ Tienes una evaluación pendiente
            </p>
            <p className="text-xs leading-relaxed" style={{ color: 'rgba(251,191,36,0.7)' }}>
              Valora la comparativa #{evaluacionPendiente.id} antes de lanzar una nueva.
              No se pueden tener dos evaluaciones sin valorar a la vez.
            </p>
          </div>
          <button
            className="flex-shrink-0 text-sm font-semibold px-4 py-2 rounded-lg transition-colors animate-pulse-strong"
            style={{
              color: TOKENS.cat3,
              border: '1px solid rgba(251,191,36,0.4)',
              background: 'rgba(251,191,36,0.08)',
            }}
            onClick={() => navigate('/historial')}
          >
            Ir a evaluarla →
          </button>
        </div>
      )}

      {/* Listado fijo de modelos participantes */}
      <div>
        <p className="text-base sm:text-xl font-semibold text-text uppercase tracking-widest mb-3 text-center
                       border border-text-alt/60 bg-primary/15 rounded-xl px-3 sm:px-5 py-2 sm:py-3">
          Listado de modelos implicados en el estudio
        </p>
        <div className="flex flex-wrap justify-center gap-2 mb-2">
          {PROVEEDORES_CHIPS.map((p) => {
            const inactivo = modelosInactivos.includes(p.id)
            return (
              <div key={p.id}
                   className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-sm font-semibold border transition-all duration-150"
                   style={{
                     borderColor:  inactivo ? '#2A2A4A' : p.color,
                     color:        inactivo ? '#3A3A5A' : p.color,
                     borderStyle:  inactivo ? 'dashed'  : 'solid',
                     opacity:      inactivo ? 0.35 : 1,
                   }}>
                <img src={p.icono} alt={p.nombre} className="w-[16px] h-[16px] rounded flex-shrink-0" />
                {p.nombre}
                {inactivo && <span className="text-[9px] ml-0.5 opacity-70">✕</span>}
              </div>
            )
          })}
        </div>
        <p className="text-xs text-muted text-center">
          Los 4 modelos participan en todas las categorías de texto.
          En generación de imagen solo participan los modelos con esa capacidad.
        </p>
      </div>

      {/* 1. Selector de categoria */}
      <div>
        <p className="text-base sm:text-xl font-semibold text-text uppercase tracking-widest mb-2 text-center
                       border border-text-alt/60 bg-primary/15 rounded-xl px-3 sm:px-5 py-2 sm:py-3">
          PRIMER PASO: Selecciona una categoría.
        </p>
        <hr className="mb-4 border-[#F5F5F0]/30" />
        <div
          className={`grid grid-cols-2 sm:grid-cols-4 gap-3 ${evaluacionPendiente || cuotaAgotada ? 'opacity-50' : ''} ${!haSeleccionadoCategoria && !evaluacionPendiente && !cuotaAgotada ? 'animate-pulse-strong' : ''}`}
          style={evaluacionPendiente || cuotaAgotada ? { cursor: 'not-allowed' } : undefined}
        >
          {CATEGORIAS_DATA.map((cat) => (
            <CatCard
              key={cat.valor}
              dato={cat}
              seleccionado={categoria === cat.valor}
              onClick={() => {
                if (evaluacionPendiente) setMostrarAlertaPendiente(true)
                else if (cuotaAgotada)   setMostrarAlertaCuota(true)
                else                     cambiarCategoria(cat.valor)
              }}
            />
          ))}
        </div>
      </div>

      {mostrarAlertaPendiente && evaluacionPendiente && (
        <ConfirmModal
          mensaje={`Tienes la comparativa #${evaluacionPendiente.id} pendiente de evaluar. No puedes lanzar una nueva hasta que la valores.`}
          textoBotom="Ir a evaluarla"
          onConfirmar={() => { setMostrarAlertaPendiente(false); navigate('/historial') }}
          onCancelar={() => setMostrarAlertaPendiente(false)}
        />
      )}

      {mostrarAlertaCuota && (() => {
        const yaSolicitoCuota = consultasSolicitadas || estadoUsuario === 'pendiente_ampliar_tokens'
        return (
          <ConfirmModal
            mensaje={yaSolicitoCuota
              ? 'Has agotado tu cuota de consultas. Estas pendiente de que el Administrador te proporcione mas cuota.'
              : 'Has agotado tu cuota de consultas. Solicita al administrador que amplie tus consultas para seguir comparando.'}
            textoBotom={yaSolicitoCuota ? 'Entendido' : 'Solicitar Consultas'}
            onConfirmar={yaSolicitoCuota
              ? () => setMostrarAlertaCuota(false)
              : async () => { await pedirMasConsultas(); setMostrarAlertaCuota(false) }}
            onCancelar={() => setMostrarAlertaCuota(false)}
          />
        )
      })()}

      {/* Panel de subcategoria - oculto si la cuota esta agotada o sin categoria */}
      {!cuotaAgotada && categoria !== null && (
      <div ref={subcatRef}>
        <SubcatPanel
          key={categoria}
          categoria={categoria}
          color={catActual?.color ?? TOKENS.primary}
          colorL={catActual?.colorL ?? '#19102B'}
          opImagenInicial={categoria === 'imagen' ? subcatImagen : null}
          onPromptChange={(p, ro, pEn) => {
            setPrompt(p)
            setPromptReadonly(ro)
            // SubcatPanel emite pEn solo en categorias bilingues con opcion
            // predefinida elegida; en cualquier otro caso, null limpia el
            // valor del intento anterior (importante al alternar entre
            // opciones predefinidas dentro de una misma categoria bilingue).
            setPromptEn(pEn ?? null)
          }}
          onInactivar={setModelosInactivos}
          onSinSoporte={setModelosSinSoporte}
          onImagenChange={(b64, mime) => { setImagenBase64(b64); setImagenMimeType(mime) }}
          onSubcatImagenChange={setSubcatImagen}
          onSubcategoriaCsvChange={setSubcategoriaCsv}
          onTextoEntradaChange={(texto, autoGen) => {
            setTextoEntrada(texto)
            setTextoEntradaAutoGen(autoGen)
          }}
        />
      </div>
      )}

      {(categoria === 'libre' || prompt.length > 0) && (
      <div ref={tercerPasoRef} className="space-y-8">
      {/* 2. Prompt */}
      <div>
        <p className="text-base sm:text-xl font-semibold text-text uppercase tracking-widest mb-3 text-center
                       border border-text-alt/60 bg-primary/15 rounded-xl px-3 sm:px-5 py-2 sm:py-3">
          TERCER PASO: Enviamos el Prompt final
        </p>

        <div className={`rounded-card overflow-hidden border ${categoria === 'libre' && prompt.length === 0 ? 'animate-pulse-strong' : ''}`}
             style={{
               borderColor: prompt.length >= 10 ? (catActual?.color ?? 'rgba(157,78,221,0.5)') : 'rgba(157,78,221,0.38)',
               boxShadow: prompt.length >= 10
                 ? `0 0 0 3px ${catActual?.color ?? TOKENS.primary}20, 0 2px 16px rgba(0,0,0,.45)`
                 : '0 2px 16px rgba(0,0,0,.45)',
               transition: 'border-color 150ms, box-shadow 150ms',
             }}>
          <textarea
            className="w-full h-36 overflow-y-auto border-none outline-none p-4 text-sm leading-relaxed
                       resize-none font-mono text-text placeholder:text-muted"
            style={{
              background: promptReadonly ? TOKENS.bg : TOKENS.surface,
              opacity:    promptReadonly ? 0.9 : 1,
              cursor:     promptReadonly ? 'default' : 'text',
            }}
            placeholder={categoria === 'libre'
              ? 'Escribe tu prompt aquí (mínimo 10 caracteres)...'
              : 'Selecciona una subcategoría para cargar el prompt automáticamente...'}
            value={prompt}
            readOnly={promptReadonly}
            onChange={(e) => !promptReadonly && setPrompt(e.target.value)}
            maxLength={promptReadonly ? undefined : 8000}
            disabled={mutacion.isPending}
          />
          <div className="flex items-center justify-between px-4 py-2.5 border-t border-border"
               style={{ background: '#0C0C18' }}>
            <span className="text-xs" style={{ color: promptReadonly ? catActual?.color : TOKENS.muted }}>
              {promptReadonly
                ? `🔒 Prompt predefinido · solo lectura`
                : prompt.length >= 10
                  ? `✓ Prompt listo (${catActual?.etiqueta ?? ''})`
                  : '💡 Selecciona una subcategoría o escribe el prompt'}
            </span>
            {!promptReadonly && (
              <span className="text-xs text-muted font-mono">{prompt.length} / 8000</span>
            )}
          </div>
        </div>

      </div>

      {/* Segunda caja con el prompt EN — solo para el sub-experimento bilingue.
          Se muestra READONLY pegada debajo del prompt ES para que el usuario vea
          exactamente que va a recibir cada LLM. No bloquea el flujo si el
          usuario no lo lee; es transparencia metodologica (ADR-029). */}
      {promptEn && esCategoriaBilingue(categoria ?? 'libre') && (
        <div className="space-y-1.5">
          <p className="text-xs font-semibold uppercase tracking-wider text-center"
             style={{ color: catActual?.color ?? TOKENS.primary }}>
            🌐 Prompt traducido al inglés (se enviará en paralelo para métricas comparativas)
          </p>
          <div className="rounded-card overflow-hidden border"
               style={{
                 borderColor: 'rgba(157,78,221,0.45)',
                 boxShadow: '0 2px 16px rgba(0,0,0,.45)',
               }}>
            <textarea
              className="w-full h-28 overflow-y-auto border-none outline-none p-4 text-sm leading-relaxed
                         resize-none font-mono text-text"
              style={{ background: TOKENS.bg, opacity: 0.9, cursor: 'default' }}
              value={promptEn}
              readOnly
            />
            <div className="flex items-center justify-between px-4 py-2.5 border-t border-border"
                 style={{ background: '#0C0C18' }}>
              <span className="text-xs" style={{ color: catActual?.color }}>
                🔒 Prompt en inglés · solo lectura · solo métricas automáticas
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Boton enviar */}
      <div className="flex flex-col items-end gap-1.5">
        <div className="flex justify-end gap-3">
          <button className="btn-ghost" onClick={() => { setCategoria(null); setPrompt(''); setPromptEn(null) }}>
            Limpiar
          </button>
          <button
            className={`btn-primary text-base px-8 py-3 ${puedeEnviar && !mutacion.isPending ? 'animate-pulse-strong' : ''}`}
            onClick={() => mutacion.mutate()}
            disabled={!puedeEnviar}
          >
            {mutacion.isPending ? 'Comparando…' : '🧠 Comparar modelos'}
          </button>
        </div>
        {faltaImagenModificar && (
          <p className="text-xs text-amber-400">
            ⚠ Debes adjuntar una imagen antes de enviar
          </p>
        )}
      </div>

      </div>
      )}

      {mutacion.isError && (() => {
        const status = axios.isAxiosError(mutacion.error)
          ? mutacion.error.response?.status
          : null
        if (status === 402) return null // ya lo muestra el banner de cuota agotada
        return (
          <p className="text-sm text-red-400 text-center">
            {status === 401
              ? 'Sesión expirada. Recarga la página para volver a iniciar sesión.'
              : 'Error al conectar con el servidor. Comprueba que el backend esta activo.'}
          </p>
        )
      })()}

      {/* Overlay del loader — aparece encima del formulario durante la llamada API y la animacion de fin */}
      {(mutacion.isPending || showLoader) && (
        <div
          style={{
            position:       'fixed',
            inset:          0,
            background:     'rgba(0, 0, 0, 0.82)',
            backdropFilter: 'blur(5px)',
            display:        'flex',
            alignItems:     'center',
            justifyContent: 'center',
            zIndex:         50,
          }}
        >
          <BatLoader
            modelos={PROVEEDORES_CHIPS.map((p) => ({
              nombre:      p.nombre,
              color:       p.color,
              sinSoporte:  modelosInactivos.includes(p.id) || modelosSinSoporte.includes(p.id),
            }))}
            isLoading={mutacion.isPending}
            onComplete={() => {
              setShowLoader(false)
              if (!mutacion.isError) setVista('resultados')
            }}
          />
        </div>
      )}
    </div>
    </>
  )
}
