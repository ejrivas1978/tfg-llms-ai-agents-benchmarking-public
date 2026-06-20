/**
 * Componente: StarRating
 * Ruta:       frontend/src/components/evaluation/StarRating.tsx
 *
 * Descripcion:
 *   Cinco estrellas clicables para puntuar una respuesta LLM (1-5).
 *   La estrella seleccionada y las anteriores se iluminan en amarillo.
 *
 * Sprint: Sprint 3
 */

interface Props {
  valor: number
  onChange: (valor: number) => void
  disabled?: boolean
}

export default function StarRating({ valor, onChange, disabled = false }: Props) {
  return (
    <div className="flex justify-center gap-1">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          disabled={disabled}
          onClick={() => onChange(n)}
          className="text-3xl leading-none transition-colors duration-100 disabled:cursor-not-allowed"
          style={{
            color: n <= valor ? '#FACC15' : 'rgba(250,204,21,0.28)',
          }}
          onMouseEnter={(e) => { if (!disabled && n > valor) (e.currentTarget as HTMLButtonElement).style.color = 'rgba(250,204,21,0.6)' }}
          onMouseLeave={(e) => { if (!disabled && n > valor) (e.currentTarget as HTMLButtonElement).style.color = 'rgba(250,204,21,0.28)' }}
        >
          ★
        </button>
      ))}
    </div>
  )
}
