"""
Modulo: routers.admin
Ruta:   backend/app/routers/admin.py

Descripcion:
    Capa HTTP para los endpoints de administracion del estudio.
    Todos los endpoints de este router requieren un JWT valido de administrador.
    Permiten listar evaluaciones con paginacion, eliminar evaluaciones individuales
    y realizar un reset completo de todos los datos del estudio.

    Endpoints:
        GET    /api/v1/admin/evaluaciones             -> RespuestaListaEvaluaciones  200
        GET    /api/v1/admin/evaluaciones/exportar-csv -> StreamingResponse text/csv 200
        DELETE /api/v1/admin/evaluaciones/{id}        -> 204 No Content
        DELETE /api/v1/admin/evaluaciones             -> dict  200
        GET    /api/v1/admin/usuarios                 -> RespuestaListaUsuarios  200
        POST   /api/v1/admin/usuarios/{id}/conceder-acceso -> RespuestaUsuarioApp  200
        POST   /api/v1/admin/usuarios/{id}/ampliar-tokens  -> RespuestaUsuarioApp  200
        DELETE /api/v1/admin/usuarios/{id}            -> 204 No Content

Dependencias:
    - fastapi
    - app.core.database
    - app.core.dependencies
    - app.models.usuario_app
    - app.repositories.benchmark_evaluacion_repository
    - app.schemas.benchmark

Sprint: Sprint 2
"""

import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.enums import LLMProvider, SessionStatus, TestCategory
from app.models.usuario_app import UsuarioApp
from app.repositories.benchmark_evaluacion_repository import BenchmarkEvaluacionRepository
from app.schemas.benchmark import ResumenEvaluacionAdmin, RespuestaListaEvaluaciones
from app.schemas.tarifa import (
    PeticionActualizarTarifa,
    RespuestaHistorialTarifa,
    RespuestaListaTarifas,
)
from app.schemas.usuario_app import (
    PeticionAmpliarTokens,
    PeticionConcederAcceso,
    PeticionPromoverAdmin,
    PeticionResetearEvaluaciones,
    RespuestaListaUsuarios,
    RespuestaResetearEvaluaciones,
    RespuestaUsuarioApp,
)
from app.services.admin_export_service import generar_csv
from app.services.tarifa_service import TarifaService
from app.services.usuario_app_admin_service import UsuarioAppAdminService

router = APIRouter(prefix="/admin", tags=["administracion"])


@router.get(
    "/evaluaciones",
    response_model=RespuestaListaEvaluaciones,
    summary="Listar todas las evaluaciones (paginado)",
    description=(
        "Devuelve el listado paginado de todas las evaluaciones de benchmark. "
        "Los resumenes no incluyen las respuestas LLM individuales. "
        "Requiere autenticacion JWT de administrador."
    ),
)
async def listar_evaluaciones(
    pagina: int = Query(default=1, ge=1, description="Numero de pagina (minimo 1)"),
    limite: int = Query(default=10, ge=1, le=100, description="Evaluaciones por pagina (max 100)"),
    nick: str | None = Query(default=None, description="Filtro parcial por nickname"),
    categoria: TestCategory | None = Query(default=None, description="Filtro exacto por categoria"),
    prompt: str | None = Query(default=None, description="Filtro parcial por texto del prompt"),
    estado: SessionStatus | None = Query(default=None, description="Filtro exacto por estado"),
    valoracion: str | None = Query(default=None, description="'valorada' o 'sin_valorar'"),
    fecha_desde: datetime | None = Query(default=None, description="Fecha-hora de inicio inclusive (ISO 8601, ej. 2026-05-09T10:30:00Z)"),
    fecha_hasta: datetime | None = Query(default=None, description="Fecha-hora de fin inclusive (ISO 8601, ej. 2026-05-09T18:00:00Z)"),
    db: AsyncSession = Depends(get_db),
    _admin: UsuarioApp = Depends(get_current_user),
) -> RespuestaListaEvaluaciones:
    """Lista todas las evaluaciones con paginacion y filtros opcionales.

    Args:
        pagina: Numero de pagina solicitada (basado en 1).
        limite: Evaluaciones por pagina.
        nick: Filtro parcial por nickname.
        categoria: Filtro exacto por categoria.
        prompt: Filtro parcial por texto del prompt.
        estado: Filtro exacto por estado.
        valoracion: 'valorada' o 'sin_valorar'.
        fecha_desde: Inicio del rango de fechas.
        fecha_hasta: Fin del rango de fechas.
        db: Sesion de base de datos asincrona.
        _admin: Administrador autenticado (solo actua como guard).

    Returns:
        RespuestaListaEvaluaciones con la pagina actual y el total de registros filtrados.
    """
    evaluada_filtro: bool | None = None
    if valoracion == 'valorada':
        evaluada_filtro = True
    elif valoracion == 'sin_valorar':
        evaluada_filtro = False

    repo = BenchmarkEvaluacionRepository(db)
    offset = (pagina - 1) * limite
    evaluaciones, total = await repo.listar_todas(
        limite=limite,
        offset=offset,
        nickname=nick,
        categoria=categoria,
        prompt=prompt,
        estado=estado,
        evaluada=evaluada_filtro,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )

    items = [
        ResumenEvaluacionAdmin(
            id=e.id,
            nickname=e.nickname,
            prompt=e.prompt,
            categoria=e.category,
            estado=e.status,
            similitud_jaccard_media=e.similitud_jaccard_media,
            created_at=e.created_at,
            completed_at=e.completed_at,
            evaluada=ev,
        )
        for e, ev in evaluaciones
    ]

    return RespuestaListaEvaluaciones(
        items=items,
        total=total,
        pagina=pagina,
        paginas=math.ceil(total / limite) if total > 0 else 1,
    )


