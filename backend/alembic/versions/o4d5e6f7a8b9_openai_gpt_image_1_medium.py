"""OpenAI: dall-e-3 retirado -> gpt-image-1 quality=medium, precio $0.07/img

Revision ID: o4d5e6f7a8b9
Revises: n3c4d5e6f7a8
Create Date: 2026-05-13

Contexto:
    OpenAI retiro `dall-e-3` del API el 13/05/2026 (HTTP 400 "model does
    not exist"). El proyecto migra a `gpt-image-1` (mismo modelo que ya
    usabamos para edicion img2img) con quality="medium" para generacion
    de imagen desde texto (txt2img).

    Quality "medium" elegida tras analisis de comparativas oficiales
    (Artificial Analysis, OpenAI dev community): produce imagenes de
    calidad comparable a Imagen 4 standard de Gemini en aesthetic y
    prompt-adherence. "low" ($0.02/img) daria imagenes visiblemente
    peores que las de Gemini/Grok y sesgaria el rating humano contra
    OpenAI sin reflejar su capacidad real.

    Cambio de precio en tarifas_llm:
      OpenAI precio_imagen_generar_usd_por_imagen: $0.04 -> $0.07
      OpenAI precio_imagen_editar_usd_por_imagen:  $0.04 -> $0.07
        (gpt-image-1 medium es el mismo modelo para ambos caminos)

    Versionado: nueva fila vigente con autor='audit-2026-05-13b'.
    La vigente anterior queda historica (vigente=FALSE).
"""

from datetime import datetime, timezone
from decimal import Decimal

import sqlalchemy as sa
from alembic import op

revision = 'o4d5e6f7a8b9'
down_revision = 'n3c4d5e6f7a8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Leer la fila vigente actual de OpenAI para copiar el resto de campos.
    # Como no podemos hacer SELECT con valores tipados desde Alembic facilmente,
    # marcamos la vigente como historica y creamos una nueva con valores
    # explicitos (los precios de texto y cacheado no cambian).
    op.execute(
        "UPDATE tarifas_llm SET vigente = FALSE "
        "WHERE proveedor = 'openai'::llmprovider AND vigente = TRUE"
    )
    ahora = datetime.now(timezone.utc)
    op.execute(
        sa.text(
            "INSERT INTO tarifas_llm "
            "(proveedor, precio_entrada_usd_por_mtoken, "
            " precio_salida_usd_por_mtoken, "
            " precio_entrada_cacheado_usd_por_mtoken, "
            " precio_imagen_generar_usd_por_imagen, "
            " precio_imagen_editar_usd_por_imagen, "
            " vigente, actualizado_en, actualizado_por) "
            "VALUES ('openai'::llmprovider, :e, :s, :c, :ig, :ie, TRUE, :t, :a)"
        ).bindparams(
            e=Decimal("2.5000"),
            s=Decimal("10.0000"),
            c=Decimal("1.2500"),
            ig=Decimal("0.0700"),  # gpt-image-1 medium quality
            ie=Decimal("0.0700"),  # gpt-image-1 medium quality (mismo modelo)
            t=ahora,
            a='audit-2026-05-13b',
        )
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM tarifas_llm "
        "WHERE proveedor = 'openai'::llmprovider AND actualizado_por = 'audit-2026-05-13b'"
    )
    # Restaurar la vigente anterior de OpenAI (la del primer audit, no la seed
    # original que ya estaba con vigente=FALSE antes).
    op.execute(
        "UPDATE tarifas_llm SET vigente = TRUE "
        "WHERE proveedor = 'openai'::llmprovider "
        "AND id = (SELECT MAX(id) FROM tarifas_llm "
        "          WHERE proveedor = 'openai'::llmprovider AND actualizado_por != 'audit-2026-05-13b')"
    )
