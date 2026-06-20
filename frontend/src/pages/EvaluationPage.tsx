/**
 * Componente: EvaluationPage
 * Ruta:       frontend/src/pages/EvaluationPage.tsx
 *
 * Descripcion:
 *   Pantalla de evaluacion humana de las respuestas LLM de una evaluacion.
 *   Carga la evaluacion por ID, permite reordenar las tarjetas con drag-and-drop
 *   (rango_preferencia) y puntuar con estrellas.
 *   Al guardar envia una evaluacion por cada respuesta LLM y navega al historial.
 *
 * Sprint: Sprint 3 — S3-07
 */

import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { DndContext, closestCenter, type DragEndEvent } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy, arrayMove } from '@dnd-kit/sortable'
import { useNickStore } from '@/store/nickStore'
import { useHistorialStore } from '@/store/historialStore'
import EvalCard from '@/components/evaluation/EvalCard'
import StarRating from '@/components/evaluation/StarRating'
import { obtenerEvaluacion } from '@/services/benchmarkApi'
import { crearEvaluacion, obtenerEvaluacionesPorEvaluacion } from '@/services/evaluacionApi'
import type { PeticionEvaluacion } from '@/types/evaluacion'
import { LLM_PROVIDERS_CONFIG } from '@/config/llmProviders'