@router.get(
    "/evaluaciones/exportar-csv",
    summary="Exportar todas las evaluaciones filtradas en CSV",
    description=(
        "Devuelve un CSV con una fila por respuesta LLM (formato tidy/largo). "
        "Aplica los mismos filtros que el listado paginado para que el admin "
        "pueda exportar exactamente lo que ve en pantalla. Codificacion UTF-8 "
        "con BOM para apertura directa en Excel. No incluye textos de prompt "
        "ni de respuestas para mantener la legibilidad. "
        "Requiere autenticacion JWT de administrador."
    ),
    responses={200: {"content": {"text/csv": {}}}},
)
async def exportar_evaluaciones_csv(
    nick: str | None = Query(default=None, description="Filtro parcial por nickname"),
    categoria: TestCategory | None = Query(default=None, description="Filtro exacto por categoria"),
    prompt: str | None = Query(default=None, description="Filtro parcial por texto del prompt"),
    estado: SessionStatus | None = Query(default=None, description="Filtro exacto por estado"),
    valoracion: str | None = Query(default=None, description="'valorada' o 'sin_valorar'"),
    fecha_desde: datetime | None = Query(default=None, description="Fecha-hora de inicio inclusive (ISO 8601)"),
    fecha_hasta: datetime | None = Query(default=None, description="Fecha-hora de fin inclusive (ISO 8601)"),
    db: AsyncSession = Depends(get_db),
    _admin: UsuarioApp = Depends(get_current_user),
) -> StreamingResponse:
    """Exporta a CSV todas las evaluaciones que cumplen los filtros.

    Args:
        nick: Filtro parcial por nickname.
        categoria: Filtro exacto por categoria.
        prompt: Filtro parcial por texto del prompt.
        estado: Filtro exacto por estado.
        valoracion: 'valorada' o 'sin_valorar'.
        fecha_desde: Inicio del rango de fechas.
        fecha_hasta: Fin del rango de fechas.
        db: Sesion de base de datos asincrona.
        _admin: Administrador autenticado (guard).

    Returns:
        StreamingResponse con Content-Type text/csv y un nombre de fichero
        que incluye marca de tiempo para distinguir descargas sucesivas.
    """
    evaluada_filtro: bool | None = None
    if valoracion == 'valorada':
        evaluada_filtro = True
    elif valoracion == 'sin_valorar':
        evaluada_filtro = False

    repo = BenchmarkEvaluacionRepository(db)
    evaluaciones = await repo.listar_para_export(
        nickname=nick,
        categoria=categoria,
        prompt=prompt,
        estado=estado,
        evaluada=evaluada_filtro,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )

    marca = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    nombre = f"benchmark-export-{marca}.csv"
    cabeceras = {"Content-Disposition": f'attachment; filename="{nombre}"'}

    return StreamingResponse(
        generar_csv(evaluaciones),
        media_type="text/csv; charset=utf-8",
        headers=cabeceras,
    )


