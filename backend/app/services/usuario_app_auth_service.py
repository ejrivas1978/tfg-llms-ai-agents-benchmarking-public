"""
Modulo: services.usuario_app_auth_service
Ruta:   backend/app/services/usuario_app_auth_service.py

Descripcion:
    Logica de negocio para autenticacion y ciclo de vida de los usuarios
    de la aplicacion web (distintos del administrador).

    Reglas implementadas:
    - Registro: nick unico, password hasheado con bcrypt, estado inicial pendiente_acceso.
    - Login: bloqueo tras 5 intentos fallidos consecutivos; pendiente_acceso devuelve 403.
    - Regenerar contrasena: cambia hash y vuelve a pendiente_acceso manteniendo cuota.
    - Tokens JWT de 1 hora con claim 'tipo: usuario_app' para distinguirlos del admin.

Dependencias:
    - app.core.security
    - app.models.enums.EstadoUsuarioApp
    - app.repositories.usuario_app_repository.UsuarioAppRepository
    - app.schemas.usuario_app

Sprint: Sprint 4
"""

from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.models.enums import EstadoUsuarioApp
from app.models.usuario_app import UsuarioApp
from app.repositories.usuario_app_repository import UsuarioAppRepository
from app.schemas.usuario_app import (
    RespuestaTokenUsuarioApp,
    RespuestaUsuarioApp,
)

_DURACION_TOKEN = timedelta(hours=1)
_MAX_INTENTOS = 5


class UsuarioAppAuthService:
    """Servicio de autenticacion para usuarios de la aplicacion web.

    Atributos:
        _db: Sesion asincrona SQLAlchemy inyectada via dependencia FastAPI.
        _repo: Repositorio de UsuarioApp para todas las operaciones de datos.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Inicializa el servicio con una sesion asincrona.

        Args:
            db: AsyncSession proporcionada por la dependencia get_db de FastAPI.
        """
        self._db = db
        self._repo = UsuarioAppRepository(db)

    async def registrar(self, nick: str, password: str) -> RespuestaUsuarioApp:
        """Registra un nuevo usuario en estado pendiente_acceso.

        Verifica que el nick no este ya registrado, hashea la contrasena
        y crea la entrada en la base de datos.

        Args:
            nick: Identificador unico elegido por el usuario.
            password: Contrasena en texto plano.

        Returns:
            RespuestaUsuarioApp con los datos publicos del nuevo usuario.

        Raises:
            HTTPException 409: Si el nick ya esta registrado.
        """
        existente = await self._repo.obtener_por_nick(nick)
        if existente is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El nick ya esta registrado. Elige otro o inicia sesion.",
            )
        usuario = await self._repo.crear(nick=nick, password_hash=hash_password(password))
        await self._db.commit()
        await self._db.refresh(usuario)
        return RespuestaUsuarioApp.model_validate(usuario)

    async def login(self, nick: str, password: str) -> RespuestaTokenUsuarioApp:
        """Autentica un usuario y devuelve un token JWT de 1 hora.

        Flujo de validacion:
        1. El nick debe existir en la base de datos.
        2. La cuenta no debe estar bloqueada (intentos_fallidos < 5).
        3. La contrasena debe coincidir con el hash almacenado.
        4. El estado debe ser habilitado o pendiente_ampliar_tokens.

        Args:
            nick: Identificador del usuario.
            password: Contrasena en texto plano a verificar.

        Returns:
            RespuestaTokenUsuarioApp con el JWT y el estado actual de cuota.

        Raises:
            HTTPException 404: Si el nick no existe.
            HTTPException 423: Si la cuenta esta bloqueada por intentos fallidos.
            HTTPException 401: Si la contrasena es incorrecta.
            HTTPException 403: Si el estado es pendiente_acceso (sin aprobar aun).
        """
        usuario = await self._repo.obtener_por_nick(nick)
        # M1-seguridad: nick inexistente devuelve 401 en lugar de 404
        # para evitar enumeracion de usuarios por codigo de respuesta.
        if usuario is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas.",
            )

        if usuario.intentos_fallidos >= _MAX_INTENTOS:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=(
                    "Cuenta bloqueada por multiples intentos fallidos. "
                    "Usa la opcion 'Regenerar contrasena' para recuperar el acceso."
                ),
            )

        if not verify_password(password, usuario.password_hash):
            await self._repo.incrementar_intentos(usuario)
            await self._db.commit()
            # M2-seguridad: no revelar intentos restantes para no asistir a ataques.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas.",
            )

        # Contrasena correcta: resetear intentos antes de comprobar estado
        await self._repo.resetear_intentos(usuario)

        if usuario.estado == EstadoUsuarioApp.pendiente_acceso:
            await self._db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tu solicitud está pendiente de aprobación por el administrador.",
            )

        await self._db.commit()
        await self._db.refresh(usuario)

        token = create_access_token(
            datos={"sub": str(usuario.id), "tipo": "usuario_app"},
            duracion=_DURACION_TOKEN,
        )
        return RespuestaTokenUsuarioApp(
            access_token=token,
            expires_in=int(_DURACION_TOKEN.total_seconds()),
            nick=usuario.nick,
            estado=usuario.estado,
            consultas_usadas=usuario.consultas_usadas,
            cuota_asignada=usuario.cuota_asignada,
            guia_vista=usuario.guia_vista,
            is_admin=usuario.is_admin,
            es_root=usuario.es_root,
        )

    async def solicitar_mas_tokens(self, usuario: UsuarioApp) -> RespuestaUsuarioApp:
        """Marca al usuario como pendiente de ampliacion de tokens.

        El administrador recibira la solicitud en el panel de gestion y
        decidira si amplia la cuota.

        Args:
            usuario: Instancia UsuarioApp autenticada que solicita mas tokens.

        Returns:
            RespuestaUsuarioApp con estado pendiente_ampliar_tokens.
        """
        usuario = await self._repo.actualizar_estado(usuario, EstadoUsuarioApp.pendiente_ampliar_tokens)
        await self._db.commit()
        await self._db.refresh(usuario)
        return RespuestaUsuarioApp.model_validate(usuario)

    async def marcar_guia_vista(self, usuario: UsuarioApp) -> RespuestaUsuarioApp:
        """Marca la guia de bienvenida como vista para el usuario autenticado.

        Args:
            usuario: Instancia UsuarioApp autenticada.

        Returns:
            RespuestaUsuarioApp con guia_vista = True.
        """
        usuario = await self._repo.marcar_guia_vista(usuario)
        await self._db.commit()
        await self._db.refresh(usuario)
        return RespuestaUsuarioApp.model_validate(usuario)

    async def regenerar_contrasena(
        self, nick: str, nueva_password: str
    ) -> RespuestaUsuarioApp:
        """Reemplaza la contrasena y devuelve el usuario a estado pendiente_acceso.

        Mantiene consultas_usadas y cuota_asignada sin cambios.
        Resetea intentos_fallidos a 0.

        Args:
            nick: Identificador del usuario que quiere recuperar el acceso.
            nueva_password: Nueva contrasena en texto plano.

        Returns:
            RespuestaUsuarioApp con estado pendiente_acceso actualizado.

        Raises:
            HTTPException 404: Si el nick no existe.
        """
        usuario = await self._repo.obtener_por_nick(nick)
        if usuario is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Nick no encontrado.",
            )
        usuario = await self._repo.regenerar_contrasena(
            usuario=usuario,
            nuevo_password_hash=hash_password(nueva_password),
        )
        await self._db.commit()
        await self._db.refresh(usuario)
        return RespuestaUsuarioApp.model_validate(usuario)
