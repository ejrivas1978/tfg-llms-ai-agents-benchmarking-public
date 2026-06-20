/**
 * Modulo: types/auth
 * Ruta:   frontend/src/types/auth.ts
 *
 * Descripcion:
 *   Tipos TypeScript para autenticacion del administrador y de usuarios web.
 *
 * Sprint: Sprint 3 / Sprint 4
 */

// --- Administrador ---

export interface PeticionLogin {
  /** Tras la unificacion ADR-027, el admin tambien entra por nick. */
  nick: string
  password: string
}

export interface RespuestaToken {
  access_token: string
  token_type: string
  expires_in: number
  /** True solo para el admin seeded; controla la visibilidad de promover/degradar. */
  es_root: boolean
}

// --- Usuarios web ---

export type EstadoUsuarioApp =
  | 'pendiente_acceso'
  | 'habilitado'
  | 'pendiente_ampliar_tokens'

export interface PeticionRegistro {
  nick: string
  password: string
}

export interface PeticionLoginUsuario {
  nick: string
  password: string
}

export interface PeticionRegenerarContrasena {
  nick: string
  nueva_password: string
}

export interface RespuestaTokenUsuarioApp {
  access_token: string
  token_type: string
  expires_in: number
  nick: string
  estado: EstadoUsuarioApp
  consultas_usadas: number
  cuota_asignada: number
  guia_vista: boolean
  /** True si el registro tiene is_admin=True tras la unificacion ADR-027. */
  is_admin: boolean
  /** True solo para el admin seeded del despliegue; controla los botones promover/degradar. */
  es_root: boolean
}

export interface RespuestaUsuarioApp {
  id: number
  nick: string
  email: string | null
  is_admin: boolean
  /** True solo para el admin seeded del despliegue. */
  es_root: boolean
  estado: EstadoUsuarioApp
  cuota_asignada: number
  consultas_usadas: number
  intentos_fallidos: number
  guia_vista: boolean
  created_at: string
}
