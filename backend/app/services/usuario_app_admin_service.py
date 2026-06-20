"""
Modulo: services.usuario_app_admin_service
Ruta:   backend/app/services/usuario_app_admin_service.py

Descripcion:
    Logica de negocio para la gestion administrativa de usuarios de la
    aplicacion web. Implementa las operaciones exclusivas del panel de admin:
    listar usuarios, conceder acceso con cuota y ampliar tokens.

Dependencias:
    - app.models.usuario_app.UsuarioApp
    - app.repositories.usuario_app_repository.UsuarioAppRepository
    - app.schemas.usuario_app

Sprint: Sprint 4
"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usuario_app import UsuarioApp
from app.repositories.benchmark_evaluacion_repository import BenchmarkEvaluacionRepository
from app.repositories.usuario_app_repository import UsuarioAppRepository
from app.schemas.usuario_app import RespuestaListaUsuarios, RespuestaResetearEvaluaciones, RespuestaUsuarioApp


class UsuarioAppAdminService:
    """Servicio de administracion de usuarios web.

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
        self._eval_repo = BenchmarkEvaluacionRepository(db)

    async def listar_usuarios(self) -> RespuestaListaUsuarios:
        """Devuelve todos los usuarios registrados ordenados por fecha de registro.

        Returns:
            RespuestaListaUsuarios con la lista completa y el total.
        """
        usuarios = await self._repo.listar_todos()
        items = [RespuestaUsuarioApp.model_validate(u) for u in usuarios]
        return RespuestaListaUsuarios(items=items, total=len(items))

    async def conceder_acceso(self, usuario_id: int, cuota: int) -> RespuestaUsuarioApp:
        """Habilita el acceso de un usuario y le asigna una cuota de consultas.

        Cambia el estado a 'habilitado' y fija la cuota_asignada.

        Args:
            usuario_id: ID del usuario a habilitar.
            cuota: Numero de consultas permitidas.

        Returns:
            RespuestaUsuarioApp con estado habilitado y cuota asignada.

        Raises:
            HTTPException 404: Si el usuario no existe.
        """
        usuario = await self._repo.obtener_por_id(usuario_id)
        if usuario is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuario {usuario_id} no encontrado",
            )
        usuario = await self._repo.asignar_cuota(usuario=usuario, cuota=cuota)
        await self._db.commit()
        await self._db.refresh(usuario)
        return RespuestaUsuarioApp.model_validate(usuario)

    async def ampliar_tokens(
        self, usuario_id: int, tokens_adicionales: int
    ) -> RespuestaUsuarioApp:
        """Incrementa la cuota asignada y devuelve el usuario a estado habilitado.

        Args:
            usuario_id: ID del usuario al que se amplian los tokens.
            tokens_adicionales: Consultas adicionales a sumar a la cuota actual.

        Returns:
            RespuestaUsuarioApp con cuota ampliada y estado habilitado.

        Raises:
            HTTPException 404: Si el usuario no existe.
        """
        usuario = await self._repo.obtener_por_id(usuario_id)
        if usuario is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuario {usuario_id} no encontrado",
            )
        usuario = await self._repo.ampliar_tokens(
            usuario=usuario, tokens_adicionales=tokens_adicionales
        )
        await self._db.commit()
        await self._db.refresh(usuario)
        return RespuestaUsuarioApp.model_validate(usuario)

    async def marcar_guia_vista(self, usuario_id: int) -> RespuestaUsuarioApp:
        """Marca guia_vista a True para el usuario indicado.

        Args:
            usuario_id: ID del usuario al que se marca la guia como vista.

        Returns:
            RespuestaUsuarioApp con guia_vista = True.

        Raises:
            HTTPException 404: Si el usuario no existe.
        """
        usuario = await self._repo.obtener_por_id(usuario_id)
        if usuario is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuario {usuario_id} no encontrado",
            )
        usuario = await self._repo.marcar_guia_vista(usuario)
        await self._db.commit()
        await self._db.refresh(usuario)
        return RespuestaUsuarioApp.model_validate(usuario)

    async def resetear_guia_vista(self, usuario_id: int) -> RespuestaUsuarioApp:
        """Resetea el flag guia_vista a False para que la guia vuelva a mostrarse.

        Args:
            usuario_id: ID del usuario al que se resetea el flag.

        Returns:
            RespuestaUsuarioApp con guia_vista = False.

        Raises:
            HTTPException 404: Si el usuario no existe.
        """
        usuario = await self._repo.obtener_por_id(usuario_id)
        if usuario is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuario {usuario_id} no encontrado",
            )
        usuario = await self._repo.resetear_guia_vista(usuario)
        await self._db.commit()
        await self._db.refresh(usuario)
        return RespuestaUsuarioApp.model_validate(usuario)

    async def resetear_evaluaciones_usuario(
        self, usuario_id: int, nueva_cuota: int
    ) -> RespuestaResetearEvaluaciones:
        """Elimina todas las evaluaciones del usuario y resetea su cuota.

        El usuario permanece activo con estado habilitado y consultas_usadas = 0.

        Args:
            usuario_id: ID del usuario al que se resetean las evaluaciones.
            nueva_cuota: Nueva cuota de consultas asignada tras el reset.

        Returns:
            RespuestaResetearEvaluaciones con el usuario actualizado y el total borrado.

        Raises:
            HTTPException 404: Si el usuario no existe.
        """
        usuario = await self._repo.obtener_por_id(usuario_id)
        if usuario is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuario {usuario_id} no encontrado",
            )
        evaluaciones_eliminadas = await self._eval_repo.eliminar_por_nickname(usuario.nick)
        usuario = await self._repo.resetear_cuota(usuario=usuario, nueva_cuota=nueva_cuota)
        await self._db.commit()
        await self._db.refresh(usuario)
        return RespuestaResetearEvaluaciones(
            usuario=RespuestaUsuarioApp.model_validate(usuario),
            evaluaciones_eliminadas=evaluaciones_eliminadas,
        )

    async def eliminar_usuario(self, usuario_id: int) -> int:
        """Elimina un usuario y todas sus evaluaciones de benchmark.

        Primero borra en cascade todas las evaluaciones del nick del usuario
        (arrastrando llm_responses y user_evaluations), y despues elimina
        el registro de UsuarioApp.

        Guard: el admin root nunca se puede eliminar desde la aplicacion.
        Es la cuenta canonica del despliegue y la perdida del root dejaria
        al sistema sin gestion de roles. La unica forma de removerlo es
        manualmente en BD por un operador con acceso al servidor.

        Args:
            usuario_id: ID del usuario a eliminar.

        Returns:
            Numero de evaluaciones eliminadas junto con el usuario.

        Raises:
            HTTPException 404: Si el usuario no existe.
            HTTPException 400: Si el usuario es root (es_root=True).
        """
        usuario = await self._repo.obtener_por_id(usuario_id)
        if usuario is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuario {usuario_id} no encontrado",
            )
        if usuario.es_root:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede eliminar al administrador root del sistema",
            )
        evaluaciones_eliminadas = await self._eval_repo.eliminar_por_nickname(usuario.nick)
        await self._db.delete(usuario)
        await self._db.commit()
        return evaluaciones_eliminadas

    async def promover_admin(
        self, caller: UsuarioApp, usuario_id: int, email: str,
    ) -> RespuestaUsuarioApp:
        """Promociona un usuario regular a administrador (solo root).

        Asigna email obligatorio (check ck_admin_requires_email) y is_admin=True.
        La contrasena se conserva tal cual; el usuario seguira accediendo con
        nick + password actuales pero ahora con privilegios administrativos.
        es_root permanece a False: solo se puede ser root via el seed_admin.py
        del despliegue.

        El estado del ciclo de vida y la cuota no se modifican aunque dejen
        de aplicar mientras is_admin=True.

        Args:
            caller: Admin autenticado que invoca el endpoint. Debe tener
                es_root=True (los admins promovidos no pueden promover a otros).
            usuario_id: ID del usuario a promover.
            email: Correo del nuevo admin (obligatorio, debe ser unico).

        Returns:
            RespuestaUsuarioApp con is_admin=True y email asignado.

        Raises:
            HTTPException 403: caller no es root.
            HTTPException 404: Usuario no existe.
            HTTPException 409: El email ya esta usado por otro usuario.
            HTTPException 400: El usuario ya es admin.
        """
        if not caller.es_root:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo el administrador root puede promover a otros usuarios",
            )
        usuario = await self._repo.obtener_por_id(usuario_id)
        if usuario is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuario {usuario_id} no encontrado",
            )
        if usuario.is_admin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El usuario @{usuario.nick} ya es administrador",
            )
        # Comprobar unicidad del email (excluye al propio usuario por si ya lo tenia).
        otro = await self._repo.obtener_por_email(email)
        if otro is not None and otro.id != usuario.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"El correo {email} ya esta asociado a otro usuario",
            )
        usuario.email = email
        usuario.is_admin = True
        # es_root NO se toca: nuevos admins son siempre no-root.
        await self._db.flush()
        await self._db.commit()
        await self._db.refresh(usuario)
        return RespuestaUsuarioApp.model_validate(usuario)

    async def degradar_admin(
        self, caller: UsuarioApp, usuario_id: int,
    ) -> RespuestaUsuarioApp:
        """Revoca privilegios de administrador a un usuario (solo root).

        Pone is_admin=False y limpia el email (la check constraint
        ck_admin_requires_email solo lo exige cuando is_admin=True; al
        degradar dejamos email=NULL para que el usuario regular no
        retenga datos de contacto innecesarios).

        Guards:
          - caller debe tener es_root=True.
          - target.es_root debe ser False (no se puede degradar al root).
          - No degradar al ultimo administrador (defensivo, redundante con
            el guard anterior pero util si alguna vez se introducen multiples
            roots).

        Args:
            caller: Admin autenticado que invoca el endpoint.
            usuario_id: ID del admin a degradar.

        Returns:
            RespuestaUsuarioApp con is_admin=False.

        Raises:
            HTTPException 403: caller no es root.
            HTTPException 404: Usuario no existe.
            HTTPException 400: Usuario no era admin, es root, o seria el
                ultimo admin del sistema.
        """
        if not caller.es_root:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo el administrador root puede quitar privilegios a otros",
            )
        usuario = await self._repo.obtener_por_id(usuario_id)
        if usuario is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuario {usuario_id} no encontrado",
            )
        if not usuario.is_admin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El usuario @{usuario.nick} no es administrador",
            )
        if usuario.es_root:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede degradar al administrador root del sistema",
            )
        # Guard del ultimo admin: defensivo (root nunca se degrada y siempre
        # cuenta al menos 1 admin, pero lo dejamos por simetria).
        n_admins = await self._repo.contar_admins()
        if n_admins <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede degradar al ultimo administrador del sistema",
            )
        usuario.is_admin = False
        usuario.email = None
        await self._db.flush()
        await self._db.commit()
        await self._db.refresh(usuario)
        return RespuestaUsuarioApp.model_validate(usuario)
