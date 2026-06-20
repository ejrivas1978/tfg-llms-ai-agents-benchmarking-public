"""
Modulo: usuario_app_repository
Ruta:   backend/app/repositories/usuario_app_repository.py

Descripcion:
    Repository para UsuarioApp. Encapsula todas las queries SQLAlchemy
    relacionadas con los usuarios de la aplicacion web.

    DECISION(ADR-003): El patron Repository desacopla la logica de negocio
    del ORM, facilitando los tests con mocks de la interfaz del repositorio.

Dependencias:
    - sqlalchemy.ext.asyncio.AsyncSession
    - app.models.usuario_app.UsuarioApp
    - app.models.enums.EstadoUsuarioApp

Sprint: Sprint 4
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import EstadoUsuarioApp
from app.models.usuario_app import UsuarioApp


class UsuarioAppRepository:
    """Repositorio de operaciones de base de datos para UsuarioApp.

    Atributos:
        _db: Sesion asincrona de SQLAlchemy inyectada en cada peticion.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Inicializa el repositorio con la sesion de base de datos.

        Args:
            db: Sesion asincrona de SQLAlchemy.
        """
        self._db = db

    async def crear(self, nick: str, password_hash: str) -> UsuarioApp:
        """Crea un nuevo usuario en estado pendiente_acceso.

        Args:
            nick: Identificador unico del usuario.
            password_hash: Hash Argon2 de la contrasena.

        Returns:
            UsuarioApp recien creado con estado pendiente_acceso.
        """
        usuario = UsuarioApp(nick=nick, password_hash=password_hash)
        self._db.add(usuario)
        await self._db.flush()
        await self._db.refresh(usuario)
        return usuario

    async def obtener_por_nick(self, nick: str) -> UsuarioApp | None:
        """Busca un usuario por su nick.

        Args:
            nick: Identificador unico del usuario.

        Returns:
            UsuarioApp si existe, None si no.
        """
        resultado = await self._db.execute(
            select(UsuarioApp).where(UsuarioApp.nick == nick)
        )
        return resultado.scalar_one_or_none()

    async def obtener_por_id(self, usuario_id: int) -> UsuarioApp | None:
        """Busca un usuario por su clave primaria.

        Args:
            usuario_id: ID del usuario.

        Returns:
            UsuarioApp si existe, None si no.
        """
        resultado = await self._db.execute(
            select(UsuarioApp).where(UsuarioApp.id == usuario_id)
        )
        return resultado.scalar_one_or_none()

    async def obtener_por_email(self, email: str) -> UsuarioApp | None:
        """Busca un usuario por su correo electronico.

        Solo deberia haber un usuario con cada email gracias al unique
        constraint, pero email es nullable (solo obligatorio para admins).

        Args:
            email: Correo electronico a buscar.

        Returns:
            UsuarioApp si existe, None si no.
        """
        resultado = await self._db.execute(
            select(UsuarioApp).where(UsuarioApp.email == email)
        )
        return resultado.scalar_one_or_none()

    async def contar_admins(self) -> int:
        """Devuelve el numero de usuarios con is_admin=True.

        Lo usa el guard 'no degradar al ultimo admin' antes de quitar
        privilegios.

        Returns:
            Numero de admins activos en usuarios_app.
        """
        from sqlalchemy import func
        resultado = await self._db.execute(
            select(func.count(UsuarioApp.id)).where(UsuarioApp.is_admin.is_(True))
        )
        return resultado.scalar_one()

    async def listar_todos(self) -> list[UsuarioApp]:
        """Devuelve todos los usuarios ordenados por fecha de registro descendente.

        Returns:
            Lista de UsuarioApp ordenada por created_at desc.
        """
        resultado = await self._db.execute(
            select(UsuarioApp).order_by(UsuarioApp.created_at.desc())
        )
        return list(resultado.scalars().all())

    async def actualizar_estado(
        self, usuario: UsuarioApp, estado: EstadoUsuarioApp
    ) -> UsuarioApp:
        """Cambia el estado del usuario.

        Args:
            usuario: Instancia UsuarioApp a modificar.
            estado: Nuevo estado.

        Returns:
            UsuarioApp actualizado.
        """
        usuario.estado = estado
        await self._db.flush()
        await self._db.refresh(usuario)
        return usuario

    async def asignar_cuota(self, usuario: UsuarioApp, cuota: int) -> UsuarioApp:
        """Asigna la cuota de consultas permitidas y habilita al usuario.

        Args:
            usuario: Instancia UsuarioApp a modificar.
            cuota: Numero de consultas permitidas.

        Returns:
            UsuarioApp con estado habilitado y cuota asignada.
        """
        usuario.cuota_asignada = cuota
        usuario.estado = EstadoUsuarioApp.habilitado
        await self._db.flush()
        await self._db.refresh(usuario)
        return usuario

    async def ampliar_tokens(self, usuario: UsuarioApp, tokens_adicionales: int) -> UsuarioApp:
        """Ajusta la cuota asignada y devuelve al usuario a estado habilitado.

        Acepta valores positivos (ampliar) y negativos (reducir).
        La cuota resultante se limita a un minimo de 0.

        Args:
            usuario: Instancia UsuarioApp a modificar.
            tokens_adicionales: Ajuste de cuota (positivo o negativo).

        Returns:
            UsuarioApp con cuota ajustada y estado habilitado.
        """
        usuario.cuota_asignada = max(0, usuario.cuota_asignada + tokens_adicionales)
        usuario.estado = EstadoUsuarioApp.habilitado
        await self._db.flush()
        await self._db.refresh(usuario)
        return usuario

    async def incrementar_consultas(self, usuario: UsuarioApp) -> UsuarioApp:
        """Suma 1 al contador de consultas usadas.

        Se llama unicamente cuando una comparacion finaliza sin error
        y sin rechazo por politica de contenido.

        Args:
            usuario: Instancia UsuarioApp a modificar.

        Returns:
            UsuarioApp con consultas_usadas incrementado.
        """
        usuario.consultas_usadas += 1
        await self._db.flush()
        await self._db.refresh(usuario)
        return usuario

    async def incrementar_intentos(self, usuario: UsuarioApp) -> UsuarioApp:
        """Suma 1 al contador de intentos de login fallidos.

        Args:
            usuario: Instancia UsuarioApp a modificar.

        Returns:
            UsuarioApp con intentos_fallidos incrementado.
        """
        usuario.intentos_fallidos += 1
        await self._db.flush()
        await self._db.refresh(usuario)
        return usuario

    async def resetear_cuota(self, usuario: UsuarioApp, nueva_cuota: int) -> UsuarioApp:
        """Resetea las consultas usadas, asigna nueva cuota y habilita al usuario.

        Se llama tras borrar todas las evaluaciones de un usuario para dejarle
        con contador a cero y nueva cuota asignada por el administrador.

        Args:
            usuario: Instancia UsuarioApp a modificar.
            nueva_cuota: Nueva cuota de consultas asignada.

        Returns:
            UsuarioApp con consultas_usadas = 0, cuota_asignada = nueva_cuota y estado habilitado.
        """
        usuario.consultas_usadas = 0
        usuario.cuota_asignada   = nueva_cuota
        usuario.estado           = EstadoUsuarioApp.habilitado
        await self._db.flush()
        await self._db.refresh(usuario)
        return usuario

    async def resetear_intentos(self, usuario: UsuarioApp) -> UsuarioApp:
        """Pone a 0 el contador de intentos fallidos tras un login exitoso.

        Args:
            usuario: Instancia UsuarioApp a modificar.

        Returns:
            UsuarioApp con intentos_fallidos = 0.
        """
        usuario.intentos_fallidos = 0
        await self._db.flush()
        await self._db.refresh(usuario)
        return usuario

    async def marcar_guia_vista(self, usuario: UsuarioApp) -> UsuarioApp:
        """Marca la guia de bienvenida como ya vista por el usuario.

        Args:
            usuario: Instancia UsuarioApp a modificar.

        Returns:
            UsuarioApp con guia_vista = True.
        """
        usuario.guia_vista = True
        await self._db.flush()
        await self._db.refresh(usuario)
        return usuario

    async def resetear_guia_vista(self, usuario: UsuarioApp) -> UsuarioApp:
        """Resetea el flag guia_vista a False para que vuelva a aparecer.

        Solo debe llamarlo el administrador desde el panel de usuarios.

        Args:
            usuario: Instancia UsuarioApp a modificar.

        Returns:
            UsuarioApp con guia_vista = False.
        """
        usuario.guia_vista = False
        await self._db.flush()
        await self._db.refresh(usuario)
        return usuario

    async def regenerar_contrasena(
        self, usuario: UsuarioApp, nuevo_password_hash: str
    ) -> UsuarioApp:
        """Actualiza la contrasena y devuelve al usuario a pendiente_acceso.

        Mantiene consultas_usadas y cuota_asignada sin cambios.
        Resetea intentos_fallidos a 0.

        Args:
            usuario: Instancia UsuarioApp a modificar.
            nuevo_password_hash: Hash Argon2 de la nueva contrasena.

        Returns:
            UsuarioApp con nueva contrasena y estado pendiente_acceso.
        """
        usuario.password_hash = nuevo_password_hash
        usuario.estado = EstadoUsuarioApp.pendiente_acceso
        usuario.intentos_fallidos = 0
        await self._db.flush()
        await self._db.refresh(usuario)
        return usuario