export default function EvaluationPage() {
  const { evaluacionId }   = useParams<{ evaluacionId: string }>()
  const nick           = useNickStore((s) => s.nick)
  const navigate       = useNavigate()
  const marcarEvaluada = useHistorialStore((s) => s.marcarEvaluada)

  const { data: evaluacion, isLoading, isError } = useQuery({
    queryKey: ['evaluacion', evaluacionId],
    queryFn: () => obtenerEvaluacion(Number(evaluacionId)),
    enabled: !!evaluacionId,
  })

  const { data: evaluacionesPrevias, isLoading: cargandoEval } = useQuery({
    queryKey: ['evaluaciones-evaluacion', evaluacionId],
    queryFn: () => obtenerEvaluacionesPorEvaluacion(Number(evaluacionId)),
    enabled: !!evaluacionId,
  })

  const [orden,   setOrden]   = useState<number[]>([])
  const [ratings, setRatings] = useState<Record<number, number>>({})
  const [borradorRecuperado, setBorradorRecuperado] = useState(false)

  const inicializadoRef = useRef(false)

  useEffect(() => {
    if (!nick) navigate('/', { replace: true })
  }, [nick, navigate])

  useEffect(() => {
    if (!evaluacion || cargandoEval) return

    const evalMap = new Map((evaluacionesPrevias ?? []).map((e) => [e.response_id, e]))

    if (evalMap.size > 0) {
      const initR: Record<number, number> = {}
      evaluacion.respuestas.forEach((r) => {
        initR[r.id] = evalMap.get(r.id)?.rating ?? 0
      })
      setRatings(initR)
      const ordenado = [...evaluacion.respuestas].sort((a, b) => {
        const ra = evalMap.get(a.id)?.rango_preferencia ?? 999
        const rb = evalMap.get(b.id)?.rango_preferencia ?? 999
        return ra - rb
      })
      setOrden(ordenado.map((r) => r.id))
    } else {
      const claveLocal = `evalborrador-${evaluacionId}`
      const guardado   = localStorage.getItem(claveLocal)
      if (guardado) {
        try {
          const draft = JSON.parse(guardado) as {
            orden: number[]
            ratings: Record<number, number>
          }
          setOrden(draft.orden   ?? evaluacion.respuestas.map((r) => r.id))
          setRatings(draft.ratings ?? {})
          setBorradorRecuperado(true)
        } catch {
          const initR: Record<number, number> = {}
          evaluacion.respuestas.forEach((r) => { initR[r.id] = 0 })
          setRatings(initR)
          setOrden(evaluacion.respuestas.map((r) => r.id))
          localStorage.removeItem(claveLocal)
        }
      } else {
        const initR: Record<number, number> = {}
        evaluacion.respuestas.forEach((r) => { initR[r.id] = 0 })
        setRatings(initR)
        setOrden(evaluacion.respuestas.map((r) => r.id))
      }
    }

    inicializadoRef.current = true
  }, [evaluacion, evaluacionesPrevias, cargandoEval, evaluacionId])

  // Guardar borrador en localStorage al cambiar orden o ratings
  useEffect(() => {
    if (!inicializadoRef.current || orden.length === 0) return
    localStorage.setItem(
      `evalborrador-${evaluacionId}`,
      JSON.stringify({ orden, ratings }),
    )
  }, [orden, ratings, evaluacionId])

  const mutacion = useMutation({
    mutationFn: async () => {
      if (!evaluacion) return
      const errorMap = new Map(evaluacion.respuestas.map((r) => [r.id, r.tuvo_error]))
      let rangoExitosa = 0
      const peticiones: PeticionEvaluacion[] = orden.map((id) => {
        const esFallida = errorMap.get(id) ?? false
        if (!esFallida) rangoExitosa++
        return {
          response_id:       id,
          nickname:          nick,
          rating:            ratings[id] ?? 1,
          rango_preferencia: esFallida ? null : rangoExitosa,
        }
      })
      for (const p of peticiones) {
        await crearEvaluacion(p)
      }
    },
    onSuccess: () => {
      localStorage.removeItem(`evalborrador-${evaluacionId}`)
      if (evaluacionId) marcarEvaluada(nick, Number(evaluacionId))
      navigate('/historial')
    },
  })

  const onDragEnd = ({ active, over }: DragEndEvent) => {
    if (over && active.id !== over.id) {
      setOrden((prev) => {
        const de   = prev.indexOf(Number(active.id))
        const para = prev.indexOf(Number(over.id))
        return arrayMove(prev, de, para)
      })
    }
  }

  if (!nick) return null

  if (isLoading || cargandoEval) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-muted animate-pulse">Cargando evaluación...</p>
      </div>
    )
  }

  if (isError || !evaluacion) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-red-400">No se pudo cargar la evaluación #{evaluacionId}</p>
      </div>
    )
  }

  // Evaluacion fallida = bloqueada automaticamente por censura de contenido
  const esFallida = evaluacion.estado === 'fallida'

  const respuestasOrdenadas = orden
    .map((id) => evaluacion.respuestas.find((r) => r.id === id))
    .filter((r): r is NonNullable<typeof r> => r !== undefined)

  // Excluir errores del requisito de rating minimo 1
  const todosConRating = (() => {
    const evaluables = orden.filter((id) => {
      const r = evaluacion.respuestas.find((x) => x.id === id)
      return r && !r.tuvo_error
    })
    return evaluables.length > 0 && evaluables.every((id) => (ratings[id] ?? 0) >= 1)
  })()

  const puedeGuardar = todosConRating

  const yaEvaluada = (evaluacionesPrevias?.length ?? 0) > 0

  // ── Vista: evaluacion fallida por politica de contenido ───────────────────────
  if (esFallida) {
    return (
      <div className="max-w-3xl mx-auto space-y-5">
        <div className="card px-5 py-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-base font-semibold mb-1">
                Evaluación #{evaluacion.id}
              </h2>
              <p className="text-sm text-muted line-clamp-2">{evaluacion.prompt}</p>
            </div>
            <span className="text-xs bg-primary-l text-primary px-2 py-1 rounded-full whitespace-nowrap flex-shrink-0">
              {evaluacion.categoria}
            </span>
          </div>
        </div>

        <div className="card px-4 py-4 flex items-start gap-3 border-red-400/30"
             style={{ background: 'rgba(239,68,68,0.05)' }}>
          <span className="text-red-400 text-base flex-shrink-0">🚫</span>
          <div>
            <p className="text-sm font-semibold text-red-400 mb-1">
              Evaluación bloqueada por política de contenido
            </p>
            <p className="text-xs text-red-300 leading-snug">
              Uno o más modelos rechazaron el prompt por su política de seguridad.
              Esta evaluación ha sido registrada automáticamente como fallida y no
              computará en las métricas de calidad del dashboard.
              Solo aparecerá en la gráfica de restrictividad por modelo.
            </p>
          </div>
        </div>

        {/* Modelos con su estado */}
        <div className="space-y-2">
          {evaluacion.respuestas.map((r) => {
            const info = LLM_PROVIDERS_CONFIG[r.proveedor] ?? { nombre: r.proveedor, color: '#888', icono: '' }
            const censurado = r.tuvo_error
            return (
              <div key={r.id} className="card px-4 py-3 flex items-center gap-3">
                {censurado
                  ? <span className="text-red-400">🚫</span>
                  : <span className="text-green-400">✓</span>
                }
                <span className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                      style={{ backgroundColor: info.color }} />
                {info.icono && (
                  <img src={info.icono} alt={info.nombre}
                       className="w-[18px] h-[18px] rounded flex-shrink-0 select-none" />
                )}
                <span className="font-semibold text-sm flex-1 min-w-0 truncate"
                      style={{ color: info.color }}>
                  {info.nombre}
                </span>
                <span className={`text-[11px] font-medium ${censurado ? 'text-red-400' : 'text-green-400'}`}>
                  {censurado ? 'Política de seguridad' : 'Respondió correctamente'}
                </span>
              </div>
            )
          })}
        </div>

        <div className="flex justify-end">
          <button className="btn-ghost text-sm" onClick={() => navigate('/historial')}>
            Cerrar y volver al menú →
          </button>
        </div>
      </div>
    )
  }

  // ── Vista de solo lectura (evaluacion ya guardada) ─────────────────────────
  if (yaEvaluada) {
    const filasOrdenadas = [...(evaluacionesPrevias ?? [])]
      .sort((a, b) => (a.rango_preferencia ?? 99) - (b.rango_preferencia ?? 99))
      .map((ev) => {
        const resp = evaluacion.respuestas.find((r) => r.id === ev.response_id)
        const info = resp
          ? (LLM_PROVIDERS_CONFIG[resp.proveedor] ?? { nombre: resp.proveedor, color: '#888', icono: '' })
          : { nombre: 'Desconocido', color: '#888', icono: '' }
        return { ev, info }
      })

    return (
      <div className="max-w-3xl mx-auto space-y-5">
        <div className="card px-5 py-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-base font-semibold mb-1">
                Evaluación #{evaluacion.id}
              </h2>
              <p className="text-sm text-muted line-clamp-2">{evaluacion.prompt}</p>
            </div>
            <span className="text-xs bg-primary-l text-primary px-2 py-1 rounded-full whitespace-nowrap flex-shrink-0">
              {evaluacion.categoria}
            </span>
          </div>
        </div>

        <div className="card px-4 py-3 flex items-center gap-2 border-green-400/30"
             style={{ background: 'rgba(52,211,153,0.05)' }}>
          <span className="text-green-400 text-sm font-medium">
            ✓ Evaluación guardada — solo lectura
          </span>
        </div>

        <div className="space-y-3">
          {filasOrdenadas.map(({ ev, info }, idx) => (
            <div key={ev.id} className="card px-4 py-3 flex items-center gap-3">
              <span className="text-base font-extrabold text-muted w-6 flex-shrink-0 text-center">
                {idx + 1}º
              </span>
              <span className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                    style={{ backgroundColor: info.color }} />
              {info.icono && (
                <img src={info.icono} alt={info.nombre}
                     className="w-[18px] h-[18px] rounded flex-shrink-0 select-none" />
              )}
              <span className="font-semibold text-sm flex-1 min-w-0 truncate"
                    style={{ color: info.color }}>
                {info.nombre}
              </span>
              <StarRating valor={ev.rating} onChange={() => {}} disabled />
            </div>
          ))}
        </div>

        <div className="flex justify-end">
          <button className="btn-ghost text-sm" onClick={() => navigate('/historial')}>
            Volver al historial
          </button>
        </div>
      </div>
    )
  }

  // ── Vista de formulario (evaluacion pendiente) ─────────────────────────────
  return (
    <div className="max-w-3xl mx-auto space-y-5">
      {/* Cabecera de evaluacion */}
      <div className="card px-5 py-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold mb-1">
              Evaluación #{evaluacion.id}
            </h2>
            <p className="text-sm text-muted line-clamp-2">{evaluacion.prompt}</p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {borradorRecuperado && (
              <span className="text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5
                               rounded-full text-yellow-400 bg-yellow-400/10 border border-yellow-400/30">
                Borrador recuperado
              </span>
            )}
            <span className="text-xs bg-primary-l text-primary px-2 py-1 rounded-full whitespace-nowrap">
              {evaluacion.categoria}
            </span>
          </div>
        </div>
      </div>

      <p className="text-xs text-muted px-1">
        Arrastra las tarjetas para ordenarlas de mejor a peor respuesta.
        La puntuación con estrellas es obligatoria.
      </p>

      {/* Lista sortable con drag-and-drop */}
      <DndContext collisionDetection={closestCenter} onDragEnd={onDragEnd}>
        <SortableContext items={orden} strategy={verticalListSortingStrategy}>
          <div className="space-y-4">
            {respuestasOrdenadas.map((r, idx) => (
              <EvalCard
                key={r.id}
                respuesta={r}
                rango={idx + 1}
                rating={ratings[r.id] ?? 0}
                onRating={(v) => setRatings((p) => ({ ...p, [r.id]: v }))}
                disabled={mutacion.isPending}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>

      {/* Barra inferior */}
      <div className="card px-5 py-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          {!todosConRating && (
            <p className="text-xs text-yellow-400">
              Puntúa todas las respuestas con al menos 1 estrella para poder guardar.
            </p>
          )}
          {mutacion.isError && (
            <p className="text-xs text-red-400">
              Error al guardar. Comprueba que el backend está activo e intenta de nuevo.
            </p>
          )}
        </div>
        <div className="flex gap-3 ml-auto">
          <button
            className="btn-ghost text-sm"
            onClick={() => navigate(-1)}
            disabled={mutacion.isPending}
          >
            Volver
          </button>
          <button
            className="btn-primary"
            onClick={() => mutacion.mutate()}
            disabled={!puedeGuardar || mutacion.isPending}
          >
            {mutacion.isPending ? 'Guardando…' : 'Guardar evaluación'}
          </button>
        </div>
      </div>
    </div>
  )
}
