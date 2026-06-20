"""
Modulo: llm_response
Ruta:   backend/app/models/llm_response.py

Descripcion:
    Modelo ORM SQLAlchemy para la tabla llm_responses.
    Cada registro almacena la salida bruta y las DIEZ metricas calculadas
    de una unica llamada a un proveedor LLM dentro de una sesion de benchmark.
    Los errores tambien se persisten (tuvo_error=True) para que los fallos
    parciales no aborten la sesion completa.

    DECISION(ADR-016): Se almacenan las 10 metricas separadas en dos grupos:
        - Desde la API: input_tokens, output_tokens, tuvo_error
        - Calculadas en backend: latency_ms, tokens_por_segundo, ratio_sal_ent,
          cost_usd, coste_por_100_palabras
        - Del texto de respuesta: palabras, diversidad_lexica, parrafos

    Caso especial imagen generativa: output_tokens, palabras, diversidad_lexica,
    parrafos son 0. El coste se calcula por imagen (precio fijo).

Dependencias:
    - app.core.database.Base
    - app.models.enums

Sprint: Sprint 2
"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import LLMProvider


class LLMResponse(Base):
    """Modelo ORM para la tabla llm_responses con las 11 metricas del benchmark.

    He decidido almacenar todas las metricas en la misma tabla en lugar de tener
    una tabla separada de metricas, porque la relacion es siempre 1:1
    (una llamada LLM tiene exactamente un conjunto de metricas) y JOIN adicional
    no aportaria valor. Unirlo todo en una tabla simplifica las queries del dashboard.

    Para los costes (cost_usd, coste_por_100_palabras) uso Numeric(12, 8) en lugar
    de Float para evitar errores de precision en coma flotante al acumular costes.
    Un Float de 64 bits acumula errores de redondeo que se vuelven visibles al
    sumar muchas llamadas baratas (Gemini cuesta ~0.000001 USD por llamada corta).

    El campo ratio_sal_ent (tokens salida / tokens entrada) esta en el DTO individual
    RespuestaLLMDTO, pero no aparece en las consultas agregadas de medias_por_proveedor().
    Lo he mantenido porque es una metrica util para analizar el comportamiento de
    verbosidad de cada modelo en respuestas individuales del historial.
    """

    __tablename__ = "llm_responses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    evaluacion_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("benchmark_evaluaciones.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        Enum(LLMProvider, name="llmprovider"),
        nullable=False,
    )
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Metricas de la API ---
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Tokens de entrada servidos desde cache (cache hit). Si > 0 y la tarifa
    # tiene precio_entrada_cacheado configurado, se aplica el descuento al
    # calcular cost_usd. Tipicamente 0 en este benchmark (prompts one-shot
    # paralelos sin reuso de contexto), pero capturarlo nos permite detectar
    # si en algun escenario futuro el proveedor lo activa por su cuenta.
    input_tokens_cached: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # Idioma del prompt enviado al LLM ('es' o 'en'). En las categorias
    # bilingues (razonamiento, creativa, concretas) cada evaluacion lanza
    # 2 rondas: una con prompt ES y otra con prompt EN traducido. Cada
    # respuesta se etiqueta con su idioma para permitir filtros y agregados
    # en el dashboard sin JOINs adicionales.
    idioma_prompt: Mapped[str] = mapped_column(
        String(2), nullable=False, default='es', server_default='es',
    )
    tuvo_error: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Metricas calculadas (tokens + tiempo) ---
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_por_segundo: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # ratio_sal_ent: tokens de salida / tokens de entrada.
    # Aparece en RespuestaLLMDTO (respuesta individual) pero no en medias_por_proveedor()
    # (dashboard). La mantuve en BB.DD. para el historial de evaluaciones individuales.
    ratio_sal_ent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # Uso Numeric para cost_usd y coste_por_100_palabras para evitar errores de
    # precision de coma flotante al acumular costes de muchas llamadas baratas.
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False, default=0)
    coste_por_100_palabras: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False, default=0)

    # --- Metricas calculadas del texto ---
    palabras: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    diversidad_lexica: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    parrafos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # --- Miniatura de imagen (JPEG base64, ~10-20 KB; solo para respuestas de imagen) ---
    # La miniatura se genera en el cliente LLM y se guarda aqui para que el frontend
    # pueda mostrar una previsualizacion rapida sin depender de URLs temporales que
    # pueden caducar (DALL-E 3 y grok-imagine-image devuelven URLs que expiran en ~1h).
    imagen_miniatura: Mapped[str | None] = mapped_column(Text, nullable=True)

    # FK a la tarifa exacta usada para calcular cost_usd en el momento de la llamada.
    # Nullable porque algunas filas legacy podrian no tener tarifa asociada y porque
    # los tests/seeds podrian crear LLMResponses sin pasar por el flujo normal.
    # ON DELETE RESTRICT (definido en la migracion): no se puede borrar una tarifa
    # si tiene respuestas asociadas, para no romper la trazabilidad historica.
    tarifa_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("tarifas_llm.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    benchmark: Mapped["BenchmarkEvaluacion"] = relationship(back_populates="respuestas")  # noqa: F821
    evaluacion: Mapped["UserEvaluation | None"] = relationship(  # noqa: F821
        back_populates="respuesta",
        uselist=False,
        cascade="all, delete-orphan",
    )
    # Lazy join al objeto TarifaLLM. Se usa para mostrar precio_entrada y
    # precio_salida en el CSV admin sin tener que hacer un SELECT adicional.
    tarifa: Mapped["TarifaLLM | None"] = relationship(  # noqa: F821
        foreign_keys=[tarifa_id],
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<LLMResponse id={self.id} provider={self.provider!r} error={self.tuvo_error}>"
