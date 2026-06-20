"""Elimina la columna bloques_codigo de llm_responses

Revision ID: b2c3d4e5f6a7
Revises: 8515120b6649
Create Date: 2026-05-06

Contexto:
    La metrica bloques_codigo (numero de bloques ``` en la respuesta) se ha eliminado
    del stack completo porque solo tiene sentido en la categoria 'codigo' y genera
    sesgo en todas las demas categorias (donde siempre vale 0). La decision de quitarla
    se tomo al analizar los resultados del TFG: un modelo con muchas respuestas de
    texto obtendrfa siempre 0 frente a otro probado en codigo, lo que distorsionaria
    las medias del dashboard.
"""

import sqlalchemy as sa
from alembic import op


revision = "b2c3d4e5f6a7"
down_revision = "8515120b6649"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("llm_responses", "bloques_codigo")


def downgrade() -> None:
    op.add_column(
        "llm_responses",
        sa.Column("bloques_codigo", sa.Integer(), nullable=False, server_default="0"),
    )
