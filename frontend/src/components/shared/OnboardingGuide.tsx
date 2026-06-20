/**
 * Componente: OnboardingGuide
 * Ruta:       frontend/src/components/shared/OnboardingGuide.tsx
 *
 * Descripcion:
 *   Guia paso a paso que se muestra cuando el padre indica visible=true.
 *   El control de visibilidad recae en el padre (BenchmarkPage), que consulta
 *   el flag guia_vista del store de usuario sincronizado con la base de datos.
 *   Se cierra con "Saltar", "Empezar" o pulsando Escape; al cerrar llama a onCerrar.
 *
 * Sprint: Sprint 3 / Sprint 4
 */

import { useEffect, useState } from 'react'

interface Paso {
  icono: string
  titulo: string
  desc: string
  /** Nombre del autor — solo primer paso */
  autor?: string
  /** Titulacion academica — solo primer paso */
  titulacion?: string
  /** Ruta a imagen de logo institucional — solo primer paso */
  logoUrl?: string
}

const PASOS: Paso[] = [
  {
    icono: '👋',
    titulo: '¡Bienvenido/a al TFG comparador de modelos de LLMs!',
    autor: 'Emilio Javier Rivas Fernández',
    titulacion: 'Grado en Ingeniería Informática',
    logoUrl: '/Logo_escuela.png',
    desc: 'Esta herramienta te permite enviar el mismo prompt a Claude, GPT-4o, Gemini y Grok simultáneamente y comparar sus respuestas de forma objetiva.',
  },
  {
    icono: '✨',
    titulo: '¡Los destellos te guían!',
    desc: 'A lo largo de toda la herramienta verás secciones que parpadean, eso significa que esperan una acción por tu parte.',
  },
  {
    icono: '🎯',
    titulo: 'PRIMER PASO: Elige una categoría.',
    desc: 'Selecciona el tipo de tarea: razonamiento lógico, código, escritura creativa, traducción, imagen… Verás que algunas categoría incluyen prompts predefinidos para facilitar la evaluación.',
  },
  {
    icono: '✍️',
    titulo: 'SEGUNDO PASO: Escribe un prompt o selecciona una Subcategoría',
    desc: 'Elige una subcategoría para cargar un prompt predefinido (solo lectura) o escribe el tuyo propio en el área de texto. Mínimo 10 caracteres.',
  },
  {
    icono: '🖼️',
    titulo: 'Imágenes y archivos adjuntos',
    desc: 'IMPORTANTE: la generación de imágenes está limitada por las políticas de contenido de cada LLM. Algunos modelos rechazarán peticiones que infrinjan sus normas.\n\nEl tamaño MAX para archivos adjuntos: imágenes JPEG/PNG (máx. 5 MB), documentos PDF/TXT (máx. 10 MB, se recomienda menos de 50 páginas). Archivos más grandes ralentizan la respuesta o pueden ser rechazados.',
  },
  {
    icono: '🚀',
    titulo: 'TERCER PASO: Lanza la comparación',
    desc: 'Pulsa "Comparar modelos" para enviar el prompt a los 4 modelos en paralelo. En unos segundos verás las respuestas.',
  },
  {
    icono: '⭐',
    titulo: 'CUARTO PASO: Evalúa las respuestas',
    desc: 'Puntúa cada respuesta con estrellas (1–5) y arrastra las tarjetas para ordenarlas de mejor a peor. Tu valoración alimenta las estadísticas del dashboard.',
  },
  {
    icono: '📊',
    titulo: 'Consulta el dashboard',
    desc: 'El dashboard muestra estadísticas agregadas de todas las evaluaciones: valoraciones medias, ranking de preferencia, latencia, coste, velocidad de generación y mucho más.',
  },
]

interface Props {
  /** El padre decide si la guia debe estar visible. */
  visible: boolean
  /**
   * Llamado cuando el usuario cierra la guia (Saltar, Empezar o Escape).
   * El padre decide si debe llamar a la API para marcar guia_vista=true.
   */
  onCerrar: () => void
}

