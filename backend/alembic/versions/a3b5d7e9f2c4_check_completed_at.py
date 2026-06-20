"""check_completed_at: constraint de integridad temporal en benchmark_sessions

Revision ID: a3b5d7e9f2c4
Revises: f2a4c6e8b1d3
Create Date: 2026-05-03

Motivacion:
    La columna completed_at debe ser posterior o igual a created_at.
    Sin esta restriccion un bug de reloj o un update manual podria
    guardar una sesion con completed_at < created_at, produciendo
    latencias negativas en el dashboard de estadisticas.

    El constraint es nullable-safe: solo se valida cuando completed_at
    no es NULL (sesion finalizada). Las sesiones en_curso o pendientes
    tienen completed_at = NULL y pasan la restriccion sin problemas.

Cambios:
    benchmark_sessions: ADD CONSTRAINT ck_completed_after_created
        CHECK (completed_at IS NULL OR completed_at >= created_at)
"""

import sqlalchemy as sa
from alembic import op


revision = "a3b5d7e9f2c4"
down_revision = "f2a4c6e8b1d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_completed_after_created",
        "benchmark_sessions",
        sa.text("completed_at IS NULL OR completed_at >= created_at"),
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_completed_after_created",
        "benchmark_sessions",
        type_="check",
    )
