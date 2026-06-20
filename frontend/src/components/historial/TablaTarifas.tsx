/**
 * Componente: TablaTarifas
 * Ruta:       frontend/src/components/historial/TablaTarifas.tsx
 *
 * Descripcion:
 *   Panel de gestion de tarifas LLM para el administrador.
 *   Muestra los cuatro proveedores con tres precios editables por fila:
 *     - Entrada (USD/Mtok)
 *     - Salida (USD/Mtok)
 *     - Entrada cacheado (USD/Mtok, opcional)
 *   Y dos costes relativos calculados por el backend (entrada y salida).
 *   El precio cacheado es opcional: si esta vacio, las llamadas con cache hit
 *   cobran todo al precio de entrada estandar (sin descuento).
 *
 *   Cambiar la tarifa crea una nueva version y refresca el cache de precios;
 *   NO recalcula los costes de respuestas LLM ya persistidas — solo afecta
 *   a las nuevas llamadas.
 *
 * Sprint: Sprint 4
 */

import { useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listarTarifasAdmin, actualizarTarifaAdmin } from '@/services/adminApi'
import type { LLMProveedor, RespuestaListaTarifas } from '@/types/admin'
import { useToastStore } from '@/store/toastStore'
import HistorialTarifaModal from '@/components/historial/HistorialTarifaModal'

interface Props {
  token: string
}

const NOMBRE_PROVEEDOR: Record<LLMProveedor, string> = {
  claude: 'Claude Sonnet 4.6',
  openai: 'GPT-4o',
  gemini: 'Gemini 2.5 Flash',
  grok:   'Grok 3',
}

const COLOR_PROVEEDOR: Record<LLMProveedor, string> = {
  claude: '#FB923C',
  openai: '#10B981',
  gemini: '#60A5FA',
  grok:   '#A78BFA',
}

type FilaEditada = {
  entrada: string; salida: string; cacheado: string;
  imagenGenerar: string; imagenEditar: string;
}

