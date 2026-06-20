/**
 * Componente: TablaAdmin
 * Ruta:       frontend/src/components/historial/TablaAdmin.tsx
 *
 * Descripcion:
 *   Tabla paginada de todas las comparativas del estudio para el administrador.
 *   Fila de filtros inline (nick, categoria, prompt, estado, rango de fechas).
 *   Checkboxes por fila con batch-bar para borrado multiple.
 *   Boton "Ver" por fila para consultar el contenido completo de la comparativa.
 *   Borrado individual y reset completo del estudio.
 *
 * Sprint: Sprint 3 / Sprint 4
 */

import React, { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  listarEvaluacionesAdmin,
  eliminarEvaluacion,
  eliminarTodasLasEvaluaciones,
  exportarEvaluacionesCsvAdmin,
  rechazarBorradoEvaluacion,
  type FiltrosAdmin,
} from '@/services/adminApi'
import { obtenerEvaluacion } from '@/services/benchmarkApi'
import { obtenerEvaluacionesPorEvaluacion } from '@/services/evaluacionApi'
import StarRating from '@/components/evaluation/StarRating'
import type { ResumenEvaluacionAdmin } from '@/types/admin'
import type { SesionBenchmark, TestCategory, SessionStatus } from '@/types/benchmark'
import ConfirmModal from '@/components/shared/ConfirmModal'
import EvalViewModal from '@/components/historial/EvalViewModal'
import MapaMentalDiagram from '@/components/shared/MapaMentalDiagram'
import VisorImagen from '@/components/shared/VisorImagen'
import VisorMapaMental from '@/components/shared/VisorMapaMental'
import { TOKENS } from '@/utils/tokens'
import BtnAmpliar from '@/components/shared/BtnAmpliar'
import DateTimePicker from '@/components/shared/DateTimePicker'
import { useNickStore } from '@/store/nickStore'
import { useToastStore } from '@/store/toastStore'
import { formatFecha } from '@/utils/formatFecha'
import { esCensura, extraerMapaMental } from '@/utils/contenidoLLM'

const LIMITE = 15


interface Props {
  token: string
}

const ESTADO_COLOR: Record<SessionStatus, string> = {
  completada:        'text-green-400',
  fallida:           'text-red-400',
  en_curso:          'text-yellow-400',
  pendiente:         'text-muted',
  solicitud_borrado: 'text-orange-400',
}

const ESTADO_LABEL: Record<SessionStatus, string> = {
  completada:        'Ejecutada',
  fallida:           'Fallida',
  en_curso:          'En curso',
  pendiente:         'Pendiente',
  solicitud_borrado: 'Borrado solicitado',
}

const PROV_INFO: Record<string, { nombre: string; color: string }> = {
  claude: { nombre: 'Claude Sonnet 4.6', color: '#E8956D' },
  openai: { nombre: 'GPT-4o',           color: '#10D9A0' },
  gemini: { nombre: 'Gemini 2.5 Flash', color: '#EF4444' },
  grok:   { nombre: 'Grok 3',           color: '#4DB8FF' },
}

const COLOR_CAT: Record<TestCategory, string> = {
  razonamiento: '#A855F7',
  codigo:       '#38BDF8',
  creativa:     TOKENS.cat3,
  concretas:    TOKENS.cat4,
  traduccion:   '#F472B6',
  resumen:      TOKENS.cat6,
  imagen:       TOKENS.errorText,
  libre:        '#94A3B8',
}

const CATEGORIAS_OPC: { valor: TestCategory | ''; etiqueta: string }[] = [
  { valor: '',             etiqueta: 'Todas las categorías' },
  { valor: 'razonamiento', etiqueta: 'Razonamiento' },
  { valor: 'codigo',       etiqueta: 'Código'         },
  { valor: 'creativa',     etiqueta: 'Creativa'      },
  { valor: 'concretas',    etiqueta: 'Concretas'     },
  { valor: 'traduccion',   etiqueta: 'Traducción'    },
  { valor: 'resumen',      etiqueta: 'Resumen'       },
  { valor: 'imagen',       etiqueta: 'Imagen'        },
  { valor: 'libre',        etiqueta: 'Libre'         },
]

const ESTADO_OPC: { valor: SessionStatus | ''; etiqueta: string }[] = [
  { valor: '',                  etiqueta: 'Todos los estados'   },
  { valor: 'completada',        etiqueta: 'Ejecutada'           },
  { valor: 'pendiente',         etiqueta: 'Pendiente'           },
  { valor: 'en_curso',          etiqueta: 'En curso'            },
  { valor: 'fallida',           etiqueta: 'Fallida'             },
  { valor: 'solicitud_borrado', etiqueta: 'Borrado solicitado'  },
]

interface ConfirmState {
  mensaje: string
  destructivo?: boolean
  accion: () => void
}

const estiloInput: React.CSSProperties = {
  background:   TOKENS.surface,
  borderColor:  'rgba(157,78,221,0.35)',
  borderRadius: '10px',
}



