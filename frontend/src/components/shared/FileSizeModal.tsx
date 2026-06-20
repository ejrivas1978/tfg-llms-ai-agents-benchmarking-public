/**
 * Componente: FileSizeModal
 * Ruta:       frontend/src/components/shared/FileSizeModal.tsx
 *
 * Descripcion:
 *   Modal de aviso cuando el usuario sube un fichero que supera el limite
 *   permitido. Se muestra sobre un backdrop oscuro con una ilustracion
 *   animada y un mensaje claro del limite.
 *
 * Props:
 *   tipo    - 'documento' (PDF/TXT/DOCX) o 'imagen' (JPG/PNG)
 *   limite  - Texto del limite a mostrar, ej: "10 MB"
 *   onCerrar - Callback para cerrar el modal
 *
 * Sprint: Sprint 4
 */

interface Props {
  tipo:    'documento' | 'imagen'
  limite:  string
  onCerrar: () => void
}

const CONTENIDO: Record<Props['tipo'], { escena: string; titulo: string; detalle: string }> = {
  documento: {
    escena:  '🐋',
    titulo:  '¡El fichero es enorme!',
    detalle: 'Los documentos deben pesar menos de',
  },
  imagen: {
    escena:  '🐘',
    titulo:  '¡La imagen pesa demasiado!',
    detalle: 'Las imágenes deben pesar menos de',
  },
}

export default function FileSizeModal({ tipo, limite, onCerrar }: Props) {
  const { escena, titulo, detalle } = CONTENIDO[tipo]

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(4px)' }}
      onClick={onCerrar}
    >
      <div
        className="card w-full max-w-xs shadow-card-lg overflow-hidden text-center"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Ilustracion */}
        <div
          className="py-8 flex flex-col items-center gap-2"
          style={{ background: 'linear-gradient(135deg, #1B0A3A 0%, #0D0E18 100%)' }}
        >
          <span
            className="select-none"
            style={{ fontSize: '72px', lineHeight: 1, filter: 'drop-shadow(0 4px 16px rgba(0,0,0,.6))' }}
            aria-hidden
          >
            {escena}
          </span>
          <div className="flex items-center gap-1 mt-1 select-none" aria-hidden>
            <span style={{ fontSize: '22px' }}>📁</span>
            <span style={{ fontSize: '16px' }}>➡️</span>
            <span style={{ fontSize: '22px' }}>🚧</span>
          </div>
        </div>

        {/* Texto */}
        <div className="px-6 py-5 space-y-2">
          <p className="font-bold text-base text-text">{titulo}</p>
          <p className="text-sm text-muted leading-relaxed">
            {detalle}{' '}
            <span className="font-semibold text-text">{limite}</span>.
            <br />
            Reduce el tamaño o elige otro fichero.
          </p>
        </div>

        {/* Accion */}
        <div className="px-6 pb-6">
          <button
            className="btn-primary w-full"
            onClick={onCerrar}
            autoFocus
          >
            Entendido
          </button>
        </div>
      </div>
    </div>
  )
}
