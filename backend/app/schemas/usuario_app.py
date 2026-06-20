"""
Modulo: schemas.usuario_app
Ruta:   backend/app/schemas/usuario_app.py

Descripcion:
    DTOs Pydantic para los endpoints de autenticacion y gestion de usuarios
    de la aplicacion web (distintos del administrador).

Dependencias:
    - pydantic>=2.9
    - app.models.enums.EstadoUsuarioApp

Sprint: Sprint 4
"""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import EstadoUsuarioApp


class PeticionRegistro(BaseModel):
    """Payload para POST /api/v1/usuarios/registrar.

    Atributos:
        nick: Identificador unico del usuario. Entre 3 y 100 caracteres.
        password: Contrasena en texto plano. Entre 8 y 100 caracteres.
    """

    nick: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=100)

    @field_validator("nick")
    @classmethod
    def _normalizar_nick(cls, v: str) -> str:
        return v.strip().lower()


class PeticionLogin(BaseModel):
    """Payload para POST /api/v1/usuarios/login.

    Atributos:
        nick: Identificador del usuario.
        password: Contrasena en texto plano a verificar.
    """

    nick: str
    password: str

    @field_validator("nick")
    @classmethod
    def _normalizar_nick(cls, v: str) -> str:
        return v.strip().lower()


class PeticionRegenerarContrasena(BaseModel):
    """Payload para POST /api/v1/usuarios/regenerar-contrasena.

    Atributos:
        nick: Identificador del usuario que quiere regenerar su contrasena.
        nueva_password: Nueva contrasena en texto plano. Entre 8 y 100 caracteres.
    """

    nick: str
    nueva_password: str = Field(min_length=8, max_length=100)

    @field_validator("nick")
    @classmethod
    def _normalizar_nick(cls, v: str) -> str:
        return v.strip().lower()


class RespuestaTokenUsuarioApp(BaseModel):
    """Cuerpo de respuesta para POST /api/v1/usuarios/login exitoso.

    Incluye el JWT y el estado actual de cuota para que el frontend
    pueda mostrar el contador sin una segunda peticion.

    Atributos:
        access_token: JWT firmado con duracion de 1 hora.
        token_type: Siempre 'bearer'.
        expires_in: Duracion del token en segundos (3600).
        nick: Nick del usuario autenticado.
        estado: Estado actual del usuario (habilitado / pendiente_ampliar_tokens).
        consultas_usadas: Numero de comparaciones realizadas hasta ahora.
        cuota_asignada: Limite maximo de consultas asignado por el admin.
    """

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    nick: str
    estado: EstadoUsuarioApp
    consultas_usadas: int
    cuota_asignada: int
    guia_vista: bool
    # Tras la unificacion ADR-027, un usuario regular puede haber sido
    # promovido a admin. El frontend usa este flag para saber si debe
    # activar el panel administrativo en lugar del UI de usuario regular.
    is_admin: bool = False
    # es_root distingue al admin seeded del despliegue de los admins
    # promovidos: solo el root puede promover/degradar a otros.
    es_root: bool = False


class PeticionConcederAcceso(BaseModel):
    """Payload para POST /api/v1/admin/usuarios/{id}/conceder-acceso.

    Atributos:
        cuota: Numero de consultas permitidas que se asignan al usuario.
    """

    cuota: int = Field(ge=1, description="Numero de consultas permitidas (minimo 1)")


class PeticionAmpliarTokens(BaseModel):
    """Payload para POST /api/v1/admin/usuarios/{id}/ampliar-tokens.

    Atributos:
        tokens_adicionales: Ajuste de cuota: positivo para ampliar, negativo para reducir.
            La cuota resultante se limita a un minimo de 0.
    """

    tokens_adicionales: int = Field(description="Ajuste de cuota (positivo ampliar, negativo reducir)")


class PeticionPromoverAdmin(BaseModel):
    """Payload para POST /api/v1/admin/usuarios/{id}/promover-admin.

    Atributos:
        email: Correo electronico del nuevo admin (obligatorio segun
            check constraint ck_admin_requires_email).
    """

    email: EmailStr


class PeticionResetearEvaluaciones(BaseModel):
    """Payload para POST /api/v1/admin/usuarios/{id}/resetear-evaluaciones.

    Atributos:
        nueva_cuota: Cuota que se asignara al usuario tras borrar sus evaluaciones.
            El contador de consultas_usadas se pone a 0 automaticamente.
    """

    nueva_cuota: int = Field(ge=0, description="Nueva cuota de consultas tras el reset (0 para dejar sin cuota)")


class RespuestaResetearEvaluaciones(BaseModel):
    """Respuesta para POST /api/v1/admin/usuarios/{id}/resetear-evaluaciones.

    Atributos:
        usuario: Estado actualizado del usuario tras el reset.
        evaluaciones_eliminadas: Numero de evaluaciones borradas.
    """

    usuario: "RespuestaUsuarioApp"
    evaluaciones_eliminadas: int


class RespuestaListaUsuarios(BaseModel):
    """Respuesta paginada para GET /api/v1/admin/usuarios.

    Atributos:
        items: Lista de usuarios con su estado actual.
        total: Numero total de usuarios registrados.
    """

    items: list["RespuestaUsuarioApp"]
    total: int


class RespuestaUsuarioApp(BaseModel):
    """Representacion publica de un usuario de la aplicacion.

    Nunca incluye password_hash ni otros campos sensibles.

    Atributos:
        id: Clave primaria.
        nick: Identificador unico del usuario.
        email: Correo electronico (obligatorio si is_admin=True).
        is_admin: True si el usuario tiene privilegios de administracion.
        estado: Estado del ciclo de vida.
        cuota_asignada: Limite maximo de consultas.
        consultas_usadas: Contador de comparaciones realizadas.
        intentos_fallidos: Intentos de login fallidos consecutivos.
        created_at: Fecha de registro.
    """

    id: int
    nick: str
    email: str | None
    is_admin: bool
    es_root: bool
    estado: EstadoUsuarioApp
    cuota_asignada: int
    consultas_usadas: int
    intentos_fallidos: int
    guia_vista: bool
    created_at: datetime

    model_config = {"from_attributes": True}
