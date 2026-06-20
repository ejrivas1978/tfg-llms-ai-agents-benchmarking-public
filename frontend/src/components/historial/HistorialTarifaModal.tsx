/**
 * Componente: HistorialTarifaModal
 * Ruta:       frontend/src/components/historial/HistorialTarifaModal.tsx
 *
 * Descripcion:
 *   Modal que muestra el historial completo de versiones de la tarifa
 *   de un proveedor LLM. La fila vigente queda destacada y arriba; las
 *   versiones historicas se listan a continuacion en orden cronologico
 *   inverso.
 *
 *   Cada llamada LLM persistida en llm_responses queda asociada a la
 *   fila exacta de tarifa con la que se cobro su coste_usd, asi que el
 *   historial preserva la trazabilidad aunque la tarifa cambie luego.
 *
 * Sprint: Sprint 4
 */

import { useQuery } from '@tanstack/react-query'
import { historialTarifaAdmin } from '@/services/adminApi'
import type { LLMProveedor, HistorialTarifaItem } from '@/types/admin'
import { formatFecha } from '@/utils/formatFecha'
import { formatPrecio } from '@/utils/formatPrecio'

interface Props {
  token: string
  proveedor: LLMProveedor
  nombreProveedor: string
  colorProveedor: string
  onClose: () => void
}

export default function HistorialTarifaModal({
  token,
  proveedor,
  nombreProveedor,
  colorProveedor,
  onClose,
}: Props) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin-tarifas-historial', proveedor],
    queryFn:  () => historialTarifaAdmin(token, proveedor),
  })

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.65)' }}
      onClick={onClose}
    >
      <div
        className="card p-6 w-full max-w-2xl shadow-card-lg space-y-4 max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="font-semibold text-sm mb-1">Historial de tarifas</p>
            <span className="text-xs font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full whitespace-nowrap"
                  style={{
                    color: colorProveedor,
                    background: `${colorProveedor}20`,
                    border: `1px solid ${colorProveedor}50`,
                  }}>
              {nombreProveedor}
            </span>
          </div>
          <button
            className="btn-ghost text-xs"
            onClick={onClose}
            aria-label="Cerrar"
          >
            ✕
          </button>
        </div>

        <p className="text-[11px] text-muted leading-snug">
          La fila marcada como <span className="font-semibold text-green-400">VIGENTE</span> es
          la que se aplica a las llamadas LLM actuales. Las versiones anteriores se conservan
          porque cada respuesta LLM guarda el <span className="font-mono">tarifa_id</span> con
          el que se cobró, garantizando la trazabilidad histórica.
        </p>

        {isLoading && <p className="text-sm text-muted text-center py-4">Cargando historial…</p>}
        {isError && <p className="text-sm text-red-400 text-center py-4">No se pudo cargar el historial.</p>}

        {data && data.items.length === 0 && (
          <p className="text-sm text-muted text-center py-4">Sin versiones registradas.</p>
        )}

        {data && data.items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs min-w-[820px]">
              <thead>
                <tr className="text-[10px] uppercase tracking-wide text-muted border-b border-border">
                  <th className="text-center py-2 px-2 w-20">Estado</th>
                  <th className="text-left  py-2 px-2 w-12">ID</th>
                  <th className="text-right py-2 px-2 w-24">Entrada $/Mtok</th>
                  <th className="text-right py-2 px-2 w-24">Salida $/Mtok</th>
                  <th className="text-right py-2 px-2 w-24">Cacheado</th>
                  <th className="text-right py-2 px-2 w-20">Img gen $/img</th>
                  <th className="text-right py-2 px-2 w-20">Img edit $/img</th>
                  <th className="text-left  py-2 px-2 w-32">Fecha</th>
                  <th className="text-left  py-2 px-2 w-24">Autor</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((v: HistorialTarifaItem) => (
                  <tr key={v.id}
                      className={`border-b border-border ${v.vigente ? 'bg-primary-l/40' : 'hover:bg-primary-l/20'} transition-colors`}>
                    <td className="py-2 px-2 text-center">
                      {v.vigente ? (
                        <span className="text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full"
                              style={{
                                color: '#34D399',
                                background: 'rgba(52,211,153,0.10)',
                                border: '1px solid rgba(52,211,153,0.40)',
                              }}>
                          Vigente
                        </span>
                      ) : (
                        <span className="text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full"
                              style={{
                                color: '#FBBF24',
                                background: 'rgba(251,191,36,0.10)',
                                border: '1px solid rgba(251,191,36,0.40)',
                              }}>
                          HISTÓRICA
                        </span>
                      )}
                    </td>
                    <td className="py-2 px-2 font-mono text-[11px]">#{v.id}</td>
                    <td className="py-2 px-2 text-right font-mono">{formatPrecio(v.precio_entrada_usd_por_mtoken)}</td>
                    <td className="py-2 px-2 text-right font-mono">{formatPrecio(v.precio_salida_usd_por_mtoken)}</td>
                    <td className="py-2 px-2 text-right font-mono">
                      {v.precio_entrada_cacheado_usd_por_mtoken != null
                        ? formatPrecio(v.precio_entrada_cacheado_usd_por_mtoken)
                        : <span className="text-muted">—</span>}
                    </td>
                    <td className="py-2 px-2 text-right font-mono">
                      {v.precio_imagen_generar_usd_por_imagen != null
                        ? formatPrecio(v.precio_imagen_generar_usd_por_imagen)
                        : <span className="text-muted">—</span>}
                    </td>
                    <td className="py-2 px-2 text-right font-mono">
                      {v.precio_imagen_editar_usd_por_imagen != null
                        ? formatPrecio(v.precio_imagen_editar_usd_por_imagen)
                        : <span className="text-muted">—</span>}
                    </td>
                    <td className="py-2 px-2 text-muted">{formatFecha(v.actualizado_en)}</td>
                    <td className="py-2 px-2 text-muted">{v.actualizado_por ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex justify-end">
          <button className="btn-ghost text-sm" onClick={onClose}>Cerrar</button>
        </div>
      </div>
    </div>
  )
}
