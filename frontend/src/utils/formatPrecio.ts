/**
 * Helper: formatPrecio
 * Ruta:    frontend/src/utils/formatPrecio.ts
 *
 * Descripcion:
 *   Formatea un precio numerico (USD/Mtok o USD/imagen) mostrando SIEMPRE
 *   8 decimales, alineado con la precision real almacenada en BD
 *   (NUMERIC(12, 8)). Sin recorte de ceros: 3 -> "3.00000000".
 *
 *   Esta uniformidad facilita comparar visualmente columnas en la tabla
 *   admin y en el modal de historial sin que valores enteros (3.0000)
 *   parezcan "menos precisos" que valores decimales largos (0.30000001).
 *
 *   Ejemplos:
 *     3            -> "3.00000000"
 *     0.3          -> "0.30000000"
 *     0.0188       -> "0.01880000"
 *     0.30000001   -> "0.30000001"
 *     0.000000125  -> "0.00000013"  (truncado por .toFixed(8))
 *     null         -> "—"
 */

export function formatPrecio(valor: number | string | null | undefined): string {
  if (valor === null || valor === undefined) return '—'
  const n = typeof valor === 'string' ? parseFloat(valor) : valor
  if (!Number.isFinite(n)) return '—'
  return n.toFixed(8)
}
