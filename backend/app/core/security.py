"""
Modulo: security
Ruta:   backend/app/core/security.py

Descripcion:
    Utilidades de cifrado de contrasenas y gestion de tokens JWT.
    Centraliza todas las operaciones criptograficas para que ningun otro
    modulo necesite importar passlib ni jose directamente.

    DECISION(ADR-008): JWT sin estado con HS256 y expiracion de 30 minutos.

Dependencias:
    - passlib[bcrypt]>=1.7
    - python-jose[cryptography]>=3.3
    - app.core.config

Sprint: Sprint 1
"""

from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

_contexto_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(contrasena: str) -> str:
    """Devuelve el hash bcrypt de una contrasena en texto plano.

    Args:
        contrasena: Contrasena original enviada por el usuario.

    Returns:
        Cadena de hash bcrypt segura para almacenar en base de datos.
    """
    return _contexto_pwd.hash(contrasena)


def verify_password(contrasena_plana: str, hash_contrasena: str) -> bool:
    """Comprueba si una contrasena en texto plano coincide con su hash almacenado.

    Args:
        contrasena_plana: Contrasena original a verificar.
        hash_contrasena: Hash bcrypt recuperado de la base de datos.

    Returns:
        True si la contrasena es correcta, False en caso contrario.
    """
    return _contexto_pwd.verify(contrasena_plana, hash_contrasena)


def create_access_token(
    datos: dict,
    duracion: timedelta | None = None,
) -> str:
    """Crea un token JWT firmado de acceso.

    Args:
        datos: Claims a incluir en el token. Debe contener 'sub' (sujeto).
        duracion: Duracion personalizada de expiracion. Por defecto usa el valor de Settings.

    Returns:
        Cadena JWT firmada para devolver al cliente.
    """
    settings = get_settings()
    payload = datos.copy()
    expiracion = datetime.now(timezone.utc) + (
        duracion
        if duracion is not None
        else timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload["exp"] = expiracion
    return jwt.encode(
        payload,
        settings.secret_key.get_secret_value(),
        algorithm=settings.algorithm,
    )


def decode_access_token(token: str) -> dict:
    """Decodifica y verifica un token JWT de acceso.

    Args:
        token: Cadena JWT del encabezado Authorization.

    Returns:
        Diccionario con el payload decodificado.

    Raises:
        jose.JWTError: Si el token es invalido, ha expirado o ha sido manipulado.
    """
    settings = get_settings()
    return jwt.decode(
        token,
        settings.secret_key.get_secret_value(),
        algorithms=[settings.algorithm],
    )
