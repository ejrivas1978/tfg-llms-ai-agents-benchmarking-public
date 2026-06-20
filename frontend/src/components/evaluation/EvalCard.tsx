/**
 * Componente: EvalCard
 * Ruta:       frontend/src/components/evaluation/EvalCard.tsx
 *
 * Descripcion:
 *   Tarjeta de evaluacion por proveedor LLM con soporte de arrastrar y soltar
 *   via dnd-kit. Incluye vista resumida de la respuesta y StarRating.
 *
 * Sprint: Sprint 3
 */

import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import StarRating from './StarRating'
import type { RespuestaLLM } from '@/types/benchmark'
import { LLM_PROVIDERS_CONFIG } from '@/config/llmProviders'

function esCensura(r: RespuestaLLM): boolean {
  if (!r.tuvo_error || !r.mensaje_error) return false
  const m = r.mensaje_error.toLowerCase()
  return m.includes('content_policy') || m.includes('politicas de seguridad') ||
         m.includes('filtros de seguridad') || m.includes('safety system')
}

interface Props {
  respuesta: RespuestaLLM
  rango: number
  rating: number
  onRating: (valor: number) => void
  disabled: boolean
}

export default function EvalCard({ respuesta, rango, rating, onRating, disabled }: Props) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: respuesta.id })

  const info = LLM_PROVIDERS_CONFIG[respuesta.proveedor] ?? { nombre: respuesta.proveedor, color: '#888', icono: '' }

  return (
    <div
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.45 : 1,
      }}
      className="card overflow-hidden"
    >
      {/* Barra de color del proveedor */}
      <div className="h-1 w-full" style={{ backgroundColor: info.color }} />

      {/* Cabecera: handle de arrastre + proveedor + rango */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-border">
        <button
          {...attributes}
          {...listeners}
          type="button"
          className="text-muted hover:text-text cursor-grab active:cursor-grabbing text-lg select-none"
          title="Arrastra para reordenar"
        >
          ⠿
        </button>
        <span
          className="w-2.5 h-2.5 rounded-full flex-shrink-0"
          style={{ backgroundColor: info.color }}
        />
        <img src={info.icono} alt={info.nombre} className="w-[18px] h-[18px] rounded flex-shrink-0 select-none" />
        <span className="font-semibold text-sm flex-1">{info.nombre}</span>
        <span className="text-xs bg-primary-l text-primary px-2 py-0.5 rounded-full font-mono">
          #{rango}
        </span>
      </div>

      {/* Fragmento de la respuesta (solo lectura) */}
      <div className="px-4 py-3 max-h-36 overflow-y-auto flex justify-center">
        {respuesta.tuvo_error ? (
          <p className="text-xs text-red-400">{respuesta.mensaje_error ?? 'Error al generar'}</p>
        ) : respuesta.es_imagen ? (
          respuesta.imagen_miniatura ? (
            <img
              src={`data:image/jpeg;base64,${respuesta.imagen_miniatura}`}
              alt="Imagen generada"
              className="max-h-28 rounded object-cover"
            />
          ) : respuesta.url_imagen ? (
            <img src={respuesta.url_imagen} alt="Imagen generada" className="max-h-28 rounded" />
          ) : (
            <p className="text-xs text-muted italic">Vista previa no disponible</p>
          )
        ) : (
          <p className="text-sm text-muted leading-relaxed whitespace-pre-wrap w-full">
            {respuesta.texto_respuesta ?? '—'}
          </p>
        )}
      </div>

      {/* Puntuacion */}
      <div className="px-4 py-3 border-t border-border">
        {esCensura(respuesta) ? (
          <div className="flex items-center gap-2">
            <span className="text-red-400">🚫</span>
            <span className="text-[11px] text-red-400 font-medium leading-snug">
              Rechazado por política de seguridad — 0 estrellas asignadas automáticamente
            </span>
          </div>
        ) : (
          <div className="flex items-center gap-3">
            <span className="text-xs text-muted w-20 flex-shrink-0">Puntuación</span>
            <StarRating valor={rating} onChange={onRating} disabled={disabled} />
            {rating > 0 && <span className="text-xs text-muted">{rating} / 5</span>}
          </div>
        )}
      </div>
    </div>
  )
}
