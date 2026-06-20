"""Anade input_tokens_cached a llm_responses y precio_entrada_cacheado a tarifas_llm

Revision ID: j9e0f1a2b3c4
Revises: i8d9e0f1a2b3
Create Date: 2026-05-13

Contexto:
    Para que el modelo de coste cubra el descuento por prompt caching (cache
    hits) que aplican Anthropic, OpenAI, Google y xAI, anadimos dos campos:

    1. llm_responses.input_tokens_cached (INT NOT NULL DEFAULT 0):
       Numero de tokens de prompt servidos desde caché en esta llamada.
       Capturado de:
         - Claude SDK:    usage.cache_read_input_tokens
         - OpenAI/Grok:   usage.prompt_tokens_details.cached_tokens
         - Gemini compat: usage.prompt_tokens_details.cached_tokens (si lo expone)
       Si la API no devuelve el campo, queda 0 y se cobra todo al precio base.

    2. tarifas_llm.precio_entrada_cacheado_usd_por_mtoken (NUMERIC(10,4) NULL):
       Precio editable por el admin para los tokens servidos desde caché.
       NULL = "este proveedor no aplica descuento (o no se ha configurado)".
       Cuando es NULL o cuando input_tokens_cached=0, calcular_coste_usd()
       se cae al cálculo estándar (todo al precio de entrada normal).

    Formula final:
      coste_in = (tokens_entrada - cached) * precio_in
               + cached * precio_cacheado   (solo si precio_cacheado IS NOT NULL)
      coste = (coste_in + tokens_salida * precio_out) / 1_000_000

    Seed inicial (tarifas estandar de mayo 2026):
      claude  cacheado=0.30   (10% de 3.00)
      openai  cacheado=1.25   (50% de 2.50)
      gemini  cacheado=0.01875 (25% de 0.075)
      grok    cacheado=0.625  (50% de 1.25, estimado)

    Los precios cacheados se aplican a TODAS las versiones vigentes seed.
    Las versiones historicas creadas antes de esta migracion quedan con
    precio_cacheado=NULL: si una respuesta antigua tuvo cache hit, su
    coste se mantiene como se calculo en su momento (sin descuento).
"""

from decimal import Decimal

import sqlalchemy as sa
from alembic import op

revision = 'j9e0f1a2b3c4'
down_revision = 'i8d9e0f1a2b3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. llm_responses: tokens cacheados ─────────────────────────────────
    op.add_column(
        'llm_responses',
        sa.Column(
            'input_tokens_cached',
            sa.Integer(),
            nullable=False,
            server_default='0',
        ),
    )

    # ── 2. tarifas_llm: precio de entrada cacheado (opcional) ──────────────
    op.add_column(
        'tarifas_llm',
        sa.Column(
            'precio_entrada_cacheado_usd_por_mtoken',
            sa.Numeric(10, 4),
            nullable=True,
        ),
    )

    # ── 3. Backfill: precios cacheados para las filas seed vigentes ────────
    # Las tarifas seed vigentes (autor='seed', vigente=TRUE) reciben las
    # tarifas de cache documentadas en cada proveedor en mayo 2026.
    # Las versiones historicas (vigente=FALSE) se dejan en NULL: si una
    # respuesta antigua tuvo cache, no podemos retroactivamente "abaratarla".
    backfill = [
        ("claude", Decimal("0.3000")),
        ("openai", Decimal("1.2500")),
        ("gemini", Decimal("0.0188")),
        ("grok",   Decimal("0.6250")),
    ]
    for proveedor, precio in backfill:
        # Cast explicito a llmprovider: PostgreSQL no compara enum con varchar
        # sin conversion manual. Embebemos el proveedor como literal en el
        # SQL para que sea facil de castear; el precio sigue parametrizado
        # porque es un Decimal y bindparams maneja bien NUMERIC.
        op.execute(
            sa.text(
                "UPDATE tarifas_llm SET precio_entrada_cacheado_usd_por_mtoken = :precio "
                f"WHERE proveedor = '{proveedor}'::llmprovider "
                "AND vigente = TRUE AND actualizado_por = 'seed'"
            ).bindparams(precio=precio)
        )


def downgrade() -> None:
    op.drop_column('tarifas_llm', 'precio_entrada_cacheado_usd_por_mtoken')
    op.drop_column('llm_responses', 'input_tokens_cached')
