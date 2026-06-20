"""indice_composite_evaluaciones: indice (nickname, response_id) en user_evaluations

Revision ID: b1c3e5f7a9d2
Revises: a3b5d7e9f2c4
Create Date: 2026-05-03

Motivacion:
    Las consultas "todas las evaluaciones de un usuario" filtran por nickname
    y luego hacen join con response_id. El indice individual en nickname ya
    existe (ix_user_evaluations_nickname), pero un indice composite permite
    que PostgreSQL resuelva ambas condiciones con un solo index scan sin
    necesidad de acceder a la tabla base (index-only scan).

    Util cuando el dashboard o el historial agreguen consultas del tipo:
        SELECT * FROM user_evaluations
        WHERE nickname = $1 AND response_id = ANY($2)

Indices anadidos:
    user_evaluations(nickname, response_id) -> ix_user_evaluations_nick_resp
"""

from alembic import op


revision = "b1c3e5f7a9d2"
down_revision = "a3b5d7e9f2c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_user_evaluations_nick_resp",
        "user_evaluations",
        ["nickname", "response_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_evaluations_nick_resp", table_name="user_evaluations")
