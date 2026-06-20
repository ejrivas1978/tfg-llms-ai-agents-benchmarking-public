/**
 * Componente: TablaUsuarios
 * Ruta:       frontend/src/components/historial/TablaUsuarios.tsx
 *
 * Descripcion:
 *   Panel de gestion de usuarios web para el administrador.
 *   Muestra todos los usuarios registrados con su estado, cuota y acciones:
 *   - Conceder acceso a usuarios pendiente_acceso (asigna cuota inicial)
 *   - Ampliar cuota de consultas a usuarios habilitados o pendiente_ampliar_tokens
 *   - Eliminar usuario y todas sus evaluaciones asociadas
 *
 * Sprint: Sprint 4
 */

import { TOKENS } from '@/utils/tokens'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  listarUsuariosAdmin,
  concederAccesoAdmin,
  ampliarConsultasAdmin,
  eliminarUsuarioAdmin,
  resetearEvaluacionesUsuario,
  marcarGuiaVistaAdmin,
  resetearGuiaUsuario,
  promoverAdminUsuario,
  quitarAdminUsuario,
} from '@/services/adminApi'
import type { RespuestaUsuarioApp, EstadoUsuarioApp } from '@/types/auth'
import ConfirmModal from '@/components/shared/ConfirmModal'
import { useToastStore } from '@/store/toastStore'
import { useAdminStore } from '@/store/adminStore'
import { formatFecha } from '@/utils/formatFecha'

interface Props {
  token: string
}

const ESTADO_LABEL: Record<EstadoUsuarioApp, string> = {
  pendiente_acceso:         'Pendiente acceso',
  habilitado:               'Habilitado',
  pendiente_ampliar_tokens: 'Solicita mas cuota',
}

const ESTADO_ESTILOS: Record<EstadoUsuarioApp, { color: string; bg: string; border: string }> = {
  pendiente_acceso:         { color: TOKENS.cat3, bg: 'rgba(251,191,36,0.10)',  border: 'rgba(251,191,36,0.35)'  },
  habilitado:               { color: TOKENS.cat4, bg: 'rgba(52,211,153,0.10)',  border: 'rgba(52,211,153,0.35)'  },
  pendiente_ampliar_tokens: { color: TOKENS.cat6, bg: 'rgba(129,140,248,0.10)', border: 'rgba(129,140,248,0.35)' },
}

type AccionActiva = {
  tipo: 'conceder' | 'ampliar'
  id: number
  nick: string
  cuotaActual: number
}


/* ── Modal de formulario para conceder acceso / ampliar cuota ───────────── */
interface FormModalProps {
  accion: AccionActiva
  cargando: boolean
  onConfirmar: (valor: number) => void
  onCancelar: () => void
}

