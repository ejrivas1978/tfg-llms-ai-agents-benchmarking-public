"""Renombra el valor 'factual' a 'concretas' en el enum testcategory

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-06

Contexto:
    La categoria 'factual' se renombra a 'concretas' para usar terminos
    en castellano coherentes con el resto del enum y eliminar el termino
    ingles de la base de datos, el codigo y la interfaz.
"""

from alembic import op

revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE testcategory RENAME VALUE 'factual' TO 'concretas'")


def downgrade() -> None:
    op.execute("ALTER TYPE testcategory RENAME VALUE 'concretas' TO 'factual'")
