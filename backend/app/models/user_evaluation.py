"""
Modulo: user_evaluation
Ruta:   backend/app/models/user_evaluation.py

Descripcion:
    Modelo ORM SQLAlchemy para la tabla user_evaluations.
    Almacena la evaluacion humana de una unica respuesta LLM: una valoracion
    de 1 a 5 estrellas y un rango de preferencia relativo a las otras
    respuestas de la misma sesion. La relacion con llm_responses es 1:1
    (una evaluacion por respuesta por sesion).

    El evaluador se identifica con una cadena de texto nickname (sin cuenta de usuario).

Dependencias:
    - app.core.database.Base

Sprint: Sprint 1
"""

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UserEvaluation(Base):
    """Modelo ORM para la tabla user_evaluations.

    He elegido una relacion 1:1 con llm_responses (response_id tiene unique=True)
    porque cada respuesta de un LLM en una evaluacion solo puede ser valorada una
    vez por el usuario que abrio esa sesion. Si quisiemos permitir multiples
    valoraciones por respuesta (por ejemplo, multiples usuarios), habria que
    eliminar el unique constraint y anadir un indice compuesto (response_id, nickname).

    La restriccion CHECK en rating (0-5) la puse en la base de datos ademas de en
    el esquema Pydantic para tener una segunda linea de defensa: aunque el backend
    valide el rango, prefiero que la BB.DD. tambien lo garantice en caso de que
    en el futuro alguien inserte datos directamente via SQL.

    Atributos:
        id: Clave primaria autoincrementada.
        response_id: FK a la LLMResponse evaluada. Unica (relacion 1:1).
        nickname: Nombre del usuario anonimo que envio la evaluacion.
        rating: Valoracion en estrellas de 0 a 5.
            0 indica rechazo por politica de seguridad (el usuario selecciona
            explicitamente que la respuesta fue rechazada por el LLM).
        rango_preferencia: Posicion ordinal dentro de la sesion (1 = mejor).
            Nullable porque el rango se puede rellenar despues de la valoracion
            inicial, o puede quedar sin rellenar si el usuario no quiso ordenar.
        created_at: Marca de tiempo UTC del envio de la evaluacion.
        updated_at: Marca de tiempo UTC de la ultima edicion.
            NOTA: Este campo se actualiza via onupdate de SQLAlchemy cuando
            el usuario edita su valoracion, pero no esta expuesto en la API
            (RespuestaEvaluacion DTO no lo incluye). Lo mantuve como auditoria.
        respuesta: Relacion con la LLMResponse evaluada.
    """

    __tablename__ = "user_evaluations"
    __table_args__ = (
        # He puesto esta restriccion en la BB.DD. ademas de en Pydantic como segunda
        # linea de defensa. Rating=0 es un valor valido que indica rechazo por
        # politica de seguridad del LLM (el usuario marco que la respuesta fue rechazada).
        CheckConstraint("rating >= 0 AND rating <= 5", name="ck_rating_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    response_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("llm_responses.id", ondelete="CASCADE"),
        unique=True,  # 1:1 con llm_responses: una evaluacion por respuesta
        nullable=False,
        index=True,
    )
    nickname: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    rango_preferencia: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    respuesta: Mapped["LLMResponse"] = relationship(back_populates="evaluacion")  # noqa: F821

    def __repr__(self) -> str:
        return f"<UserEvaluation id={self.id} rating={self.rating} response_id={self.response_id}>"
