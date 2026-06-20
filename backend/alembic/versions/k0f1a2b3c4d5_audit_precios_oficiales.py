"""Auditoria 13/05/2026: precio_imagen en tarifas_llm + correccion Gemini

Revision ID: k0f1a2b3c4d5
Revises: j9e0f1a2b3c4
Create Date: 2026-05-13

Contexto (auditoria oficial 13/05/2026):
    Se contrastaron los precios sembrados originalmente contra las webs
    oficiales de cada proveedor (Anthropic, OpenAI, Google, xAI). Resultado:

      * Claude Sonnet 4.6   $3 / $15 / $0.30 cached   -> OK
      * GPT-4o              $2.50 / $10 / $1.25       -> OK
      * Gemini 2.5 Flash    $0.30 / $2.50 / $0.03     -> DESACTUALIZADO
                            (teniamos $0.075/$0.30/$0.0188, valores de un
                            tier anterior; el Standard tier vigente es 4-8x
                            mayor)
      * Grok 4.3 texto      $1.25 / $2.50             -> OK
      * Grok imagen         $0.02 / img               -> teniamos $0.04 (2x alto)
      * DALL-E 3            $0.04 / img (deprecada)   -> OK
      * Imagen 4 standard   $0.04 / img               -> OK

    Ademas, hasta ahora el precio por imagen vivia en un dict hardcoded en
    metricas.py (_PRECIO_IMAGEN_USD). Esta migracion lo mueve a una nueva
    columna 'precio_imagen_usd_por_imagen' en tarifas_llm, igual de editable
    por el admin que los demas precios.

Operaciones:
    1. ADD COLUMN tarifas_llm.precio_imagen_usd_por_imagen NUMERIC(10,4) NULL.
       NULL = el proveedor no soporta imagen (Claude por ADR-011).
    2. Backfill columna nueva en todas las filas existentes:
         claude  -> NULL
         openai  -> 0.0400 (DALL-E 3 standard 1024x1024)
         gemini  -> 0.0400 (Imagen 4 standard)
         grok    -> 0.0200 (grok-imagine-image, CORRECCION del 0.04 antiguo)
    3. Crear NUEVA vigente para Gemini con los precios audit:
         entrada=0.30, salida=2.50, cacheado=0.03, imagen=0.04
       Marca la vigente actual como historica (vigente=FALSE).
       Autor='audit-2026-05-13' para trazabilidad de la correccion.

    NOTA: estamos en periodo de desarrollo; las evaluaciones existentes en
    llm_responses van a borrarse en cuanto arranque el estudio final, asi
    que la divergencia entre tarifa_id antiguo y precios reales no impacta.
"""

from datetime import datetime, timezone
from decimal import Decimal

import sqlalchemy as sa
from alembic import op

revision = 'k0f1a2b3c4d5'
down_revision = 'j9e0f1a2b3c4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Anadir columna nueva ───────────────────────────────────────────
    op.add_column(
        'tarifas_llm',
        sa.Column(
            'precio_imagen_usd_por_imagen',
            sa.Numeric(10, 4),
            nullable=True,
        ),
    )

    # ── 2. Backfill por proveedor en todas las filas existentes ───────────
    # Claude queda NULL (no soporta imagen, ADR-011). Resto reciben sus
    # tarifas oficiales auditadas hoy.
    op.execute(
        sa.text(
            "UPDATE tarifas_llm SET precio_imagen_usd_por_imagen = :p "
            "WHERE proveedor = 'openai'::llmprovider"
        ).bindparams(p=Decimal("0.0400"))
    )
    op.execute(
        sa.text(
            "UPDATE tarifas_llm SET precio_imagen_usd_por_imagen = :p "
            "WHERE proveedor = 'gemini'::llmprovider"
        ).bindparams(p=Decimal("0.0400"))
    )
    op.execute(
        sa.text(
            "UPDATE tarifas_llm SET precio_imagen_usd_por_imagen = :p "
            "WHERE proveedor = 'grok'::llmprovider"
        ).bindparams(p=Decimal("0.0200"))
    )

    # ── 3. Correccion Gemini: nueva vigente con precios audit ─────────────
    # Marcar la vigente actual como historica.
    op.execute(
        "UPDATE tarifas_llm SET vigente = FALSE "
        "WHERE proveedor = 'gemini'::llmprovider AND vigente = TRUE"
    )
    # Insertar nueva vigente con precios oficiales (Standard tier mayo 2026).
    ahora = datetime.now(timezone.utc)
    op.execute(
        sa.text(
            "INSERT INTO tarifas_llm "
            "(proveedor, precio_entrada_usd_por_mtoken, "
            " precio_salida_usd_por_mtoken, "
            " precio_entrada_cacheado_usd_por_mtoken, "
            " precio_imagen_usd_por_imagen, "
            " vigente, actualizado_en, actualizado_por) "
            "VALUES ('gemini'::llmprovider, :e, :s, :c, :i, TRUE, :t, :a)"
        ).bindparams(
            e=Decimal("0.3000"),
            s=Decimal("2.5000"),
            c=Decimal("0.0300"),
            i=Decimal("0.0400"),
            t=ahora,
            a='audit-2026-05-13',
        )
    )


def downgrade() -> None:
    # Borrar la nueva fila audit y restaurar la vigente anterior de Gemini.
    op.execute(
        "DELETE FROM tarifas_llm "
        "WHERE proveedor = 'gemini'::llmprovider AND actualizado_por = 'audit-2026-05-13'"
    )
    op.execute(
        "UPDATE tarifas_llm SET vigente = TRUE "
        "WHERE proveedor = 'gemini'::llmprovider AND actualizado_por = 'seed'"
    )
    op.drop_column('tarifas_llm', 'precio_imagen_usd_por_imagen')
