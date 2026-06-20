"""
Modulo: services.auth_service
Ruta:   backend/app/services/auth_service.py

Descripcion:
    Logica de negocio para el inicio de sesion del administrador sobre la
    tabla unificada usuarios_app (ADR-027 supersede ADR-024).

    Tras la unificacion, los administradores se autentican con su nick
    (mismo campo identidad que cualquier otro usuario web). El servicio
    busca el registro por nick, verifica la contrasena con bcrypt y emite
    un JWT con el id del registro como subject. El guard 'is_admin=True'
    se aplica AQUI para que un nick sin privilegios reciba 401 (no permite
    a un usuario regular entrar al panel admin).

    DECISION(ADR-008): Tokens JWT sin estado.
    DECISION(ADR-027): Login unificado por nick + condicion is_admin.

Sprint: Sprint 4
"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token, verify_password
from app.repositories.usuario_app_repository import UsuarioAppRepository
from app.schemas.auth import RespuestaToken


class AuthService:
    """Capa de servicio para el login del administrador."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = UsuarioAppRepository(db)

    async def login(self, nick: str, password: str) -> RespuestaToken:
        """Autentica un administrador por nick + password.

        Args:
            nick: Identificador unico del registro en usuarios_app.
            password: Contrasena en texto plano.

        Returns:
            RespuestaToken con JWT firmado y duracion en segundos.

        Raises:
            HTTPException 401: nick no existe, password incorrecta, o el
                registro no es admin (is_admin=False). Mensaje generico
                para no filtrar la existencia del nick.
        """
        excepcion = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Bearer"},
        )
        usuario = await self.repo.obtener_por_nick(nick)
        if usuario is None or not verify_password(password, usuario.password_hash):
            raise excepcion
        if not usuario.is_admin:
            # Mismo 401 generico: un usuario regular no debe saber que su
            # password es valida pero le falta el privilegio.
            raise excepcion

        settings = get_settings()
        token = create_access_token({"sub": str(usuario.id)})
        return RespuestaToken(
            access_token=token,
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60,
            es_root=usuario.es_root,
        )