@router.post(
    "/evaluaciones/{evaluacion_id}/rechazar-borrado",
    summary="Rechazar solicitud de borrado y restaurar evaluacion",
    description=(
        "Revierte el estado de una evaluacion de 'solicitud_borrado' a 'completada', "
        "cancelando la solicitud del usuario. La evaluacion queda disponible para "
        "seguir siendo valorada si aun no lo fue. Requiere JWT de administrador."
    ),
)
async def rechazar_solicitud_borrado(
    evaluacion_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: UsuarioApp = Depends(get_current_user),
) -> dict[str, object]:
    """Rechaza la solicitud de borrado y devuelve la evaluacion a estado completada.

    Args:
        evaluacion_id: ID de la evaluacion cuya solicitud se rechaza.
        db: Sesion de base de datos asincrona.
        _admin: Administrador autenticado (solo actua como guard).

    Returns:
        Confirmacion con el ID y el nuevo estado de la evaluacion.

    Raises:
        HTTPException 404: Evaluacion no encontrada.
        HTTPException 409: La evaluacion no esta en estado solicitud_borrado.
    """
    from fastapi import HTTPException

    repo = BenchmarkEvaluacionRepository(db)
    evaluacion = await repo.obtener_por_id(evaluacion_id)
    if evaluacion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluacion {evaluacion_id} no encontrada",
        )
    if evaluacion.status != SessionStatus.solicitud_borrado:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La evaluacion no tiene una solicitud de borrado activa",
        )
    await repo.actualizar_estado(evaluacion, SessionStatus.completada)
    await db.commit()
    return {"ok": True, "evaluacion_id": evaluacion_id, "nuevo_estado": SessionStatus.completada}


@router.delete(
    "/evaluaciones/{evaluacion_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar una evaluacion de benchmark",
    description=(
        "Elimina una evaluacion y todas sus respuestas LLM y evaluaciones de usuario (cascade). "
        "Requiere autenticacion JWT de administrador."
    ),
)
async def eliminar_evaluacion(
    evaluacion_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: UsuarioApp = Depends(get_current_user),
) -> Response:
    """Elimina una evaluacion y su contenido en cascade.

    Args:
        evaluacion_id: ID de la evaluacion a eliminar.
        db: Sesion de base de datos asincrona.
        _admin: Administrador autenticado (solo actua como guard).

    Returns:
        204 No Content si la eliminacion tiene exito.
    """
    from fastapi import HTTPException

    repo = BenchmarkEvaluacionRepository(db)
    evaluacion = await repo.obtener_por_id(evaluacion_id)
    if evaluacion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluacion {evaluacion_id} no encontrada",
        )
    await repo.eliminar(evaluacion)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/evaluaciones",
    summary="Eliminar todas las evaluaciones (reset del estudio)",
    description=(
        "Elimina todas las evaluaciones de benchmark, respuestas LLM y evaluaciones de usuario. "
        "Esta operacion es irreversible y debe usarse solo para reiniciar el estudio. "
        "Requiere autenticacion JWT de administrador."
    ),
)
async def eliminar_todas_las_evaluaciones(
    db: AsyncSession = Depends(get_db),
    _admin: UsuarioApp = Depends(get_current_user),
) -> dict[str, int]:
    """Elimina todas las evaluaciones del estudio.

    Args:
        db: Sesion de base de datos asincrona.
        _admin: Administrador autenticado (solo actua como guard).

    Returns:
        Diccionario con la clave 'eliminadas' y el total de evaluaciones borradas.
    """
    repo = BenchmarkEvaluacionRepository(db)
    eliminadas = await repo.eliminar_todas()
    return {"eliminadas": eliminadas}


# ---------------------------------------------------------------------------
# Gestion de usuarios de la aplicacion web
# ---------------------------------------------------------------------------


@router.get(
    "/usuarios",
    response_model=RespuestaListaUsuarios,
    summary="Listar todos los usuarios registrados",
    description=(
        "Devuelve la lista completa de usuarios web con su estado actual "
        "(pendiente_acceso, habilitado, pendiente_ampliar_tokens) y sus "
        "contadores de cuota. Requiere autenticacion JWT de administrador."
    ),
)
async def listar_usuarios(
    db: AsyncSession = Depends(get_db),
    _admin: UsuarioApp = Depends(get_current_user),
) -> RespuestaListaUsuarios:
    """Lista todos los usuarios registrados en la aplicacion.

    Args:
        db: Sesion de base de datos asincrona.
        _admin: Administrador autenticado (guard).

    Returns:
        RespuestaListaUsuarios con todos los usuarios y el total.
    """
    servicio = UsuarioAppAdminService(db)
    return await servicio.listar_usuarios()


