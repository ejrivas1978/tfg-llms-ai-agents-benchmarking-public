/**
 * Componente: NickPage (LoginPage)
 * Ruta:       frontend/src/pages/NickPage.tsx
 *
 * Descripcion:
 *   Pantalla de acceso a la aplicacion. Flujo en 4 vistas:
 *     inicio    -> el evaluador escribe su nick y pulsa Continuar.
 *                  La app comprueba si el nick existe en la base de datos.
 *     login     -> el nick existe. El usuario introduce su contrasena.
 *     registro  -> el nick no existe. El usuario introduce y confirma contrasena
 *                  para solicitar acceso al administrador.
 *     regenerar -> el usuario ha olvidado la contrasena o esta bloqueado.
 *                  Introduce nick y nueva contrasena (vuelve a pendiente_acceso).
 *
 *   Tras login exitoso el JWT se almacena en usuarioStore y el nick en nickStore
 *   (compatibilidad con componentes existentes). Se redirige a /benchmark.
 *
 * Sprint: Sprint 4
 */
import { TOKENS } from '@/utils/tokens'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import logoTfg from '@/utils/LOGO_TFG.png'
import { useUsuarioStore } from '@/store/usuarioStore'
import { useAdminStore } from '@/store/adminStore'
import { useNickStore } from '@/store/nickStore'
import { useHistorialStore } from '@/store/historialStore'
import {
  verificarNick,
  registrarUsuario,
  loginUsuario,
  regenerarContrasena,
} from '@/services/usuarioApi'
import { loginAdmin } from '@/services/authApi'
import { listarUsuariosAdmin } from '@/services/adminApi'
import axios from 'axios'

type Vista = 'inicio' | 'login' | 'registro' | 'regenerar' | 'login_admin'