function FormModal({ accion, cargando, onConfirmar, onCancelar }: FormModalProps) {
  const esConceder = accion.tipo === 'conceder'
  const [valor, setValor] = useState(esConceder ? '10' : '5')
  const num = parseInt(valor, 10)
  const nuevaCuota = accion.cuotaActual + (isNaN(num) ? 0 : num)
  const resultadoValido = !isNaN(num) && num !== 0 && (esConceder ? num >= 1 : nuevaCuota >= 0)

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.65)' }}
      onClick={onCancelar}
    >
      <div
        className="card p-6 w-full max-w-sm shadow-card-lg space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div>
          <p className="font-semibold text-sm mb-1">
            {esConceder ? 'Conceder acceso' : 'Ajustar cuota de consultas'}
          </p>
          <p className="text-xs text-muted">
            Usuario: <span className="text-white font-medium">@{accion.nick}</span>
            {!esConceder && accion.cuotaActual > 0 && (
              <> · Cuota actual: <span className="font-mono">{accion.cuotaActual}</span></>
            )}
          </p>
        </div>

        <div className="space-y-1">
          <label className="text-[10px] text-muted uppercase tracking-wide font-medium">
            {esConceder ? 'Consultas a asignar' : 'Ajuste (positivo para ampliar, negativo para reducir)'}
          </label>
          <input
            type="number"
            className="input-base w-full text-center font-mono"
            value={valor}
            onChange={(e) => setValor(e.target.value)}
            autoFocus
            onKeyDown={(e) => { if (e.key === 'Enter' && resultadoValido) onConfirmar(num) }}
          />
          {!esConceder && !isNaN(num) && num !== 0 && (
            <p className={`text-[11px] text-center ${nuevaCuota < 0 ? 'text-red-400' : 'text-muted'}`}>
              Nueva cuota total:{' '}
              <span className="font-mono text-white">{Math.max(0, nuevaCuota)}</span>
              {nuevaCuota < 0 && ' (mínimo 0)'}
            </p>
          )}
        </div>

        <div className="flex justify-end gap-2">
          <button className="btn-ghost text-sm" onClick={onCancelar} disabled={cargando}>
            Cancelar
          </button>
          <button
            className="btn-primary text-sm"
            onClick={() => onConfirmar(num)}
            disabled={!resultadoValido || cargando}
          >
            {cargando
              ? 'Guardando…'
              : esConceder
                ? 'Conceder acceso'
                : num < 0 ? 'Reducir cuota' : 'Ampliar cuota'}
          </button>
        </div>
      </div>
    </div>
  )
}

/* ── Modal de confirmacion de reset de evaluaciones ────────────────────── */
interface ResetModalProps {
  nick:       string
  esAdmin:    boolean
  cargando:   boolean
  onConfirmar: (nuevaCuota: number) => void
  onCancelar:  () => void
}

function ResetModal({ nick, esAdmin, cargando, onConfirmar, onCancelar }: ResetModalProps) {
  const [cuota, setCuota] = useState('10')
  const num = parseInt(cuota, 10)
  const valido = !isNaN(num) && num >= 0

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.72)' }}
      onClick={onCancelar}
    >
      <div
        className="card p-6 w-full max-w-sm shadow-card-lg space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Cabecera destructiva */}
        <div className="flex items-start gap-3">
          <span className="text-2xl flex-shrink-0">⚠️</span>
          <div>
            <p className="font-semibold text-sm text-red-400">
              Resetear evaluaciones de @{nick}
            </p>
            <p className="text-xs text-muted mt-1 leading-snug">
              Se eliminarán <span className="text-white font-semibold">todas las evaluaciones</span> de este usuario.
              El usuario permanecerá activo con la nueva cuota asignada y el contador a cero.
              <span className="block mt-1 text-red-400/80">Esta acción es irreversible.</span>
            </p>
            {esAdmin && (
              <p className="text-[11px] text-muted mt-2 leading-snug px-2 py-1.5 rounded"
                 style={{ background: 'rgba(251,191,36,0.08)', border: '1px solid rgba(251,191,36,0.30)' }}>
                <span className="text-yellow-400 font-semibold">Nota:</span> este usuario es{' '}
                administrador, así que la cuota está inactiva ahora. La nueva cuota que asignes solo se
                aplicará cuando se le quite el rol admin en el futuro.
              </p>
            )}
          </div>
        </div>

        {/* Input nueva cuota */}
        <div className="space-y-1">
          <label className="text-[10px] text-muted uppercase tracking-wide font-medium">
            Nueva cuota de consultas tras el reset
            {esAdmin && <span className="normal-case text-muted/70"> (se aplicará al degradar)</span>}
          </label>
          <input
            type="number"
            min={0}
            className="input-base w-full text-center font-mono"
            value={cuota}
            onChange={(e) => setCuota(e.target.value)}
            autoFocus
            onKeyDown={(e) => { if (e.key === 'Enter' && valido) onConfirmar(num) }}
          />
          <p className="text-[11px] text-muted text-center">
            El contador de consultas usadas se pondrá a <span className="font-mono text-white">0</span>
          </p>
        </div>

        <div className="flex justify-end gap-2">
          <button className="btn-ghost text-sm" onClick={onCancelar} disabled={cargando}>
            Cancelar
          </button>
          <button
            className="text-sm font-semibold px-4 py-1.5 rounded-lg transition-colors"
            style={{
              background: 'rgba(248,113,113,0.15)',
              border:     '1px solid rgba(248,113,113,0.5)',
              color:      TOKENS.errorText,
            }}
            onClick={() => onConfirmar(num)}
            disabled={!valido || cargando}
          >
            {cargando ? 'Reseteando…' : 'Confirmar reset'}
          </button>
        </div>
      </div>
    </div>
  )
}

