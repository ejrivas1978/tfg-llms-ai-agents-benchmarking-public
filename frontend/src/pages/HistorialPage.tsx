/**
 * Componente: HistorialPage
 * Ruta:       frontend/src/pages/HistorialPage.tsx
 *
 * Descripcion:
 *   Pantalla de historial con dos vistas segun el rol:
 *   - Usuario normal: lista de sus sesiones almacenadas en localStorage.
 *   - Admin (nick='admin'): login JWT + tabla paginada de todas las sesiones.
 *
 * Sprint: Sprint 3
 */

import { TOKENS } from '@/utils/tokens'
import { useEffect, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useNickStore } from '@/store/nickStore'
import { useAdminStore } from '@/store/adminStore'
import { useHistorialStore } from '@/store/historialStore'
import { useUsuarioStore } from '@/store/usuarioStore'
import { useToastStore } from '@/store/toastStore'
import LoginAdmin from '@/components/historial/LoginAdmin'
import TablaAdmin from '@/components/historial/TablaAdmin'
import TablaUsuarios from '@/components/historial/TablaUsuarios'
import TablaTarifas from '@/components/historial/TablaTarifas'
import EvalViewModal from '@/components/historial/EvalViewModal'
import ConfirmModal from '@/components/shared/ConfirmModal'
import { solicitarBorradoEvaluacion, obtenerEvaluacion, obtenerHistorialPorNick } from '@/services/benchmarkApi'
import type { TestCategory } from '@/types/benchmark'
import { formatFecha } from '@/utils/formatFecha'

const COLOR_CAT: Record<TestCategory, string> = {
  razonamiento: '#A855F7',
  codigo:       '#38BDF8',
  creativa:     TOKENS.cat3,
  concretas:    TOKENS.cat4,
  traduccion:   '#F472B6',
  resumen:      TOKENS.cat6,
  imagen:       TOKENS.errorText,
  libre:        '#94A3B8',
}

const ESTADO_LABEL: Record<string, string> = {
  completada:        'Ejecutada',
  fallida:           'Fallida',
  en_curso:          'En curso',
  pendiente:         'Pendiente',
  solicitud_borrado: 'Borrado solicitado',
}

const ESTADO_COLOR: Record<string, string> = {
  completada:        'text-green-400',
  fallida:           'text-red-400',
  en_curso:          'text-yellow-400',
  pendiente:         'text-muted',
  solicitud_borrado: 'text-orange-400',
}

