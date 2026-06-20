"""rating_min_cero_censura

Descripcion:
    Amplia el rango permitido del campo rating en user_evaluations de
    [1, 5] a [0, 5]. El valor 0 representa el caso en que el modelo LLM
    rechaza el prompt por politica de seguridad (content_policy_violation,
    filtros de seguridad, content moderation). Estos modelos quedan fuera
    del ranking de preferencia y se marcan automaticamente con 0 estrellas
    en el frontend.

    La restriccion CHECK 'ck_rating_range' se elimina y se vuelve a crear
    con la nueva condicion rating >= 0.

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-05-04

"""

from alembic import op

revision = 'd2e3f4a5b6c7'
down_revision = 'c1d2e3f4a5b6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint('ck_rating_range', 'user_evaluations', type_='check')
    op.create_check_constraint(
        'ck_rating_range',
        'user_evaluations',
        'rating >= 0 AND rating <= 5',
    )


def downgrade() -> None:
    op.drop_constraint('ck_rating_range', 'user_evaluations', type_='check')
    op.create_check_constraint(
        'ck_rating_range',
        'user_evaluations',
        'rating >= 1 AND rating <= 5',
    )
