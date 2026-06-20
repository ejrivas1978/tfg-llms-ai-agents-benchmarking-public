"""Anade columna guia_vista a la tabla usuarios_app

Revision ID: d3e4f5a6b7c8
Revises: c3d4e5f6a7b8
Create Date: 2026-05-06

Contexto:
    Guarda en base de datos si el usuario ya ha visto la guia de bienvenida.
    El administrador puede resetear el flag desde el panel de usuarios para
    que la guia vuelva a aparecer al usuario en su proximo login.
    Valor por defecto False (no vista) para todos los usuarios existentes.
"""

import sqlalchemy as sa
from alembic import op

revision = 'd3e4f5a6b7c8'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'usuarios_app',
        sa.Column('guia_vista', sa.Boolean(), nullable=False, server_default='false'),
    )


def downgrade() -> None:
    op.drop_column('usuarios_app', 'guia_vista')
