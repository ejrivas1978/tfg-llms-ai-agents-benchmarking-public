"""Edicion de imagen nativa para Gemini y Grok: separa precio generar/editar

Revision ID: n3c4d5e6f7a8
Revises: m2b3c4d5e6f7
Create Date: 2026-05-13

Contexto:
    Hasta esta migracion el cliente Gemini y el cliente Grok no usaban API
    nativa de edicion de imagen: cuando el flujo era "editar imagen subida"
    el codigo delegaba a generar_imagen() ignorando la imagen de referencia.
    Solo OpenAI (gpt-image-1) editaba realmente.

    Tras consultar las webs oficiales (13/05/2026 tarde):
      * Gemini tiene 'gemini-2.5-flash-image' (alias Nano Banana) para
        edicion nativa: 1290 tok output * $30/M = ~$0.039/img.
      * xAI tiene 'grok-imagine-image-quality' en el endpoint /v1/images/edits
        con $0.05/img.

    Para reflejar esto en la tabla de tarifas hay que separar el precio por
    imagen en dos columnas:
      * precio_imagen_generar_usd_por_imagen (modelo "txt2img")
      * precio_imagen_editar_usd_por_imagen  (modelo "img2img")

    El proveedor Claude no participa en imagen (ADR-011): ambos NULL.

Operaciones:
    1. RENAME COLUMN tarifas_llm.precio_imagen_usd_por_imagen
                   -> tarifas_llm.precio_imagen_generar_usd_por_imagen.
    2. ADD COLUMN tarifas_llm.precio_imagen_editar_usd_por_imagen
                  NUMERIC(12, 8) NULL.
    3. Backfill precio_imagen_editar_usd_por_imagen en TODAS las filas:
         claude -> NULL  (no soporta imagen)
         openai -> 0.04  (gpt-image-1 default, ~standard)
         gemini -> 0.039 (gemini-2.5-flash-image, 1024x1024)
         grok   -> 0.05  (grok-imagine-image-quality)
    4. Limpieza dev: borrar filas con autor='verify-script' (residuos de
       tests; estamos en fase de desarrollo antes del estudio final).
"""

from decimal import Decimal

import sqlalchemy as sa
from alembic import op

revision = 'n3c4d5e6f7a8'
down_revision = 'm2b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Rename de la columna existente ────────────────────────────────
    op.alter_column(
        'tarifas_llm',
        'precio_imagen_usd_por_imagen',
        new_column_name='precio_imagen_generar_usd_por_imagen',
        existing_type=sa.Numeric(12, 8),
        existing_nullable=True,
    )

    # ── 2. Anadir columna nueva para edicion ─────────────────────────────
    op.add_column(
        'tarifas_llm',
        sa.Column(
            'precio_imagen_editar_usd_por_imagen',
            sa.Numeric(12, 8),
            nullable=True,
        ),
    )

    # ── 3. Backfill precios de edicion en todas las filas existentes ────
    op.execute(
        sa.text(
            "UPDATE tarifas_llm SET precio_imagen_editar_usd_por_imagen = :p "
            "WHERE proveedor = 'openai'::llmprovider"
        ).bindparams(p=Decimal("0.04000000"))
    )
    op.execute(
        sa.text(
            "UPDATE tarifas_llm SET precio_imagen_editar_usd_por_imagen = :p "
            "WHERE proveedor = 'gemini'::llmprovider"
        ).bindparams(p=Decimal("0.03900000"))
    )
    op.execute(
        sa.text(
            "UPDATE tarifas_llm SET precio_imagen_editar_usd_por_imagen = :p "
            "WHERE proveedor = 'grok'::llmprovider"
        ).bindparams(p=Decimal("0.05000000"))
    )
    # Claude queda con NULL en ambas columnas (ADR-011, no soporta imagen).

    # ── 4. Limpieza de filas test del entorno dev ───────────────────────
    # Antes del estudio final no queremos arrastrar versiones espureas creadas
    # por scripts de verificacion (_verify_*.py). FK ON DELETE RESTRICT no
    # permitiria borrar filas referenciadas por llm_responses, pero esas
    # filas espureas tampoco tienen referencias (eran experimentos manuales
    # sin llamadas LLM colgando).
    op.execute(
        "DELETE FROM tarifas_llm "
        "WHERE actualizado_por = 'verify-script'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE tarifas_llm SET precio_imagen_editar_usd_por_imagen = NULL"
    )
    op.drop_column('tarifas_llm', 'precio_imagen_editar_usd_por_imagen')
    op.alter_column(
        'tarifas_llm',
        'precio_imagen_generar_usd_por_imagen',
        new_column_name='precio_imagen_usd_por_imagen',
        existing_type=sa.Numeric(12, 8),
        existing_nullable=True,
    )
