"""
Modulo: routers.usuarios
Ruta:   backend/app/routers/usuarios.py

Descripcion:
    Capa HTTP para los endpoints de autenticacion de usuarios web.
    Solo usuarios web (no administradores) usan estos endpoints.

    Endpoints:
        GET  /api/v1/usuarios/me                  -> RespuestaUsuarioApp  200
        POST /api/v1/usuarios/registrar           -> RespuestaUsuarioApp  201
        POST /api/v1/usuarios/login               -> RespuestaTokenUsuarioApp  200
        POST /api/v1/usuarios/regenerar-contrasena -> RespuestaUsuarioApp  200

Dependencias:
    - fastapi
    - app.core.database
    - app.middleware.rate_limit
    - app.schemas.usuario_app
    - app.services.usuario_app_auth_service

Sprint: Sprint 4
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_usuario_app
from app.middleware.rate_limit import limitador
from app.models.usuario_app import UsuarioApp
from app.repositories.benchmark_evaluacion_repository import BenchmarkEvaluacionRepository
from app.schemas.benchmark import ResumenEvaluacionUsuario
from app.schemas.usuario_app import (
    PeticionLogin,
    PeticionRegenerarContrasena,
    PeticionRegistro,
    RespuestaTokenUsuarioApp,
    RespuestaUsuarioApp,
)
from app.services.usuario_app_auth_service import UsuarioAppAuthService

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


@router.get(
    "/me",
    response_model=RespuestaUsuarioApp,
    summary="Perfil del usuario autenticado",
    description=(
        "Devuelve el estado actual del usuario web autenticado, incluida la cuota "
        "vigente. Usado por el frontend al recargar la pagina para sincronizar los "
        "contadores de cuota con la base de datos."
    ),
)
async def obtener_perfil_usuario(
    usuario_actual: UsuarioApp = Depends(get_current_usuario_app),
) -> RespuestaUsuarioApp:
    """Devuelve el perfil del usuario web autenticado con datos frescos de BD.

    Args:
        usuario_actual: Usuario web inyectado por get_current_usuario_app.

    Returns:
        RespuestaUsuarioApp con cuota y estado actualizados.
    """
    return RespuestaUsuarioApp.model_validate(usuario_actual)



@router.get(
    "/mis-evaluaciones",
    response_model=list[ResumenEvaluacionUsuario],
    summary="Historial de evaluaciones del usuario autenticado",
    description=(
        "Devuelve las ultimas 50 evaluaciones del usuario web autenticado "
        "ordenadas por fecha descendente, incluyendo el flag evaluada calculado "
        "en BD. El frontend usa este endpoint como fuente de verdad para el "
        "historial, independientemente del dispositivo o navegador."
    ),
)
async def mis_evaluaciones(
    db: AsyncSession = Depends(get_db),
    usuario_actual: UsuarioApp = Depends(get_current_usuario_app),
) -> list[ResumenEvaluacionUsuario]:
    """Recupera el historial de evaluaciones del usuario autenticado desde BD.

    Args:
        db: Sesion de base de datos asincrona.
        usuario_actual: Usuario web inyectado por get_current_usuario_app.

    Returns:
        Lista de ResumenEvaluacionUsuario con las ultimas 50 evaluaciones
        y el flag evaluada calculado mediante subconsulta correlacionada.
    """
    repo = BenchmarkEvaluacionRepository(db)
    pares = await repo.listar_historial_usuario(nickname=usuario_actual.nick, limite=50)
    return [
        ResumenEvaluacionUsuario(
            id=ev.id,
            prompt=ev.prompt,
            categoria=ev.category,
            estado=ev.status,
            created_at=ev.created_at,
            evaluada=evaluada,
        )
        for ev, evaluada in pares
    ]


@router.get(
    "/verificar/{nick}",
    summary="Verificar si un nick esta registrado",
    description="Devuelve si el nick ya existe en la base de datos. No revela el estado ni la contrasena.",
)
@limitador.limit("20/minute")
async def verificar_nick(
    request: Request,
    nick: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    """Comprueba si un nick esta registrado sin revelar informacion sensible.

    C2-seguridad: limitado a 20 peticiones por minuto por IP para
    mitigar enumeracion automatizada de nicks.

    Args:
        request: Objeto HTTP necesario para slowapi.
        nick: Identificador a verificar.
        db: Sesion de base de datos asincrona.

    Returns:
        Diccionario con la clave 'existe' indicando si el nick esta registrado.
    """
    from app.repositories.usuario_app_repository import UsuarioAppRepository
    repo = UsuarioAppRepository(db)
    usuario = await repo.obtener_por_nick(nick.strip().lower())
    return {"existe": usuario is not None}


@router.post(
    "/registrar",
    response_model=RespuestaUsuarioApp,
    status_code=status.HTTP_201_CREATED,
    summary="Solicitar acceso a la aplicacion",
    description=(
        "Registra un nuevo nick con contrasena y deja la cuenta en estado "
        "'pendiente_acceso'. El administrador debe aprobarla antes de que el "
        "usuario pueda iniciar sesion y ejecutar comparaciones."
    ),
)
@limitador.limit("5/minute")
async def registrar(
    request: Request,
    peticion: PeticionRegistro,
    db: AsyncSession = Depends(get_db),
) -> RespuestaUsuarioApp:
    """Registra un nuevo usuario en estado pendiente_acceso.

    Args:
        peticion: Nick y contrasena elegidos por el usuario.
        db: Sesion de base de datos asincrona.

    Returns:
        RespuestaUsuarioApp con los datos publicos del nuevo usuario.
    """
    servicio = UsuarioAppAuthService(db)
    return await servicio.registrar(nick=peticion.nick, password=peticion.password)


@router.post(
    "/login",
    response_model=RespuestaTokenUsuarioApp,
    summary="Inicio de sesion de usuario",
    description=(
        "Autentica un usuario habilitado y devuelve un JWT valido durante 1 hora. "
        "La cuenta se bloquea tras 5 intentos fallidos consecutivos. "
        "Limite: 10 peticiones por minuto por IP."
    ),
)
@limitador.limit("10/minute")
async def login(
    request: Request,
    peticion: PeticionLogin,
    db: AsyncSession = Depends(get_db),
) -> RespuestaTokenUsuarioApp:
    """Autentica un usuario y devuelve JWT con estado de cuota incluido.

    Args:
        peticion: Nick y contrasena del usuario.
        db: Sesion de base de datos asincrona.

    Returns:
        RespuestaTokenUsuarioApp con el JWT y el estado actual de cuota.
    """
    servicio = UsuarioAppAuthService(db)
    return await servicio.login(nick=peticion.nick, password=peticion.password)


@router.post(
    "/solicitar-mas-tokens",
    response_model=RespuestaUsuarioApp,
    summary="Solicitar ampliación de cuota de consultas",
    description=(
        "Marca al usuario autenticado como 'pendiente_ampliar_tokens'. "
        "El administrador recibira la solicitud en el panel de gestion y "
        "decidira si amplia la cuota asignada."
    ),
)
async def solicitar_mas_tokens(
    db: AsyncSession = Depends(get_db),
    usuario_actual: UsuarioApp = Depends(get_current_usuario_app),
) -> RespuestaUsuarioApp:
    """Solicita al administrador una ampliacion de la cuota de consultas.

    Args:
        db: Sesion de base de datos asincrona.
        usuario_actual: Usuario web autenticado que solicita la ampliacion.

    Returns:
        RespuestaUsuarioApp con estado pendiente_ampliar_tokens.
    """
    servicio = UsuarioAppAuthService(db)
    return await servicio.solicitar_mas_tokens(usuario_actual)


@router.patch(
    "/marcar-guia-vista",
    response_model=RespuestaUsuarioApp,
    summary="Marcar la guia de bienvenida como vista",
    description=(
        "Actualiza el flag guia_vista del usuario autenticado a True. "
        "Se llama automaticamente cuando el usuario cierra la guia por primera vez."
    ),
)
async def marcar_guia_vista(
    db: AsyncSession = Depends(get_db),
    usuario_actual: UsuarioApp = Depends(get_current_usuario_app),
) -> RespuestaUsuarioApp:
    """Marca la guia de bienvenida como vista para el usuario autenticado.

    Args:
        db: Sesion de base de datos asincrona.
        usuario_actual: Usuario web autenticado.

    Returns:
        RespuestaUsuarioApp con guia_vista = True.
    """
    servicio = UsuarioAppAuthService(db)
    return await servicio.marcar_guia_vista(usuario_actual)


@router.post(
    "/evaluaciones/{evaluacion_id}/solicitar-borrado",
    summary="Solicitar al administrador el borrado de una evaluacion propia",
    description=(
        "Marca la evaluacion indicada como 'solicitud_borrado'. "
        "El administrador recibira la solicitud en el panel de comparativas "
        "y podra borrarla definitivamente si lo considera adecuado. "
        "Solo el dueno de la evaluacion puede solicitarlo."
    ),
)
async def solicitar_borrado_evaluacion(
    evaluacion_id: int,
    db: AsyncSession = Depends(get_db),
    usuario_actual: UsuarioApp = Depends(get_current_usuario_app),
) -> dict[str, object]:
    """Solicita al admin el borrado de una evaluacion del usuario autenticado.

    Valida que la evaluacion pertenece al usuario antes de cambiar el estado.

    Args:
        evaluacion_id: ID de la evaluacion a marcar para borrado.
        db: Sesion de base de datos asincrona.
        usuario_actual: Usuario web autenticado propietario de la evaluacion.

    Returns:
        Confirmacion con el ID de la evaluacion marcada.

    Raises:
        HTTPException 404: Evaluacion no encontrada.
        HTTPException 403: La evaluacion no pertenece al usuario.
        HTTPException 409: Ya existe una solicitud de borrado activa.
    """
    repo = BenchmarkEvaluacionRepository(db)
    try:
        await repo.marcar_solicitud_borrado(
            evaluacion_id=evaluacion_id,
            nickname=usuario_actual.nick,
        )
    except ValueError as exc:
        codigos = {
            "no_encontrada": (status.HTTP_404_NOT_FOUND, "Evaluacion no encontrada"),
            "sin_permiso":   (status.HTTP_403_FORBIDDEN, "No tienes permiso para solicitar el borrado de esta evaluacion"),
            "ya_solicitada": (status.HTTP_409_CONFLICT,  "Ya existe una solicitud de borrado activa para esta evaluacion"),
        }
        http_status_code, detalle = codigos.get(str(exc), (status.HTTP_400_BAD_REQUEST, str(exc)))
        raise HTTPException(status_code=http_status_code, detail=detalle)
    await db.commit()
    return {"ok": True, "evaluacion_id": evaluacion_id}


@router.post(
    "/regenerar-contrasena",
    response_model=RespuestaUsuarioApp,
    summary="Regenerar contrasena olvidada o cuenta bloqueada",
    description=(
        "Actualiza la contrasena del nick indicado y devuelve la cuenta a estado "
        "'pendiente_acceso'. Mantiene las consultas usadas y la cuota asignada. "
        "El administrador debera volver a aprobar el acceso."
    ),
)
@limitador.limit("2/minute")
async def regenerar_contrasena(
    request: Request,
    peticion: PeticionRegenerarContrasena,
    db: AsyncSession = Depends(get_db),
) -> RespuestaUsuarioApp:
    """Regenera la contrasena y devuelve el usuario a estado pendiente_acceso.

    M3-seguridad: limite reducido a 2/minuto por IP para dificultar
    ataques de denegacion de servicio selectivos a cuentas concretas.

    Args:
        request: Objeto HTTP necesario para slowapi.
        peticion: Nick y nueva contrasena.
        db: Sesion de base de datos asincrona.

    Returns:
        RespuestaUsuarioApp con estado pendiente_acceso actualizado.
    """
    servicio = UsuarioAppAuthService(db)
    return await servicio.regenerar_contrasena(
        nick=peticion.nick, nueva_password=peticion.nueva_password
    )