/* ── Modal de promocion a administrador ─────────────────────────────────── */
interface PromoteModalProps {
  nick:       string
  cargando:   boolean
  onConfirmar: (email: string) => void
  onCancelar:  () => void
}

function PromoteModal({ nick, cargando, onConfirmar, onCancelar }: PromoteModalProps) {
  const [email, setEmail] = useState('')
  // Validacion ligera de email — la final la hace Pydantic en el backend.
  const valido = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.65)' }}
      onClick={onCancelar}
    >
      <div
        className="card p-6 w-full max-w-sm shadow-card-lg space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-3">
          <span className="text-2xl flex-shrink-0">👑</span>
          <div>
            <p className="font-semibold text-sm" style={{ color: TOKENS.cat3 }}>
              Promover a administrador
            </p>
            <p className="text-xs text-muted mt-1 leading-snug">
              Vas a otorgar privilegios de administración a{' '}
              <span className="text-white font-medium">@{nick}</span>. Sigue accediendo
              con su nick + contraseña actuales pero ahora con permisos del panel admin.
            </p>
          </div>
        </div>

        <div className="space-y-1">
          <label className="text-[10px] text-muted uppercase tracking-wide font-medium">
            Email del administrador (obligatorio)
          </label>
          <input
            type="email"
            className="input-base w-full"
            placeholder="ejemplo@dominio.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoFocus
            onKeyDown={(e) => { if (e.key === 'Enter' && valido) onConfirmar(email) }}
          />
        </div>

        <div className="flex justify-end gap-2">
          <button className="btn-ghost text-sm" onClick={onCancelar} disabled={cargando}>
            Cancelar
          </button>
          <button
            className="text-sm font-semibold px-4 py-1.5 rounded-lg transition-colors"
            style={{
              background: 'rgba(251,191,36,0.15)',
              border:     '1px solid rgba(251,191,36,0.55)',
              color:      TOKENS.cat3,
            }}
            onClick={() => onConfirmar(email)}
            disabled={!valido || cargando}
          >
            {cargando ? 'Promoviendo…' : 'Confirmar promoción'}
          </button>
        </div>
      </div>
    </div>
  )
}

