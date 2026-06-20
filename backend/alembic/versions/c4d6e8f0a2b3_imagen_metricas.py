"""imagen_metricas

Descripcion:
    Anade las columnas imagen_size_bytes, imagen_ancho e imagen_alto a
    llm_responses para almacenar metricas de imagen generativa.

Revision ID: c4d6e8f0a2b3
Revises: a3b5c7d9e1f2
Create Date: 2026-05-03

"""

from alembic import op
import sqlalchemy as sa

revision = 'c4d6e8f0a2b3'
down_revision = 'a3b5c7d9e1f2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('llm_responses', sa.Column('imagen_size_bytes', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('llm_responses', sa.Column('imagen_ancho',      sa.Integer(), nullable=False, server_default='0'))
    op.add_column('llm_responses', sa.Column('imagen_alto',       sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('llm_responses', 'imagen_alto')
    op.drop_column('llm_responses', 'imagen_ancho')
    op.drop_column('llm_responses', 'imagen_size_bytes')