export default function HistorialPage() {
  const nick      = useNickStore((s) => s.nick)
  const navigate  = useNavigate()

  const token       = useAdminStore((s) => s.token)
  const setSession  = useAdminStore((s) => s.setSession)

  // Sesion admin = token administrativo presente. La suscripcion directa
  // al store hace que la pagina re-renderice al login/logout admin.
  const esAdmin  = token !== null
  const sesiones = useHistorialStore((s) => s.sesiones[nick] ?? [])

  const usuarioToken           = useUsuarioStore((s) => s.token)
  const marcarSolicitudBorrado = useHistorialStore((s) => s.marcarSolicitudBorrado)
  const mostrarToast           = useToastStore((s) => s.mostrar)

  // ID de la evaluacion que el usuario ha pulsado para confirmar solicitud de borrado
  const [confirmandoId, setConfirmandoId] = useState<number | null>(null)

  const hidratar         = useHistorialStore((s) => s.hidratar)
  const eliminarSesion   = useHistorialStore((s) => s.eliminarSesion)
  const actualizarEstado = useHistorialStore((s) => s.actualizarEstado)

  // Carga desde BD el historial del evaluador activo.
  // Usa un endpoint publico (sin JWT) para que funcione aunque el token
  // haya expirado. El nick persiste en nickStore entre sesiones.
  useEffect(() => {
    if (esAdmin || !nick) return
    obtenerHistorialPorNick(nick)
      .then((sesionesDB) => hidratar(nick, sesionesDB))
      .catch((err) => console.error('[historial]', err))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nick])

  // Sincroniza el estado de las evaluaciones 'solicitud_borrado' con la BD al
  // cargar el historial: si el admin rechazó la solicitud, la BD ya tiene
  // 'completada' pero el localStorage sigue con 'solicitud_borrado'.
  useEffect(() => {
    const pendientes = sesiones.filter((s) => s.estado === 'solicitud_borrado')
    if (pendientes.length === 0 || esAdmin) return

    const sincronizar = async () => {
      await Promise.allSettled(
        pendientes.map(async (s) => {
          try {
            const sesionDB = await obtenerEvaluacion(s.id)
            if (sesionDB.estado !== 'solicitud_borrado') {
              actualizarEstado(nick, s.id, sesionDB.estado)
            }
          } catch (err) {
            const httpStatus = (err as { response?: { status: number } }).response?.status
            if (httpStatus === 404) eliminarSesion(nick, s.id)
          }
        }),
      )
    }
    sincronizar()
  // Solo al montar la vista de usuario (nick cambia cuando el usuario se identifica)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nick])

  const mutSolicitudBorrado = useMutation({
    mutationFn: (id: number) => solicitarBorradoEvaluacion(id),
    onSuccess: (_data, id) => {
      marcarSolicitudBorrado(nick, id)
      setConfirmandoId(null)
      mostrarToast('Solicitud de borrado enviada al administrador', 'exito')
    },
    onError: (error: unknown, id) => {
      setConfirmandoId(null)
      const status = (error as { response?: { status: number } }).response?.status
      if (status === 404) {
        // La evaluacion no existe en BD (borrada externamente): limpiar localStorage
        eliminarSesion(nick, id)
        mostrarToast('Esta evaluación ya no existe en el estudio y se ha eliminado de tu historial.', 'info')
      } else {
        mostrarToast('Error al enviar la solicitud. Inicia sesion e intentalo de nuevo.', 'error')
      }
    },
  })

  const [searchParams]  = useSearchParams()
  const [modalSesionId, setModalSesionId] = useState<number | null>(null)
  const [pestanaAdmin, setPestanaAdmin]   = useState<'comparativas' | 'usuarios' | 'tarifas'>(
    () => {
      const tab = searchParams.get('tab')
      if (tab === 'usuarios') return 'usuarios'
      if (tab === 'tarifas')  return 'tarifas'
      return 'comparativas'
    },
  )

  useEffect(() => {
    if (!nick) navigate('/', { replace: true })
  }, [nick, navigate])

  if (!nick) return null

  // ── Vista administrador ──────────────────────────────────────────────────
  if (esAdmin) {
    if (!token) {
      return (
        <div className="max-w-3xl mx-auto py-8">
          <p className="text-xs text-muted text-center mb-6">
            Introduce tus credenciales de administrador para ver todas las sesiones del estudio.
          </p>
          <LoginAdmin onLogin={setSession} />
        </div>
      )
    }

    return (
      <div className="max-w-5xl mx-auto space-y-4">
        {/* Barra de navegacion entre pestanas */}
        <div className="flex items-center gap-2 pb-2">
          {(['comparativas', 'usuarios', 'tarifas'] as const).map((p) => (
            <button
              key={p}
              onClick={() => setPestanaAdmin(p)}
              className={`px-4 py-1.5 text-sm font-medium rounded-lg transition-all duration-150
                border border-white/25 ${
                pestanaAdmin === p
                  ? 'bg-primary-l text-primary border-white/80 shadow-[0_0_14px_4px_rgba(255,255,255,0.45)]'
                  : 'text-muted hover:text-text hover:bg-primary-l hover:border-white/40'
              }`}
            >
              {p === 'comparativas' ? 'Comparativas' : p === 'usuarios' ? 'Usuarios' : 'Tarifas'}
            </button>
          ))}
        </div>

        {pestanaAdmin === 'comparativas' && (
          <TablaAdmin token={token} />
        )}
        {pestanaAdmin === 'usuarios' && (
          <TablaUsuarios token={token} />
        )}
        {pestanaAdmin === 'tarifas' && (
          <TablaTarifas token={token} />
        )}
      </div>
    )
  }

  // ── Vista usuario normal ─────────────────────────────────────────────────
  return (
    <>
    <div className="max-w-3xl mx-auto space-y-5">
      <div className="relative">
        <p className="text-base sm:text-xl font-semibold text-text uppercase tracking-widest mb-3 text-center
                       border border-text-alt/60 bg-primary/15 rounded-xl px-3 sm:px-5 py-2 sm:py-3
                       pr-20 sm:pr-5">
          Mis comparativas
        </p>
        <span className="absolute top-1/2 right-3 -translate-y-1/2
                          text-sm font-semibold text-[#FBBF24]
                          border border-[#FBBF24]/60 bg-[#FBBF24]/10 rounded-full px-3 py-1">
          @{nick}
        </span>
      </div>

      {sesiones.length === 0 ? (
        <div className="card flex flex-col items-center justify-center py-16 gap-3">
          <p className="text-muted text-sm">Aun no has ejecutado ningun benchmark.</p>
          <button className="btn-primary text-sm" onClick={() => navigate('/benchmark')}>
            Ejecutar primer benchmark
          </button>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <div className="space-y-3 min-w-[640px]">
          {sesiones.map((s) => (
            <div key={s.id}
                 className="card px-4 py-3 flex items-center gap-3 hover:border-primary/30 transition-colors">
              {/* # ID — ancho fijo */}
              <span className="text-xs text-muted font-mono w-10 flex-shrink-0">#{s.id}</span>

              {/* Categoria — contenedor de ancho fijo para alinear columnas */}
              <div className="w-28 flex-shrink-0 flex items-center">
                <span
                  className="text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full whitespace-nowrap"
                  style={{
                    color: COLOR_CAT[s.categoria] ?? '#8B949E',
                    background: `${COLOR_CAT[s.categoria] ?? '#8B949E'}20`,
                    border: `1px solid ${COLOR_CAT[s.categoria] ?? '#8B949E'}40`,
                  }}
                >
                  {s.categoria}
                </span>
              </div>

              {/* Prompt — ocupa el espacio restante */}
              <div className="flex-1 min-w-0">
                <p className="text-sm truncate">{s.prompt}</p>
              </div>

              {/* Estado — ancho fijo */}
              <span className={`text-xs font-medium w-20 flex-shrink-0 text-right ${ESTADO_COLOR[s.estado] ?? 'text-muted'}`}>
                {ESTADO_LABEL[s.estado] ?? s.estado}
              </span>

              {/* Fecha — ancho fijo */}
              <span className="text-xs text-muted flex-shrink-0 w-36 text-right">
                {formatFecha(s.created_at)}
              </span>

              {/* Accion — ancho fijo alineado a la derecha */}
              <div className="w-44 flex-shrink-0 flex flex-col items-end gap-1">
                {s.estado === 'solicitud_borrado' ? (
                  <span
                    className="text-xs font-semibold px-2.5 py-1 rounded-full whitespace-nowrap"
                    style={{ color: TOKENS.cat7, background: 'rgba(251,146,60,0.12)',
                             border: '1px solid rgba(251,146,60,0.45)' }}
                  >
                    ⏳ Borrado solicitado
                  </span>
                ) : s.estado === 'fallida' ? (
                  <button
                    className="btn-ghost text-xs"
                    onClick={() => setModalSesionId(s.id)}
                  >
                    Ver evaluación
                  </button>
                ) : s.estado === 'en_curso' || s.estado === 'pendiente' ? (
                  <span className="text-xs text-muted animate-pulse">En curso…</span>
                ) : (
                  // completada — accion principal + solicitud de borrado
                  <>
                    {s.evaluada ? (
                      <button
                        className="btn-ghost text-xs"
                        onClick={() => setModalSesionId(s.id)}
                      >
                        Ver evaluación
                      </button>
                    ) : (
                      <button
                        className="text-xs font-semibold px-2.5 py-1 rounded-full animate-pulse"
                        style={{ color: TOKENS.error, background: 'rgba(255,0,0,0.15)',
                                 border: '1px solid rgba(255,0,0,0.6)' }}
                        onClick={() => setModalSesionId(s.id)}
                      >
                        ● Finalizar evaluación
                      </button>
                    )}
                    {/* Solo si el usuario tiene sesion activa */}
                    {usuarioToken && (
                      <button
                        className="text-[10px] font-semibold px-2 py-0.5 rounded-md transition-all duration-200"
                        style={{
                          color:  TOKENS.errorText,
                          border: '1px solid rgba(248,113,113,0.55)',
                          background: 'transparent',
                        }}
                        onMouseEnter={(e) => {
                          const t = e.currentTarget
                          t.style.background  = 'rgba(248,113,113,0.12)'
                          t.style.borderColor = 'rgba(248,113,113,0.9)'
                          t.style.boxShadow   = '0 0 10px 2px rgba(248,113,113,0.45)'
                        }}
                        onMouseLeave={(e) => {
                          const t = e.currentTarget
                          t.style.background  = 'transparent'
                          t.style.borderColor = 'rgba(248,113,113,0.55)'
                          t.style.boxShadow   = 'none'
                        }}
                        onClick={() => setConfirmandoId(s.id)}
                      >
                        Solicitar borrado
                      </button>
                    )}
                  </>
                )}
              </div>
            </div>
          ))}
          </div>
        </div>
      )}

    </div>

    {modalSesionId !== null && (
      <EvalViewModal
        sesionId={modalSesionId}
        onClose={() => setModalSesionId(null)}
      />
    )}

    {confirmandoId !== null && (
      <ConfirmModal
        mensaje={`¿Solicitar al administrador el borrado de la evaluación #${confirmandoId}? El administrador revisará la solicitud y la eliminará si lo considera adecuado.`}
        textoBotom="Solicitar borrado"
        onConfirmar={() => mutSolicitudBorrado.mutate(confirmandoId)}
        onCancelar={() => setConfirmandoId(null)}
      />
    )}
    </>
  )
}
