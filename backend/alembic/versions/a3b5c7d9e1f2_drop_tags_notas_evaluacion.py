"""drop_tags_notas_evaluacion: elimina columnas tags y notas de user_evaluations

Revision ID: a3b5c7d9e1f2
Revises: f2a4c6e8b1d3
Create Date: 2026-05-03

Motivacion:
    Los campos tags (ARRAY) y notas (TEXT) nunca se mostraron en los
    dashboards ni se usaron en ninguna consulta de agregacion. Se
    eliminan del modelo, esquemas, repositorio y servicio para mantener
    la base de datos coherente con el codigo.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'a3b5c7d9e1f2'
down_revision = 'b1c3e5f7a9d2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('user_evaluations', 'tags')
    op.drop_column('user_evaluations', 'notas')


def downgrade() -> None:
    op.add_column(
        'user_evaluations',
        sa.Column('notas', sa.Text(), nullable=True),
    )
    op.add_column(
        'user_evaluations',
        sa.Column(
            'tags',
            postgresql.ARRAY(sa.String(length=50)),
            nullable=False,
            server_default='{}',
        ),
    )
