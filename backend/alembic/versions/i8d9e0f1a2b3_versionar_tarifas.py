"""Versiona tarifas_llm con flag 'vigente' y enlaza llm_responses.tarifa_id

Revision ID: i8d9e0f1a2b3
Revises: h7c8d9e0f1a2
Create Date: 2026-05-13

Contexto:
    Cada actualizacion de tarifa pasa a generar una NUEVA fila en lugar
    de hacer UPDATE in-place. La fila antigua queda con vigente=False
    para preservar el historico, y la nueva con vigente=True.

    Las respuestas LLM (llm_responses) ganan una FK opcional 'tarifa_id'
    que apunta a la tarifa exacta usada para calcular su coste_usd. Asi
    cada respuesta queda asociada al precio que se cobro en ese momento
    aunque despues se actualice la tarifa.

    Cambios:
      1. tarifas_llm:
         - Drop unique constraint en proveedor.
         - Add columna vigente BOOLEAN NOT NULL DEFAULT TRUE.
         - Partial unique index: solo puede haber una fila con vigente=TRUE
           por proveedor. La BD garantiza la invariante 'una tarifa vigente
           por proveedor' sin necesidad de logica de aplicacion.
      2. llm_responses:
         - Add columna tarifa_id INTEGER NULL FK -> tarifas_llm.id ON DELETE RESTRICT.
         - Backfill: respuestas existentes apuntan al seed inicial de su
           proveedor (autor='seed'). Es una aproximacion: la respuesta antigua
           no tenia trazabilidad real de tarifa, pero asociarla al seed evita
           huecos en el CSV y deja constancia explicita del autor 'seed'.
      3. CHECK opcional en llm_responses: no se anade porque la columna debe
         ser nullable para soportar tests/seeds sin tarifa.
"""

import sqlalchemy as sa
from alembic import op

revision = 'i8d9e0f1a2b3'
down_revision = 'h7c8d9e0f1a2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Versionado de tarifas_llm ───────────────────────────────────────
    # Drop unique en proveedor (permitimos varias filas por proveedor).
    op.drop_constraint('tarifas_llm_proveedor_key', 'tarifas_llm', type_='unique')

    # Anadir columna vigente con default TRUE (todas las filas existentes
    # son vigentes en este momento, son las del seed).
    op.add_column(
        'tarifas_llm',
        sa.Column('vigente', sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    # Indice unico parcial: una unica fila vigente por proveedor.
    # PostgreSQL soporta esto nativamente con WHERE, otros motores no.
    op.create_index(
        'ux_tarifas_llm_proveedor_vigente',
        'tarifas_llm',
        ['proveedor'],
        unique=True,
        postgresql_where=sa.text('vigente = TRUE'),
    )

    # Indice no unico para acelerar las consultas del historial por proveedor.
    op.create_index(
        'ix_tarifas_llm_proveedor_actualizado_en',
        'tarifas_llm',
        ['proveedor', 'actualizado_en'],
    )

    # ── 2. tarifa_id en llm_responses ─────────────────────────────────────
    op.add_column(
        'llm_responses',
        sa.Column('tarifa_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'fk_llm_responses_tarifa_id',
        'llm_responses',
        'tarifas_llm',
        ['tarifa_id'],
        ['id'],
        ondelete='RESTRICT',
    )
    op.create_index(
        'ix_llm_responses_tarifa_id',
        'llm_responses',
        ['tarifa_id'],
    )

    # ── 3. Backfill: respuestas antiguas -> seed inicial de su proveedor ──
    # En este momento solo existen las 4 filas seed (vigente=TRUE, autor='seed').
    # El subquery hace match por proveedor.
    op.execute(
        """
        UPDATE llm_responses
        SET tarifa_id = (
            SELECT id FROM tarifas_llm
            WHERE tarifas_llm.proveedor = llm_responses.provider
              AND tarifas_llm.actualizado_por = 'seed'
            LIMIT 1
        )
        WHERE tarifa_id IS NULL
        """
    )


def downgrade() -> None:
    # 1. llm_responses: quitar FK + columna + indice
    op.drop_index('ix_llm_responses_tarifa_id', table_name='llm_responses')
    op.drop_constraint('fk_llm_responses_tarifa_id', 'llm_responses', type_='foreignkey')
    op.drop_column('llm_responses', 'tarifa_id')

    # 2. tarifas_llm: quitar indices + columna vigente + restaurar unique
    op.drop_index('ix_tarifas_llm_proveedor_actualizado_en', table_name='tarifas_llm')
    op.drop_index('ux_tarifas_llm_proveedor_vigente', table_name='tarifas_llm')
    op.drop_column('tarifas_llm', 'vigente')
    op.create_unique_constraint('tarifas_llm_proveedor_key', 'tarifas_llm', ['proveedor'])
