/**
 * Componente: DateTimePicker
 * Ruta:       frontend/src/components/shared/DateTimePicker.tsx
 *
 * Descripcion:
 *   Input de fecha y hora controlado, sustituto del nativo
 *   <input type="datetime-local"> cuando se necesita garantizar el formato
 *   DD/MM/YYYY HH:mm con independencia del locale del SO. El popover usa
 *   react-day-picker (locale es) para el almanaque y dos "tiles" grandes
 *   para HH y MM que, al pulsarse, despliegan rejillas con todas las
 *   opciones (24 horas / 60 minutos) para seleccion visual rapida.
 *
 * Contrato de valor:
 *   - value: cadena en formato "YYYY-MM-DDTHH:MM" (compatible con la salida
 *     del antiguo input nativo, que el helper aIsoUtc() del adminApi
 *     convierte despues a ISO 8601 UTC para el backend).
 *   - onChange: misma cadena (o vacia si el usuario limpia el campo).
 *
 * Sprint: Sprint 4
 */

import type React from 'react'
import { useEffect, useRef, useState } from 'react'
import { DayPicker } from 'react-day-picker'
import { es } from 'date-fns/locale'
import { format, parse } from 'date-fns'
import 'react-day-picker/dist/style.css'
import { TOKENS } from '@/utils/tokens'

interface Props {
  value:       string
  onChange:    (valor: string) => void
  placeholder?: string
  ariaLabel?:  string
  /** Para alinear la apariencia con los demas filtros de TablaAdmin. */
  className?:  string
}

const FORMATO_INTERNO = "yyyy-MM-dd'T'HH:mm"
const FORMATO_VISIBLE = 'dd/MM/yyyy HH:mm'

function parsearValor(valor: string): Date | null {
  if (!valor) return null
  // El input emite siempre yyyy-MM-ddTHH:mm; si llega algo raro devolvemos null.
  const fecha = parse(valor, FORMATO_INTERNO, new Date())
  return isNaN(fecha.getTime()) ? null : fecha
}

function formatearInterno(fecha: Date): string {
  return format(fecha, FORMATO_INTERNO)
}

function formatearVisible(fecha: Date): string {
  return format(fecha, FORMATO_VISIBLE)
}

type GridAbierto = 'horas' | 'minutos' | null

