"""Revierte el minimo de rating a 1 tras eliminar el mecanismo de censura por rating=0

Revision ID: e1f2a3b4c5d6
Revises: d2e3f4a5b6c7
Create Date: 2026-05-04

Contexto:
    La migracion d2e3f4a5b6c7 bajo el minimo de rating a 0 para registrar
    rechazos de politica de contenido con rating=0 en UserEvaluation.
    El nuevo diseno (ADR-023 rev.2) marca la BenchmarkEvaluacion con
    status='fallida' directamente en el runner, sin crear registros
    UserEvaluation con rating=0. El constraint vuelve a ser 1-5.
"""

from alembic import op


revision = "e1f2a3b4c5d6"
down_revision = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Sesiones completadas que tienen algun rating=0 pasan a fallida
    #    (el mecanismo anterior no cambiaba su status, el nuevo si lo hace)
    op.execute("""
        UPDATE benchmark_evaluaciones
        SET status = 'fallida'
        WHERE status = 'completada'
          AND id IN (
              SELECT DISTINCT lr.evaluacion_id
              FROM llm_responses lr
              JOIN user_evaluations ue ON ue.response_id = lr.id
              WHERE ue.rating = 0
          )
    """)

    # 2. Eliminar los registros UserEvaluation con rating=0 (ya no se usan)
    op.execute("DELETE FROM user_evaluations WHERE rating = 0")

    # 3. Restaurar el constraint a 1-5
    op.drop_constraint("ck_rating_range", "user_evaluations", type_="check")
    op.create_check_constraint(
        "ck_rating_range", "user_evaluations", "rating >= 1 AND rating <= 5"
    )


def downgrade() -> None:
    op.drop_constraint("ck_rating_range", "user_evaluations", type_="check")
    op.create_check_constraint(
        "ck_rating_range", "user_evaluations", "rating >= 0 AND rating <= 5"
    )
