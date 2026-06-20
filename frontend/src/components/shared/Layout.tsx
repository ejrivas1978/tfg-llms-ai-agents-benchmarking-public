/**
 * Componente: Layout
 * Ruta:       frontend/src/components/shared/Layout.tsx
 *
 * Descripcion:
 *   Envoltorio comun para todas las pantallas excepto NickPage.
 *   Topbar con logo, nombre de la aplicacion, navegacion y nick pill.
 *
 * Sprint: Sprint 3
 */
import { useState, useEffect, useRef } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useNickStore } from '@/store/nickStore'
import { useAdminStore } from '@/store/adminStore'
import { useUsuarioStore } from '@/store/usuarioStore'
import { obtenerPerfilUsuario } from '@/services/usuarioApi'
import ToastContainer from '@/components/shared/Toast'
import logoTfg from '@/utils/LOGO_TFG.png'

const ENLACES = [
  { to: '/benchmark', label: 'Benchmark'         },
  { to: '/historial',  label: 'Historial'       },
  { to: '/dashboard',  label: 'Dashboard'        },
]

export default function Layout() {
  const nick              = useNickStore((s) => s.nick)
  const clearNick         = useNickStore((s) => s.clearNick)
  const clearToken        = useAdminStore((s) => s.clearToken)
  const tokenAdmin        = useAdminStore((s) => s.token)
  const logoutUser        = useUsuarioStore((s) => s.logout)
  const tokenUsuario      = useUsuarioStore((s) => s.token)
  const actualizarCuota   = useUsuarioStore((s) => s.actualizarCuota)
  const actualizarEstado  = useUsuarioStore((s) => s.actualizarEstado)
  const navigate          = useNavigate()
  const inicial           = nick ? nick[0].toUpperCase() : '?'

  const [menuAbierto, setMenuAbierto] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  // Refresca cuota y estado del usuario desde BD al montar el Layout.
  // Evita que el localStorage muestre valores obsoletos tras cambios del admin.
  useEffect(() => {
    if (!tokenUsuario) return
    obtenerPerfilUsuario(tokenUsuario)
      .then((perfil) => {
        actualizarCuota(perfil.consultas_usadas, perfil.cuota_asignada)
        actualizarEstado(perfil.estado)
      })
      .catch(() => {
        // El interceptor de axios ya gestiona el 401 (logout automatico)
      })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!menuAbierto) return
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuAbierto(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [menuAbierto])

  const cerrarSesion = () => {
    clearToken()
    logoutUser()
    clearNick()
    setMenuAbierto(false)
    navigate('/')
  }

  return (
    <div className="min-h-screen flex flex-col bg-bg">
      <header className="sticky top-0 z-10 h-16 flex items-center justify-between
                         px-6 bg-surface border-b border-border"
              style={{ boxShadow: '0 1px 12px rgba(0,0,0,.5)' }}>

        {/* Marca: logo + nombre + subtitulo */}
        <div className="flex items-center gap-3 flex-shrink-0">
          <img src={logoTfg} alt="Logo TFG"
               className="w-9 h-9 rounded-xl flex-shrink-0"
               style={{ boxShadow: '0 2px 14px rgba(0,0,0,.45)' }} />
          <div className="hidden sm:block leading-tight">
            <div className="text-sm font-bold">
              <span className="text-primary">Benchmarking</span>
              <span className="text-text"> de LLMs</span>
            </div>
            <div className="text-[11px] text-muted">TFG · Emilio Javier Rivas Fernandez</div>
          </div>
        </div>

        {/* Navegacion */}
        <nav className="flex items-center gap-0.5">
          {ENLACES.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-150
                 border border-white/25 ${
                  isActive
                    ? 'bg-primary-l text-primary border-white/80 shadow-[0_0_14px_4px_rgba(255,255,255,0.45)]'
                    : 'text-muted hover:text-text hover:bg-primary-l hover:border-white/40'
                }`
              }
            >
              {to === '/historial' && tokenAdmin ? 'Gestiones Administrador' : label}
            </NavLink>
          ))}
        </nav>

        {/* Nick pill con avatar — clic abre menu de sesion */}
        <div className="relative flex-shrink-0" ref={menuRef}>
          <button
            className="flex items-center gap-2 bg-primary-l rounded-full px-3 py-1.5
                       hover:bg-primary-l/80 transition-colors"
            style={{ border: '1px solid rgba(157,78,221,0.25)' }}
            onClick={() => setMenuAbierto((v) => !v)}
            title={nick || ''}
          >
            <div className="w-6 h-6 rounded-full flex items-center justify-center
                            text-xs text-white font-bold bg-gradient-to-br from-primary to-primary-d"
                 style={{ flexShrink: 0 }}>
              {inicial}
            </div>
            <span className="text-sm font-semibold text-primary">{nick || '—'}</span>
          </button>

          {menuAbierto && (
            <div className="absolute right-0 top-full mt-2 w-44 rounded-xl border border-border
                            shadow-card-lg overflow-hidden bg-surface"
                 style={{ zIndex: 20 }}>
              <div className="px-4 py-3 border-b border-border">
                <p className="text-[10px] text-muted uppercase tracking-wide">Sesión activa</p>
                <p className="text-sm font-semibold text-text truncate">{nick}</p>
              </div>
              <button
                className="w-full text-left px-4 py-2.5 text-sm text-muted
                           hover:text-text hover:bg-primary-l transition-colors"
                onClick={cerrarSesion}
              >
                Cerrar sesión
              </button>
            </div>
          )}
        </div>
      </header>

      <main className="flex-1 p-6">
        <Outlet />
      </main>

      <ToastContainer />
    </div>
  )
}