/* ── Componente principal ───────────────────────────────────────────────── */
export default function TablaUsuarios({ token }: Props) {
  const queryClient  = useQueryClient()
  // Solo el admin root puede promover y degradar a otros. Los admins
  // promovidos ven el resto del panel pero no estos dos botones.
  const esRoot       = useAdminStore((s) => s.esRoot)
  const mostrarToast = useToastStore((s) => s.mostrar)

  const [accionActiva,     setAccionActiva]     = useState<AccionActiva | null>(null)
  const [eliminandoUsuario, setEliminandoUsuario] = useState<RespuestaUsuarioApp | null>(null)
  const [resetandoUsuario,  setResetandoUsuario]  = useState<{ id: number; nick: string; esAdmin: boolean } | null>(null)
  const [promoviendoUsuario, setPromoviendoUsuario] = useState<{ id: number; nick: string } | null>(null)
  const [degradandoUsuario,  setDegradandoUsuario]  = useState<RespuestaUsuarioApp | null>(null)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin-usuarios'],
    queryFn:  () => listarUsuariosAdmin(token),
  })

  const invalidar = () => queryClient.invalidateQueries({ queryKey: ['admin-usuarios'] })

  const mutConceder = useMutation({
    mutationFn: ({ id, cuota }: { id: number; cuota: number }) =>
      concederAccesoAdmin(token, id, cuota),
    onSuccess: (u) => {
      invalidar()
      setAccionActiva(null)
      mostrarToast(`Acceso concedido a @${u.nick} (cuota: ${u.cuota_asignada} consultas)`, 'exito')
    },
    onError: () => mostrarToast('Error al conceder acceso', 'error'),
  })

  const mutAmpliar = useMutation({
    mutationFn: ({ id, adicionales }: { id: number; adicionales: number }) =>
      ampliarConsultasAdmin(token, id, adicionales),
    onSuccess: (u, vars) => {
      invalidar()
      setAccionActiva(null)
      const accion = vars.adicionales < 0 ? 'reducida' : 'ampliada'
      mostrarToast(`Cuota ${accion} para @${u.nick} — nueva cuota: ${u.cuota_asignada}`, 'exito')
    },
    onError: () => mostrarToast('Error al ajustar la cuota', 'error'),
  })

  const mutReset = useMutation({
    mutationFn: ({ id, nuevaCuota }: { id: number; nuevaCuota: number }) =>
      resetearEvaluacionesUsuario(token, id, nuevaCuota),
    onSuccess: (resultado) => {
      const nick = resetandoUsuario?.nick ?? '?'
      invalidar()
      queryClient.invalidateQueries({ queryKey: ['admin-comparativas'] })
      setResetandoUsuario(null)
      mostrarToast(
        `Evaluaciones de @${nick} eliminadas (${resultado.evaluaciones_eliminadas}) · nueva cuota: ${resultado.usuario.cuota_asignada}`,
        'exito',
      )
    },
    onError: () => mostrarToast('Error al resetear las evaluaciones', 'error'),
  })

  const mutEliminar = useMutation({
    mutationFn: (id: number) => eliminarUsuarioAdmin(token, id),
    onSuccess: (resultado) => {
      const nick = eliminandoUsuario?.nick ?? '?'
      invalidar()
      mostrarToast(
        `Usuario @${nick} eliminado (${resultado.evaluaciones_eliminadas} evaluacion${resultado.evaluaciones_eliminadas !== 1 ? 'es' : ''} borrada${resultado.evaluaciones_eliminadas !== 1 ? 's' : ''})`,
        'exito',
      )
      setEliminandoUsuario(null)
    },
    onError: () => mostrarToast('Error al eliminar el usuario', 'error'),
  })

  const mutToggleGuia = useMutation({
    mutationFn: ({ id, vista }: { id: number; vista: boolean }) =>
      vista ? resetearGuiaUsuario(token, id) : marcarGuiaVistaAdmin(token, id),
    onSuccess: (u) => {
      invalidar()
      mostrarToast(
        u.guia_vista
          ? `Guía marcada como vista para @${u.nick}`
          : `Guía reseteada para @${u.nick} — la verá al entrar`,
        'exito',
      )
    },
    onError: () => mostrarToast('Error al actualizar el estado de la guía', 'error'),
  })

  const mutPromover = useMutation({
    mutationFn: ({ id, email }: { id: number; email: string }) =>
      promoverAdminUsuario(token, id, email),
    onSuccess: (u) => {
      invalidar()
      setPromoviendoUsuario(null)
      mostrarToast(`@${u.nick} ahora es administrador (${u.email})`, 'exito')
    },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: { detail?: string } } }
      mostrarToast(e?.response?.data?.detail ?? 'Error al promover el usuario', 'error')
    },
  })

  const mutDegradar = useMutation({
    mutationFn: (id: number) => quitarAdminUsuario(token, id),
    onSuccess: (u) => {
      invalidar()
      const nick = degradandoUsuario?.nick ?? u.nick
      setDegradandoUsuario(null)
      mostrarToast(`@${nick} ya no es administrador`, 'exito')
    },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: { detail?: string } } }
      mostrarToast(e?.response?.data?.detail ?? 'Error al quitar privilegios', 'error')
    },
  })

  const onConfirmarAccion = (valor: number) => {
    if (!accionActiva) return
    if (accionActiva.tipo === 'conceder') {
      mutConceder.mutate({ id: accionActiva.id, cuota: valor })
    } else {
      mutAmpliar.mutate({ id: accionActiva.id, adicionales: valor })
    }
  }

  const accionCargando = mutConceder.isPending || mutAmpliar.isPending

  // Ordena: primero pendiente_acceso, luego pendiente_ampliar_tokens, luego habilitados
  const usuariosOrdenados = [...(data?.items ?? [])].sort((a, b) => {
    const orden: Record<EstadoUsuarioApp, number> = {
      pendiente_acceso: 0, pendiente_ampliar_tokens: 1, habilitado: 2,
    }
    return orden[a.estado] - orden[b.estado]
  })

  return (
    <div className="space-y-4">

      {/* Cabecera */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h2 className="text-base font-semibold">
          Gestión de usuarios
          {data && (
            <span className="ml-2 text-xs text-muted font-normal">
              ({data.total} usuario{data.total !== 1 ? 's' : ''})
            </span>
          )}
        </h2>
      </div>

      {/* Leyenda rapida de estados pendientes */}
      {data && data.items.some((u) => u.estado !== 'habilitado') && (
        <div className="rounded-xl border border-border px-4 py-3 text-xs text-muted flex flex-wrap gap-x-6 gap-y-1.5">
          {data.items.filter((u) => u.estado === 'pendiente_acceso').length > 0 && (
            <span>
              <span className="font-bold" style={{ color: TOKENS.cat3 }}>
                {data.items.filter((u) => u.estado === 'pendiente_acceso').length}
              </span>
              {' '}usuario{data.items.filter((u) => u.estado === 'pendiente_acceso').length !== 1 ? 's' : ''} pendiente{data.items.filter((u) => u.estado === 'pendiente_acceso').length !== 1 ? 's' : ''} de acceso
            </span>
          )}
          {data.items.filter((u) => u.estado === 'pendiente_ampliar_tokens').length > 0 && (
            <span>
              <span className="font-bold" style={{ color: TOKENS.cat6 }}>
                {data.items.filter((u) => u.estado === 'pendiente_ampliar_tokens').length}
              </span>
              {' '}solicita{data.items.filter((u) => u.estado === 'pendiente_ampliar_tokens').length !== 1 ? 'n' : ''} mas consultas
            </span>
          )}
        </div>
      )}

      {isLoading && (
        <div className="card p-8 flex items-center justify-center">
          <p className="text-muted animate-pulse">Cargando usuarios...</p>
        </div>
      )}
      {isError && (
        <div className="card p-8 flex items-center justify-center">
          <p className="text-red-400 text-sm">Error al cargar usuarios. El token puede haber expirado.</p>
        </div>
      )}

      {data && (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm min-w-[960px]">
            <thead>
              <tr className="border-b border-border text-xs text-muted uppercase tracking-wider">
                <th className="px-4 py-3 text-left">Nick</th>
                <th className="px-3 py-3 text-left w-20">Rol</th>
                <th className="px-2 py-3 text-left w-36">Estado</th>
                <th className="px-2 py-3 text-center w-24">Consultas</th>
                <th className="px-1 py-3 text-center w-14">Intentos</th>
                <th className="px-2 py-3 text-center w-20">Guía</th>
                <th className="px-2 py-3 text-left w-28">Registro</th>
                <th className="px-2 py-3 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {usuariosOrdenados.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-muted text-xs">
                    No hay usuarios registrados.
                  </td>
                </tr>
              ) : (
                usuariosOrdenados.map((u) => {
                  const est      = ESTADO_ESTILOS[u.estado]
                  const pct      = u.cuota_asignada > 0
                    ? Math.min((u.consultas_usadas / u.cuota_asignada) * 100, 100)
                    : 0
                  const colorBarra = pct >= 100 ? TOKENS.errorText : pct >= 80 ? TOKENS.cat3 : TOKENS.cat4

                  return (
                    <tr
                      key={u.id}
                      className={`transition-colors hover:bg-primary-l/20 ${
                        u.estado === 'pendiente_acceso'         ? 'bg-yellow-900/5'  :
                        u.estado === 'pendiente_ampliar_tokens' ? 'bg-indigo-900/5'  : ''
                      }`}
                    >
                      {/* Nick */}
                      <td className="px-4 py-3">
                        <span className="font-semibold text-sm">@{u.nick}</span>
                        <span className="ml-1.5 text-[10px] text-muted font-mono">#{u.id}</span>
                        {u.email && (
                          <span className="block text-[10px] text-muted truncate max-w-[180px]" title={u.email}>
                            {u.email}
                          </span>
                        )}
                      </td>

                      {/* Rol */}
                      <td className="px-4 py-3">
                        {u.is_admin ? (
                          u.es_root ? (
                            <span
                              className="text-[11px] font-semibold px-2 py-1 rounded-full whitespace-nowrap"
                              style={{
                                color:      TOKENS.errorText,
                                background: 'rgba(248,113,113,0.12)',
                                border:     '1px solid rgba(248,113,113,0.50)',
                              }}
                              title="Administrador root — único con permiso para promover y quitar admins"
                            >
                              ⭐ Root
                            </span>
                          ) : (
                            <span
                              className="text-[11px] font-semibold px-2 py-1 rounded-full whitespace-nowrap"
                              style={{
                                color:      TOKENS.cat3,
                                background: 'rgba(251,191,36,0.10)',
                                border:     '1px solid rgba(251,191,36,0.45)',
                              }}
                              title="Administrador promovido — sin permiso para gestionar roles"
                            >
                              👑 Admin
                            </span>
                          )
                        ) : (
                          <span className="text-[11px] text-muted">Usuario</span>
                        )}
                      </td>

                      {/* Estado */}
                      <td className="px-2 py-3">
                        <span
                          className={`text-[11px] font-semibold px-2 py-1 rounded-full whitespace-nowrap ${
                            u.estado === 'pendiente_ampliar_tokens' ? 'animate-pulse' : ''
                          }`}
                          style={{ color: est.color, background: est.bg, border: `1px solid ${est.border}` }}
                        >
                          {ESTADO_LABEL[u.estado]}
                        </span>
                      </td>

                      {/* Consultas con mini barra de progreso */}
                      <td className="px-2 py-3 text-center">
                        {u.cuota_asignada > 0 ? (
                          <div className="flex flex-col items-center gap-1">
                            <span className="font-mono text-xs">
                              <span style={{ color: pct >= 100 ? TOKENS.errorText : pct >= 80 ? TOKENS.cat3 : undefined }}>
                                {u.consultas_usadas}
                              </span>
                              <span className="text-muted"> / {u.cuota_asignada}</span>
                            </span>
                            <div className="w-16 h-1 rounded-full overflow-hidden"
                                 style={{ background: 'rgba(255,255,255,0.08)' }}>
                              <div
                                className="h-full rounded-full transition-all"
                                style={{ width: `${pct}%`, background: colorBarra }}
                              />
                            </div>
                          </div>
                        ) : (
                          <span className="text-xs text-muted">—</span>
                        )}
                      </td>

                      {/* Intentos fallidos */}
                      <td className="px-1 py-3 text-center">
                        <span
                          className="text-xs font-mono"
                          style={{
                            color: u.intentos_fallidos >= 5 ? TOKENS.errorText
                                 : u.intentos_fallidos >  0 ? TOKENS.cat3
                                 : '#6B6B9A',
                          }}
                        >
                          {u.intentos_fallidos}
                          {u.intentos_fallidos >= 5 && (
                            <span className="ml-1 text-[9px]">🔒</span>
                          )}
                        </span>
                      </td>

                      {/* Guia vista */}
                      <td className="px-2 py-3 text-center">
                        {u.guia_vista ? (
                          <span
                            className="text-xs"
                            title="Ya vio la guía de bienvenida"
                          >
                            ✅
                          </span>
                        ) : (
                          <span
                            className="text-xs"
                            title="Aún no ha visto la guía"
                          >
                            ⬜
                          </span>
                        )}
                      </td>

                      {/* Fecha */}
                      <td className="px-2 py-3 text-xs text-muted font-mono">
                        {formatFecha(u.created_at)}
                      </td>

                      {/* Acciones */}
                      <td className="px-2 py-3">
                        <div className="flex items-center justify-end gap-1 flex-nowrap whitespace-nowrap">
                          {u.estado === 'pendiente_acceso' && (
                            <button
                              className="text-xs font-semibold px-2 py-1 rounded-lg transition-colors"
                              style={{
                                color:      TOKENS.cat4,
                                background: 'rgba(52,211,153,0.10)',
                                border:     '1px solid rgba(52,211,153,0.35)',
                              }}
                              onClick={() =>
                                setAccionActiva({ tipo: 'conceder', id: u.id, nick: u.nick, cuotaActual: 0 })
                              }
                              title="Conceder acceso al usuario y asignarle cuota"
                            >
                              ✓ Conceder
                            </button>
                          )}
                          {!u.is_admin && (u.estado === 'habilitado' || u.estado === 'pendiente_ampliar_tokens') && (
                            <button
                              className={`text-xs font-semibold px-2 py-1 rounded-lg transition-colors ${
                                u.estado === 'pendiente_ampliar_tokens' ? 'animate-pulse' : ''
                              }`}
                              style={{
                                color:      TOKENS.cat6,
                                background: 'rgba(129,140,248,0.10)',
                                border:     '1px solid rgba(129,140,248,0.35)',
                              }}
                              onClick={() =>
                                setAccionActiva({
                                  tipo: 'ampliar',
                                  id: u.id,
                                  nick: u.nick,
                                  cuotaActual: u.cuota_asignada,
                                })
                              }
                              title="Ajustar cuota de consultas"
                            >
                              ± Cuota
                            </button>
                          )}
                          <button
                            className="text-xs px-2 py-1 rounded-lg transition-colors"
                            style={
                              u.guia_vista
                                ? { color: TOKENS.cat3, background: 'rgba(251,191,36,0.08)', border: '1px solid rgba(251,191,36,0.3)' }
                                : { color: TOKENS.cat4, background: 'rgba(52,211,153,0.08)', border: '1px solid rgba(52,211,153,0.3)' }
                            }
                            onClick={() => mutToggleGuia.mutate({ id: u.id, vista: u.guia_vista })}
                            disabled={mutToggleGuia.isPending}
                            title={
                              u.guia_vista
                                ? 'Resetear guía — volverá a aparecer al usuario'
                                : 'Marcar guía como vista — no volverá a aparecer'
                            }
                          >
                            {u.guia_vista ? '↩ Guía' : '✓ Guía'}
                          </button>
                          {(u.estado === 'habilitado' || u.estado === 'pendiente_ampliar_tokens') && (
                            <button
                              className="text-xs px-2 py-1 rounded-lg transition-colors"
                              style={{
                                color:      TOKENS.cat7,
                                background: 'rgba(251,146,60,0.08)',
                                border:     '1px solid rgba(251,146,60,0.3)',
                              }}
                              onClick={() => setResetandoUsuario({ id: u.id, nick: u.nick, esAdmin: u.is_admin })}
                              disabled={mutReset.isPending}
                              title="Resetear evaluaciones — borra datos y reinicia cuota"
                            >
                              ↺ Reset
                            </button>
                          )}
                          {esRoot && !u.is_admin && u.estado === 'habilitado' && (
                            <button
                              className="text-xs font-semibold px-2 py-1 rounded-lg transition-colors"
                              style={{
                                color:      TOKENS.cat3,
                                background: 'rgba(251,191,36,0.10)',
                                border:     '1px solid rgba(251,191,36,0.40)',
                              }}
                              onClick={() => setPromoviendoUsuario({ id: u.id, nick: u.nick })}
                              disabled={mutPromover.isPending}
                              title="Promover a administrador — pedirá email obligatorio"
                            >
                              👑 Promover
                            </button>
                          )}
                          {esRoot && u.is_admin && !u.es_root && (
                            <button
                              className="text-xs font-semibold px-2 py-1 rounded-lg transition-colors"
                              style={{
                                color:      '#C0BCDC',
                                background: 'rgba(192,188,220,0.08)',
                                border:     '1px solid rgba(192,188,220,0.30)',
                              }}
                              onClick={() => setDegradandoUsuario(u)}
                              disabled={mutDegradar.isPending}
                              title="Quitar privilegios de admin — vuelve a control de cuota"
                            >
                              ↩ Quitar
                            </button>
                          )}
                          {!u.es_root && (
                            <button
                              className="text-xs px-2 py-1 rounded-lg transition-colors
                                         text-red-400 hover:text-red-300 hover:bg-red-400/10"
                              onClick={() => setEliminandoUsuario(u)}
                              disabled={mutEliminar.isPending}
                              title="Eliminar usuario y todas sus evaluaciones"
                            >
                              ✕
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Modal de formulario conceder / ampliar */}
      {accionActiva && (
        <FormModal
          accion={accionActiva}
          cargando={accionCargando}
          onConfirmar={onConfirmarAccion}
          onCancelar={() => setAccionActiva(null)}
        />
      )}

      {/* Modal de confirmacion eliminar */}
      {eliminandoUsuario && (
        <ConfirmModal
          mensaje={`¿Eliminar el usuario @${eliminandoUsuario.nick}? Se eliminarán también todas sus evaluaciones. Esta acción es irreversible.`}
          textoBotom="Eliminar usuario"
          destructivo
          onConfirmar={() => mutEliminar.mutate(eliminandoUsuario.id)}
          onCancelar={() => setEliminandoUsuario(null)}
        />
      )}

      {/* Modal de reset de evaluaciones */}
      {resetandoUsuario && (
        <ResetModal
          nick={resetandoUsuario.nick}
          esAdmin={resetandoUsuario.esAdmin}
          cargando={mutReset.isPending}
          onConfirmar={(nuevaCuota) => mutReset.mutate({ id: resetandoUsuario.id, nuevaCuota })}
          onCancelar={() => setResetandoUsuario(null)}
        />
      )}

      {/* Modal de promocion a administrador */}
      {promoviendoUsuario && (
        <PromoteModal
          nick={promoviendoUsuario.nick}
          cargando={mutPromover.isPending}
          onConfirmar={(email) => mutPromover.mutate({ id: promoviendoUsuario.id, email })}
          onCancelar={() => setPromoviendoUsuario(null)}
        />
      )}

      {/* Confirmacion de degradar admin */}
      {degradandoUsuario && (
        <ConfirmModal
          mensaje={`¿Quitar privilegios de administrador a @${degradandoUsuario.nick}? Volverá a tener control de cuota; podrás reasignársela con los botones de ajuste o reset.`}
          textoBotom="Quitar admin"
          destructivo
          onConfirmar={() => mutDegradar.mutate(degradandoUsuario.id)}
          onCancelar={() => setDegradandoUsuario(null)}
        />
      )}
    </div>
  )
}
