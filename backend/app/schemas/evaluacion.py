"""
Modulo: schemas/evaluacion
Ruta:   backend/app/schemas/evaluacion.py

Descripcion:
    DTOs Pydantic para los endpoints de evaluacion de respuestas LLM.

Sprint: Sprint 2
"""

from datetime import datetime

from pydantic import BaseModel, Field


class PeticionEvaluacion(BaseModel):
    """Cuerpo de la peticion POST /api/v1/evaluaciones.

    Atributos:
        response_id: ID de la LLMResponse que se evalua.
        nickname: Alias del evaluador (debe coincidir con el de la sesion).
        rating: Puntuacion del 1 al 5.
        rango_preferencia: Posicion ordinal en el ranking de respuestas (1 = mejor).
    """

    response_id: int
    nickname: str = Field(..., min_length=1, max_length=100)
    rating: int = Field(..., ge=0, le=5)  # 0 = rechazado por politica de seguridad
    # le=10 cubre hasta 10 proveedores; las respuestas con error reciben null
    rango_preferencia: int | None = Field(default=None, ge=1, le=10)


class RespuestaEvaluacion(BaseModel):
    """DTO de respuesta para POST /evaluaciones."""

    id: int
    response_id: int
    nickname: str
    rating: int
    rango_preferencia: int | None
    created_at: datetime

    model_config = {"from_attributes": True}
