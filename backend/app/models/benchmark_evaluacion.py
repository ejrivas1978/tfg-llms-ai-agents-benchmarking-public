"""
Modulo: benchmark_evaluacion
Ruta:   backend/app/models/benchmark_evaluacion.py

Descripcion:
    Modelo ORM SQLAlchemy para la tabla benchmark_evaluaciones.
    Una evaluacion representa un prompt enviado a todos los proveedores LLM seleccionados.
    Contiene de 1 a N registros LLMResponse, uno por proveedor invocado.

    Los usuarios son anonimos: las evaluaciones se asocian a una cadena de texto nickname,
    no a una cuenta de usuario registrada. Solo la cuenta de administrador usa JWT.

Dependencias:
    - app.core.database.Base
    - app.models.enums

Sprint: Sprint 1
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import SessionStatus, TestCategory


class BenchmarkEvaluacion(Base):
    """Modelo ORM para la tabla benchmark_evaluaciones.

    Representa una evaluacion completa: un prompt enviado a todos los proveedores
    LLM activos. En la capa de dominio y en la API publica se usa el termino
    'evaluacion' (n_evaluaciones, evaluaciones_por_semana...). El nombre de la tabla
    y la clase ORM usan 'evaluacion' como nombre canonico.

    Atributos:
        id: Clave primaria autoincrementada.
        nickname: Nombre elegido por el usuario anonimo. Sin FK a users.
        prompt: Texto original enviado a todos los proveedores LLM. Se almacena tal cual.
        category: Categoria del prompt usada para filtrar en el dashboard.
        es_generacion_imagen: True solo para subcategorias generar/logotipo/modificar (3 LLMs,
            salida imagen). False para describir imagen y todas las categorias de texto.
            Discriminador preciso que evita incluir a Claude en metricas de imagen.
        status: Estado del ciclo de vida de la evaluacion.
        created_at: Marca de tiempo UTC de creacion.
        completed_at: Marca de tiempo UTC de finalizacion de todas las llamadas LLM (nullable).
        respuestas: Todas las respuestas LLM recopiladas para esta evaluacion.
    """

    __tablename__ = "benchmark_evaluaciones"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nickname: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(
        Enum(TestCategory, name="testcategory"),
        nullable=False,
    )
    es_generacion_imagen: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    status: Mapped[str] = mapped_column(
        Enum(SessionStatus, name="sessionstatus"),
        nullable=False,
        default=SessionStatus.pendiente,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    # Similitud media de Jaccard entre todos los pares de respuestas de texto.
    # Nulo hasta que la evaluacion se completa y hay al menos dos respuestas validas.
    # DECISION(ADR-016): calculada en benchmark_service al guardar la evaluacion.
    similitud_jaccard_media: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Texto de entrada original antes de aplicar el prefijo de instruccion del prompt.
    # Solo se rellena en la categoria resumen cuando el usuario usa el boton de
    # generacion automatica. Permite mostrar el texto original en el historial.
    texto_entrada: Mapped[str | None] = mapped_column(Text, nullable=True)
    # True cuando texto_entrada fue generado automaticamente por un LLM.
    texto_entrada_autogenerado: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # Subcategoria seleccionada en la UI, persistida solo para el CSV de admin.
    # No participa en runner, metricas ni dashboards. Para prompts predefinidos
    # contiene "N. Etiqueta" (ej. "2. Efecto Doppler"); para traduccion el idioma;
    # para imagen la opcion ('generar', 'describir', 'logotipo', 'modificar');
    # para texto libre siempre "Texto Libre". Nullable para registros previos a
    # la migracion e4f5a6b7c8d9.
    subcategoria_csv: Mapped[str | None] = mapped_column(String(150), nullable=True)

    respuestas: Mapped[list["LLMResponse"]] = relationship(  # noqa: F821
        back_populates="benchmark",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<BenchmarkEvaluacion id={self.id} nickname={self.nickname!r} status={self.status!r}>"
