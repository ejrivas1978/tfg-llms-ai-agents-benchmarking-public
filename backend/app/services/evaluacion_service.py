"""
Modulo: services.evaluacion_service
Ruta:   backend/app/services/evaluacion_service.py

Descripcion:
    Capa de servicio para la creacion y validacion de evaluaciones de usuario.
    Valida que la LLMResponse exista, que el nickname coincida con el de la
    evaluacion propietaria y que no exista ya una evaluacion previa para esa respuesta.

    DECISION(ADR-003): La logica de validacion de negocio reside en el Service,
    no en el router ni en el repositorio.

Dependencias:
    - app.repositories.llm_response_repository
    - app.repositories.user_evaluation_repository
    - app.schemas.evaluacion

Sprint: Sprint 2
"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.llm_response_repository import LLMResponseRepository
from app.repositories.user_evaluation_repository import UserEvaluationRepository
from app.schemas.evaluacion import RespuestaEvaluacion


class EvaluacionService:
    """Capa de servicio para la gestion de evaluaciones de respuestas LLM.

    Atributos:
        _db: Sesion asincrona SQLAlchemy inyectada via dependencia FastAPI.
        _eval_repo: Repositorio de UserEvaluation.
        _resp_repo: Repositorio de LLMResponse.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Inicializa el servicio con sus repositorios.

        Args:
            db: AsyncSession proporcionada por la dependencia get_db de FastAPI.
        """
        self._db = db
        self._eval_repo = UserEvaluationRepository(db)
        self._resp_repo = LLMResponseRepository(db)

    async def obtener_por_evaluacion(self, evaluacion_id: int) -> list[RespuestaEvaluacion]:
        """Devuelve todas las valoraciones persistidas para las respuestas de una evaluacion.

        Args:
            evaluacion_id: ID de la BenchmarkEvaluacion.

        Returns:
            Lista de RespuestaEvaluacion (vacia si aun no hay evaluaciones).
        """
        evaluaciones = await self._eval_repo.obtener_por_evaluacion_id(evaluacion_id)
        return [
            RespuestaEvaluacion(
                id=e.id,
                response_id=e.response_id,
                nickname=e.nickname,
                rating=e.rating,
                rango_preferencia=e.rango_preferencia,
                created_at=e.created_at,
            )
            for e in evaluaciones
        ]

    async def crear(
        self,
        response_id: int,
        nickname: str,
        rating: int,
        rango_preferencia: int | None,
    ) -> RespuestaEvaluacion:
        """Valida y persiste una evaluacion de respuesta LLM.

        Comprueba tres condiciones antes de crear la evaluacion:
          1. La LLMResponse debe existir en la base de datos.
          2. El nickname del evaluador debe coincidir con el de la evaluacion.
          3. No debe existir ya una evaluacion para esa respuesta (1:1).

        Args:
            response_id: ID de la LLMResponse a evaluar.
            nickname: Alias del evaluador (debe coincidir con el de la evaluacion).
            rating: Puntuacion del 1 al 5.
            rango_preferencia: Posicion ordinal de preferencia (1 = mejor).

        Returns:
            RespuestaEvaluacion con los datos persistidos.

        Raises:
            HTTPException 404: Si la LLMResponse no existe.
            HTTPException 403: Si el nickname no coincide con el de la evaluacion.
        """
        respuesta = await self._resp_repo.obtener_por_id(response_id)
        if respuesta is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Respuesta {response_id} no encontrada",
            )

        if respuesta.benchmark.nickname != nickname:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="El nickname no coincide con el de la evaluacion de benchmark",
            )

        existente = await self._eval_repo.obtener_por_response_id(response_id)
        if existente is not None:
            evaluacion = await self._eval_repo.actualizar(
                evaluacion=existente,
                rating=rating,
                rango_preferencia=rango_preferencia,
            )
        else:
            evaluacion = await self._eval_repo.crear(
                response_id=response_id,
                nickname=nickname,
                rating=rating,
                rango_preferencia=rango_preferencia,
            )

        return RespuestaEvaluacion(
            id=evaluacion.id,
            response_id=evaluacion.response_id,
            nickname=evaluacion.nickname,
            rating=evaluacion.rating,
            rango_preferencia=evaluacion.rango_preferencia,
            created_at=evaluacion.created_at,
        )