@router.post(
    "/usuarios/{usuario_id}/conceder-acceso",
    response_model=RespuestaUsuarioApp,
    summary="Conceder acceso a un usuario y asignar cuota",
    description=(
        "Habilita el acceso de un usuario pendiente y le asigna la cuota "
        "de consultas indicada. Requiere autenticacion JWT de administrador."
    ),
)
async def conceder_acceso(
    usuario_id: int,
    peticion: PeticionConcederAcceso,
    db: AsyncSession = Depends(get_db),
    _admin: UsuarioApp = Depends(get_current_user),
) -> RespuestaUsuarioApp:
    """Habilita un usuario y le asigna cuota de consultas.

    Args:
        usuario_id: ID del usuario a habilitar.
        peticion: Cuota de consultas a asignar.
        db: Sesion de base de datos asincrona.
        _admin: Administrador autenticado (guard).

    Returns:
        RespuestaUsuarioApp con estado habilitado y cuota asignada.
    """
    servicio = UsuarioAppAdminService(db)
    return await servicio.conceder_acceso(usuario_id=usuario_id, cuota=peticion.cuota)


@router.post(
    "/usuarios/{usuario_id}/ampliar-tokens",
    response_model=RespuestaUsuarioApp,
    summary="Ampliar la cuota de consultas de un usuario",
    description=(
        "Incrementa la cuota asignada del usuario en la cantidad indicada "
        "y lo devuelve a estado habilitado. Requiere autenticacion JWT de administrador."
    ),
)
async def ampliar_tokens(
    usuario_id: int,
    peticion: PeticionAmpliarTokens,
    db: AsyncSession = Depends(get_db),
    _admin: UsuarioApp = Depends(get_current_user),
) -> RespuestaUsuarioApp:
    """Amplia la cuota de consultas de un usuario.

    Args:
        usuario_id: ID del usuario al que se amplian los tokens.
        peticion: Tokens adicionales a sumar.
        db: Sesion de base de datos asincrona.
        _admin: Administrador autenticado (guard).

    Returns:
        RespuestaUsuarioApp con cuota ampliada y estado habilitado.
    """
    servicio = UsuarioAppAdminService(db)
    return await servicio.ampliar_tokens(
        usuario_id=usuario_id, tokens_adicionales=peticion.tokens_adicionales
    )


@router.post(
    "/usuarios/{usuario_id}/marcar-guia-vista",
    response_model=RespuestaUsuarioApp,
    summary="Marcar la guia de bienvenida como vista para un usuario",
    description=(
        "Pone guia_vista a True para el usuario indicado. "
        "Requiere autenticacion JWT de administrador."
    ),
)
async def marcar_guia_vista_usuario(
    usuario_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: UsuarioApp = Depends(get_current_user),
) -> RespuestaUsuarioApp:
    """Marca guia_vista = True para el usuario indicado.

    Args:
        usuario_id: ID del usuario al que se marca la guia como vista.
        db: Sesion de base de datos asincrona.
        _admin: Administrador autenticado (guard).

    Returns:
        RespuestaUsuarioApp con guia_vista = True.
    """
    servicio = UsuarioAppAdminService(db)
    return await servicio.marcar_guia_vista(usuario_id)


@router.post(
    "/usuarios/{usuario_id}/resetear-guia",
    response_model=RespuestaUsuarioApp,
    summary="Resetear la guia de bienvenida de un usuario",
    description=(
        "Pone guia_vista a False para que la guia de bienvenida vuelva a aparecer "
        "la proxima vez que el usuario inicie sesion. "
        "Requiere autenticacion JWT de administrador."
    ),
)
async def resetear_guia_usuario(
    usuario_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: UsuarioApp = Depends(get_current_user),
) -> RespuestaUsuarioApp:
    """Resetea el flag guia_vista del usuario para que vuelva a ver la guia.

    Args:
        usuario_id: ID del usuario al que se resetea la guia.
        db: Sesion de base de datos asincrona.
        _admin: Administrador autenticado (guard).

    Returns:
        RespuestaUsuarioApp con guia_vista = False.
    """
    servicio = UsuarioAppAdminService(db)
    return await servicio.resetear_guia_vista(usuario_id)


