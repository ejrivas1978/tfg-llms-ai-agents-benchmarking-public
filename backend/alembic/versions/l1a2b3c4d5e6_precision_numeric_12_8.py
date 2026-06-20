"""Aumenta precision de precios y costes a NUMERIC(12,8)

Revision ID: l1a2b3c4d5e6
Revises: k0f1a2b3c4d5
Create Date: 2026-05-13

Contexto:
    Las columnas de precio (tarifas_llm.precio_*) estaban a NUMERIC(10, 4)
    y las de coste (llm_responses.cost_usd, llm_responses.coste_por_100_palabras)
    a NUMERIC(10, 6). Hay tres motivos para subir a NUMERIC(12, 8):

    1. Coherencia input/output: el calculo en Python redondea a 8 decimales
       (calcular_coste_usd hace round(coste, 8)) pero la BD truncaba al
       almacenar a 4-6 decimales, perdiendo precision al final.

    2. Llamadas LLM pequenas: para una llamada de pocos tokens cacheados a
       Gemini (precio cacheado $0.03/Mtok), el coste real es del orden de
       $0.000003 a $0.00003. Con NUMERIC(10, 6) el menor valor representable
       es $0.000001, y muchas llamadas pequenas sufren error de redondeo
       que se acumula en las medias agregadas del dashboard.

    3. Futuro-proofing: precios futuros mas baratos (sub-centesima de Mtok)
       o pricing por capas refinado (por tier de calidad de imagen) podrian
       requerir 5+ decimales nativos sin perder precision.

    Tipo elegido: NUMERIC(12, 8) = 4 digitos antes del punto + 8 despues.
    Maximo: 9999.99999999. Suficiente para cualquier precio razonable
    (el mas alto hoy es Claude Opus 4.7 Fast Mode output $150/MTok).

Operaciones:
    1. ALTER COLUMN sobre 4 columnas de tarifas_llm.
    2. ALTER COLUMN sobre 2 columnas de llm_responses.

    PostgreSQL ALTER COLUMN TYPE NUMERIC(12,8) es **no destructivo**:
    los valores existentes se conservan exactos (los $3.0000 quedan
    como $3.00000000, sin cambio numerico).
"""

import sqlalchemy as sa
from alembic import op

revision = 'l1a2b3c4d5e6'
down_revision = 'k0f1a2b3c4d5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── tarifas_llm: precios a NUMERIC(12, 8) ─────────────────────────────
    for col in (
        'precio_entrada_usd_por_mtoken',
        'precio_salida_usd_por_mtoken',
        'precio_entrada_cacheado_usd_por_mtoken',
        'precio_imagen_usd_por_imagen',
    ):
        op.alter_column(
            'tarifas_llm',
            col,
            type_=sa.Numeric(12, 8),
            existing_type=sa.Numeric(10, 4),
            existing_nullable=True if col != 'precio_entrada_usd_por_mtoken'
                              and col != 'precio_salida_usd_por_mtoken' else False,
        )

    # ── llm_responses: costes a NUMERIC(12, 8) ────────────────────────────
    op.alter_column(
        'llm_responses',
        'cost_usd',
        type_=sa.Numeric(12, 8),
        existing_type=sa.Numeric(10, 6),
        existing_nullable=False,
    )
    op.alter_column(
        'llm_responses',
        'coste_por_100_palabras',
        type_=sa.Numeric(12, 8),
        existing_type=sa.Numeric(10, 6),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Bajar precision puede truncar datos. Solo seguro si no hay valores
    # con mas de 4-6 decimales. Para el rollback usar a tu propio riesgo.
    op.alter_column(
        'llm_responses',
        'coste_por_100_palabras',
        type_=sa.Numeric(10, 6),
        existing_type=sa.Numeric(12, 8),
        existing_nullable=False,
    )
    op.alter_column(
        'llm_responses',
        'cost_usd',
        type_=sa.Numeric(10, 6),
        existing_type=sa.Numeric(12, 8),
        existing_nullable=False,
    )
    for col in (
        'precio_imagen_usd_por_imagen',
        'precio_entrada_cacheado_usd_por_mtoken',
        'precio_salida_usd_por_mtoken',
        'precio_entrada_usd_por_mtoken',
    ):
        op.alter_column(
            'tarifas_llm',
            col,
            type_=sa.Numeric(10, 4),
            existing_type=sa.Numeric(12, 8),
        )