export default function OnboardingGuide({ visible, onCerrar }: Props) {
  const [paso, setPaso] = useState(0)

  // Reinicia al paso 0 cada vez que la guia se hace visible
  useEffect(() => {
    if (visible) setPaso(0)
  }, [visible])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onCerrar() }
    if (visible) window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [visible, onCerrar])

  if (!visible) return null

  const actual    = PASOS[paso]
  const esUltimo  = paso === PASOS.length - 1
  const esPrimero = paso === 0

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.75)' }}
    >
      <div
        className="relative w-full max-w-md rounded-card border border-border shadow-card-lg flex flex-col overflow-hidden"
        style={{ background: '#0e0b22' }}
      >
        {/* Contenedor de contenido */}
        <div className="flex flex-col flex-1">

        {/* Barra de progreso */}
        <div className="h-1 w-full bg-border">
          <div
            className="h-1 transition-all duration-300 bg-primary"
            style={{ width: `${((paso + 1) / PASOS.length) * 100}%` }}
          />
        </div>

        {/* Cabecera */}
        <div className="flex items-center justify-between px-5 pt-4 pb-2">
          <span className="text-[10px] font-semibold text-muted uppercase tracking-widest">
            Paso {paso + 1} de {PASOS.length}
          </span>
          <button
            onClick={onCerrar}
            className="text-xs text-muted hover:text-text transition-colors"
          >
            Saltar guía ✕
          </button>
        </div>

        {/* Contenido del paso */}
        <div className="px-6 py-5 flex flex-col items-center text-center gap-3 flex-1">
          <span style={{ fontSize: 64, lineHeight: 1 }}>{actual.icono}</span>
          <h2 className={`text-base font-bold leading-snug ${actual.titulo === '¡Los destellos te guían!' ? 'animate-pulse-strong' : ''}`}>{actual.titulo}</h2>

          {/* Bloque de autor e imagen institucional — solo primer paso */}
          {(actual.autor || actual.titulacion || actual.logoUrl) && (
            <>
              <div className="flex flex-col gap-0.5">
                {actual.autor && (
                  <p className="text-[11px] text-muted font-medium">
                    Autor: {actual.autor}
                  </p>
                )}
                {actual.titulacion && (
                  <p className="text-[11px] text-muted">
                    Titulación: {actual.titulacion}
                  </p>
                )}
              </div>
              {actual.logoUrl && (
                <img
                  src={actual.logoUrl}
                  alt="Escudo Universidad de Granada"
                  style={{ height: 80, objectFit: 'contain', marginTop: 4 }}
                  onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
                />
              )}
            </>
          )}

          <p className="text-sm text-muted leading-relaxed whitespace-pre-line">{actual.desc}</p>
        </div>

        {/* Puntos de navegación */}
        <div className="flex items-center justify-center gap-1.5 pb-2">
          {PASOS.map((_, i) => (
            <button
              key={i}
              onClick={() => setPaso(i)}
              className={`rounded-full transition-all ${i === paso ? 'bg-primary' : 'bg-border'}`}
              style={{ width: i === paso ? 20 : 8, height: 8 }}
            />
          ))}
        </div>

        {/* Botones */}
        <div className="flex items-center justify-between gap-3 px-6 py-4 border-t border-border">
          <button
            className="btn-ghost text-sm"
            onClick={() => setPaso((p) => p - 1)}
            disabled={esPrimero}
            style={{ visibility: esPrimero ? 'hidden' : 'visible' }}
          >
            ← Anterior
          </button>

          {esUltimo ? (
            <button className="btn-primary" onClick={onCerrar}>
              ¡Empezar! 🚀
            </button>
          ) : (
            <button className="btn-primary" onClick={() => setPaso((p) => p + 1)}>
              Siguiente →
            </button>
          )}
        </div>

        </div>
      </div>
    </div>
  )
}
