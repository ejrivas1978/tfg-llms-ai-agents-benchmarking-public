"""Anade texto_entrada y texto_entrada_autogenerado a benchmark_evaluaciones

Revision ID: q6f7a8b9c0d1
Revises: p5e6f7a8b9c0
Create Date: 2026-05-15

Contexto:
    Para la categoria de resumen se ha incorporado un boton que genera
    automaticamente un texto de ~300 palabras mediante llamada a un LLM.
    Cuando el usuario usa este texto generado como entrada del resumen,
    queremos persistirlo para poder recuperarlo desde el historial de
    evaluaciones, de forma analoga a como se muestra la version inglesa
    en el sub-experimento bilingue ES/EN.

    texto_entrada almacena el texto original que el usuario introdujo
    (pegado manualmente o generado por LLM) sin el prefijo instruccion
    del prompt de resumen.
    texto_entrada_autogenerado es el flag que indica si ese texto fue
    generado automaticamente por el sistema o introducido por el usuario.
    Solo se muestra el acordeon de texto original en el modal del historial
    cuando texto_entrada_autogenerado=True.

Esquema:
    benchmark_evaluaciones.texto_entrada              TEXT NULL
    benchmark_evaluaciones.texto_entrada_autogenerado BOOLEAN NOT NULL DEFAULT FALSE
"""

import sqlalchemy as sa
from alembic import op

revision = 'q6f7a8b9c0d1'
down_revision = 'p5e6f7a8b9c0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'benchmark_evaluaciones',
        sa.Column('texto_entrada', sa.Text(), nullable=True),
    )
    op.add_column(
        'benchmark_evaluaciones',
        sa.Column(
            'texto_entrada_autogenerado',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column('benchmark_evaluaciones', 'texto_entrada_autogenerado')
    op.drop_column('benchmark_evaluaciones', 'texto_entrada')