export default function NickPage() {
  const [vista, setVista] = useState<Vista>('inicio')
  const [nick, setNick] = useState('')
  const [password, setPassword] = useState('')
  const [confirmar, setConfirmar] = useState('')
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [cargando, setCargando] = useState(false)
  const [tienePendienteEval, setTienePendienteEval] = useState(false)
  const [pendientesNotif, setPendientesNotif] = useState<{
    acceso: number
    ampliar: number
  } | null>(null)

  const loginStore        = useUsuarioStore((s) => s.login)
  const logoutUsuario     = useUsuarioStore((s) => s.logout)
  const setSessionAdmin   = useAdminStore((s) => s.setSession)
  const setNickStore      = useNickStore((s) => s.setNick)
  const limpiarHistorial  = useHistorialStore((s) => s.limpiar)
  const navigate = useNavigate()

  const limpiarMensajes = () => { setError(''); setInfo('') }

  // ── Vista: inicio ──────────────────────────────────────────────────────────

  const continuar = async () => {
    if (!nick.trim()) return
    limpiarMensajes()
    // El nick 'admin' usa la vista de login_admin (acceso directo al panel administrativo)
    if (nick.trim().toLowerCase() === 'admin') {
      setVista('login_admin')
      return
    }
    setCargando(true)
    try {
      const { existe } = await verificarNick(nick.trim())
      setVista(existe ? 'login' : 'registro')
    } catch {
      setError('Error de conexión. Comprueba que el servidor está activo.')
    } finally {
      setCargando(false)
    }
  }

  // ── Vista: login_admin ─────────────────────────────────────────────────────

  const entrarAdmin = async () => {
    if (!nick.trim() || !password) return
    limpiarMensajes()
    setCargando(true)
    try {
      // Tras la unificacion ADR-027, el admin se loguea por nick + password
      // (igual que cualquier usuario). El email ya no participa en el login;
      // solo es dato de contacto del admin.
      const respuesta = await loginAdmin({ nick: nick.trim(), password })
      logoutUsuario()          // limpiar token de usuario web residual en localStorage
      setSessionAdmin(respuesta.access_token, respuesta.es_root)
      setNickStore(nick.trim())
      // Comprobar si hay usuarios pendientes de revision para mostrar notificacion
      try {
        const lista   = await listarUsuariosAdmin(respuesta.access_token)
        const acceso  = lista.items.filter((u) => u.estado === 'pendiente_acceso').length
        const ampliar = lista.items.filter((u) => u.estado === 'pendiente_ampliar_tokens').length
        if (acceso + ampliar > 0) {
          setPendientesNotif({ acceso, ampliar })
          return  // esperar accion del admin en el popup antes de navegar
        }
      } catch {
        // Si falla la consulta de usuarios continuar sin popup
      }
      navigate('/historial')
    } catch {
      setError('Credenciales incorrectas. Comprueba la contraseña.')
    } finally {
      setCargando(false)
    }
  }

  // ── Vista: login ───────────────────────────────────────────────────────────

  const entrar = async () => {
    if (!password) return
    limpiarMensajes()
    setCargando(true)
    try {
      const respuesta = await loginUsuario({ nick: nick.trim(), password })
      // Tras la unificacion ADR-027 un usuario regular puede haber sido
      // promovido a administrador. Si is_admin=true, activamos la sesion
      // como admin (mismo JWT, distinto store) en lugar del UI de usuario:
      // su panel ya no es Nueva Comparativa/Historial sino el admin completo.
      if (respuesta.is_admin) {
        logoutUsuario()
        setSessionAdmin(respuesta.access_token, respuesta.es_root)
        setNickStore(respuesta.nick)
        try {
          const lista   = await listarUsuariosAdmin(respuesta.access_token)
          const acceso  = lista.items.filter((u) => u.estado === 'pendiente_acceso').length
          const ampliar = lista.items.filter((u) => u.estado === 'pendiente_ampliar_tokens').length
          if (acceso + ampliar > 0) {
            setPendientesNotif({ acceso, ampliar })
            return
          }
        } catch {
          // Si falla la consulta de pendientes, continuar sin popup
        }
        navigate('/historial')
        return
      }
      // Si el usuario no tiene consultas usadas, puede ser una cuenta nueva o
      // recreada tras ser eliminada: limpiar historial local obsoleto
      if (respuesta.consultas_usadas === 0) {
        limpiarHistorial(respuesta.nick)
      }
      loginStore(respuesta)
      setNickStore(respuesta.nick)
      // Comprobar si hay evaluaciones pendientes de valorar antes de navegar
      const sesiones = useHistorialStore.getState().sesiones[respuesta.nick] ?? []
      const pendiente = sesiones.find((s) => s.estado === 'completada' && !s.evaluada)
      if (pendiente) {
        setTienePendienteEval(true)
        return
      }
      navigate('/benchmark')
    } catch (err) {
      if (axios.isAxiosError(err)) {
        const status = err.response?.status
        const detail = err.response?.data?.detail ?? ''
        if (status === 403) {
          setInfo('Tu solicitud está pendiente de aprobación por el administrador.')
        } else if (status === 423) {
          setInfo(
            'Cuenta bloqueada por múltiples intentos fallidos. ' +
            'Usa "Regenerar contraseña" para recuperar el acceso.',
          )
        } else if (status === 401) {
          setError(detail || 'Contraseña incorrecta.')
        } else {
          setError(detail || 'Error al iniciar sesión.')
        }
      } else {
        setError('Error de conexión.')
      }
    } finally {
      setCargando(false)
    }
  }

  // ── Vista: registro ────────────────────────────────────────────────────────

  const solicitarAcceso = async () => {
    limpiarMensajes()
    if (password.length < 8) {
      setError('La contraseña debe tener al menos 8 caracteres.')
      return
    }
    if (password !== confirmar) {
      setError('Las contraseñas no coinciden.')
      return
    }
    setCargando(true)
    try {
      await registrarUsuario({ nick: nick.trim(), password })
      setInfo(
        'Solicitud enviada. El administrador revisará tu acceso y te habilitará en breve.',
      )
      setPassword('')
      setConfirmar('')
    } catch (err) {
      if (axios.isAxiosError(err)) {
        setError(err.response?.data?.detail ?? 'Error al solicitar acceso.')
      } else {
        setError('Error de conexión.')
      }
    } finally {
      setCargando(false)
    }
  }

  // ── Vista: regenerar ───────────────────────────────────────────────────────

  const regenerar = async () => {
    limpiarMensajes()
    if (password.length < 8) {
      setError('La nueva contraseña debe tener al menos 8 caracteres.')
      return
    }
    if (password !== confirmar) {
      setError('Las contraseñas no coinciden.')
      return
    }
    setCargando(true)
    try {
      await regenerarContrasena({ nick: nick.trim(), nueva_password: password })
      setInfo(
        'Contraseña actualizada. Tu cuenta vuelve a estado pendiente: ' +
        'el administrador deberá aprobar tu acceso de nuevo.',
      )
      setPassword('')
      setConfirmar('')
      setVista('login')
    } catch (err) {
      if (axios.isAxiosError(err)) {
        setError(err.response?.data?.detail ?? 'Error al regenerar contraseña.')
      } else {
        setError('Error de conexión.')
      }
    } finally {
      setCargando(false)
    }
  }

  const volverAInicio = () => {
    setVista('inicio')
    setPassword('')
    setConfirmar('')
    limpiarMensajes()
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <>
    <div className="min-h-screen flex items-center justify-center
                    bg-gradient-to-br from-[#1B0A3A] to-bg">
      <div className="card p-12 w-[440px] max-w-[92vw] text-center shadow-card-lg">

        {/* Logo y cabecera */}
        <img src={logoTfg} alt="Logo TFG"
             className="w-24 h-24 rounded-2xl mx-auto mb-7"
             style={{ boxShadow: '0 4px 24px rgba(0,0,0,.6)' }} />
        <h1 className="text-2xl font-bold mb-1">Benchmarking de LLMs</h1>
        <p className="text-[11px] text-muted uppercase tracking-widest mb-1">
          Trabajo Fin de Grado
        </p>
        <p className="text-xs text-muted mb-8">Emilio Javier Rivas Fernandez</p>

        {/* Mensajes de error / informacion */}
        {error && (
          <div className="mb-4 rounded-lg bg-red-900/40 border border-red-500/40
                          text-red-300 text-sm px-4 py-3">
            {error}
          </div>
        )}
        {info && (
          <div className="mb-4 rounded-lg bg-blue-900/40 border border-blue-500/40
                          text-blue-300 text-sm px-4 py-3">
            {info}
          </div>
        )}

        {/* ── Vista: inicio ── */}
        {vista === 'inicio' && (
          <>
            <input
              className="input-base mb-4 text-center"
              placeholder="Tu nickname…"
              value={nick}
              onChange={(e) => setNick(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && continuar()}
              maxLength={100}
              autoFocus
            />
            <button
              className="btn-primary w-full"
              onClick={continuar}
              disabled={!nick.trim() || cargando}
            >
              {cargando ? 'Comprobando…' : 'Continuar'}
            </button>
          </>
        )}

        {/* ── Vista: login ── */}
        {vista === 'login' && (
          <>
            <p className="text-sm text-muted mb-4">
              Bienvenido de nuevo, <span className="text-white font-semibold">{nick}</span>
            </p>
            <input
              className="input-base mb-4 text-center"
              type="password"
              placeholder="Contraseña…"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && entrar()}
              autoFocus
            />
            <button
              className="btn-primary w-full mb-4"
              onClick={entrar}
              disabled={!password || cargando}
            >
              {cargando ? 'Entrando…' : 'Entrar'}
            </button>
            <div className="flex flex-col gap-2 text-xs text-muted">
              <button
                className="hover:text-white transition-colors"
                onClick={() => { setVista('regenerar'); limpiarMensajes() }}
              >
                ¿Olvidaste la contraseña?
              </button>
              <button
                className="hover:text-white transition-colors"
                onClick={volverAInicio}
              >
                ← Cambiar nick
              </button>
            </div>
          </>
        )}

        {/* ── Vista: registro ── */}
        {vista === 'registro' && (
          <>
            {!info ? (
              <>
                <p className="text-sm text-muted mb-4">
                  El nick <span className="text-white font-semibold">{nick}</span> no está registrado.
                  Elige una contraseña para solicitar acceso.
                </p>
                <input
                  className="input-base mb-3 text-center"
                  type="password"
                  placeholder="Contraseña (mínimo 8 caracteres)…"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoFocus
                />
                <input
                  className="input-base mb-4 text-center"
                  type="password"
                  placeholder="Confirmar contraseña…"
                  value={confirmar}
                  onChange={(e) => setConfirmar(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && solicitarAcceso()}
                />
                <button
                  className="btn-primary w-full mb-4"
                  onClick={solicitarAcceso}
                  disabled={!password || !confirmar || cargando}
                >
                  {cargando ? 'Enviando solicitud…' : 'Solicitar Acceso'}
                </button>
                <button
                  className="text-xs text-muted hover:text-white transition-colors"
                  onClick={volverAInicio}
                >
                  ← Cambiar nick
                </button>
              </>
            ) : (
              <button
                className="text-xs text-muted hover:text-white transition-colors"
                onClick={volverAInicio}
              >
                ← Volver al inicio
              </button>
            )}
          </>
        )}

        {/* ── Vista: regenerar ── */}
        {vista === 'regenerar' && (
          <>
            <p className="text-sm text-muted mb-4">
              Introduce tu nick y una nueva contraseña.
              Tu cuenta volverá a estado pendiente de aprobación.
            </p>
            <input
              className="input-base mb-3 text-center"
              placeholder="Tu nickname…"
              value={nick}
              onChange={(e) => setNick(e.target.value)}
              autoFocus
            />
            <input
              className="input-base mb-3 text-center"
              type="password"
              placeholder="Nueva contraseña (mínimo 8 caracteres)…"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <input
              className="input-base mb-4 text-center"
              type="password"
              placeholder="Confirmar nueva contraseña…"
              value={confirmar}
              onChange={(e) => setConfirmar(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && regenerar()}
            />
            <button
              className="btn-primary w-full mb-4"
              onClick={regenerar}
              disabled={!nick.trim() || !password || !confirmar || cargando}
            >
              {cargando ? 'Guardando…' : 'Regenerar Contraseña'}
            </button>
            <button
              className="text-xs text-muted hover:text-white transition-colors"
              onClick={volverAInicio}
            >
              ← Volver al inicio
            </button>
          </>
        )}

        {/* ── Vista: login_admin ── */}
        {vista === 'login_admin' && (
          <>
            <p className="text-sm text-muted mb-4">
              Acceso de <span className="text-white font-semibold">administrador</span>
              {' · '}
              <span className="text-muted">@{nick.trim()}</span>
            </p>
            <input
              className="input-base mb-4 text-center"
              type="password"
              placeholder="Contraseña…"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && entrarAdmin()}
              autoFocus
            />
            <button
              className="btn-primary w-full mb-4"
              onClick={entrarAdmin}
              disabled={!password || cargando}
            >
              {cargando ? 'Autenticando…' : 'Entrar como administrador'}
            </button>
            <button
              className="text-xs text-muted hover:text-white transition-colors"
              onClick={volverAInicio}
            >
              ← Cambiar nick
            </button>
          </>
        )}

      </div>
    </div>

    {/* ── Popup de evaluación pendiente (usuario web) ── */}
    {tienePendienteEval && (
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
           style={{ background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(4px)' }}>
        <div className="card p-7 w-full max-w-sm shadow-card-lg space-y-5 text-center">
          <div className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto text-3xl"
               style={{ background: 'rgba(251,191,36,0.12)', border: '1px solid rgba(251,191,36,0.35)' }}>
            ⏳
          </div>
          <div>
            <p className="font-bold text-base mb-2">Tienes una evaluación pendiente</p>
            <p className="text-sm text-muted leading-relaxed">
              Debes valorar la comparativa anterior antes de lanzar una nueva.
              No se puede tener más de una evaluación sin valorar a la vez.
            </p>
          </div>
          <button className="btn-primary w-full" onClick={() => navigate('/historial')}>
            Ir a evaluarla →
          </button>
        </div>
      </div>
    )}

    {/* ── Popup de usuarios pendientes (admin) ── */}
    {pendientesNotif && (
      <div
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        style={{ background: 'rgba(0,0,0,0.72)' }}
      >
        <div className="card p-7 w-full max-w-sm shadow-card-lg space-y-5 text-center">
          <div className="w-12 h-12 rounded-2xl flex items-center justify-center mx-auto text-2xl"
               style={{ background: 'rgba(251,191,36,0.15)', border: '1px solid rgba(251,191,36,0.35)' }}>
            🔔
          </div>
          <div>
            <p className="font-semibold text-sm mb-3">Hay solicitudes pendientes de revisión</p>
            <div className="space-y-1.5">
              {pendientesNotif.acceso > 0 && (
                <p className="text-xs rounded-lg px-3 py-2"
                   style={{ background: 'rgba(251,191,36,0.08)', color: TOKENS.cat3 }}>
                  {pendientesNotif.acceso} usuario{pendientesNotif.acceso !== 1 ? 's' : ''} pendiente{pendientesNotif.acceso !== 1 ? 's' : ''} de acceso
                </p>
              )}
              {pendientesNotif.ampliar > 0 && (
                <p className="text-xs rounded-lg px-3 py-2"
                   style={{ background: 'rgba(129,140,248,0.08)', color: TOKENS.cat6 }}>
                  {pendientesNotif.ampliar} usuario{pendientesNotif.ampliar !== 1 ? 's' : ''} solicita{pendientesNotif.ampliar !== 1 ? 'n' : ''} más cuota
                </p>
              )}
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <button
              className="btn-primary w-full"
              onClick={() => navigate('/historial?tab=usuarios')}
            >
              Revisar ahora
            </button>
            <button
              className="btn-ghost text-sm w-full"
              onClick={() => navigate('/historial')}
            >
              Más tarde
            </button>
          </div>
        </div>
      </div>
    )}
    </>
  )
}
