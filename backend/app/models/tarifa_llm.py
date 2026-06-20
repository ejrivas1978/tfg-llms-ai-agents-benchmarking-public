"""
Modulo: tarifa_llm
Ruta:   backend/app/models/tarifa_llm.py

Descripcion:
    Modelo ORM SQLAlchemy para la tabla tarifas_llm. Almacena los precios
    por millon de tokens (entrada y salida) de cada proveedor LLM.

    Hasta esta tabla, los precios estaban hardcoded en metricas.py.
    Ahora se cargan a un cache en memoria al arrancar la aplicacion
    (via lifespan en main.py) y se refrescan tras cada PUT del panel admin.

Dependencias:
    - app.core.database.Base
    - app.models.enums.LLMProvider

Sprint: Sprint 4
"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import LLMProvider


class TarifaLLM(Base):
    """Modelo ORM para la tarifa USD por millon de tokens de un proveedor LLM.

    Versionado: cada actualizacion genera una nueva fila en lugar de un
    UPDATE in-place. La fila antigua queda con vigente=False (historico)
    y la nueva con vigente=True. La invariante 'una unica vigente por
    proveedor' la garantiza el indice unico parcial
    ux_tarifas_llm_proveedor_vigente (PostgreSQL: UNIQUE WHERE vigente=TRUE).

    Esto permite trazar a posteriori que tarifa se aplico a cada llamada
    LLM concreta: llm_responses.tarifa_id apunta a la fila exacta usada
    para calcular su coste_usd. Cambiar la tarifa NO afecta a las
    respuestas ya persistidas.

    Atributos:
        id: Clave primaria autoincremental. Cada version tiene su propio id.
        proveedor: LLMProvider enum. NO es unique: puede haber multiples
            filas para el mismo proveedor (las versiones historicas).
        precio_entrada_usd_por_mtoken: Tarifa de tokens de prompt en USD/Mtok.
        precio_salida_usd_por_mtoken: Tarifa de tokens generados en USD/Mtok.
        vigente: True si esta es la version activa para su proveedor.
            Solo una fila puede tener vigente=True por proveedor.
        actualizado_en: Cuando se creo la version (UTC).
        actualizado_por: Nick del admin que la creo. 'seed' para las del
            despliegue inicial.
    """

    __tablename__ = "tarifas_llm"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    proveedor: Mapped[LLMProvider] = mapped_column(
        Enum(LLMProvider, name="llmprovider", create_type=False),
        nullable=False,
    )
    precio_entrada_usd_por_mtoken: Mapped[Decimal] = mapped_column(
        Numeric(12, 8),
        nullable=False,
    )
    precio_salida_usd_por_mtoken: Mapped[Decimal] = mapped_column(
        Numeric(12, 8),
        nullable=False,
    )
    # Precio editable opcional para tokens servidos desde caché (cache hit).
    # NULL = el proveedor no aplica descuento o no se ha configurado: en ese
    # caso calcular_coste_usd() cobra todo al precio_entrada estandar aunque
    # la API devuelva cached_tokens > 0. Valores tipicos (mayo 2026): Claude
    # 10% del base, OpenAI/Grok 50%, Gemini 25%.
    precio_entrada_cacheado_usd_por_mtoken: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 8),
        nullable=True,
    )
    # Precio fijo por imagen GENERADA desde texto (txt2img).
    # NULL = el proveedor no soporta imagen (Claude por ADR-011) o no se ha
    # configurado. Modelos: DALL-E 3 (OpenAI), Imagen 4 (Gemini),
    # grok-imagine-image (Grok).
    precio_imagen_generar_usd_por_imagen: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 8),
        nullable=True,
    )
    # Precio fijo por imagen EDITADA con imagen de referencia (img2img).
    # NULL = el proveedor no soporta edicion nativa. Modelos: gpt-image-1
    # (OpenAI), gemini-2.5-flash-image (Gemini), grok-imagine-image-quality
    # (Grok). Generalmente distinto del precio de generacion.
    precio_imagen_editar_usd_por_imagen: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 8),
        nullable=True,
    )
    vigente: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    actualizado_por: Mapped[str | None] = mapped_column(String(64), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<TarifaLLM id={self.id} proveedor={self.proveedor!r} "
            f"entrada={self.precio_entrada_usd_por_mtoken} "
            f"salida={self.precio_salida_usd_por_mtoken} "
            f"vigente={self.vigente}>"
        )
