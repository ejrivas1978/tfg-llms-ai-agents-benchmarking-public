"""
Modulo: routers.auth
Ruta:   backend/app/routers/auth.py

Descripcion:
    Capa HTTP para los endpoints de autenticacion del administrador.
    Tras la unificacion (ADR-027), el admin se autentica con nick +
    password sobre la tabla usuarios_app, igual que cualquier usuario.
    Los usuarios regulares siguen usando su router /usuarios.

    Endpoints:
        POST /api/v1/auth/login  -> RespuestaToken  200
        GET  /api/v1/auth/me     -> RespuestaUsuario 200

Sprint: Sprint 1 / Sprint 4
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.middleware.rate_limit import limitador
from app.models.usuario_app import UsuarioApp
from app.schemas.auth import PeticionLoginUsuario, RespuestaToken, RespuestaUsuario
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["autenticacion"])


@router.post(
    "/login",
    response_model=RespuestaToken,
    summary="Inicio de sesion del administrador",
    description=(
        "Autentica una cuenta con privilegios de administracion (is_admin=True) "
        "y devuelve un token JWT firmado. El payload usa 'nick' (no email) "
        "tras la unificacion ADR-027. Los usuarios regulares no pueden iniciar "
        "sesion aqui aunque la password sea correcta. "
        "Limite: 10 peticiones por minuto por IP."
    ),
)
@limitador.limit("10/minute")
async def login(
    request: Request,
    peticion: PeticionLoginUsuario,
    db: AsyncSession = Depends(get_db),
) -> RespuestaToken:
    """Endpoint de login del administrador.

    Args:
        peticion: Datos de acceso (nick + password).
        db: Sesion de base de datos asincrona.

    Returns:
        RespuestaToken con JWT y su duracion en segundos.
    """
    servicio = AuthService(db)
    return await servicio.login(nick=peticion.nick, password=peticion.password)


@router.get(
    "/me",
    response_model=RespuestaUsuario,
    summary="Perfil del administrador autenticado",
    description=(
        "Devuelve el perfil del administrador del JWT actual. "
        "Requiere is_admin=True en el registro de usuarios_app."
    ),
)
async def obtener_perfil(
    usuario_actual: UsuarioApp = Depends(get_current_user),
) -> RespuestaUsuario:
    """Devuelve el perfil del admin autenticado.

    Args:
        usuario_actual: Usuario inyectado por get_current_user (is_admin=True).

    Returns:
        RespuestaUsuario con id, nick, email e is_admin.
    """
    return RespuestaUsuario.model_validate(usuario_actual)