export default function TablaTarifas({ token }: Props) {
  const queryClient  = useQueryClient()
  const mostrarToast = useToastStore((s) => s.mostrar)

  const [edits, setEdits] = useState<Partial<Record<LLMProveedor, FilaEditada>>>({})
  const [historialAbierto, setHistorialAbierto] = useState<LLMProveedor | null>(null)

  const { data, isLoading, isError } = useQuery<RespuestaListaTarifas>({
    queryKey: ['admin-tarifas'],
    queryFn:  () => listarTarifasAdmin(token),
  })

  const guardar = useMutation({
    mutationFn: ({ proveedor, entrada, salida, cacheado, imagenGenerar, imagenEditar }: {
      proveedor: LLMProveedor; entrada: number; salida: number;
      cacheado: number | null;
      imagenGenerar: number | null; imagenEditar: number | null;
    }) =>
      actualizarTarifaAdmin(token, proveedor, {
        precio_entrada_usd_por_mtoken: entrada,
        precio_salida_usd_por_mtoken:  salida,
        precio_entrada_cacheado_usd_por_mtoken: cacheado,
        precio_imagen_generar_usd_por_imagen: imagenGenerar,
        precio_imagen_editar_usd_por_imagen:  imagenEditar,
      }),
    onSuccess: (lista, vars) => {
      queryClient.setQueryData(['admin-tarifas'], lista)
      setEdits((prev) => {
        const copia = { ...prev }
        delete copia[vars.proveedor]
        return copia
      })
      mostrarToast(`Tarifa de ${NOMBRE_PROVEEDOR[vars.proveedor]} actualizada`, 'exito')
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
                ?? 'No se pudo actualizar la tarifa'
      mostrarToast(msg, 'error')
    },
  })

  /**
   * Vista derivada: combina valores del servidor con los edits locales para
   * previsualizar relativos antes de pulsar Guardar.
   */
  const filas = useMemo(() => {
    if (!data) return []
    const efectivos = data.items.map((t) => {
      const e = edits[t.proveedor]
      const entrada = e ? parseFloat(e.entrada) : Number(t.precio_entrada_usd_por_mtoken)
      const salida  = e ? parseFloat(e.salida)  : Number(t.precio_salida_usd_por_mtoken)
      const cacheadoStr = e ? e.cacheado : (
        t.precio_entrada_cacheado_usd_por_mtoken != null
          ? Number(t.precio_entrada_cacheado_usd_por_mtoken).toFixed(8)
          : ''
      )
      const cacheado = cacheadoStr === '' ? null : parseFloat(cacheadoStr)
      const imagenGenerarStr = e ? e.imagenGenerar : (
        t.precio_imagen_generar_usd_por_imagen != null
          ? Number(t.precio_imagen_generar_usd_por_imagen).toFixed(8)
          : ''
      )
      const imagenGenerar = imagenGenerarStr === '' ? null : parseFloat(imagenGenerarStr)
      const imagenEditarStr = e ? e.imagenEditar : (
        t.precio_imagen_editar_usd_por_imagen != null
          ? Number(t.precio_imagen_editar_usd_por_imagen).toFixed(8)
          : ''
      )
      const imagenEditar = imagenEditarStr === '' ? null : parseFloat(imagenEditarStr)
      return {
        t, entrada, salida,
        cacheado, cacheadoStr,
        imagenGenerar, imagenGenerarStr,
        imagenEditar, imagenEditarStr,
      }
    })
    const validos = efectivos.filter(
      (f) => Number.isFinite(f.entrada) && Number.isFinite(f.salida)
          && f.entrada > 0 && f.salida > 0,
    )
    const baseEntrada = validos.length ? Math.min(...validos.map((f) => f.entrada)) : 0
    const baseSalida  = validos.length ? Math.min(...validos.map((f) => f.salida))  : 0

    return efectivos.map(({ t, entrada, salida, cacheado, cacheadoStr, imagenGenerar, imagenGenerarStr, imagenEditar, imagenEditarStr }) => {
      const editado = edits[t.proveedor] !== undefined
      const cacheadoValido = cacheado === null
        || (Number.isFinite(cacheado) && cacheado > 0 && cacheado <= entrada)
      const imagenGenerarValido = imagenGenerar === null
        || (Number.isFinite(imagenGenerar) && imagenGenerar > 0)
      const imagenEditarValido = imagenEditar === null
        || (Number.isFinite(imagenEditar) && imagenEditar > 0)
      const valido = Number.isFinite(entrada) && Number.isFinite(salida)
                  && entrada > 0 && salida > 0
                  && cacheadoValido && imagenGenerarValido && imagenEditarValido
      const relEntrada = valido && baseEntrada > 0 ? entrada / baseEntrada : t.coste_relativo_entrada
      const relSalida  = valido && baseSalida  > 0 ? salida  / baseSalida  : t.coste_relativo_salida
      return {
        t, entrada, salida,
        cacheado, cacheadoStr,
        imagenGenerar, imagenGenerarStr,
        imagenEditar, imagenEditarStr,
        relEntrada, relSalida, editado, valido,
      }
    })
  }, [data, edits])

  if (isLoading) {
    return <p className="text-sm text-muted text-center py-6">Cargando tarifas…</p>
  }
  if (isError || !data) {
    return <p className="text-sm text-red-400 text-center py-6">No se pudieron cargar las tarifas.</p>
  }

  const setField = (p: LLMProveedor, key: keyof FilaEditada, v: string) =>
    setEdits((prev) => {
      const actual = prev[p]
      const t = data.items.find((x) => x.proveedor === p)!
      const base: FilaEditada = actual ?? {
        entrada:  Number(t.precio_entrada_usd_por_mtoken).toFixed(8),
        salida:   Number(t.precio_salida_usd_por_mtoken).toFixed(8),
        cacheado: t.precio_entrada_cacheado_usd_por_mtoken != null
          ? Number(t.precio_entrada_cacheado_usd_por_mtoken).toFixed(8)
          : '',
        imagenGenerar: t.precio_imagen_generar_usd_por_imagen != null
          ? Number(t.precio_imagen_generar_usd_por_imagen).toFixed(8)
          : '',
        imagenEditar: t.precio_imagen_editar_usd_por_imagen != null
          ? Number(t.precio_imagen_editar_usd_por_imagen).toFixed(8)
          : '',
      }
      return { ...prev, [p]: { ...base, [key]: v } }
    })

  return (
    <div className="space-y-4">
      <div className="card px-4 py-3">
        <p className="text-xs text-muted leading-snug">
          Edita los precios de cada proveedor:{' '}
          <span className="font-mono text-white">Entrada</span>,{' '}
          <span className="font-mono text-white">Salida</span> y{' '}
          <span className="font-mono text-white">Cacheado</span> en USD por millón de tokens;{' '}
          <span className="font-mono text-white">Img gen</span> (texto→imagen, txt2img) y{' '}
          <span className="font-mono text-white">Img edit</span> (imagen→imagen, img2img) en USD por imagen.
          El cacheado y los dos de imagen son opcionales: si los dejas en blanco, las llamadas correspondientes
          cobran al precio estándar o no cobran nada. Los relativos se recalculan frente al proveedor más barato
          de cada columna. Los cambios afectan a las nuevas llamadas; las respuestas guardadas conservan la tarifa
          con la que se cobraron.
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[980px]">
          <thead>
            <tr className="text-[10px] uppercase tracking-wide text-muted border-b border-border">
              <th className="text-left  py-2 px-2 w-40">Proveedor</th>
              <th className="text-right py-2 px-2 w-24">Entrada $/Mtok</th>
              <th className="text-right py-2 px-2 w-24">Salida $/Mtok</th>
              <th className="text-right py-2 px-2 w-24">Cacheado $/Mtok</th>
              <th className="text-right py-2 px-2 w-20">Img gen $/img</th>
              <th className="text-right py-2 px-2 w-20">Img edit $/img</th>
              <th className="text-right py-2 px-2 w-16">Rel. ent.</th>
              <th className="text-right py-2 px-2 w-16">Rel. sal.</th>
              <th className="text-center py-2 px-2 w-20">Historial</th>
              <th className="text-right py-2 px-2 w-24">Acción</th>
            </tr>
          </thead>
          <tbody>
            {filas.map(({ t, entrada, salida, cacheado, cacheadoStr, imagenGenerar, imagenGenerarStr, imagenEditar, imagenEditarStr, relEntrada, relSalida, editado, valido }) => {
              const valEntrada = edits[t.proveedor]?.entrada ?? Number(t.precio_entrada_usd_por_mtoken).toFixed(8)
              const valSalida  = edits[t.proveedor]?.salida  ?? Number(t.precio_salida_usd_por_mtoken).toFixed(8)
              return (
                <tr key={t.proveedor}
                    className="border-b border-border hover:bg-primary-l/30 transition-colors">
                  <td className="py-2 px-2">
                    <span className="text-xs font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full whitespace-nowrap"
                          style={{
                            color: COLOR_PROVEEDOR[t.proveedor],
                            background: `${COLOR_PROVEEDOR[t.proveedor]}20`,
                            border: `1px solid ${COLOR_PROVEEDOR[t.proveedor]}50`,
                          }}>
                      {NOMBRE_PROVEEDOR[t.proveedor]}
                    </span>
                  </td>
                  <td className="py-2 px-2 text-right">
                    <input
                      type="number" step="0.00000001" min="0.00000001" max="9999.99999999"
                      value={valEntrada}
                      onChange={(e) => setField(t.proveedor, 'entrada', e.target.value)}
                      className="input-base w-24 text-right font-mono text-sm"
                    />
                  </td>
                  <td className="py-2 px-2 text-right">
                    <input
                      type="number" step="0.00000001" min="0.00000001" max="9999.99999999"
                      value={valSalida}
                      onChange={(e) => setField(t.proveedor, 'salida', e.target.value)}
                      className="input-base w-24 text-right font-mono text-sm"
                    />
                  </td>
                  <td className="py-2 px-2 text-right">
                    <input
                      type="number" step="0.00000001" min="0" max="9999.99999999"
                      value={cacheadoStr}
                      placeholder="—"
                      onChange={(e) => setField(t.proveedor, 'cacheado', e.target.value)}
                      className="input-base w-24 text-right font-mono text-sm"
                    />
                  </td>
                  <td className="py-2 px-2 text-right">
                    <input
                      type="number" step="0.00000001" min="0" max="9999.99999999"
                      value={imagenGenerarStr}
                      placeholder="—"
                      onChange={(e) => setField(t.proveedor, 'imagenGenerar', e.target.value)}
                      className="input-base w-20 text-right font-mono text-sm"
                      title="Coste por imagen generada desde texto (txt2img). Modelos: dall-e-3 / gemini-2.5-flash-image / grok-imagine-image. Vacío si no aplica."
                    />
                  </td>
                  <td className="py-2 px-2 text-right">
                    <input
                      type="number" step="0.00000001" min="0" max="9999.99999999"
                      value={imagenEditarStr}
                      placeholder="—"
                      onChange={(e) => setField(t.proveedor, 'imagenEditar', e.target.value)}
                      className="input-base w-20 text-right font-mono text-sm"
                      title="Coste por imagen editada con imagen de referencia (img2img). Modelos: gpt-image-1 / gemini-2.5-flash-image / grok-imagine-image-quality. Vacío si no aplica."
                    />
                  </td>
                  <td className="py-2 px-2 text-right font-mono text-xs">{relEntrada.toFixed(1)}x</td>
                  <td className="py-2 px-2 text-right font-mono text-xs">{relSalida.toFixed(1)}x</td>
                  <td className="py-2 px-2 text-center">
                    <button
                      className="text-[11px] font-medium px-2 py-1 rounded-lg transition-colors hover:bg-primary-l/50"
                      style={{
                        background: 'rgba(255,255,255,0.04)',
                        border:     '1px solid rgba(255,255,255,0.15)',
                        color:      '#94A3B8',
                      }}
                      onClick={() => setHistorialAbierto(t.proveedor)}
                      title={`Ultima edicion: ${t.actualizado_por ?? '—'} · v#${t.id}`}
                    >
                      Ver historial
                    </button>
                  </td>
                  <td className="py-2 px-2 text-right">
                    <button
                      className="text-xs font-semibold px-3 py-1 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                      style={{
                        background: editado && valido ? 'rgba(52,211,153,0.15)' : 'rgba(255,255,255,0.05)',
                        border:     `1px solid ${editado && valido ? 'rgba(52,211,153,0.55)' : 'rgba(255,255,255,0.15)'}`,
                        color:      editado && valido ? '#34D399' : '#94A3B8',
                      }}
                      disabled={!editado || !valido || guardar.isPending}
                      onClick={() => guardar.mutate({ proveedor: t.proveedor, entrada, salida, cacheado, imagenGenerar, imagenEditar })}
                    >
                      {guardar.isPending && guardar.variables?.proveedor === t.proveedor
                        ? 'Guardando…'
                        : 'Guardar'}
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {historialAbierto && (
        <HistorialTarifaModal
          token={token}
          proveedor={historialAbierto}
          nombreProveedor={NOMBRE_PROVEEDOR[historialAbierto]}
          colorProveedor={COLOR_PROVEEDOR[historialAbierto]}
          onClose={() => setHistorialAbierto(null)}
        />
      )}
    </div>
  )
}
