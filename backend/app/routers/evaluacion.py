"""
Modulo: routers.evaluacion
Ruta:   backend/app/routers/evaluacion.py

Descripcion:
    Capa HTTP para los endpoints de evaluacion de respuestas LLM.
    Los usuarios anonimos envian su valoracion identificandose con nickname.
    No requiere JWT: la autorizacion se basa en que el nickname coincida
    con el de la evaluacion propietaria de la respuesta evaluada.

    Endpoints:
        POST /api/v1/evaluaciones                      -> RespuestaEvaluacion  201
        GET  /api/v1/evaluaciones/evaluacion/{id}      -> list[RespuestaEvaluacion]  200

Dependencias:
    - fastapi
    - app.core.database
    - app.schemas.evaluacion
    - app.services.evaluacion_service

Sprint: Sprint 2 / Sprint 3
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.evaluacion import PeticionEvaluacion, RespuestaEvaluacion
from app.services.evaluacion_service import EvaluacionService

router = APIRouter(prefix="/evaluaciones", tags=["evaluacion"])


@router.get(
    "/evaluacion/{evaluacion_id}",
    response_model=list[RespuestaEvaluacion],
    summary="Obtener evaluaciones de una evaluacion de benchmark",
    description=(
        "Devuelve todas las evaluaciones ya guardadas para las respuestas LLM "
        "de una evaluacion concreta. Devuelve lista vacia si aun no hay evaluaciones. "
        "No requiere autenticacion JWT."
    ),
)
async def obtener_evaluaciones_por_evaluacion(
    evaluacion_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[RespuestaEvaluacion]:
    """Recupera las evaluaciones previas de una evaluacion para pre-rellenar el formulario.

    Args:
        evaluacion_id: ID de la BenchmarkEvaluacion.
        db: Sesion de base de datos asincrona.

    Returns:
        Lista de RespuestaEvaluacion ordenada por rango_preferencia.
    """
    servicio = EvaluacionService(db)
    return await servicio.obtener_por_evaluacion(evaluacion_id)


@router.post(
    "",
    response_model=RespuestaEvaluacion,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar la evaluacion de una respuesta LLM",
    description=(
        "Persiste la valoracion humana de una respuesta LLM concreta. "
        "El campo nickname debe coincidir con el de la evaluacion de benchmark. "
        "Cada respuesta solo admite una evaluacion (relacion 1:1). "
        "No requiere autenticacion JWT."
    ),
)
async def crear_evaluacion(
    peticion: PeticionEvaluacion,
    db: AsyncSession = Depends(get_db),
) -> RespuestaEvaluacion:
    """Registra la valoracion humana de una respuesta LLM.

    Args:
        peticion: Datos de la evaluacion (response_id, nickname, rating, tags...).
        db: Sesion de base de datos asincrona.

    Returns:
        RespuestaEvaluacion con los datos persistidos.
    """
    servicio = EvaluacionService(db)
    return await servicio.crear(
        response_id=peticion.response_id,
        nickname=peticion.nickname,
        rating=peticion.rating,
        rango_preferencia=peticion.rango_preferencia,
    )