@router.post(
    "/usuarios/{usuario_id}/resetear-evaluaciones",
    response_model=RespuestaResetearEvaluaciones,
    summary="Resetear evaluaciones de un usuario",
    description=(
        "Elimina todas las evaluaciones del usuario, pone consultas_usadas a 0 "
        "y asigna la nueva cuota indicada. El usuario permanece activo. "
        "Requiere autenticacion JWT de administrador."
    ),
)
async def resetear_evaluaciones_usuario(
    usuario_id: int,
    peticion: PeticionResetearEvaluaciones,
    db: AsyncSession = Depends(get_db),
    _admin: UsuarioApp = Depends(get_current_user),
) -> RespuestaResetearEvaluaciones:
    """Resetea evaluaciones y cuota de un usuario sin eliminarlo.

    Args:
        usuario_id: ID del usuario a resetear.
        peticion: Nueva cuota de consultas tras el reset.
        db: Sesion de base de datos asincrona.
        _admin: Administrador autenticado (guard).

    Returns:
        RespuestaResetearEvaluaciones con usuario actualizado y total de evaluaciones borradas.
    """
    servicio = UsuarioAppAdminService(db)
    return await servicio.resetear_evaluaciones_usuario(
        usuario_id=usuario_id, nueva_cuota=peticion.nueva_cuota
    )


@router.delete(
    "/usuarios/{usuario_id}",
    summary="Eliminar un usuario y todas sus evaluaciones",
    description=(
        "Elimina permanentemente un usuario y en cascade todas sus evaluaciones "
        "de benchmark, respuestas LLM y valoraciones asociadas. "
        "Requiere autenticacion JWT de administrador."
    ),
)
async def eliminar_usuario(
    usuario_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: UsuarioApp = Depends(get_current_user),
) -> dict[str, int]:
    """Elimina un usuario y todas sus evaluaciones en cascade.

    Args:
        usuario_id: ID del usuario a eliminar.
        db: Sesion de base de datos asincrona.
        _admin: Administrador autenticado (guard).

    Returns:
        Diccionario con el numero de evaluaciones eliminadas junto con el usuario.
    """
    servicio = UsuarioAppAdminService(db)
    evaluaciones_eliminadas = await servicio.eliminar_usuario(usuario_id)
    return {"evaluaciones_eliminadas": evaluaciones_eliminadas}


@router.post(
    "/usuarios/{usuario_id}/promover-admin",
    response_model=RespuestaUsuarioApp,
    summary="Promover un usuario regular a administrador (solo root)",
    description=(
        "Otorga privilegios de administracion al usuario indicado y le asigna "
        "el correo electronico (obligatorio para admins). La contrasena se "
        "conserva tal cual. El nuevo admin tendra es_root=False, asi que NO "
        "podra promover ni degradar a otros: solo el admin root (creado en el "
        "seed del despliegue) puede gestionar roles. "
        "Devuelve 403 si el caller no es root."
    ),
)
async def promover_admin(
    usuario_id: int,
    peticion: PeticionPromoverAdmin,
    db: AsyncSession = Depends(get_db),
    admin: UsuarioApp = Depends(get_current_user),
) -> RespuestaUsuarioApp:
    """Asigna is_admin=True y email al usuario indicado (solo root).

    Args:
        usuario_id: ID del usuario a promover.
        peticion: Cuerpo con el email del nuevo admin.
        db: Sesion de base de datos asincrona.
        admin: Administrador autenticado; debe tener es_root=True.

    Returns:
        RespuestaUsuarioApp con is_admin=True y email asignado.
    """
    servicio = UsuarioAppAdminService(db)
    return await servicio.promover_admin(
        caller=admin, usuario_id=usuario_id, email=peticion.email,
    )


@router.post(
    "/usuarios/{usuario_id}/quitar-admin",
    response_model=RespuestaUsuarioApp,
    summary="Revocar privilegios de administrador a un usuario (solo root)",
    description=(
        "Pone is_admin=False y limpia el email. La cuota y consultas_usadas "
        "no se modifican: el usuario reanuda el control de cuota con los "
        "valores que tenia. "
        "Devuelve 403 si el caller no es root, 400 si el target es root o "
        "si seria el ultimo admin del sistema."
    ),
)
async def quitar_admin(
    usuario_id: int,
    db: AsyncSession = Depends(get_db),
    admin: UsuarioApp = Depends(get_current_user),
) -> RespuestaUsuarioApp:
    """Revoca is_admin del usuario indicado (solo root).

    Args:
        usuario_id: ID del admin a degradar.
        db: Sesion de base de datos asincrona.
        admin: Administrador autenticado; debe tener es_root=True.

    Returns:
        RespuestaUsuarioApp con is_admin=False.
    """
    servicio = UsuarioAppAdminService(db)
    return await servicio.degradar_admin(caller=admin, usuario_id=usuario_id)


