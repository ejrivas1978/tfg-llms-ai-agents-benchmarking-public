/**
 * Componente: TagSelector
 * Ruta:       frontend/src/components/evaluation/TagSelector.tsx
 *
 * Descripcion:
 *   Chips de etiquetas predefinidas para calificar cualitativamente
 *   una respuesta LLM. Maximo 10 etiquetas seleccionadas simultaneamente.
 *
 * Sprint: Sprint 3
 */

const TAGS: string[] = [
  'Precisa', 'Clara', 'Completa', 'Concisa', 'Creativa', 'Bien estructurada',
  'Útil', 'Lenta', 'Imprecisa', 'Repetitiva', 'Incompleta', 'Confusa',
]

interface Props {
  seleccionados: string[]
  onChange: (tags: string[]) => void
  disabled?: boolean
}

export default function TagSelector({ seleccionados, onChange, disabled = false }: Props) {
  const toggle = (tag: string) => {
    if (seleccionados.includes(tag)) {
      onChange(seleccionados.filter((t) => t !== tag))
    } else if (seleccionados.length < 10) {
      onChange([...seleccionados, tag])
    }
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {TAGS.map((tag) => {
        const activo = seleccionados.includes(tag)
        return (
          <button
            key={tag}
            type="button"
            disabled={disabled}
            onClick={() => toggle(tag)}
            className={`px-2.5 py-0.5 rounded-full text-xs font-medium transition-colors duration-100 ${
              activo
                ? 'bg-primary text-white'
                : 'bg-border text-muted hover:bg-primary-l hover:text-text'
            } disabled:cursor-not-allowed`}
          >
            {tag}
          </button>
        )
      })}
    </div>
  )
}
