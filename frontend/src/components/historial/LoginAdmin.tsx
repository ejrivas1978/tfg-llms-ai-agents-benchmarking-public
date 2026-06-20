/**
 * Componente: LoginAdmin
 * Ruta:       frontend/src/components/historial/LoginAdmin.tsx
 *
 * Descripcion:
 *   Formulario de autenticacion para el administrador.
 *   Al obtener el JWT lo propaga al padre via onLogin para almacenarlo
 *   en adminStore.
 *
 * Sprint: Sprint 3
 */

import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { loginAdmin } from '@/services/authApi'

interface Props {
  /** Recibe el token y el flag esRoot para inicializar adminStore correctamente. */
  onLogin: (token: string, esRoot: boolean) => void
}

export default function LoginAdmin({ onLogin }: Props) {
  const [nick,     setNick]     = useState('')
  const [password, setPassword] = useState('')

  const mutacion = useMutation({
    mutationFn: () => loginAdmin({ nick, password }),
    onSuccess: (data) => onLogin(data.access_token, data.es_root),
  })

  return (
    <div className="max-w-sm mx-auto card p-8 space-y-5">
      <h3 className="text-base font-semibold text-center">Acceso de administrador</h3>

      <input
        className="input-base"
        type="text"
        placeholder="Nick"
        value={nick}
        onChange={(e) => setNick(e.target.value)}
        disabled={mutacion.isPending}
        autoFocus
      />

      <input
        className="input-base"
        type="password"
        placeholder="Contraseña"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && mutacion.mutate()}
        disabled={mutacion.isPending}
      />

      {mutacion.isError && (
        <p className="text-xs text-red-400 text-center">
          Credenciales incorrectas. Comprueba el nick y la contraseña.
        </p>
      )}

      <button
        className="btn-primary w-full"
        onClick={() => mutacion.mutate()}
        disabled={!nick || !password || mutacion.isPending}
      >
        {mutacion.isPending ? 'Autenticando…' : 'Entrar'}
      </button>
    </div>
  )
}