export default function DateTimePicker({
  value,
  onChange,
  placeholder = 'dd/mm/aaaa --:--',
  ariaLabel,
  className = '',
}: Props) {
  const [abierto, setAbierto] = useState(false)
  const [gridAbierto, setGridAbierto] = useState<GridAbierto>(null)
  // Buffers de edicion: cuando el input de hora/minuto tiene foco mostramos
  // el texto en bruto (sin padStart) para no bloquear el segundo digito.
  // null = no editando, se muestra el valor formateado del estado padre.
  const [bufferHora, setBufferHora]     = useState<string | null>(null)
  const [bufferMinuto, setBufferMinuto] = useState<string | null>(null)
  const fechaActual = parsearValor(value)
  const horaActualNum   = fechaActual ? fechaActual.getHours()   : 0
  const minutoActualNum = fechaActual ? fechaActual.getMinutes() : 0
  const horaActual   = horaActualNum.toString().padStart(2, '0')
  const minutoActual = minutoActualNum.toString().padStart(2, '0')
  const refRoot = useRef<HTMLDivElement>(null)

  // Cierra el popover al pulsar fuera o pulsar Escape; tambien colapsa la
  // rejilla expandida si esta abierta (Escape colapsa primero la rejilla,
  // segundo el popover entero).
  useEffect(() => {
    if (!abierto) return
    const fueraClick = (e: MouseEvent) => {
      if (refRoot.current && !refRoot.current.contains(e.target as Node)) {
        setAbierto(false)
        setGridAbierto(null)
      }
    }
    const escape = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      if (gridAbierto) setGridAbierto(null)
      else setAbierto(false)
    }
    document.addEventListener('mousedown', fueraClick)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('mousedown', fueraClick)
      document.removeEventListener('keydown', escape)
    }
  }, [abierto, gridAbierto])

  const fijarFecha = (d: Date | undefined) => {
    if (!d) {
      onChange('')
      return
    }
    // Conserva la hora actual si ya habia una; si no, 00:00.
    const base = fechaActual ?? new Date(d)
    const nueva = new Date(d)
    nueva.setHours(base.getHours(), base.getMinutes(), 0, 0)
    onChange(formatearInterno(nueva))
  }

  const fijarHoraMinuto = (h: number, m: number) => {
    const base = fechaActual ?? new Date()
    const nueva = new Date(base)
    nueva.setHours(
      Math.max(0, Math.min(23, h)),
      Math.max(0, Math.min(59, m)),
      0, 0,
    )
    onChange(formatearInterno(nueva))
  }

  const limpiar = () => {
    onChange('')
    setAbierto(false)
    setGridAbierto(null)
  }

  const elegirHora = (h: number) => {
    setBufferHora(null)
    fijarHoraMinuto(h, minutoActualNum)
    setGridAbierto(null)
  }

  const elegirMinuto = (m: number) => {
    setBufferMinuto(null)
    fijarHoraMinuto(horaActualNum, m)
    setGridAbierto(null)
  }

  // Estilo unificado de cada celda de la rejilla horaria.
  const estiloCelda = (seleccionada: boolean): React.CSSProperties => ({
    background:   seleccionada ? `linear-gradient(135deg, ${TOKENS.primary}, ${TOKENS.primaryGrad})` : 'rgba(157,78,221,0.08)',
    border:       `1px solid ${seleccionada ? '#9D4EDD' : 'rgba(157,78,221,0.28)'}`,
    color:        seleccionada ? '#FFFFFF' : '#F4F1FF',
    borderRadius: '8px',
    fontWeight:   seleccionada ? 700 : 500,
    boxShadow:    seleccionada ? '0 2px 10px rgba(157, 78, 221, 0.5)' : undefined,
  })

  const etiquetaBoton = fechaActual ? formatearVisible(fechaActual) : placeholder

  return (
    <div ref={refRoot} className="relative">
      <button
        type="button"
        aria-label={ariaLabel}
        onClick={() => setAbierto((v) => !v)}
        className={`input-base text-xs py-1.5 w-full text-left flex items-center justify-between gap-2 ${className}`}
        style={{
          background:   '#0F0F1C',
          borderColor:  abierto ? '#9D4EDD' : 'rgba(157,78,221,0.35)',
          borderRadius: '10px',
          color:        fechaActual ? '#F4F1FF' : 'rgba(192,188,220,0.7)',
        }}
      >
        <span className="font-mono">{etiquetaBoton}</span>
        <span className="text-primary text-sm leading-none flex-shrink-0" aria-hidden>📅</span>
      </button>

      {abierto && (
        <div
          className="absolute z-40 mt-1 rounded-card shadow-card-lg border"
          style={{
            background:   '#0F0F1C',
            borderColor:  'rgba(157,78,221,0.45)',
            minWidth:     '320px',
          }}
        >
          <div className="p-3">
            <DayPicker
              mode="single"
              selected={fechaActual ?? undefined}
              onSelect={fijarFecha}
              locale={es}
              weekStartsOn={1}
              showOutsideDays
              className="rdp-tfg"
            />

            {/* Tiles HH : MM — al pulsar/foco despliegan la rejilla; tambien aceptan tecleo manual */}
            <div className="pt-3 mt-1 border-t border-border">
              <p className="text-[10px] text-muted uppercase tracking-wider font-semibold text-center mb-2">
                Hora
              </p>
              <div className="flex items-center justify-center gap-2">
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={2}
                  value={bufferHora ?? horaActual}
                  onFocus={(e) => {
                    setGridAbierto('horas')
                    // Sin padStart durante edicion: muestra "4" en lugar de "04"
                    // para que el usuario pueda teclear el segundo digito.
                    setBufferHora(horaActualNum.toString())
                    e.currentTarget.select()
                  }}
                  onClick={() => setGridAbierto('horas')}
                  onChange={(e) => {
                    const soloDigitos = e.target.value.replace(/\D/g, '').slice(0, 2)
                    setBufferHora(soloDigitos)
                    if (soloDigitos === '') return
                    const num = parseInt(soloDigitos, 10)
                    fijarHoraMinuto(Math.max(0, Math.min(23, num)), minutoActualNum)
                  }}
                  onBlur={() => setBufferHora(null)}
                  className="font-mono text-2xl font-bold w-16 py-2 rounded-lg transition-all text-center cursor-pointer focus:outline-none"
                  style={{
                    background:   gridAbierto === 'horas' ? `linear-gradient(135deg, ${TOKENS.primary}, ${TOKENS.primaryGrad})` : 'rgba(157,78,221,0.12)',
                    border:       `1.5px solid ${gridAbierto === 'horas' ? '#9D4EDD' : 'rgba(157,78,221,0.4)'}`,
                    color:        '#FFFFFF',
                    boxShadow:    gridAbierto === 'horas' ? '0 0 14px rgba(157, 78, 221, 0.55)' : undefined,
                  }}
                  aria-label="Hora (tecleala o pulsala para abrir el selector)"
                />
                <span className="text-primary text-2xl font-bold">:</span>
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={2}
                  value={bufferMinuto ?? minutoActual}
                  onFocus={(e) => {
                    setGridAbierto('minutos')
                    setBufferMinuto(minutoActualNum.toString())
                    e.currentTarget.select()
                  }}
                  onClick={() => setGridAbierto('minutos')}
                  onChange={(e) => {
                    const soloDigitos = e.target.value.replace(/\D/g, '').slice(0, 2)
                    setBufferMinuto(soloDigitos)
                    if (soloDigitos === '') return
                    const num = parseInt(soloDigitos, 10)
                    fijarHoraMinuto(horaActualNum, Math.max(0, Math.min(59, num)))
                  }}
                  onBlur={() => setBufferMinuto(null)}
                  className="font-mono text-2xl font-bold w-16 py-2 rounded-lg transition-all text-center cursor-pointer focus:outline-none"
                  style={{
                    background:   gridAbierto === 'minutos' ? `linear-gradient(135deg, ${TOKENS.primary}, ${TOKENS.primaryGrad})` : 'rgba(157,78,221,0.12)',
                    border:       `1.5px solid ${gridAbierto === 'minutos' ? '#9D4EDD' : 'rgba(157,78,221,0.4)'}`,
                    color:        '#FFFFFF',
                    boxShadow:    gridAbierto === 'minutos' ? '0 0 14px rgba(157, 78, 221, 0.55)' : undefined,
                  }}
                  aria-label="Minuto (tecleala o pulsala para abrir el selector)"
                />
              </div>

              {/* Rejilla expandida — modal/popover dentro del propio popover */}
              {gridAbierto === 'horas' && (
                <div className="mt-3 p-2 rounded-lg" style={{ background: 'rgba(8,8,16,0.65)', border: '1px solid rgba(157,78,221,0.25)' }}>
                  <p className="text-[10px] text-muted text-center mb-2 font-semibold uppercase tracking-wider">
                    Selecciona hora (00–23)
                  </p>
                  <div className="grid grid-cols-6 gap-1.5">
                    {Array.from({ length: 24 }, (_, h) => (
                      <button
                        key={h}
                        type="button"
                        onClick={() => elegirHora(h)}
                        className="font-mono text-xs py-1.5 transition-colors hover:brightness-125"
                        style={estiloCelda(h === horaActualNum)}
                      >
                        {h.toString().padStart(2, '0')}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {gridAbierto === 'minutos' && (
                <div className="mt-3 p-2 rounded-lg" style={{ background: 'rgba(8,8,16,0.65)', border: '1px solid rgba(157,78,221,0.25)' }}>
                  <p className="text-[10px] text-muted text-center mb-2 font-semibold uppercase tracking-wider">
                    Selecciona minuto (00–59)
                  </p>
                  <div className="grid grid-cols-10 gap-1">
                    {Array.from({ length: 60 }, (_, m) => (
                      <button
                        key={m}
                        type="button"
                        onClick={() => elegirMinuto(m)}
                        className="font-mono text-[11px] py-1 transition-colors hover:brightness-125"
                        style={estiloCelda(m === minutoActualNum)}
                      >
                        {m.toString().padStart(2, '0')}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Acciones */}
            <div className="flex items-center justify-between gap-2 mt-3">
              <button
                type="button"
                onClick={limpiar}
                disabled={!fechaActual}
                className="text-[11px] text-red-400 hover:text-red-300 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                ✕ Limpiar
              </button>
              <button
                type="button"
                onClick={() => setAbierto(false)}
                className="text-[11px] font-semibold px-3 py-1.5 rounded-lg transition-colors"
                style={{
                  color:      '#FFFFFF',
                  background: 'rgba(157,78,221,0.85)',
                  border:     '1px solid rgba(157,78,221,1)',
                }}
              >
                Aceptar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