/* ── Modal de detalle de comparativa ───────────────────────────────────── */
function DetalleComparativaModal({
  sesionId,
  token,
  onClose,
  onEliminada,
}: {
  sesionId:    number
  token:       string
  onClose:     () => void
  onEliminada: () => void
}) {
  const [confirmandoBorrar, setConfirmandoBorrar] = useState(false)
  const [visorSrc,         setVisorSrc]         = useState<string | null>(null)
  const [visorFallbackSrc, setVisorFallbackSrc] = useState<string | undefined>(undefined)
  const [svgMap,           setSvgMap]           = useState<Record<number, string>>({})
  const [mapaMentalSvg,    setMapaMentalSvg]    = useState<string | null>(null)
  // ADR-029: estado de cada acordeon "Ver respuesta en ingles" indexado
  // por id de la respuesta ES (la EN se localiza por proveedor en runtime).
  const [verEn,            setVerEn]            = useState<Record<number, boolean>>({})
  // Toggle ampliado/comprimido del texto EN. Doble-clic sobre el texto o
  // clic en el boton inferior alterna el estado por respuesta.
  const [ampliadoEn,       setAmpliadoEn]       = useState<Record<number, boolean>>({})
  // Mismo toggle para el texto ES de cada respuesta: el admin tambien necesita
  // poder ampliar la respuesta en castellano dentro del modal "Ver".
  const [ampliadoEs,       setAmpliadoEs]       = useState<Record<number, boolean>>({})
  const mostrarToast = useToastStore((s) => s.mostrar)

  const abrirMapaMental = (svg: string) => setMapaMentalSvg(svg)

  const { data, isLoading, isError } = useQuery<SesionBenchmark>({
    queryKey: ['detalle-comparativa', sesionId],
    queryFn:  () => obtenerEvaluacion(sesionId),
  })

  const { data: evaluaciones } = useQuery({
    queryKey: ['evaluaciones-detalle', sesionId],
    queryFn:  () => obtenerEvaluacionesPorEvaluacion(sesionId),
  })

  const filasEval = [...(evaluaciones ?? [])]
    .sort((a, b) => (a.rango_preferencia ?? 99) - (b.rango_preferencia ?? 99))
    .map((ev) => {
      const resp = data?.respuestas.find((r) => r.id === ev.response_id)
      const info = resp
        ? (PROV_INFO[resp.proveedor] ?? { nombre: resp.proveedor, color: '#888' })
        : { nombre: 'Desconocido', color: '#888' }
      return { ev, info }
    })

  const mutEliminar = useMutation({
    mutationFn: () => eliminarEvaluacion(token, sesionId),
    onSuccess: () => {
      mostrarToast('Comparativa eliminada', 'exito')
      onClose()
      onEliminada()
    },
    onError: () => mostrarToast('Error al eliminar la comparativa', 'error'),
  })

  // Cerrar con Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <>
    {/* Visor imagen */}
    {visorSrc && (
      <VisorImagen src={visorSrc} fallbackSrc={visorFallbackSrc} onClose={() => setVisorSrc(null)} />
    )}

    {/* Lightbox mapa mental */}
    {mapaMentalSvg && (
      <VisorMapaMental svg={mapaMentalSvg} onClose={() => setMapaMentalSvg(null)} />
    )}

    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.72)' }}
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-4xl rounded-card border border-border shadow-card-lg flex flex-col bg-surface"
        style={{ maxHeight: '90vh' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Cabecera */}
        <div className="flex items-start justify-between gap-3 px-5 py-4 border-b border-border flex-shrink-0">
          <div className="min-w-0">
            <p className="text-sm font-semibold">
              Comparativa #{sesionId}
            </p>
            {data && (
              <p className="text-xs text-muted mt-0.5 line-clamp-2 leading-snug">{data.prompt}</p>
            )}
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {data && (
              <span className="text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5
                               rounded-full bg-primary-l text-primary">
                {data.categoria}
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

        {/* Metadatos */}
        {data && (
          <div className="px-5 py-2.5 border-b border-border flex flex-wrap gap-x-4 gap-y-1
                          text-xs text-muted flex-shrink-0">
            <span><span className="text-text font-medium">Nick: </span>@{data.nickname ?? '—'}</span>
            <span><span className="text-text font-medium">Fecha: </span>{formatFecha(data.created_at)}</span>
            <span className={ESTADO_COLOR[data.estado as SessionStatus] ?? 'text-muted'}>
              <span className="text-text font-medium">Estado: </span>
              {ESTADO_LABEL[data.estado as SessionStatus] ?? data.estado}
            </span>
            {data.similitud_jaccard_media != null && (
              <span>
                <span className="text-text font-medium">Jaccard: </span>
                {(data.similitud_jaccard_media * 100).toFixed(1)}%
              </span>
            )}
          </div>
        )}

        {/* Cuerpo con scroll */}
        <div className="px-5 py-4 overflow-y-auto flex-1">
          {isLoading && (
            <p className="text-muted text-sm text-center py-10 animate-pulse">Cargando respuestas...</p>
          )}
          {isError && (
            <p className="text-red-400 text-sm text-center py-10">Error al cargar el detalle.</p>
          )}

          {/* Evaluacion del usuario — vista solo lectura igual que EvalViewModal */}
          {filasEval.length > 0 && (
            <div className="space-y-2 pb-3 border-b border-border mb-3">
              <p className="text-xs text-muted font-semibold uppercase tracking-wider">
                Evaluacion del usuario
              </p>
              {filasEval.map(({ ev, info }, idx) => (
                <div
                  key={ev.id}
                  className="flex items-center gap-3 rounded-[10px] px-3 py-2.5 border border-border"
                  style={{ background: TOKENS.depth }}
                >
                  <span className="text-base font-extrabold text-muted w-6 flex-shrink-0 text-center">
                    {idx + 1}º
                  </span>
                  <span
                    className="w-2 h-2 rounded-full flex-shrink-0"
                    style={{ backgroundColor: info.color }}
                  />
                  <span
                    className="text-sm font-semibold flex-1 min-w-0 truncate"
                    style={{ color: info.color }}
                  >
                    {info.nombre}
                  </span>
                  <StarRating valor={ev.rating} onChange={() => {}} disabled />
                </div>
              ))}
            </div>
          )}

          {data && (() => {
            // ADR-029: en evaluaciones bilingues data.respuestas trae 8 filas
            // (4 ES + 4 EN). El grid principal del admin solo muestra las ES
            // y enchufa la respuesta EN en un acordeon dentro de cada tarjeta,
            // igual que la vista de usuario.
            const respuestasEs = data.respuestas.filter((r) => r.idioma_prompt === 'es')
            const respuestasEn = data.respuestas.filter((r) => r.idioma_prompt === 'en')
            return (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {respuestasEs.map((r) => {
                const color = PROV_INFO[r.proveedor]?.color ?? '#8B949E'
                const respEn = respuestasEn.find((x) => x.proveedor === r.proveedor)
                return (
                  <div
                    key={r.id}
                    className="rounded-card p-4 space-y-2.5 flex flex-col"
                    style={{ border: `1.5px solid ${color}40`, background: `${color}0a` }}
                  >
                    {/* Nombre del modelo */}
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-semibold" style={{ color }}>
                        {r.modelo ?? r.proveedor}
                      </span>
                      {r.tuvo_error && (
                        <span className="text-[10px] font-bold text-red-400 bg-red-400/10
                                         px-1.5 py-0.5 rounded-full">Error</span>
                      )}
                    </div>

                    {/* Metricas clave */}
                    {!r.tuvo_error && (
                      <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-muted">
                        <span>{r.latencia_ms} ms</span>
                        <span>{r.tokens_por_segundo.toFixed(1)} tok/s</span>
                        <span>${r.cost_usd.toFixed(8)}</span>
                        <span>{r.palabras} pal.</span>
                      </div>
                    )}

                    {/* Contenido: miniatura si es imagen, texto si es texto */}
                    <div className="border-t border-border pt-2.5 mt-0.5 flex-1">
                      {r.tuvo_error ? (
                        esCensura(r.mensaje_error) ? (
                          <div className="flex flex-col items-center justify-center gap-2 py-4 text-center">
                            <span className="text-3xl">🚫</span>
                            <p className="text-xs font-semibold text-red-400">Politica de seguridad</p>
                            <p className="text-[10px] text-muted leading-snug">
                              Este modelo rechazo el prompt por sus filtros de contenido.
                            </p>
                          </div>
                        ) : (
                          <div className="flex items-start gap-1.5 text-red-400">
                            <span className="flex-shrink-0 mt-0.5 text-xs">⚠</span>
                            <p className="text-xs italic">{r.mensaje_error ?? 'Sin detalle del error'}</p>
                          </div>
                        )
                      ) : r.es_imagen ? (
                        (r.url_imagen || r.imagen_miniatura) ? (
                          <div className="flex flex-col items-center gap-2">
                            <img
                              src={r.url_imagen ?? `data:image/jpeg;base64,${r.imagen_miniatura}`}
                              alt={`Imagen generada por ${r.proveedor}`}
                              className="rounded-lg object-cover mx-auto cursor-pointer"
                              style={{ width: 160, height: 160 }}
                              onError={(e) => {
                                if (r.imagen_miniatura)
                                  (e.target as HTMLImageElement).src = `data:image/jpeg;base64,${r.imagen_miniatura}`
                              }}
                              onDoubleClick={() => {
                                const fb = r.url_imagen && r.imagen_miniatura ? `data:image/jpeg;base64,${r.imagen_miniatura}` : undefined
                                setVisorFallbackSrc(fb)
                                setVisorSrc(r.url_imagen ?? `data:image/jpeg;base64,${r.imagen_miniatura!}`)
                              }}
                            />
                            <BtnAmpliar onClick={() => {
                              const fb = r.url_imagen && r.imagen_miniatura ? `data:image/jpeg;base64,${r.imagen_miniatura}` : undefined
                              setVisorFallbackSrc(fb)
                              setVisorSrc(r.url_imagen ?? `data:image/jpeg;base64,${r.imagen_miniatura!}`)
                            }}>
                              ⤢ Ampliar imagen
                            </BtnAmpliar>
                          </div>
                        ) : (
                          <span className="text-xs text-muted italic">Vista previa no disponible</span>
                        )
                      ) : (() => {
                        const mapaMental = extraerMapaMental(r.texto_respuesta)
                        return mapaMental ? (
                          <div className="space-y-1.5">
                            <div className="w-full overflow-hidden rounded-lg cursor-pointer" style={{ height: 160 }}
                                 onDoubleClick={() => svgMap[r.id] && abrirMapaMental(svgMap[r.id])}>
                              <MapaMentalDiagram
                                codigo={mapaMental}
                                onSvgReady={(svg) => setSvgMap((p) => ({ ...p, [r.id]: svg }))}
                              />
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
                                className="text-xs text-text leading-relaxed"
                                style={{
                                  maxHeight: ampliado ? undefined : (textLargoEs ? '200px' : undefined),
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

                    {/* ADR-029: acordeon con la respuesta EN paralela. Solo
                        existe en evaluaciones bilingues (razonamiento, creativa,
                        concretas con prompt predefinido). El admin la consulta
                        del mismo modo que el evaluador. */}
                    {respEn && (
                      <div className="border-t border-border pt-2.5">
                        <BotonVerEn
                          color={color}
                          abierto={!!verEn[r.id]}
                          onClick={() => setVerEn((p) => ({ ...p, [r.id]: !p[r.id] }))}
                        />
                        {verEn[r.id] && (() => {
                          const textLargoEn = (respEn.palabras ?? 0) > 60
                          const ampliado = !!ampliadoEn[r.id]
                          return (
                            <div className="mt-2 space-y-1.5">
                              {!respEn.tuvo_error && (
                                <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-muted">
                                  <span>{respEn.latencia_ms} ms</span>
                                  <span>{respEn.tokens_por_segundo.toFixed(1)} tok/s</span>
                                  <span>${respEn.cost_usd.toFixed(8)}</span>
                                  <span>{respEn.palabras} pal.</span>
                                </div>
                              )}
                              {respEn.tuvo_error ? (
                                <p className="text-[11px] text-red-400 italic">
                                  {respEn.mensaje_error ?? 'Error técnico'}
                                </p>
                              ) : (
                                <>
                                  <p
                                    className="text-[11px] text-text leading-relaxed whitespace-pre-wrap"
                                    style={{
                                      maxHeight: ampliado ? undefined : (textLargoEn ? '140px' : undefined),
                                      overflow: ampliado ? 'visible' : (textLargoEn ? 'hidden' : 'visible'),
                                      wordBreak: 'break-word',
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
            )
          })()}
        </div>

        {/* Pie — botón eliminar */}
        <div className="px-5 py-3 border-t border-border flex items-center justify-between
                        gap-3 flex-shrink-0">
          {!confirmandoBorrar ? (
            <>
              <button
                className="text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors
                           text-red-400 hover:text-red-300 hover:bg-red-400/10 border
                           border-red-400/40 hover:border-red-300/60"
                onClick={() => setConfirmandoBorrar(true)}
                disabled={mutEliminar.isPending}
              >
                Eliminar comparativa
              </button>
              <button className="btn-ghost text-xs" onClick={onClose}>
                Cerrar
              </button>
            </>
          ) : (
            <>
              <p className="text-xs text-red-400 font-medium">
                ¿Eliminar la comparativa #{sesionId}? Esta acción es irreversible.
              </p>
              <div className="flex gap-2 flex-shrink-0">
                <button
                  className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-red-500
                             hover:bg-red-400 text-white transition-colors"
                  onClick={() => mutEliminar.mutate()}
                  disabled={mutEliminar.isPending}
                >
                  {mutEliminar.isPending ? 'Eliminando…' : 'Confirmar'}
                </button>
                <button
                  className="btn-ghost text-xs"
                  onClick={() => setConfirmandoBorrar(false)}
                  disabled={mutEliminar.isPending}
                >
                  Cancelar
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
    </>
  )
}

/* ── Componente principal ───────────────────────────────────────────────── */
export default function TablaAdmin({ token }: Props) {
  const [pagina, setPagina] = useState(1)
  const queryClient = useQueryClient()
  const mostrarToast = useToastStore((s) => s.mostrar)
  // Nick del actor actual (admin root o promovido). Solo el dueño de
  // una evaluación puede valorarla — el backend ya devuelve 403 si no
  // coincide; aquí ocultamos el botón "Evaluar" cuando el admin
  // visualiza evaluaciones de otro nickname para no exponer una
  // acción que fallaría.
  const nickActual = useNickStore((s) => s.nick)

  /* ── Modal de confirmacion ── */
  const [confirmando, setConfirmando] = useState<ConfirmState | null>(null)
  const confirmar    = (cfg: ConfirmState) => setConfirmando(cfg)
  const cerrarConfirm = () => setConfirmando(null)

  /* ── Modal de detalle ── */
  const [verDetalleId,  setVerDetalleId]  = useState<number | null>(null)
  /* ── Modal de evaluacion (admin puede evaluar igual que usuario) ── */
  const [verEvaluarId,  setVerEvaluarId]  = useState<number | null>(null)

  /* ── Filtros ── */
  const [filtroNick,       setFiltroNick]       = useState('')
  const [filtroCat,        setFiltroCat]        = useState<TestCategory | ''>('')
  const [filtroPrompt,     setFiltroPrompt]     = useState('')
  const [filtroEstado,     setFiltroEstado]     = useState<SessionStatus | ''>('')
  const [filtroFechaDesde, setFiltroFechaDesde] = useState('')
  const [filtroFechaHasta, setFiltroFechaHasta] = useState('')
  const [filtroValoracion, setFiltroValoracion] = useState<'' | 'sin_valorar' | 'valorada'>('')

  const hayFiltros = filtroNick || filtroCat || filtroPrompt || filtroEstado || filtroFechaDesde || filtroFechaHasta || filtroValoracion

  const nFiltrosActivos = [filtroNick, filtroCat, filtroPrompt, filtroEstado, filtroValoracion, filtroFechaDesde, filtroFechaHasta]
    .filter(Boolean).length

  /* ── Seleccion multiple ── */
  const [seleccionados, setSeleccionados] = useState<Set<number>>(new Set())

  /* ── Queries y mutaciones ── */
  const filtrosActivos: FiltrosAdmin = {
    nick:       filtroNick       || undefined,
    categoria:  (filtroCat       || undefined) as FiltrosAdmin['categoria'],
    prompt:     filtroPrompt     || undefined,
    estado:     (filtroEstado    || undefined) as FiltrosAdmin['estado'],
    valoracion: (filtroValoracion || undefined) as FiltrosAdmin['valoracion'],
    fechaDesde: filtroFechaDesde || undefined,
    fechaHasta: filtroFechaHasta || undefined,
  }

  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin-comparativas', pagina, filtrosActivos],
    queryFn:  () => listarEvaluacionesAdmin(token, pagina, LIMITE, filtrosActivos),
    placeholderData: (prev) => prev,
  })

  // Contador de solicitudes de borrado pendientes para el badge de alerta
  const { data: dataSolicitudes } = useQuery({
    queryKey: ['admin-solicitudes-borrado'],
    queryFn:  () => listarEvaluacionesAdmin(token, 1, 1, { estado: 'solicitud_borrado' }),
    refetchInterval: 60_000,
  })
  const nSolicitudesBorrado = dataSolicitudes?.total ?? 0

  const mutEliminar = useMutation({
    mutationFn: (id: number) => eliminarEvaluacion(token, id),
    onSuccess: () => {
      setSeleccionados(new Set())
      queryClient.invalidateQueries({ queryKey: ['admin-comparativas'] })
      queryClient.invalidateQueries({ queryKey: ['admin-solicitudes-borrado'] })
      mostrarToast('Comparativa eliminada', 'exito')
    },
    onError: () => mostrarToast('Error al eliminar la comparativa', 'error'),
  })

  const mutRechazar = useMutation({
    mutationFn: (id: number) => rechazarBorradoEvaluacion(token, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-comparativas'] })
      queryClient.invalidateQueries({ queryKey: ['admin-solicitudes-borrado'] })
      mostrarToast('Solicitud de borrado rechazada — evaluación restaurada', 'info')
    },
    onError: () => mostrarToast('Error al rechazar la solicitud', 'error'),
  })

  const mutReset = useMutation({
    mutationFn: () => eliminarTodasLasEvaluaciones(token),
    onSuccess: () => {
      setPagina(1)
      setSeleccionados(new Set())
      queryClient.invalidateQueries({ queryKey: ['admin-comparativas'] })
      queryClient.invalidateQueries({ queryKey: ['admin-solicitudes-borrado'] })
      mostrarToast('Estudio reiniciado — todas las comparativas eliminadas', 'exito')
    },
    onError: () => mostrarToast('Error al reiniciar el estudio', 'error'),
  })

  // Mutacion de descarga CSV: usa los filtros activos para que el export
  // refleje exactamente lo que el admin ve filtrado en la tabla.
  const mutExportCsv = useMutation({
    mutationFn: () => exportarEvaluacionesCsvAdmin(token, filtrosActivos),
    onSuccess: ({ blob, nombre }) => {
      const url = URL.createObjectURL(blob)
      const enlace = document.createElement('a')
      enlace.href = url
      enlace.download = nombre
      document.body.appendChild(enlace)
      enlace.click()
      enlace.remove()
      URL.revokeObjectURL(url)
      const total = data?.total ?? 0
      mostrarToast(
        hayFiltros
          ? `CSV exportado (${total} evaluacion${total !== 1 ? 'es' : ''} con filtros aplicados)`
          : `CSV exportado (${total} evaluacion${total !== 1 ? 'es' : ''})`,
        'exito',
      )
    },
    onError: () => mostrarToast('Error al exportar el CSV', 'error'),
  })

  /* ── Filtrado en servidor — items ya filtrados y paginados ── */
  const itemsFiltrados: ResumenEvaluacionAdmin[] = data?.items ?? []

  /* ── Helpers de seleccion ── */
  const toggleSeleccion = (id: number) => {
    setSeleccionados((prev) => {
      const sig = new Set(prev)
      if (sig.has(id)) { sig.delete(id) } else { sig.add(id) }
      return sig
    })
  }

  const seleccionarTodos = () => {
    const todosIds = new Set(itemsFiltrados.map((s) => s.id))
    setSeleccionados((prev) => prev.size === todosIds.size ? new Set() : todosIds)
  }

  const eliminarSeleccionados = () => {
    confirmar({
      mensaje: `Eliminar ${seleccionados.size} comparativa${seleccionados.size !== 1 ? 's' : ''} seleccionada${seleccionados.size !== 1 ? 's' : ''}?`,
      destructivo: true,
      accion: () => seleccionados.forEach((id) => mutEliminar.mutate(id)),
    })
  }

  const limpiarFiltros = () => {
    setFiltroNick('')
    setFiltroCat('')
    setFiltroPrompt('')
    setFiltroEstado('')
    setFiltroFechaDesde('')
    setFiltroFechaHasta('')
    setFiltroValoracion('')
  }

  return (
    <div className="space-y-4">

      {/* Cabecera admin */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h2 className="text-base font-semibold flex items-center gap-2 flex-wrap">
          Panel de administración
          {nSolicitudesBorrado > 0 && (
            <button
              className="text-[10px] font-bold px-2.5 py-0.5 rounded-full cursor-pointer"
              style={{ color: TOKENS.cat7, background: 'rgba(251,146,60,0.15)',
                       border: '1px solid rgba(251,146,60,0.5)' }}
              title="Ver evaluaciones con solicitud de borrado"
              onClick={() => {
                setFiltroEstado('solicitud_borrado')
                setPagina(1)
              }}
            >
              ⚠ {nSolicitudesBorrado} solicitud{nSolicitudesBorrado !== 1 ? 'es' : ''} de borrado
            </button>
          )}
          {data && (
            <span className="text-xs text-muted font-normal">
              ({data.total} comparativa{data.total !== 1 ? 's' : ''})
            </span>
          )}
        </h2>
        <div className="flex gap-2">
          <button
            className="text-xs font-semibold px-2.5 py-1 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            style={{
              color:      TOKENS.cat4,
              background: 'rgba(52,211,153,0.10)',
              border:     '1px solid rgba(52,211,153,0.35)',
            }}
            onClick={() => mutExportCsv.mutate()}
            disabled={mutExportCsv.isPending || (data?.total ?? 0) === 0}
            title={
              hayFiltros
                ? 'Descargar CSV con los filtros aplicados'
                : 'Descargar CSV con todas las evaluaciones del estudio'
            }
          >
            {mutExportCsv.isPending ? 'Exportando…' : '📥 Exportar CSV'}
          </button>
          <button
            className="btn-ghost text-xs text-red-400 hover:text-red-300"
            onClick={() => confirmar({
              mensaje: '¿Eliminar TODAS las comparativas del estudio? Esta acción es irreversible.',
              destructivo: true,
              accion: () => mutReset.mutate(),
            })}
            disabled={mutReset.isPending}
          >
            Reset estudio
          </button>
        </div>
      </div>

      {/* Panel de filtros */}
      <div className="bg-primary-l border border-primary/25 rounded-card px-5 py-4 space-y-4">

        {/* Cabecera del panel */}
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted">Filtros</span>
            {nFiltrosActivos > 0 && (
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-primary/20 text-primary">
                {nFiltrosActivos} activo{nFiltrosActivos !== 1 ? 's' : ''}
              </span>
            )}
            {data && hayFiltros && (
              <span className="text-[10px] text-muted">
                — {data.total} resultado{data.total !== 1 ? 's' : ''}
              </span>
            )}
          </div>
          <button
            className={`text-xs font-semibold transition-colors flex items-center gap-1 ${
              hayFiltros
                ? 'text-red-400 hover:text-red-300'
                : 'text-muted/30 cursor-default pointer-events-none'
            }`}
            onClick={limpiarFiltros}
            disabled={!hayFiltros}
          >
            ✕ Limpiar filtros
          </button>
        </div>

        {/* Primera fila: busquedas de texto */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="space-y-1">
            <label className="text-[10px] text-muted font-medium uppercase tracking-wide">Nick</label>
            <input
              type="text"
              className="input-base text-xs py-1.5 w-full"
              style={estiloInput}
              placeholder="Buscar por nick…"
              value={filtroNick}
              onChange={(e) => { setFiltroNick(e.target.value); setPagina(1) }}
            />
          </div>
          <div className="space-y-1">
            <label className="text-[10px] text-muted font-medium uppercase tracking-wide">Categoría</label>
            <select
              className="input-base text-xs py-1.5 w-full"
              style={estiloInput}
              value={filtroCat}
              onChange={(e) => { setFiltroCat(e.target.value as TestCategory | ''); setPagina(1) }}
            >
              {CATEGORIAS_OPC.map((o) => (
                <option key={o.valor} value={o.valor}>{o.etiqueta}</option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-[10px] text-muted font-medium uppercase tracking-wide">Prompt</label>
            <input
              type="text"
              className="input-base text-xs py-1.5 w-full"
              style={estiloInput}
              placeholder="Buscar en el prompt…"
              value={filtroPrompt}
              onChange={(e) => { setFiltroPrompt(e.target.value); setPagina(1) }}
            />
          </div>
        </div>

        {/* Segunda fila: estados y fechas */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="space-y-1">
            <label className="text-[10px] text-muted font-medium uppercase tracking-wide">Estado ejecución</label>
            <select
              className="input-base text-xs py-1.5 w-full"
              style={estiloInput}
              value={filtroEstado}
              onChange={(e) => { setFiltroEstado(e.target.value as SessionStatus | ''); setPagina(1) }}
            >
              {ESTADO_OPC.map((o) => (
                <option key={o.valor} value={o.valor}>{o.etiqueta}</option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-[10px] text-muted font-medium uppercase tracking-wide">Estado valoración</label>
            <select
              className="input-base text-xs py-1.5 w-full"
              style={estiloInput}
              value={filtroValoracion}
              onChange={(e) => { setFiltroValoracion(e.target.value as '' | 'sin_valorar' | 'valorada'); setPagina(1) }}
            >
              <option value="">Todas las valoraciones</option>
              <option value="sin_valorar">Sin valorar</option>
              <option value="valorada">Valorada</option>
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-[10px] text-muted font-medium uppercase tracking-wide">Desde (fecha y hora)</label>
            <DateTimePicker
              value={filtroFechaDesde}
              onChange={(v) => { setFiltroFechaDesde(v); setPagina(1) }}
              ariaLabel="Filtro fecha y hora desde"
            />
          </div>
          <div className="space-y-1">
            <label className="text-[10px] text-muted font-medium uppercase tracking-wide">Hasta (fecha y hora)</label>
            <DateTimePicker
              value={filtroFechaHasta}
              onChange={(v) => { setFiltroFechaHasta(v); setPagina(1) }}
              ariaLabel="Filtro fecha y hora hasta"
            />
          </div>
        </div>

      </div>

      {/* Batch-bar */}
      {seleccionados.size > 0 && (
        <div className="rounded-card px-4 py-2.5 flex items-center justify-between gap-3"
             style={{ background: 'rgba(157,78,221,0.10)', border: '1px solid rgba(157,78,221,0.3)' }}>
          <span className="text-xs text-primary font-semibold">
            {seleccionados.size} comparativa{seleccionados.size !== 1 ? 's' : ''} seleccionada{seleccionados.size !== 1 ? 's' : ''}
          </span>
          <div className="flex gap-2">
            <button
              className="btn-ghost text-xs text-red-400 hover:text-red-300"
              onClick={eliminarSeleccionados}
              disabled={mutEliminar.isPending}
            >
              Eliminar seleccionadas
            </button>
            <button className="btn-ghost text-xs" onClick={() => setSeleccionados(new Set())}>
              Cancelar
            </button>
          </div>
        </div>
      )}

      {isLoading && (
        <div className="card p-8 flex items-center justify-center">
          <p className="text-muted animate-pulse">Cargando comparativas...</p>
        </div>
      )}
      {isError && (
        <div className="card p-8 flex items-center justify-center">
          <p className="text-red-400">Error al cargar. El token puede haber expirado.</p>
        </div>
      )}

      {data && (
        <>
          {/* Tabla */}
          <div className="card overflow-x-auto">
            <table className="w-full text-sm min-w-[860px]">
              <thead>
                <tr className="border-b border-border text-xs text-muted uppercase tracking-wider">
                  <th className="px-3 py-3 w-8">
                    <input
                      type="checkbox"
                      checked={seleccionados.size === itemsFiltrados.length && itemsFiltrados.length > 0}
                      onChange={seleccionarTodos}
                      className="cursor-pointer accent-primary"
                    />
                  </th>
                  <th className="px-3 py-3 text-left w-12">#</th>
                  <th className="px-3 py-3 text-left w-24">Nick</th>
                  <th className="px-3 py-3 text-left w-48">Prompt</th>
                  <th className="px-3 py-3 text-left w-24">Categoría</th>
                  <th className="px-3 py-3 text-left w-20">Estado</th>
                  <th className="px-3 py-3 text-left w-28">Estado Valoración</th>
                  <th className="px-3 py-3 text-left w-44">Fecha</th>
                  <th className="px-3 py-3 text-left w-36">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {itemsFiltrados.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="px-4 py-8 text-center text-muted text-xs">
                      {hayFiltros ? 'Sin resultados para los filtros aplicados.' : 'No hay comparativas.'}
                    </td>
                  </tr>
                ) : (
                  itemsFiltrados.map((s) => (
                    <tr key={s.id}
                        className={`transition-colors ${
                          seleccionados.has(s.id)
                            ? 'bg-primary-l/40'
                            : s.estado === 'solicitud_borrado'
                              ? 'bg-orange-400/10 hover:bg-orange-400/20'
                              : 'hover:bg-primary-l/20'
                        }`}>
                      <td className="px-3 py-3">
                        <input
                          type="checkbox"
                          checked={seleccionados.has(s.id)}
                          onChange={() => toggleSeleccion(s.id)}
                          className="cursor-pointer accent-primary"
                        />
                      </td>
                      <td className="px-3 py-3 font-mono text-xs text-muted">{s.id}</td>
                      <td className="px-3 py-3 text-xs">@{s.nickname}</td>
                      <td className="px-3 py-3 text-xs text-muted max-w-0 truncate">{s.prompt}</td>
                      <td className="px-3 py-3">
                        <span
                          className="text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full whitespace-nowrap"
                          style={{
                            color:      COLOR_CAT[s.categoria] ?? '#8B949E',
                            background: `${COLOR_CAT[s.categoria] ?? '#8B949E'}20`,
                            border:     `1px solid ${COLOR_CAT[s.categoria] ?? '#8B949E'}40`,
                          }}
                        >
                          {s.categoria}
                        </span>
                      </td>
                      <td className={`px-3 py-3 text-xs font-medium ${ESTADO_COLOR[s.estado] ?? 'text-muted'}`}>
                        {ESTADO_LABEL[s.estado] ?? s.estado}
                      </td>
                      <td className="px-3 py-3">
                        {s.estado === 'completada' ? (
                          s.evaluada ? (
                            <span
                              className="text-xs font-semibold px-2.5 py-1 rounded-full whitespace-nowrap"
                              style={{
                                color: '#4ade80',
                                background: 'rgba(74,222,128,0.12)',
                                border: '1px solid rgba(74,222,128,0.5)',
                              }}
                            >
                              ● Valorada
                            </span>
                          ) : s.nickname === nickActual ? (
                            <button
                              className="text-xs font-semibold px-2.5 py-1 rounded-full animate-pulse whitespace-nowrap"
                              style={{
                                color: '#FF0000',
                                background: 'rgba(255,0,0,0.15)',
                                border: '1px solid rgba(255,0,0,0.6)',
                              }}
                              onClick={() => setVerEvaluarId(s.id)}
                              title="Completar evaluación (eres el propietario)"
                            >
                              ● Sin valorar
                            </button>
                          ) : (
                            <button
                              className="text-xs font-semibold px-2.5 py-1 rounded-full whitespace-nowrap cursor-not-allowed"
                              style={{
                                color: 'rgba(192,188,220,0.85)',
                                background: 'rgba(192,188,220,0.08)',
                                border: '1px solid rgba(192,188,220,0.30)',
                              }}
                              onClick={() => mostrarToast(
                                `Solo el propietario @${s.nickname} puede valorar esta evaluación.`,
                                'error',
                              )}
                              title={`Solo @${s.nickname} puede valorar esta evaluación`}
                            >
                              ● Sin valorar
                            </button>
                          )
                        ) : (
                          <span className="text-xs text-muted">—</span>
                        )}
                      </td>
                      <td className="px-3 py-3 text-xs text-muted font-mono whitespace-nowrap">
                        {formatFecha(s.created_at)}
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex items-center justify-start gap-2 whitespace-nowrap">
                          <button
                            className="text-primary hover:text-primary/80 text-xs transition-colors font-medium"
                            onClick={() => setVerDetalleId(s.id)}
                            title="Ver comparativa"
                          >
                            Ver
                          </button>
                          {s.estado === 'completada' && !s.evaluada && s.nickname === nickActual && (
                            <button
                              className="text-yellow-400 hover:text-yellow-300 text-xs transition-colors font-medium"
                              onClick={() => setVerEvaluarId(s.id)}
                              title="Completar evaluación (eres el propietario)"
                            >
                              Evaluar
                            </button>
                          )}
                          {s.estado === 'completada' && !s.evaluada && s.nickname !== nickActual && (
                            <span
                              className="text-[11px] text-muted/70 italic"
                              title="Solo el propietario de la evaluación puede valorarla"
                            >
                              sin valorar
                            </span>
                          )}
                          {s.estado === 'completada' && s.evaluada && (
                            <button
                              className="text-green-400 hover:text-green-300 text-xs transition-colors font-medium"
                              onClick={() => setVerEvaluarId(s.id)}
                              title="Ver evaluación"
                            >
                              Eval
                            </button>
                          )}
                          {s.estado === 'solicitud_borrado' && (
                            <button
                              className="text-xs font-medium transition-colors"
                              style={{ color: TOKENS.cat7 }}
                              onClick={() => confirmar({
                                mensaje: `Rechazar la solicitud de borrado de la evaluación #${s.id} (@${s.nickname})? La evaluación volverá a estado completada.`,
                                accion: () => mutRechazar.mutate(s.id),
                              })}
                              disabled={mutRechazar.isPending}
                              title="Rechazar solicitud de borrado y restaurar evaluación"
                            >
                              Rechazar
                            </button>
                          )}
                          <button
                            className="text-red-400 hover:text-red-300 text-xs transition-colors"
                            onClick={() => confirmar({
                              mensaje: `Eliminar la comparativa #${s.id}?`,
                              destructivo: true,
                              accion: () => mutEliminar.mutate(s.id),
                            })}
                            disabled={mutEliminar.isPending}
                            title="Eliminar comparativa"
                          >
                            ✕
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Paginacion */}
          {data.paginas > 1 && (
            <div className="flex items-center justify-center gap-1.5">
              <button className="btn-ghost text-xs px-3" onClick={() => setPagina(1)} disabled={pagina === 1}>«</button>
              <button className="btn-ghost text-xs" onClick={() => setPagina((p) => Math.max(1, p - 1))} disabled={pagina === 1}>
                ← Anterior
              </button>
              {Array.from({ length: data.paginas }, (_, i) => i + 1)
                .filter((n) => n === 1 || n === data.paginas || Math.abs(n - pagina) <= 1)
                .reduce<(number | '…')[]>((acc, n, i, arr) => {
                  if (i > 0 && n - (arr[i - 1] as number) > 1) acc.push('…')
                  acc.push(n)
                  return acc
                }, [])
                .map((n, i) =>
                  n === '…' ? (
                    <span key={`dots-${i}`} className="text-xs text-muted px-1">…</span>
                  ) : (
                    <button
                      key={n}
                      className={`text-xs px-2.5 py-1 rounded-lg transition-colors ${
                        pagina === n ? 'bg-primary text-white font-bold' : 'btn-ghost'
                      }`}
                      onClick={() => setPagina(n as number)}
                    >
                      {n}
                    </button>
                  )
                )}
              <button className="btn-ghost text-xs" onClick={() => setPagina((p) => Math.min(data.paginas, p + 1))} disabled={pagina === data.paginas}>
                Siguiente →
              </button>
              <button className="btn-ghost text-xs px-3" onClick={() => setPagina(data.paginas)} disabled={pagina === data.paginas}>»</button>
            </div>
          )}
        </>
      )}

      {/* Modal de detalle de comparativa */}
      {verDetalleId !== null && (
        <DetalleComparativaModal
          sesionId={verDetalleId}
          token={token}
          onClose={() => setVerDetalleId(null)}
          onEliminada={() => {
            setVerDetalleId(null)
            setSeleccionados(new Set())
            queryClient.invalidateQueries({ queryKey: ['admin-comparativas'] })
          }}
        />
      )}

      {/* Modal de evaluacion — admin puede evaluar o revisar igual que usuario */}
      {verEvaluarId !== null && (
        <EvalViewModal
          sesionId={verEvaluarId}
          onClose={() => setVerEvaluarId(null)}
          onEvaluated={() => {
            queryClient.invalidateQueries({ queryKey: ['admin-comparativas'] })
          }}
        />
      )}

      {confirmando && (
        <ConfirmModal
          mensaje={confirmando.mensaje}
          textoBotom="Eliminar"
          destructivo={confirmando.destructivo}
          onConfirmar={() => { confirmando.accion(); cerrarConfirm() }}
          onCancelar={cerrarConfirm}
        />
      )}
    </div>
  )
}

/**
 * Boton del acordeon "Ver respuesta en ingles" (ADR-029) con afordancia
 * visual dependiente del color del LLM. Identico al de BenchmarkCard y
 * EvalViewModal para que admin, evaluador inmediato y revision del
 * historial tengan la misma senalizacion.
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
