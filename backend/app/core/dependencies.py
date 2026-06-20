"""
Modulo: dependencies
Ruta:   backend/app/core/dependencies.py

Descripcion:
    Dependencias reutilizables de FastAPI para autenticacion y autorizacion
    sobre la tabla unificada usuarios_app (ADR-027 supersede ADR-024).

    Cuatro dependencias segun el tipo de acceso:
    1. get_current_user: solo administradores (is_admin=True). Usado por los
       endpoints administrativos.
    2. get_current_usuario_app: solo usuarios web regulares (is_admin=False).
       Aplica el guard de estado pendiente_acceso.
    3. get_actor_benchmark: acepta a ambos. Si es admin devuelve None
       (cuota ilimitada); si es usuario regular devuelve UsuarioApp para
       que el servicio descuente cuota.
    4. get_usuario_opcional: JWT opcional para endpoints semipublicos.
       Nunca lanza 401: devuelve None si el token esta ausente o es invalido.
       Permite que los endpoints distingan entre anonimo y autenticado
       sin bloquear el acceso a usuarios con el JWT expirado.

    El JWT lleva siempre claim 'sub' (id del registro en usuarios_app);
    la condicion is_admin se resuelve siempre consultando la BD para que
    cambios de rol (promote/demote) se reflejen al instante en la sesion
    activa, sin esperar a renovar el token.

Sprint: Sprint 4 / Sprint 5 (get_usuario_opcional)
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.enums import EstadoUsuarioApp
from app.models.usuario_app import UsuarioApp
from app.repositories.usuario_app_repository import UsuarioAppRepository

_settings = get_settings()

# Esquemas OAuth2 separados para que Swagger UI muestre botones independientes.
esquema_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{_settings.api_prefix}/auth/login",
)
esquema_oauth2_usuarios = OAuth2PasswordBearer(
    tokenUrl=f"{_settings.api_prefix}/usuarios/login",
    scheme_name="UsuarioAppBearer",
)
_esquema_benchmark = OAuth2PasswordBearer(
    tokenUrl=f"{_settings.api_prefix}/usuarios/login",
    scheme_name="BenchmarkBearer",
)

# auto_error=False: no lanza 401 si la cabecera Authorization esta ausente.
_esquema_opcional = OAuth2PasswordBearer(
    tokenUrl=f"{_settings.api_prefix}/usuarios/login",
    scheme_name="HistorialOptionalBearer",
    auto_error=False,
)


def _decodificar_id(token: str) -> int:
    """Decodifica el JWT y devuelve el id de usuario, o lanza 401."""
    excepcion = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales invalidas o expiradas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        id_texto: str | None = payload.get("sub")
        if id_texto is None:
            raise excepcion
        return int(id_texto)
    except (JWTError, ValueError):
        raise excepcion


async def get_current_user(
    token: str = Depends(esquema_oauth2),
    db: AsyncSession = Depends(get_db),
) -> UsuarioApp:
    """Resuelve un JWT a un usuario administrador.

    Devuelve la instancia UsuarioApp si y solo si is_admin=True. La
    condicion se comprueba contra la BD en cada peticion: si un admin
    es degradado (is_admin=False) por otro admin mientras tiene un JWT
    activo, ese token deja de servir al instante.

    Args:
        token: Cadena JWT del header Authorization Bearer.
        db: AsyncSession inyectada por get_db.

    Returns:
        UsuarioApp con is_admin=True.

    Raises:
        HTTPException 401: token invalido, usuario no existe o no es admin.
    """
    excepcion = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales invalidas o expiradas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    id_usuario = _decodificar_id(token)
    repo = UsuarioAppRepository(db)
    usuario = await repo.obtener_por_id(id_usuario)
    if usuario is None or not usuario.is_admin:
        raise excepcion
    return usuario


async def get_current_usuario_app(
    token: str = Depends(esquema_oauth2_usuarios),
    db: AsyncSession = Depends(get_db),
) -> UsuarioApp:
    """Resuelve un JWT a un usuario web regular (no admin).

    Rechaza tokens cuyo registro tiene is_admin=True para evitar que un
    admin acceda como usuario regular y rompa la cuota. Aplica el guard
    de estado pendiente_acceso (devuelve 403 hasta aprobacion).

    Args:
        token: JWT del header Authorization Bearer.
        db: AsyncSession.

    Returns:
        UsuarioApp con is_admin=False.

    Raises:
        HTTPException 401: token invalido o el usuario es admin.
        HTTPException 403: usuario en estado pendiente_acceso.
    """
    excepcion = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales invalidas o expiradas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    id_usuario = _decodificar_id(token)
    repo = UsuarioAppRepository(db)
    usuario = await repo.obtener_por_id(id_usuario)
    if usuario is None or usuario.is_admin:
        raise excepcion
    if usuario.estado == EstadoUsuarioApp.pendiente_acceso:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu solicitud está pendiente de aprobación por el administrador.",
        )
    return usuario


async def get_actor_benchmark(
    token: str = Depends(_esquema_benchmark),
    db: AsyncSession = Depends(get_db),
) -> UsuarioApp | None:
    """Dependencia para el endpoint de benchmark. Acepta admin y usuario web.

    - Si el JWT pertenece a un admin (is_admin=True): retorna None para que
      BenchmarkService sepa que no hay que aplicar control de cuota.
    - Si pertenece a un usuario regular: retorna la instancia UsuarioApp;
      el servicio descontara consultas en su cuota tras una ejecucion OK.

    Args:
        token: JWT del header Authorization Bearer.
        db: AsyncSession.

    Returns:
        None si es admin; UsuarioApp si es usuario regular habilitado.

    Raises:
        HTTPException 401: token invalido o usuario inexistente.
        HTTPException 403: usuario regular en estado pendiente_acceso.
    """
    excepcion = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales invalidas o expiradas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    id_usuario = _decodificar_id(token)
    repo = UsuarioAppRepository(db)
    usuario = await repo.obtener_por_id(id_usuario)
    if usuario is None:
        raise excepcion
    if usuario.is_admin:
        return None  # cuota ilimitada
    if usuario.estado == EstadoUsuarioApp.pendiente_acceso:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu solicitud está pendiente de aprobación por el administrador.",
        )
    return usuario


async def get_usuario_opcional(
    token: str | None = Depends(_esquema_opcional),
    db: AsyncSession = Depends(get_db),
) -> UsuarioApp | None:
    """JWT opcional para endpoints semipublicos (historial, etc.).

    Devuelve la instancia UsuarioApp si el token es valido y el usuario
    existe en BD. Devuelve None sin lanzar excepcion si:
      - No hay cabecera Authorization.
      - El token esta expirado o es invalido.
      - El id del token no corresponde a ningun usuario.

    Permite que los endpoints distingan entre acceso anonimo y autenticado
    sin romper la compatibilidad con clientes cuyo JWT ha expirado.

    Args:
        token: JWT del header Authorization Bearer, o None si ausente.
        db: AsyncSession inyectada por get_db.

    Returns:
        UsuarioApp si el token es valido, None en caso contrario.
    """
    if token is None:
        return None
    try:
        id_usuario = _decodificar_id(token)
    except HTTPException:
        return None
    repo = UsuarioAppRepository(db)
    return await repo.obtener_por_id(id_usuario)
