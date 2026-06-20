/**
 * Componente: ConfirmModal
 * Ruta:       frontend/src/components/shared/ConfirmModal.tsx
 *
 * Descripcion:
 *   Modal de confirmacion reutilizable que sustituye a window.confirm().
 *   Se renderiza sobre un backdrop semitransparente. Acepta un mensaje
 *   libre, callbacks de confirmacion y cancelacion, y un flag opcional
 *   para marcar la accion como destructiva (boton en rojo).
 *
 * Sprint: Sprint 3
 */

interface Props {
  mensaje: string
  textoBotom?: string
  destructivo?: boolean
  onConfirmar: () => void
  onCancelar: () => void
}

export default function ConfirmModal({
  mensaje,
  textoBotom = 'Confirmar',
  destructivo = false,
  onConfirmar,
  onCancelar,
}: Props) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.65)' }}
      onClick={onCancelar}
    >
      <div
        className="card p-6 w-full max-w-sm shadow-card-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <p className="text-sm text-text mb-6 leading-relaxed">{mensaje}</p>
        <div className="flex justify-end gap-2">
          <button className="btn-ghost text-sm" onClick={onCancelar}>
            Cancelar
          </button>
          <button
            className={`text-sm px-4 py-1.5 rounded-lg font-medium transition-colors ${
              destructivo
                ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30 border border-red-500/40'
                : 'btn-primary'
            }`}
            onClick={onConfirmar}
          >
            {textoBotom}
          </button>
        </div>
      </div>
    </div>
  )
}
