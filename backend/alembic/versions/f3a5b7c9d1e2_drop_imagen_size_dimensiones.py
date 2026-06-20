"""drop_imagen_size_dimensiones

Descripcion:
    Elimina las columnas imagen_size_bytes, imagen_ancho e imagen_alto de
    la tabla llm_responses.

    Motivo: estas columnas no aportan informacion diferencial entre proveedores:
      - imagen_size_bytes es 0 para OpenAI y Grok (devuelven URL externa, no bytes).
      - imagen_ancho e imagen_alto son 1024 para todos los modelos (resolucion
        por defecto uniforme; no hay variacion observable entre proveedores).
    Las unicas metricas comparativas para imagen son latencia_ms y cost_usd.

Revision ID: f3a5b7c9d1e2
Revises: e9f1a3b5c7d2
Create Date: 2026-05-03

"""

import sqlalchemy as sa
from alembic import op

revision = 'f3a5b7c9d1e2'
down_revision = 'e9f1a3b5c7d2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('llm_responses', 'imagen_size_bytes')
    op.drop_column('llm_responses', 'imagen_ancho')
    op.drop_column('llm_responses', 'imagen_alto')


def downgrade() -> None:
    op.add_column('llm_responses', sa.Column('imagen_alto',       sa.Integer(), nullable=False, server_default='0'))
    op.add_column('llm_responses', sa.Column('imagen_ancho',      sa.Integer(), nullable=False, server_default='0'))
    op.add_column('llm_responses', sa.Column('imagen_size_bytes', sa.Integer(), nullable=False, server_default='0'))