# ---------------------------------------------------------------------------
# Gestion de tarifas LLM ($/Mtoken por proveedor)
# ---------------------------------------------------------------------------


@router.get(
    "/tarifas",
    response_model=RespuestaListaTarifas,
    summary="Listar las tarifas LLM con costes relativos",
    description=(
        "Devuelve las cuatro tarifas (Claude, GPT-4o, Gemini, Grok) con el "
        "precio actual de entrada y salida (USD/Mtoken) y los dos costes "
        "relativos calculados frente al minimo de cada columna. "
        "Requiere autenticacion JWT de administrador."
    ),
)
async def listar_tarifas(
    db: AsyncSession = Depends(get_db),
    _admin: UsuarioApp = Depends(get_current_user),
) -> RespuestaListaTarifas:
    """Devuelve las 4 tarifas con sus costes relativos.

    Args:
        db: Sesion de base de datos asincrona.
        _admin: Administrador autenticado (guard).

    Returns:
        RespuestaListaTarifas con las 4 filas y los baselines.
    """
    servicio = TarifaService(db)
    return await servicio.listar_con_relativos()


@router.put(
    "/tarifas/{proveedor}",
    response_model=RespuestaListaTarifas,
    summary="Actualizar la tarifa de un proveedor",
    description=(
        "Actualiza precio_entrada y precio_salida (USD/Mtoken) de un proveedor "
        "y refresca el cache en memoria que usan los clientes LLM. Las llamadas "
        "siguientes calcularan coste_usd con la nueva tarifa. Los costes ya "
        "persistidos en respuestas anteriores no se recalculan. "
        "Requiere autenticacion JWT de administrador."
    ),
)
async def actualizar_tarifa(
    proveedor: LLMProvider,
    peticion: PeticionActualizarTarifa,
    db: AsyncSession = Depends(get_db),
    admin: UsuarioApp = Depends(get_current_user),
) -> RespuestaListaTarifas:
    """Actualiza una tarifa, refresca cache y devuelve el listado actualizado.

    Devolver el listado entero (no solo la fila modificada) facilita al
    frontend refrescar la tabla sin disparar un segundo GET: con un solo
    intercambio HTTP la UI ya tiene los relativos recalculados.

    Args:
        proveedor: Identificador del proveedor a actualizar.
        peticion: Cuerpo con precio_entrada y precio_salida nuevos.
        db: Sesion de base de datos asincrona.
        admin: Administrador autenticado (guard + autor del cambio).

    Returns:
        RespuestaListaTarifas con las 4 tarifas y relativos recalculados.

    Raises:
        HTTPException 404 si el proveedor no existe en la tabla.
    """
    from fastapi import HTTPException

    servicio = TarifaService(db)
    actualizada = await servicio.actualizar_tarifa(
        proveedor=proveedor,
        precio_entrada=peticion.precio_entrada_usd_por_mtoken,
        precio_salida=peticion.precio_salida_usd_por_mtoken,
        actualizado_por=admin.nick,
        precio_entrada_cacheado=peticion.precio_entrada_cacheado_usd_por_mtoken,
        precio_imagen_generar=peticion.precio_imagen_generar_usd_por_imagen,
        precio_imagen_editar=peticion.precio_imagen_editar_usd_por_imagen,
    )
    if actualizada is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tarifa para proveedor '{proveedor.value}' no encontrada",
        )
    return await servicio.listar_con_relativos()


@router.get(
    "/tarifas/{proveedor}/historial",
    response_model=RespuestaHistorialTarifa,
    summary="Historial de versiones de la tarifa de un proveedor",
    description=(
        "Devuelve todas las versiones (vigente + historicas) de la tarifa "
        "del proveedor indicado, ordenadas por fecha descendente. Cada llamada "
        "LLM antigua conserva su FK a la version exacta con la que se cobro. "
        "Requiere autenticacion JWT de administrador."
    ),
)
async def historial_tarifa(
    proveedor: LLMProvider,
    db: AsyncSession = Depends(get_db),
    _admin: UsuarioApp = Depends(get_current_user),
) -> RespuestaHistorialTarifa:
    """Devuelve todas las versiones de tarifa de un proveedor.

    Args:
        proveedor: Identificador del proveedor.
        db: Sesion de base de datos asincrona.
        _admin: Administrador autenticado (guard).

    Returns:
        RespuestaHistorialTarifa con las versiones ordenadas (recientes primero).
    """
    servicio = TarifaService(db)
    return await servicio.listar_historial(proveedor)
