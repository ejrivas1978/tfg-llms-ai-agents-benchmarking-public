/**
 * Componente: EvalViewModal
 * Ruta:       frontend/src/components/historial/EvalViewModal.tsx
 *
 * Descripcion:
 *   Modal accesible desde el historial de usuario. Cubre dos casos:
 *   - Evaluacion no valorada: formulario con estrellas + ranking DnD horizontal.
 *   - Evaluacion ya valorada: vista de solo lectura con ranking y estrellas.
 *   Se cierra con el boton X, pulsando Escape o haciendo clic en el fondo.
 *
 * Sprint: Sprint 3
 */

import { useState, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { DndContext, closestCenter, useSensor, useSensors, PointerSensor, TouchSensor, useDraggable, useDroppable, type DragEndEvent } from '@dnd-kit/core'
import StarRating from '@/components/evaluation/StarRating'
import MapaMentalDiagram from '@/components/shared/MapaMentalDiagram'
import VisorImagen from '@/components/shared/VisorImagen'
import VisorMapaMental from '@/components/shared/VisorMapaMental'
import BtnAmpliar from '@/components/shared/BtnAmpliar'
import { LLM_PROVIDERS_CONFIG } from '@/config/llmProviders'
import { useNickStore } from '@/store/nickStore'
import { useHistorialStore } from '@/store/historialStore'
import { obtenerEvaluacion } from '@/services/benchmarkApi'
import { crearEvaluacion, obtenerEvaluacionesPorEvaluacion } from '@/services/evaluacionApi'
import type { LLMProvider } from '@/types/benchmark'
import type { PeticionEvaluacion } from '@/types/evaluacion'
import { formatFecha } from '@/utils/formatFecha'
import { esCensura, extraerMapaMental } from '@/utils/contenidoLLM'
import { TOKENS } from '@/utils/tokens'

type LightboxState =
  | { tipo: 'imagen'; src: string; fallbackSrc?: string }
  | { tipo: 'mapaMental'; svg: string }


const COLOR_CAT: Record<string, string> = {
  razonamiento: '#A855F7',
  codigo:       '#38BDF8',
  creativa:     TOKENS.cat3,
  concretas:    TOKENS.cat4,
  traduccion:   '#F472B6',
  resumen:      TOKENS.cat6,
  imagen:       TOKENS.errorText,
  libre:        '#94A3B8',
}

/* ── Chip arrastrable de LLM (sin posicion intrinseca) ──────────────────── */
function DraggableLLMChip({
  id, nombre, color, icono, disabled, fullSize = false,
}: { id: number; nombre: string; color: string; icono: string; disabled: boolean; fullSize?: boolean }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({ id: `chip-${id}`, disabled })

  const style = transform
    ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`, opacity: isDragging ? 0.45 : 1 }
    : { opacity: isDragging ? 0.45 : 1 }

  return (
    <div ref={setNodeRef} style={style} className={fullSize ? 'w-full h-full' : ''}>
      <button
        {...attributes} {...listeners}
        type="button"
        disabled={disabled}
        style={{ touchAction: 'none', borderColor: fullSize ? 'transparent' : color }}
        className={`w-full ${fullSize ? 'h-full border-0' : 'rounded-[10px] border-2'} py-2 px-2 text-center
                   cursor-grab active:cursor-grabbing select-none transition-colors
                   focus:outline-none disabled:cursor-default disabled:opacity-50`}
      >
        <span className="flex items-center justify-center gap-1.5">
          <img src={icono} alt={nombre} className="w-[16px] h-[16px] rounded flex-shrink-0" />
          <span className="text-[12px] font-semibold leading-snug" style={{ color }}>
            {nombre.split(/[\s-]/)[0]}
          </span>
        </span>
      </button>
    </div>
  )
}

/* ── Slot numerado droppable ──────────────────────────────────────────────── */
function DroppableSlot({
  posicion, ocupante, disabled,
}: { posicion: number; ocupante: { id: number; nombre: string; color: string; icono: string } | null; disabled: boolean }) {
  const { setNodeRef, isOver } = useDroppable({ id: `slot-${posicion - 1}` })
  return (
    <div className="flex flex-col items-center">
      <span className="block text-[18px] font-extrabold text-muted leading-none mb-1.5">
        {posicion}º
      </span>
      <div
        ref={setNodeRef}
        className={`w-full rounded-[10px] border-2 ${ocupante ? 'border-solid border-border' : 'border-dashed border-[#D6D3CA]'}
                    ${isOver ? 'bg-primary-l/60' : ''}
                    min-h-[52px] flex items-stretch transition-colors`}
        style={ocupante
          ? { borderColor: ocupante.color, backgroundColor: `${ocupante.color}1A` }
          : undefined}
      >
        {ocupante && (
          <DraggableLLMChip id={ocupante.id} nombre={ocupante.nombre} color={ocupante.color} icono={ocupante.icono} disabled={disabled} fullSize />
        )}
      </div>
    </div>
  )
}

/* ── Pool droppable inferior ──────────────────────────────────────────────── */
function DroppablePool({ children }: { children: React.ReactNode }) {
  const { setNodeRef, isOver } = useDroppable({ id: 'pool' })
  return (
    <div
      ref={setNodeRef}
      className={`rounded-[10px] border-2 border-dashed border-[#D6D3CA] p-2 min-h-[52px]
                  flex flex-wrap gap-2 items-center justify-center transition-colors
                  ${isOver ? 'bg-primary-l/40' : ''}`}
    >
      {children}
    </div>
  )
}

/* ── Modal principal ─────────────────────────────────────────────────────── */
interface Props {
  sesionId:    number
  onClose:     () => void
  onEvaluated?: () => void
}

export default function EvalViewModal({ sesionId, onClose, onEvaluated }: Props) {
  const nick            = useNickStore((s) => s.nick)
  const marcarEvaluada  = useHistorialStore((s) => s.marcarEvaluada)
  const eliminarSesion  = useHistorialStore((s) => s.eliminarSesion)

  const { data: sesion, isLoading: cargandoSesion, isError: errorSesion } = useQuery({
    queryKey: ['sesion', sesionId],
    queryFn: () => obtenerEvaluacion(sesionId),
    retry: false,
  })

  const { data: evaluaciones, isLoading: cargandoEval, refetch } = useQuery({
    queryKey: ['evaluaciones-sesion', sesionId],
    queryFn: () => obtenerEvaluacionesPorEvaluacion(sesionId),
  })

  // orden: slots numerados (1º…Nº). null = vacio. El humano arrastra cada chip
  // del pool a un slot para construir el ranking sin sesgo de orden inicial.
  const [orden,   setOrden]   = useState<(number | null)[]>([])
  const [ratings, setRatings] = useState<Record<number, number>>({})

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(TouchSensor, { activationConstraint: { distance: 5 } }),
  )
  const [lightbox, setLightbox] = useState<LightboxState | null>(null)
  const [svgMap,   setSvgMap]   = useState<Record<number, string>>({})
  // ADR-029: estado de cada acordeon "Ver respuesta en inglés". Se indexa por
  // id de respuesta ES (la EN se busca en respuestasEn por proveedor).
  const [verEn, setVerEn] = useState<Record<number, boolean>>({})
  // Toggle ampliado/comprimido del texto EN dentro de cada acordeon. Misma
  // clave (id ES) que verEn; doble-clic alterna su valor.
  const [ampliadoEn, setAmpliadoEn] = useState<Record<number, boolean>>({})
  // Acordeon del texto original autogenerado (categoria resumen).
  const [verTextoOriginal, setVerTextoOriginal] = useState(false)
  const [ampliadoTextoOriginal, setAmpliadoTextoOriginal] = useState(false)
  // Toggle ampliado/comprimido del texto ES de cada respuesta. Indexado por
  // id de la respuesta para que cada tarjeta tenga su estado independiente.
  const [ampliadoEs, setAmpliadoEs] = useState<Record<number, boolean>>({})

  const abrirImagen  = (src: string, fallbackSrc?: string) => setLightbox({ tipo: 'imagen', src, fallbackSrc })
  const abrirMapaMental = (svg: string) => setLightbox({ tipo: 'mapaMental', svg })

  // Inicializar estado del formulario cuando cargan los datos.
  // ADR-029: en evaluaciones bilingues el backend devuelve 8 respuestas
  // (4 ES + 4 EN), pero el humano solo puntua y rankea las ES. Filtrar a
  // idioma_prompt='es' aqui mantiene la UI estable entre evaluaciones
  // bilingues y no bilingues.
  useEffect(() => {
    if (!sesion || cargandoEval) return
    const respuestasEs = sesion.respuestas.filter((r) => r.idioma_prompt === 'es')
    const initR: Record<number, number> = {}
    respuestasEs.forEach((r) => {
      initR[r.id] = r.tuvo_error ? 1 : 0
    })
    setRatings(initR)
    // Slots vacios: el humano debe arrastrar cada LLM desde el pool a uno de
    // los puestos numerados. Sin orden inicial: cero sesgo de presentacion.
    const respValidas = respuestasEs.filter((r) => !r.tuvo_error)
    setOrden(new Array(respValidas.length).fill(null))
  }, [sesion, cargandoEval])

  const mutacion = useMutation({
    mutationFn: async () => {
      if (!sesion) return
      // orden: slots con id del LLM por posicion. Nulls no llegan aqui porque
      // puedeGuardar exige rankingCompleto.
      let rangoExitosa = 0
      const peticiones: PeticionEvaluacion[] = []
      for (const id of orden) {
        if (id === null) continue
        const r = sesion.respuestas.find((x) => x.id === id)
        const esFallida = r?.tuvo_error ?? false
        if (!esFallida) rangoExitosa++
        peticiones.push({
          response_id:       id,
          nickname:          nick,
          rating:            ratings[id] ?? 1,
          rango_preferencia: esFallida ? null : rangoExitosa,
        })
      }
      for (const p of peticiones) await crearEvaluacion(p)
    },
    onSuccess: () => {
      marcarEvaluada(nick, sesionId)
      refetch()
      onEvaluated?.()
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
        next[to] = chipId
      } else {
        next[from] = ocupante
        next[to]   = chipId
      }
      return next
    })
  }

  // Cerrar con Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  const cargando   = cargandoSesion || cargandoEval
  const yaEvaluada = (evaluaciones?.length ?? 0) > 0

  // Sincroniza el flag de localStorage si el servidor confirma que ya hay evaluacion
  useEffect(() => {
    if (yaEvaluada) marcarEvaluada(nick, sesionId)
  }, [yaEvaluada, nick, sesionId, marcarEvaluada])

  // ADR-029: separar ES (evaluables) y EN (acordeon comparativo) antes de
  // construir cualquier derivado. Los efectos y eventos solo deben razonar
  // sobre ES; las respuestas EN viajan aparte para enriquecer la vista.
  const respuestasEs = (sesion?.respuestas ?? []).filter((r) => r.idioma_prompt === 'es')
  const respuestasEn = (sesion?.respuestas ?? []).filter((r) => r.idioma_prompt === 'en')
  const buscarEn = (prov: LLMProvider) => respuestasEn.find((r) => r.proveedor === prov)

  // Datos para la vista de solo lectura
  const filasOrdenadas = !yaEvaluada ? [] : [...(evaluaciones ?? [])]
    .sort((a, b) => (a.rango_preferencia ?? 99) - (b.rango_preferencia ?? 99))
    .map((ev) => {
      const resp = respuestasEs.find((r) => r.id === ev.response_id)
      const info = resp
        ? (LLM_PROVIDERS_CONFIG[resp.proveedor] ?? { nombre: resp.proveedor, color: '#888', icono: '' })
        : { nombre: 'Desconocido', color: '#888' }
      return { ev, info, resp }
    })

  // Datos para el formulario
  const respuestasValidas = respuestasEs.filter((r) => !r.tuvo_error)
  const todosConRating    = respuestasValidas.length > 0
    && respuestasValidas.every((r) => (ratings[r.id] ?? 0) >= 1)
  const idsEnSlots        = new Set(orden.filter((s): s is number => s !== null))
  const pool              = respuestasValidas.filter((r) => !idsEnSlots.has(r.id))
  const rankingCompleto   = orden.length > 0 && orden.every((s) => s !== null)
  const puedeGuardar      = todosConRating && rankingCompleto

  const fechaGuardado = evaluaciones?.[0]?.created_at
    ? formatFecha(evaluaciones[0].created_at)
    : null

  return (
    <>
    {/* Lightbox imagen — componente compartido con BenchmarkCard */}
    {lightbox?.tipo === 'imagen' && (
      <VisorImagen
        src={lightbox.src}
        fallbackSrc={lightbox.fallbackSrc}
        onClose={() => setLightbox(null)}
      />
    )}

    {/* Lightbox mapa mental */}
    {lightbox?.tipo === 'mapaMental' && (
      <VisorMapaMental svg={lightbox.svg} onClose={() => setLightbox(null)} />
    )}
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.65)' }}
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-3xl rounded-card border border-border shadow-card-lg overflow-hidden bg-surface"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Cabecera */}
        <div className="flex items-start justify-between gap-3 px-5 py-4 border-b border-border flex-wrap">
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold">
              {yaEvaluada ? 'Evaluación guardada' : 'Evaluar respuestas'} — Evaluación #{sesionId}
            </p>
            {sesion && (
              <p className="text-xs text-muted mt-0.5 line-clamp-1">{sesion.prompt}</p>
            )}
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {sesion && (
              <span
                className="hidden sm:inline-flex text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full whitespace-nowrap"
                style={{
                  color: COLOR_CAT[sesion.categoria] ?? '#8B949E',
                  background: `${COLOR_CAT[sesion.categoria] ?? '#8B949E'}20`,
                  border: `1px solid ${COLOR_CAT[sesion.categoria] ?? '#8B949E'}40`,
                }}
              >
                {sesion.categoria}
              </span>
            )}
            <button
              onClick={onClose}
              className="text-muted hover:text-text transition-colors text-lg leading-none"
              title="Cerrar"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Contenido */}
        <div className="px-4 sm:px-5 py-4 space-y-4 max-h-[70vh] overflow-y-auto">
          {cargando ? (
            <p className="text-sm text-muted text-center py-6 animate-pulse">Cargando...</p>

          ) : errorSesion ? (
            <div className="flex flex-col items-center gap-4 py-8 text-center">
              <p className="text-sm text-red-400 font-medium">
                Esta evaluación ya no existe en el estudio.
              </p>
              <p className="text-xs text-muted max-w-xs">
                Puede que el administrador la haya eliminado. Puedes quitarla de tu historial local.
              </p>
              <button
                className="text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors
                           text-red-400 hover:text-red-300 hover:bg-red-400/10
                           border border-red-400/40 hover:border-red-300/60"
                onClick={() => { eliminarSesion(nick, sesionId); onClose() }}
              >
                Eliminar del historial
              </button>
            </div>

          ) : yaEvaluada ? (
            /* ── Vista solo lectura ── */
            <div className="space-y-2.5">
              {/* Acordeon texto original autogenerado (solo categoria resumen) */}
              {sesion?.texto_entrada_autogenerado && sesion.texto_entrada && (
                <div className="rounded-[10px] border overflow-hidden transition-all duration-150
                                hover:border-text-alt/60 hover:shadow-[0_0_22px_6px_rgba(245,245,240,0.75)]"
                     style={{ background: TOKENS.depth, borderColor: 'rgba(245,245,240,0.15)' }}>
                  <button
                    type="button"
                    className="w-full flex items-center justify-between px-3 py-2 text-xs font-semibold"
                    style={{ color: TOKENS.cat6 }}
                    onClick={() => setVerTextoOriginal((v) => !v)}
                  >
                    <span className="flex items-center gap-1.5">
                      <span>✨</span>
                      Ver texto original generado automáticamente
                    </span>
                    <span className="text-[10px]">{verTextoOriginal ? '▲' : '▼'}</span>
                  </button>
                  {verTextoOriginal && (
                    <div className="px-3 pb-3 border-t border-border">
                      <p
                        className="text-[11px] text-text leading-relaxed whitespace-pre-wrap mt-2"
                        style={{
                          maxHeight: ampliadoTextoOriginal ? undefined : '120px',
                          overflow:  ampliadoTextoOriginal ? 'visible' : 'hidden',
                          cursor: 'pointer',
                        }}
                        onDoubleClick={() => setAmpliadoTextoOriginal((v) => !v)}
                        title={ampliadoTextoOriginal ? 'Doble clic para contraer' : 'Doble clic para ampliar'}
                      >
                        {sesion.texto_entrada}
                      </p>
                      <button
                        type="button"
                        className="text-[10px] text-primary hover:opacity-80 transition-opacity mt-1"
                        onClick={() => setAmpliadoTextoOriginal((v) => !v)}
                      >
                        {ampliadoTextoOriginal ? '▲ Contraer' : '▼ Ampliar · doble clic'}
                      </button>
                    </div>
                  )}
                </div>
              )}
              {filasOrdenadas.map(({ ev, info, resp }, idx) => {
                const respEn = resp ? buscarEn(resp.proveedor) : undefined
                return (
                <div key={ev.id}
                     className="rounded-[10px] border border-border overflow-hidden"
                     style={{ background: TOKENS.depth }}>
                  {/* Fila ranking */}
                  <div className="flex items-center gap-3 px-3 py-2.5">
                    <span className="text-base font-extrabold text-muted w-6 flex-shrink-0 text-center">
                      {idx + 1}º
                    </span>
                    <span className="w-2 h-2 rounded-full flex-shrink-0"
                          style={{ backgroundColor: info.color }} />
                    <span className="text-sm font-semibold flex-1 min-w-0 truncate"
                          style={{ color: info.color }}>
                      {info.nombre}
                    </span>
                    <StarRating valor={ev.rating} onChange={() => {}} disabled />
                  </div>
                  {/* Respuesta del modelo */}
                  {resp && (
                    <div className="px-3 pb-3 border-t border-border mt-0 space-y-2">
                      {resp.tuvo_error ? (
                        <p className="text-[10px] text-red-400 italic pt-2">
                          {esCensura(resp.mensaje_error) ? '🚫 Rechazado por política de seguridad' : resp.mensaje_error ?? 'Error técnico'}
                        </p>
                      ) : resp.es_imagen ? (
                        (resp.url_imagen || resp.imagen_miniatura) ? (
                          <div className="flex flex-col items-center gap-2 pt-2">
                            <img
                              src={resp.url_imagen ?? `data:image/jpeg;base64,${resp.imagen_miniatura}`}
                              alt={`Imagen generada por ${info.nombre}`}
                              className="rounded-lg object-cover cursor-pointer"
                              style={{ width: 140, height: 140 }}
                              onError={(e) => {
                                if (resp.imagen_miniatura)
                                  (e.target as HTMLImageElement).src = `data:image/jpeg;base64,${resp.imagen_miniatura}`
                              }}
                              onDoubleClick={() => abrirImagen(
                                resp.url_imagen ?? `data:image/jpeg;base64,${resp.imagen_miniatura!}`,
                                resp.url_imagen && resp.imagen_miniatura ? `data:image/jpeg;base64,${resp.imagen_miniatura}` : undefined,
                              )}
                            />
                            <BtnAmpliar onClick={() => abrirImagen(
                              resp.url_imagen ?? `data:image/jpeg;base64,${resp.imagen_miniatura!}`,
                              resp.url_imagen && resp.imagen_miniatura ? `data:image/jpeg;base64,${resp.imagen_miniatura}` : undefined,
                            )}>
                              ⤢ Ampliar imagen
                            </BtnAmpliar>
                          </div>
                        ) : (
                          <p className="text-xs text-muted italic pt-2">Vista previa no disponible</p>
                        )
                      ) : (() => {
                        const mapaMental = extraerMapaMental(resp.texto_respuesta)
                        return mapaMental ? (
                          <div className="space-y-1.5 pt-2">
                            <div className="w-full overflow-hidden rounded-lg cursor-pointer" style={{ height: 160 }}
                                 onDoubleClick={() => svgMap[resp.id] && abrirMapaMental(svgMap[resp.id])}>
                              <MapaMentalDiagram codigo={mapaMental}
                                onSvgReady={(svg) => setSvgMap((p) => ({ ...p, [resp.id]: svg }))} />
                            </div>
                            <BtnAmpliar onClick={() => svgMap[resp.id] && abrirMapaMental(svgMap[resp.id])}>
                              ⤢ Ampliar mapa
                            </BtnAmpliar>
                          </div>
                        ) : (() => {
                          const textLargoEs = (resp.palabras ?? 0) > 60
                          const ampliado = !!ampliadoEs[resp.id]
                          return (
                            <div className="pt-2 space-y-1">
                              <div
                                className="text-[11px] text-text leading-relaxed"
                                style={{
                                  maxHeight: ampliado ? undefined : (textLargoEs ? '100px' : undefined),
                                  overflow: ampliado ? 'visible' : (textLargoEs ? 'hidden' : 'visible'),
                                  whiteSpace: 'pre-wrap',
                                  wordBreak: 'break-word',
                                  cursor: textLargoEs ? 'pointer' : 'default',
                                }}
                                onDoubleClick={() => {
                                  if (textLargoEs) setAmpliadoEs((p) => ({ ...p, [resp.id]: !p[resp.id] }))
                                }}
                                title={textLargoEs ? (ampliado ? 'Doble clic para contraer' : 'Doble clic para ampliar') : undefined}
                              >
                                {resp.texto_respuesta || <span className="text-muted italic">Sin respuesta</span>}
                              </div>
                              {textLargoEs && (
                                <button
                                  type="button"
                                  className="text-[10px] text-primary hover:opacity-80 transition-opacity"
                                  onClick={() => setAmpliadoEs((p) => ({ ...p, [resp.id]: !p[resp.id] }))}
                                >
                                  {ampliado ? '▲ Contraer respuesta' : '▼ Ampliar respuesta · doble clic'}
                                </button>
                              )}
                            </div>
                          )
                          })()
                        })()}
                    </div>
                  )}
                  {/* ADR-029: acordeon comparativo con la respuesta EN para
                      evaluaciones bilingues. No participa en ranking ni
                      rating; solo informa de la respuesta del mismo modelo
                      en ingles a quien quiera consultarla. */}
                  {respEn && resp && (
                    <div className="px-3 pb-3 pt-2 border-t border-border">
                      <BotonVerEn
                        color={info.color}
                        abierto={!!verEn[resp.id]}
                        onClick={() => setVerEn((p) => ({ ...p, [resp.id]: !p[resp.id] }))}
                      />
                      {verEn[resp.id] && (() => {
                        const textLargoEn = (respEn.palabras ?? 0) > 60
                        const ampliado = !!ampliadoEn[resp.id]
                        return (
                          <div className="mt-2 space-y-1">
                            {respEn.tuvo_error ? (
                              <p className="text-[10px] text-red-400 italic">
                                {respEn.mensaje_error ?? 'Error técnico'}
                              </p>
                            ) : (
                              <>
                                <p
                                  className="text-[11px] text-text leading-relaxed whitespace-pre-wrap"
                                  style={{
                                    maxHeight: ampliado ? undefined : (textLargoEn ? '120px' : undefined),
                                    overflow: ampliado ? 'visible' : (textLargoEn ? 'hidden' : 'visible'),
                                    cursor: textLargoEn ? 'pointer' : 'default',
                                  }}
                                  onDoubleClick={() => {
                                    if (textLargoEn) setAmpliadoEn((p) => ({ ...p, [resp.id]: !p[resp.id] }))
                                  }}
                                  title={textLargoEn ? (ampliado ? 'Doble clic para contraer' : 'Doble clic para ampliar') : undefined}
                                >
                                  {respEn.texto_respuesta ?? <span className="text-muted italic">Sin respuesta</span>}
                                </p>
                                {textLargoEn && (
                                  <button
                                    type="button"
                                    className="text-[10px] text-primary hover:opacity-80 transition-opacity"
                                    onClick={() => setAmpliadoEn((p) => ({ ...p, [resp.id]: !p[resp.id] }))}
                                  >
                                    {ampliado ? '▲ Contraer respuesta' : '▼ Ampliar respuesta · doble clic'}
                                  </button>
                                )}
                              </>
                            )}
                          </div>
                        )
                      })()}
                    </div>
                  )}
                </div>
                )
              })}
            </div>

          ) : sesion ? (
            /* ── Formulario de evaluacion ── */
            <>
              {/* Acordeon texto original autogenerado (solo categoria resumen) */}
              {sesion.texto_entrada_autogenerado && sesion.texto_entrada && (
                <div className="rounded-[10px] border overflow-hidden transition-all duration-150
                                hover:border-text-alt/60 hover:shadow-[0_0_22px_6px_rgba(245,245,240,0.75)]"
                     style={{ background: TOKENS.depth, borderColor: 'rgba(245,245,240,0.15)' }}>
                  <button
                    type="button"
                    className="w-full flex items-center justify-between px-3 py-2 text-xs font-semibold"
                    style={{ color: TOKENS.cat6 }}
                    onClick={() => setVerTextoOriginal((v) => !v)}
                  >
                    <span className="flex items-center gap-1.5">
                      <span>✨</span>
                      Ver texto original generado automáticamente
                    </span>
                    <span className="text-[10px]">{verTextoOriginal ? '▲' : '▼'}</span>
                  </button>
                  {verTextoOriginal && (
                    <div className="px-3 pb-3 border-t border-border">
                      <p
                        className="text-[11px] text-text leading-relaxed whitespace-pre-wrap mt-2"
                        style={{
                          maxHeight: ampliadoTextoOriginal ? undefined : '120px',
                          overflow:  ampliadoTextoOriginal ? 'visible' : 'hidden',
                          cursor: 'pointer',
                        }}
                        onDoubleClick={() => setAmpliadoTextoOriginal((v) => !v)}
                        title={ampliadoTextoOriginal ? 'Doble clic para contraer' : 'Doble clic para ampliar'}
                      >
                        {sesion.texto_entrada}
                      </p>
                      <button
                        type="button"
                        className="text-[10px] text-primary hover:opacity-80 transition-opacity mt-1"
                        onClick={() => setAmpliadoTextoOriginal((v) => !v)}
                      >
                        {ampliadoTextoOriginal ? '▲ Contraer' : '▼ Ampliar · doble clic'}
                      </button>
                    </div>
                  )}
                </div>
              )}
              {/* Respuestas de los modelos */}
              <div>
                <p className="text-base sm:text-xl font-semibold text-text uppercase tracking-widest mb-3 text-center
                               border border-text-alt/60 bg-primary/15 rounded-xl px-3 sm:px-5 py-2 sm:py-3">
                  Respuestas
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {respuestasEs.map((r) => {
                    const chip = LLM_PROVIDERS_CONFIG[r.proveedor] ?? { nombre: r.proveedor, color: '#888', icono: '' }
                    const respEn = buscarEn(r.proveedor)
                    return (
                      <div
                        key={r.id}
                        className="rounded-card p-3 space-y-2 flex flex-col"
                        style={{ border: `1.5px solid ${chip.color}40`, background: `${chip.color}0a` }}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs font-semibold" style={{ color: chip.color }}>
                            {chip.nombre}
                          </span>
                          {r.tuvo_error && (
                            <span className="text-[10px] font-bold text-red-400 bg-red-400/10
                                             px-1.5 py-0.5 rounded-full">Error</span>
                          )}
                        </div>
                        <div className="border-t border-border pt-2 flex-1">
                          {r.tuvo_error ? (
                            esCensura(r.mensaje_error) ? (
                              <div className="flex flex-col items-center justify-center gap-1.5 py-3 text-center">
                                <span className="text-2xl">🚫</span>
                                <p className="text-[10px] font-semibold text-red-400">Politica de seguridad</p>
                              </div>
                            ) : (
                              <p className="text-[10px] text-red-400 italic">
                                {r.mensaje_error ?? 'Error tecnico'}
                              </p>
                            )
                          ) : r.es_imagen ? (
                            (r.url_imagen || r.imagen_miniatura) ? (
                              <div className="flex flex-col items-center gap-1.5">
                                <img
                                  src={r.url_imagen ?? `data:image/jpeg;base64,${r.imagen_miniatura}`}
                                  alt={`Imagen generada por ${chip.nombre}`}
                                  className="rounded-lg object-cover cursor-pointer"
                                  style={{ width: 120, height: 120 }}
                                  onError={(e) => {
                                    if (r.imagen_miniatura)
                                      (e.target as HTMLImageElement).src = `data:image/jpeg;base64,${r.imagen_miniatura}`
                                  }}
                                  onDoubleClick={() => abrirImagen(
                                    r.url_imagen ?? `data:image/jpeg;base64,${r.imagen_miniatura!}`,
                                    r.url_imagen && r.imagen_miniatura ? `data:image/jpeg;base64,${r.imagen_miniatura}` : undefined,
                                  )}
                                />
                                <BtnAmpliar onClick={() => abrirImagen(
                                  r.url_imagen ?? `data:image/jpeg;base64,${r.imagen_miniatura!}`,
                                  r.url_imagen && r.imagen_miniatura ? `data:image/jpeg;base64,${r.imagen_miniatura}` : undefined,
                                )}>
                                  ⤢ Ampliar imagen
                                </BtnAmpliar>
                              </div>
                            ) : (
                              <p className="text-[10px] text-muted italic">Vista previa no disponible</p>
                            )
                          ) : (() => {
                            const mapaMental = extraerMapaMental(r.texto_respuesta)
                            return mapaMental ? (
                              <div className="space-y-1.5">
                                <div className="w-full overflow-hidden rounded-lg cursor-pointer" style={{ height: 150 }}
                                     onDoubleClick={() => svgMap[r.id] && abrirMapaMental(svgMap[r.id])}>
                                  <MapaMentalDiagram codigo={mapaMental}
                                    onSvgReady={(svg) => setSvgMap((p) => ({ ...p, [r.id]: svg }))} />
                                </div>
                                <BtnAmpliar onClick={() => svgMap[r.id] && abrirMapaMental(svgMap[r.id])}>
                                  ⤢ Ampliar mapa
                                </BtnAmpliar>
                              </div>
                            ) : (() => {
                              const textLargoEs = (r.palabras ?? 0) > 60
                              const ampliado = !!ampliadoEs[r.id]
                              return (
                                <div className="space-y-1">
                                  <div
                                    className="text-[11px] text-text leading-relaxed"
                                    style={{
                                      maxHeight: ampliado ? undefined : (textLargoEs ? '120px' : undefined),
                                      overflow: ampliado ? 'visible' : (textLargoEs ? 'hidden' : 'visible'),
                                      whiteSpace: 'pre-wrap',
                                      wordBreak: 'break-word',
                                      cursor: textLargoEs ? 'pointer' : 'default',
                                    }}
                                    onDoubleClick={() => {
                                      if (textLargoEs) setAmpliadoEs((p) => ({ ...p, [r.id]: !p[r.id] }))
                                    }}
                                    title={textLargoEs ? (ampliado ? 'Doble clic para contraer' : 'Doble clic para ampliar') : undefined}
                                  >
                                    {r.texto_respuesta || <span className="text-muted italic">Sin respuesta</span>}
                                  </div>
                                  {textLargoEs && (
                                    <button
                                      type="button"
                                      className="text-[10px] text-primary hover:opacity-80 transition-opacity"
                                      onClick={() => setAmpliadoEs((p) => ({ ...p, [r.id]: !p[r.id] }))}
                                    >
                                      {ampliado ? '▲ Contraer respuesta' : '▼ Ampliar respuesta · doble clic'}
                                    </button>
                                  )}
                                </div>
                              )
                            })()
                          })()}
                        </div>
                        {/* ADR-029: acordeon comparativo con la respuesta EN.
                            Solo aparece si la evaluacion es bilingue y existe
                            su par EN del mismo proveedor. No participa en
                            puntuacion ni ranking. */}
                        {respEn && (
                          <div className="border-t border-border pt-2">
                            <BotonVerEn
                              color={chip.color}
                              abierto={!!verEn[r.id]}
                              onClick={() => setVerEn((p) => ({ ...p, [r.id]: !p[r.id] }))}
                            />
                            {verEn[r.id] && (() => {
                              const textLargoEn = (respEn.palabras ?? 0) > 60
                              const ampliado = !!ampliadoEn[r.id]
                              return (
                                <div className="mt-2 space-y-1">
                                  {respEn.tuvo_error ? (
                                    <p className="text-[10px] text-red-400 italic">
                                      {respEn.mensaje_error ?? 'Error técnico'}
                                    </p>
                                  ) : (
                                    <>
                                      <p
                                        className="text-[11px] text-text leading-relaxed whitespace-pre-wrap"
                                        style={{
                                          maxHeight: ampliado ? undefined : (textLargoEn ? '120px' : undefined),
                                          overflow: ampliado ? 'visible' : (textLargoEn ? 'hidden' : 'visible'),
                                          cursor: textLargoEn ? 'pointer' : 'default',
                                        }}
                                        onDoubleClick={() => {
                                          if (textLargoEn) setAmpliadoEn((p) => ({ ...p, [r.id]: !p[r.id] }))
                                        }}
                                        title={textLargoEn ? (ampliado ? 'Doble clic para contraer' : 'Doble clic para ampliar') : undefined}
                                      >
                                        {respEn.texto_respuesta ?? <span className="text-muted italic">Sin respuesta</span>}
                                      </p>
                                      {textLargoEn && (
                                        <button
                                          type="button"
                                          className="text-[10px] text-primary hover:opacity-80 transition-opacity"
                                          onClick={() => setAmpliadoEn((p) => ({ ...p, [r.id]: !p[r.id] }))}
                                        >
                                          {ampliado ? '▲ Contraer respuesta' : '▼ Ampliar respuesta · doble clic'}
                                        </button>
                                      )}
                                    </>
                                  )}
                                </div>
                              )
                            })()}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Titulo de seccion: cuarto paso */}
              <p className="text-base sm:text-xl font-semibold text-text uppercase tracking-widest text-center
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

              {/* Puntuacion por modelo */}
              <div>
                <p className="text-base sm:text-xl font-semibold text-text uppercase tracking-widest mb-3 text-center
                               border border-text-alt/60 bg-primary/15 rounded-xl px-3 sm:px-5 py-2 sm:py-3
                               flex items-center justify-center gap-2">
                  Puntuación
                  {todosConRating
                    ? <span className="text-green-400 font-bold">✓</span>
                    : <span className="text-yellow-400 font-bold">*</span>
                  }
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  {respuestasEs.map((r) => {
                    const chip = LLM_PROVIDERS_CONFIG[r.proveedor] ?? { nombre: r.proveedor, color: '#888', icono: '' }
                    if (r.tuvo_error) {
                      return (
                        <div key={r.id}
                             className="rounded-[10px] border border-border p-3 text-center opacity-50"
                             style={{ background: TOKENS.depth }}>
                          <p className="text-xs font-semibold line-through mb-2"
                             style={{ color: chip.color }}>{chip.nombre}</p>
                          {esCensura(r.mensaje_error) ? (
                            <div className="flex flex-col items-center gap-1">
                              <span className="text-xl">🚫</span>
                              <p className="text-[10px] text-red-400 font-semibold">Politica de seguridad</p>
                            </div>
                          ) : (
                            <p className="text-[10px] text-red-400">Error</p>
                          )}
                        </div>
                      )
                    }
                    const valorado = (ratings[r.id] ?? 0) > 0
                    return (
                      <div key={r.id}
                           className={`rounded-[10px] border-[1.5px] p-3 text-center transition-colors ${!valorado ? 'animate-pulse-strong' : ''}`}
                           style={{
                             borderColor: valorado ? chip.color + 'AA' : TOKENS.border,
                             background:  valorado ? chip.color + '12' : TOKENS.depth,
                           }}>
                        <p className="text-xs font-semibold mb-2" style={{ color: chip.color }}>
                          {chip.nombre}
                        </p>
                        <StarRating
                          valor={ratings[r.id] ?? 0}
                          onChange={(v) => setRatings((p) => ({ ...p, [r.id]: v }))}
                          disabled={mutacion.isPending}
                        />
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Ranking: slots numerados + pool */}
              <div className="space-y-3">
                <p className="text-base sm:text-xl font-semibold text-text uppercase tracking-widest mb-3 text-center
                               border border-text-alt/60 bg-primary/15 rounded-xl px-3 sm:px-5 py-2 sm:py-3
                               flex items-center justify-center gap-2">
                  Ranking de preferencia
                  {rankingCompleto
                    ? <span className="text-green-400 font-bold">✓</span>
                    : <span className="text-yellow-400 font-bold">*</span>
                  }
                </p>
                <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
                  <div className={`grid grid-cols-2 ${orden.length === 3 ? 'sm:grid-cols-3' : 'sm:grid-cols-4'} gap-2 ${!rankingCompleto ? 'animate-pulse-strong' : ''}`}>
                    {orden.map((slotId, idx) => {
                      const r    = slotId !== null ? respuestasEs.find((x) => x.id === slotId) : null
                      const chip = r ? LLM_PROVIDERS_CONFIG[r.proveedor as LLMProvider] : null
                      const ocupante = (slotId !== null && chip && r) ? {
                        id: slotId, nombre: chip.nombre, color: chip.color, icono: chip.icono,
                      } : null
                      return (
                        <DroppableSlot
                          key={idx}
                          posicion={idx + 1}
                          ocupante={ocupante}
                          disabled={mutacion.isPending}
                        />
                      )
                    })}
                  </div>

                  {pool.length > 0 && (
                    <div className="space-y-1.5">
                      <p className="text-[11px] text-muted text-center uppercase tracking-wider">
                        Arrastra cada modelo a uno de los puestos
                      </p>
                      <DroppablePool>
                        {pool.map((r) => {
                          const chip = LLM_PROVIDERS_CONFIG[r.proveedor as LLMProvider]
                          if (!chip) return null
                          return (
                            <div key={r.id} className="w-[100px] sm:w-[120px]">
                              <DraggableLLMChip
                                id={r.id}
                                nombre={chip.nombre}
                                color={chip.color}
                                icono={chip.icono}
                                disabled={mutacion.isPending}
                              />
                            </div>
                          )
                        })}
                      </DroppablePool>
                    </div>
                  )}
                </DndContext>
              </div>

              {/* Validacion y boton */}
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pt-1">
                <div className="space-y-0.5">
                  {!todosConRating && (
                    <p className="text-xs text-yellow-400">Puntua todas las respuestas.</p>
                  )}
                  {todosConRating && !rankingCompleto && (
                    <p className="text-xs text-yellow-400">Coloca cada modelo en uno de los puestos.</p>
                  )}
                  {mutacion.isError && (
                    <p className="text-xs text-red-400">Error al guardar. Intenta de nuevo.</p>
                  )}
                </div>
                <button
                  className={`btn-primary flex-shrink-0 ${puedeGuardar && !mutacion.isPending ? 'animate-pulse-strong' : ''}`}
                  onClick={() => mutacion.mutate()}
                  disabled={!puedeGuardar || mutacion.isPending}
                >
                  {mutacion.isPending ? 'Guardando…' : 'Guardar evaluación'}
                </button>
              </div>
            </>
          ) : null}
        </div>

        {/* Pie — solo lectura */}
        {yaEvaluada && fechaGuardado && (
          <div className="px-5 pb-4 border-t border-border pt-3">
            <p className="text-[10px] text-muted text-right">Guardada el {fechaGuardado}</p>
          </div>
        )}

        {/* Boton cerrar inferior */}
        <div className="px-5 py-3 border-t border-border flex justify-end">
          <button className="btn-ghost text-sm" onClick={onClose}>
            Cerrar
          </button>
        </div>
      </div>
    </div>

    </>
  )
}

/**
 * Boton del acordeon "Ver respuesta en ingles" (ADR-029) con afordancia
 * visual dependiente del color del LLM. Mismo estilo que el de
 * BenchmarkCard para que la senalizacion sea consistente entre el flujo
 * de evaluacion inmediata y el modal del historial.
 *
 * - Reposo: borde semitransparente + fondo muy tenue del color del LLM.
 * - Hover: fondo y borde plenos + halo de color para sugerir el clic.
 * - Active: pequena reduccion de escala que acompana al mousedown.
 * - Abierto: borde solido + halo suave permanente para indicar el estado.
 */
function BotonVerEn({ color, abierto, onClick }: { color: string; abierto: boolean; onClick: () => void }) {
  const [hov, setHov] = useState(false)
  const enfasis = hov || abierto
  return (
    <button
      type="button"
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      className="w-full flex items-center justify-between px-3 py-2 text-[11px] font-semibold uppercase tracking-wider rounded-md border-2 transition-all duration-150 cursor-pointer active:scale-[0.98]"
      style={{
        color,
        borderColor: enfasis ? color : `${color}66`,
        background: hov ? `${color}25` : abierto ? `${color}15` : `${color}0A`,
        boxShadow: hov
          ? `0 0 14px ${color}66, 0 2px 6px rgba(0,0,0,0.35)`
          : abierto
            ? `0 0 6px ${color}44`
            : 'none',
      }}
      title="Las respuestas en inglés se generan solo para métricas comparativas; no se valoran."
    >
      <span className="flex items-center gap-1.5">
        <span>🌐</span>
        Ver respuesta en inglés
      </span>
      <span className="text-[10px]">{abierto ? '▲' : '▼'}</span>
    </button>
  )
}
