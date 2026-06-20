/**
 * Utilidad: formatFecha
 * Ruta:     frontend/src/utils/formatFecha.ts
 *
 * Descripcion:
 *   Convierte una cadena ISO 8601 al formato DD-MM-YYYY HH:MM:SS.
 *   Usado en toda la aplicacion para garantizar un formato de fecha uniforme.
 *
 * Sprint: Sprint 3
 */

export function formatFecha(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '—'
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d.getDate())}-${p(d.getMonth() + 1)}-${d.getFullYear()} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}
