/**
 * Componente: BenchmarkCard
 * Ruta:       frontend/src/components/benchmark/BenchmarkCard.tsx
 *
 * Descripcion:
 *   Tarjeta que muestra la respuesta y las metricas de un proveedor LLM.
 *   - Doble clic en la tarjeta: abre/cierra el modal ampliado (mapa mental o texto largo).
 *   - Modal mapa mental: zoom con rueda/botones + arrastre con el raton (cursor mano).
 *   - Detecta bloques de diagrama y los renderiza como SVG con MapaMentalDiagram.
 *   - Para imagenes generativas: lightbox con zoom toggle.
 *
 * Sprint: Sprint 3
 */

import { useState } from 'react'
import type { ReactNode } from 'react'
import type { RespuestaLLM, LLMProvider } from '@/types/benchmark'
import MapaMentalDiagram from '@/components/shared/MapaMentalDiagram'
import VisorImagen from '@/components/shared/VisorImagen'
import VisorMapaMental from '@/components/shared/VisorMapaMental'
import { esCensura, extraerMapaMental } from '@/utils/contenidoLLM'
import { LLM_PROVIDERS_CONFIG } from '@/config/llmProviders'
import { TOKENS } from '@/utils/tokens'

const BG_CARD = TOKENS.surface


interface Props {
  proveedor: LLMProvider
  respuesta?: RespuestaLLM
  cargando: boolean
  /**
   * Respuesta paralela en ingles del mismo proveedor (ADR-029).
   * Solo viene cuando la evaluacion pertenece al sub-experimento bilingue ES/EN.
   * No se valora; se muestra bajo un acordeon 'Ver respuesta en inglés' con
   * su propio texto y metricas tecnicas. La tarjeta principal sigue siendo
   * la respuesta ES, que es la unica que el humano puntua y rankea.
   */
  respuestaEn?: RespuestaLLM
}

