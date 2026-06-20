"""
Modulo: schemas.auth
Ruta:   backend/app/schemas/auth.py

Descripcion:
    DTOs Pydantic para los endpoints de autenticacion.
    Separa el contrato de la API (lo que el cliente envia y recibe)
    del modelo ORM (lo que vive en la base de datos).

Dependencias:
    - pydantic>=2.9
    - pydantic[email]

Sprint: Sprint 1
"""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class PeticionRegistroUsuario(BaseModel):
    """Payload para POST /auth/register (solo uso interno/seeds).

    Atributos:
        email: Direccion de correo valida, usada como identificador de acceso.
        username: Nombre de usuario unico, entre 3 y 50 caracteres.
        password: Contrasena en texto plano, entre 8 y 100 caracteres. Nunca se almacena en crudo.
    """

    email: EmailStr
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=100)


class PeticionLoginUsuario(BaseModel):
    """Payload para POST /auth/login (login del administrador).

    Tras la unificacion ADR-027, los administradores se autentican con
    'nick' (campo identidad de la tabla unificada usuarios_app), igual
    que cualquier otro usuario. El email queda solo como dato de
    contacto/recuperacion.

    Atributos:
        nick: Identificador unico (mismo campo que para usuarios web).
        password: Contrasena en texto plano a verificar contra el hash almacenado.
    """

    nick: str = Field(min_length=1, max_length=100)
    password: str

    @field_validator("nick")
    @classmethod
    def _normalizar_nick(cls, v: str) -> str:
        return v.strip().lower()


# Mantener alias en ingles para compatibilidad con los tests existentes
UserLoginRequest = PeticionLoginUsuario


class RespuestaToken(BaseModel):
    """Cuerpo de respuesta para POST /auth/login.

    Atributos:
        access_token: JWT firmado para incluir en los encabezados Authorization: Bearer.
        token_type: Siempre 'bearer' segun el convenio OAuth2.
        expires_in: Duracion del token en segundos.
        es_root: True solo para el admin seeded del despliegue. El frontend
            usa este flag para mostrar/ocultar los botones de promover y
            quitar admin (ADR-027).
    """

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    es_root: bool = False


# Mantener alias en ingles para compatibilidad con los tests existentes
TokenResponse = RespuestaToken


class RespuestaUsuario(BaseModel):
    """Representacion publica de una cuenta de administrador.

    Devuelta por GET /auth/me. Nunca incluye password_hash.

    Atributos:
        id: Clave primaria.
        nick: Identificador de login.
        email: Correo electronico (obligatorio para admins).
        is_admin: True (siempre lo es si /auth/me devolvio 200).
        created_at: Fecha de creacion UTC.
    """

    id: int
    nick: str
    email: str | None
    is_admin: bool
    es_root: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# Mantener alias en ingles para compatibilidad con los tests existentes
UserResponse = RespuestaUsuario
