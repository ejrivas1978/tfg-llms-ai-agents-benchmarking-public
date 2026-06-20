/**
 * Utilidad: contenidoLLM
 * Ruta:     frontend/src/utils/contenidoLLM.ts
 *
 * Descripcion:
 *   Funciones de analisis sobre el contenido generado por modelos LLM.
 *   Reutilizadas en BenchmarkCard, EvalViewModal y TablaAdmin.
 *
 * Sprint: Sprint 3
 */

export function esCensura(msg: string | null | undefined): boolean {
  if (!msg) return false
  const m = msg.toLowerCase()
  return (
    m.includes('content_policy') ||
    m.includes('politicas de seguridad') ||
    m.includes('filtros de seguridad') ||
    m.includes('safety system')
  )
}

export function extraerMapaMental(texto: string | null | undefined): string | null {
  if (!texto) return null
  const norm = texto.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
  const m = norm.match(/```\s*mermaid\s*\n([\s\S]*?)```/)
  return m ? m[1].trim() : null
}