export default function BenchmarkCard({ proveedor, respuesta, cargando, respuestaEn }: Props) {
  const info = LLM_PROVIDERS_CONFIG[proveedor]

  // Estados tarjeta
  const [hover,        setHover]        = useState(false)
  const [ampliado,     setAmpliado]     = useState(false)
  const [mostrarModal, setMostrarModal] = useState(false)
  const [verEn,        setVerEn]        = useState(false)
  // Toggle ampliado/comprimido del texto en ingles. Reusa la misma logica que
  // 'ampliado' del lado ES para que doble-clic se comporte igual en los dos.
  const [ampliadoEn,   setAmpliadoEn]   = useState(false)
  const textLargoEn = (respuestaEn?.palabras ?? 0) > 60

  // MapaMental
  const codigoMapaMental = extraerMapaMental(respuesta?.texto_respuesta ?? null)
  const esMapaMental     = !!codigoMapaMental
  const textLargo     = !esMapaMental && (respuesta?.palabras ?? 0) > 60

  const [svgMapaMental,   setSvgMapaMental]   = useState<string>('')
  const [modalMapaMental, setModalMapaMental] = useState(false)

  const abrirMapaMental  = () => setModalMapaMental(true)
  const cerrarMapaMental = () => setModalMapaMental(false)

  // Descargas
  const descargar = () => {
    if (!respuesta?.texto_respuesta) return
    const cabecera = `${info.nombre}\n${'─'.repeat(50)}\n\n`
    const blob = new Blob([cabecera + respuesta.texto_respuesta], { type: 'text/plain;charset=utf-8' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href = url; a.download = `respuesta-${proveedor}.txt`; a.click()
    URL.revokeObjectURL(url)
  }

  const descargarImagen = async () => {
    const url = respuesta?.url_imagen
    if (!url) return
    try {
      let blob: Blob
      if (url.startsWith('data:')) {
        blob = await (await fetch(url)).blob()
      } else {
        const res = await fetch(`/api/v1/benchmarks/imagen/descargar?${new URLSearchParams({ url })}`)
        if (!res.ok) throw new Error()
        blob = await res.blob()
      }
      const blobUrl = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = blobUrl; a.download = `imagen-${proveedor}.png`
      document.body.appendChild(a); a.click(); document.body.removeChild(a)
      URL.revokeObjectURL(blobUrl)
    } catch {
      if (!url.startsWith('data:')) window.open(url, '_blank', 'noopener,noreferrer')
    }
  }

  const descargarMapaMentalPng = () => {
    if (!svgMapaMental) return
    const vbMatch = svgMapaMental.match(/viewBox="[\d.]+\s+[\d.]+\s+([\d.]+)\s+([\d.]+)"/)
    const w = vbMatch ? Math.max(parseFloat(vbMatch[1]), 100) : 1200
    const h = vbMatch ? Math.max(parseFloat(vbMatch[2]), 100) : 800

    let svgStr = svgMapaMental
      .replace(/(\s)width="[^"]*"/, ` width="${w}"`)
      .replace(/(\s)height="[^"]*"/, ` height="${h}"`)
    if (!svgStr.includes(`width="${w}"`)) svgStr = svgStr.replace('<svg', `<svg width="${w}" height="${h}"`)

    const dataUrl = `data:image/svg+xml;base64,${btoa(unescape(encodeURIComponent(svgStr)))}`
    const escala = 2
    const canvas = document.createElement('canvas')
    canvas.width = w * escala; canvas.height = h * escala
    const ctx = canvas.getContext('2d')!
    ctx.fillStyle = TOKENS.surface; ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.scale(escala, escala)
    const img = new Image()
    img.onload = () => {
      ctx.drawImage(img, 0, 0)
      canvas.toBlob((pngBlob) => {
        if (!pngBlob) return
        const pngUrl = URL.createObjectURL(pngBlob)
        const a = document.createElement('a')
        a.href = pngUrl; a.download = `mapa-mental-${proveedor}.png`
        document.body.appendChild(a); a.click(); document.body.removeChild(a)
        URL.revokeObjectURL(pngUrl)
      }, 'image/png')
    }
    img.src = dataUrl
  }

  const abrirModal  = () => setMostrarModal(true)
  const cerrarModal = () => setMostrarModal(false)

  return (
    <>
      <div
        className="flex flex-col overflow-hidden rounded-card border-2 shadow-card min-w-0 transition-colors duration-150"
        style={{ borderColor: hover ? info.color : TOKENS.border, background: TOKENS.surface }}
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        onDoubleClick={(e) => {
          if ((e.target as HTMLElement).closest('button')) return
          if (esMapaMental && svgMapaMental) { abrirMapaMental(); return }
          if (respuesta?.es_imagen && respuesta?.url_imagen) { abrirModal(); return }
          if (textLargo && !respuesta?.es_imagen && !respuesta?.tuvo_error) setAmpliado((v) => !v)
        }}
      >
        {/* Cabecera */}
        <div className="flex items-center justify-between px-3 py-3 border-b border-border"
             style={{ background: info.bg }}>
          <div className="flex items-center gap-2 min-w-0">
            <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: info.color }} />
            <span className="font-bold text-sm truncate">{info.nombre}</span>
          </div>
          {!cargando && respuesta && (
            <div className="flex items-center gap-2 ml-2 flex-shrink-0">
              <span className="text-[10px] text-muted font-mono truncate max-w-[80px]">{respuesta.modelo}</span>
              {textLargo && !respuesta.es_imagen && !respuesta.tuvo_error && (
                <span className="text-[9px] text-muted select-none"
                      title={ampliado ? 'Doble clic para contraer' : 'Doble clic para ampliar'}>
                  {ampliado ? '▲' : '▼'}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Cuerpo */}
        <div className="flex-1 px-4 py-4 min-h-[180px]">
          {cargando && (
            <div className="flex gap-1.5 items-center py-6">
              {[0, 1, 2].map((i) => (
                <span key={i} className="loading-dot w-2.5 h-2.5 rounded-full"
                      style={{ background: info.color, animationDelay: `${i * 0.2}s` }} />
              ))}
            </div>
          )}

          {!cargando && respuesta?.tuvo_error && (
            esCensura(respuesta.mensaje_error) ? (
              <div className="flex flex-col items-center justify-center gap-2 py-6 text-center">
                <span className="text-4xl">🚫</span>
                <p className="text-sm font-semibold text-red-400">Política de seguridad</p>
                <p className="text-xs text-muted max-w-[200px]">
                  Este modelo rechazó el prompt por sus filtros de contenido.
                </p>
              </div>
            ) : (
              <div className="flex items-start gap-2 text-red-400">
                <span className="flex-shrink-0 mt-0.5">⚠</span>
                <p className="text-sm">{respuesta.mensaje_error ?? 'Error desconocido'}</p>
              </div>
            )
          )}

          {/* Imagen generativa */}
          {!cargando && respuesta && !respuesta.tuvo_error && respuesta.es_imagen && (
            <div className="space-y-2">
              <div className="w-full rounded-lg overflow-hidden flex items-center justify-center"
                   style={{ aspectRatio: '1 / 1', background: 'rgba(0,0,0,0.25)' }}>
                {respuesta.url_imagen
                  ? <img src={respuesta.url_imagen} alt="Imagen generada" className="w-full h-full object-contain" />
                  : respuesta.texto_respuesta
                    ? <p className="text-sm text-text leading-relaxed whitespace-pre-wrap px-3 py-3">{respuesta.texto_respuesta}</p>
                    : <div className="flex flex-col items-center justify-center gap-2 text-center px-4">
                        <span className="text-3xl opacity-40">🚫</span>
                        <p className="text-sm text-muted italic">Este modelo no soporta generación de imágenes</p>
                      </div>
                }
              </div>
              {respuesta.url_imagen && (
                <div className="flex gap-2 pt-1">
                  <BtnImg color="#818CF8" onClick={abrirModal}>⤢ Ampliar · doble clic</BtnImg>
                  <BtnImg color="#34D399" onClick={descargarImagen}>↓ Descargar</BtnImg>
                </div>
              )}
            </div>
          )}

          {/* Texto / MapaMental */}
          {!cargando && respuesta && !respuesta.tuvo_error && !respuesta.es_imagen && (
            <div className="space-y-2">
              {esMapaMental ? (
                <div className="space-y-2">
                  {/* Contenedor de altura fija para que la miniatura sea igual en las 4 tarjetas */}
                  <div className="w-full overflow-hidden rounded-lg" style={{ height: 220 }}>
                    <MapaMentalDiagram codigo={codigoMapaMental!} onSvgReady={setSvgMapaMental} />
                  </div>
                  {svgMapaMental && (
                    <div className="flex gap-2 pt-1">
                      <BtnImg color="#818CF8" onClick={abrirMapaMental}>⤢ Ampliar · doble clic</BtnImg>
                      <BtnImg color="#34D399" onClick={descargarMapaMentalPng}>↓ Descargar PNG</BtnImg>
                    </div>
                  )}
                </div>
              ) : (
                <>
                  <div className={`relative ${!ampliado && textLargo ? 'max-h-48 overflow-hidden' : ''}`}>
                    <p className="text-sm text-text leading-relaxed whitespace-pre-wrap">{respuesta.texto_respuesta}</p>
                    {!ampliado && textLargo && (
                      <div className="absolute bottom-0 left-0 right-0 h-14 pointer-events-none"
                           style={{ background: `linear-gradient(to top, ${BG_CARD}, transparent)` }} />
                    )}
                  </div>
                  <div className="flex items-center justify-between gap-2 pt-0.5">
                    {textLargo
                      ? <button className="text-xs text-primary hover:opacity-80 transition-opacity"
                                onClick={() => setAmpliado((v) => !v)}>
                          {ampliado ? '▲ Contraer respuesta' : '▼ Ampliar respuesta · doble clic'}
                        </button>
                      : <span />
                    }
                    <button className="text-xs text-muted hover:text-text transition-colors"
                            onClick={descargar} title="Descargar respuesta como fichero de texto">
                      ↓ Descargar
                    </button>
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        {/* Métricas */}
        {!cargando && respuesta && !respuesta.tuvo_error && (
          respuesta.es_imagen ? (
            <div className="px-3 py-2.5 border-t border-border flex gap-4"
                 style={{ background: 'rgba(12,12,26,0.6)' }}>
              <Metrica label="Latencia" valor={`${respuesta.latencia_ms} ms`} />
            </div>
          ) : (
            <div className="px-3 py-2.5 border-t border-border grid grid-cols-3 gap-x-2 gap-y-1.5"
                 style={{ background: 'rgba(12,12,26,0.6)' }}>
              <Metrica label="Latencia"    valor={`${respuesta.latencia_ms} ms`} />
              <Metrica label="Tok/s"       valor={respuesta.tokens_por_segundo.toFixed(1)} />
              <Metrica label="Coste"       valor={`$${respuesta.cost_usd.toFixed(8)}`} />
              <Metrica label="Palabras"    valor={respuesta.palabras.toString()} />
              <Metrica label="Sal/Ent"     valor={respuesta.ratio_sal_ent.toFixed(2)} />
              <Metrica label="Div. léx."   valor={`${(respuesta.diversidad_lexica * 100).toFixed(0)}%`} />
              <Metrica label="Párrafos"    valor={respuesta.parrafos.toString()} />
              <Metrica label="¢/100 pal."  valor={`$${respuesta.coste_por_100_palabras.toFixed(8)}`} />
            </div>
          )
        )}

        {/* Acordeon respuesta EN — sub-experimento bilingue ES/EN (ADR-029).
            Solo se renderiza cuando la evaluacion incluye una respuesta en
            ingles del mismo proveedor. La cara que se valora es la ES (lo
            mostrado arriba); aqui se acumula la respuesta EN replicada para
            que el lector pueda inspeccionarla manualmente sin que altere la
            tarea de valoracion humana. */}
        {!cargando && respuestaEn && (
          <div className="border-t border-border px-3 py-2.5" style={{ background: 'rgba(12,12,26,0.45)' }}>
            <BotonVerEn
              color={info.color}
              abierto={verEn}
              onClick={() => setVerEn((v) => !v)}
            />
            {verEn && (
              <div className="mt-2.5 space-y-2">
                {respuestaEn.tuvo_error ? (
                  <p className="text-xs text-red-400 flex items-start gap-2">
                    <span className="flex-shrink-0 mt-0.5">⚠</span>
                    <span>{respuestaEn.mensaje_error ?? 'Error en respuesta EN'}</span>
                  </p>
                ) : (
                  <>
                    <div
                      className={`relative ${!ampliadoEn && textLargoEn ? 'max-h-40 overflow-hidden' : ''}`}
                      onDoubleClick={(e) => {
                        // Evita que el doble-clic propague al onDoubleClick del
                        // contenedor principal (que toggle el ampliado de la
                        // respuesta ES). Cada idioma se expande de forma
                        // independiente.
                        e.stopPropagation()
                        if (textLargoEn) setAmpliadoEn((v) => !v)
                      }}
                      title={textLargoEn ? (ampliadoEn ? 'Doble clic para contraer' : 'Doble clic para ampliar') : undefined}
                      style={{ cursor: textLargoEn ? 'pointer' : 'default' }}
                    >
                      <p className="text-[13px] text-text leading-relaxed whitespace-pre-wrap">
                        {respuestaEn.texto_respuesta}
                      </p>
                      {!ampliadoEn && textLargoEn && (
                        <div className="absolute bottom-0 left-0 right-0 h-10 pointer-events-none"
                             style={{ background: `linear-gradient(to top, ${BG_CARD}, transparent)` }} />
                      )}
                    </div>
                    {textLargoEn && (
                      <button
                        type="button"
                        className="text-[10px] text-primary hover:opacity-80 transition-opacity"
                        onClick={() => setAmpliadoEn((v) => !v)}
                      >
                        {ampliadoEn ? '▲ Contraer respuesta' : '▼ Ampliar respuesta · doble clic'}
                      </button>
                    )}
                    <div className="grid grid-cols-3 gap-x-2 gap-y-1">
                      <Metrica label="Latencia"   valor={`${respuestaEn.latencia_ms} ms`} />
                      <Metrica label="Tok/s"      valor={respuestaEn.tokens_por_segundo.toFixed(1)} />
                      <Metrica label="Coste"      valor={`$${respuestaEn.cost_usd.toFixed(8)}`} />
                      <Metrica label="Palabras"   valor={respuestaEn.palabras.toString()} />
                      <Metrica label="Sal/Ent"    valor={respuestaEn.ratio_sal_ent.toFixed(2)} />
                      <Metrica label="Div. léx."  valor={`${(respuestaEn.diversidad_lexica * 100).toFixed(0)}%`} />
                      <Metrica label="¢/100 pal." valor={`$${respuestaEn.coste_por_100_palabras.toFixed(8)}`} />
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Modal mapa mental ─────────────────────────────────────────── */}
      {modalMapaMental && svgMapaMental && (
        <VisorMapaMental
          svg={svgMapaMental}
          onClose={cerrarMapaMental}
          onDescargar={descargarMapaMentalPng}
        />
      )}

      {/* ── Modal lightbox imagen generativa ──────────────────────────── */}
      {mostrarModal && respuesta?.url_imagen && (
        <VisorImagen
          src={respuesta.url_imagen}
          onClose={cerrarModal}
          onDescargar={descargarImagen}
        />
      )}
    </>
  )
}

/* ── Subcomponentes ──────────────────────────────────────────────────────── */

function Metrica({ label, valor }: { label: string; valor: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-[9px] text-muted uppercase tracking-wider leading-tight">{label}</span>
      <span className="text-[11px] font-mono font-bold text-text leading-snug">{valor}</span>
    </div>
  )
}

/**
 * Boton del acordeon "Ver respuesta en ingles" con afordancia visual
 * dependiente del color del LLM (ADR-029). Hereda el patron de BtnImg:
 *
 * - Reposo: borde semitransparente + fondo muy tenue del color del LLM
 *   para insinuar que es interactivo sin gritarlo.
 * - Hover: el fondo se intensifica y aparece un halo del color del LLM
 *   para que se entienda que se puede pulsar.
 * - Active (mousedown): scale ligero hacia abajo, asi acompana el clic.
 * - Abierto: borde solido + halo suave permanente para senalar el estado.
 */
function BotonVerEn({ color, abierto, onClick }: { color: string; abierto: boolean; onClick: () => void }) {
  const [hov, setHov] = useState(false)
  const enfasis = hov || abierto
  return (
    <button
      type="button"
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      className="w-full flex items-center justify-between px-3 py-2 text-[11px] font-semibold uppercase tracking-wider rounded-md border-2 transition-all duration-150 cursor-pointer active:scale-[0.98]"
      style={{
        color,
        borderColor: enfasis ? color : `${color}66`,
        background: hov ? `${color}25` : abierto ? `${color}15` : `${color}0A`,
        boxShadow: hov
          ? `0 0 14px ${color}66, 0 2px 6px rgba(0,0,0,0.35)`
          : abierto
            ? `0 0 6px ${color}44`
            : 'none',
      }}
      title="Las respuestas en inglés se generan solo para métricas comparativas; no se valoran."
    >
      <span className="flex items-center gap-1.5">
        <span>🌐</span>
        Ver respuesta en inglés
      </span>
      <span className="text-[10px]">{abierto ? '▲' : '▼'}</span>
    </button>
  )
}

function BtnImg({ color, children, onClick }: { color: string; children: ReactNode; onClick: () => void }) {
  const [hov, setHov] = useState(false)
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      className="text-[11px] font-semibold py-1.5 px-2.5 rounded-lg flex items-center justify-center gap-1 transition-all duration-150 whitespace-nowrap"
      style={{
        color:      hov ? '#0F0F1C' : color,
        background: hov ? color     : `${color}25`,
        border:     `1px solid ${color}${hov ? '' : '70'}`,
      }}
    >
      {children}
    </button>
  )
}
