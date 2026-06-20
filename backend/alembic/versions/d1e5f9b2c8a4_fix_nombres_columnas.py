"""fix_nombres_columnas: renombra columnas BD para alinear con modelos ORM

Revision ID: d1e5f9b2c8a4
Revises: b3c5e7a9f1d2
Create Date: 2026-05-03

Problema:
    La migracion inicial creo tres columnas con nombres en ingles/diferente
    que no coinciden con los atributos del modelo ORM en Python.
    SQLAlchemy usa el nombre del atributo como nombre de columna si no se
    especifica la columna explicitamente, por lo que cualquier INSERT o
    SELECT contra estas columnas falla con un error de columna no existente.

Cambios:
    llm_responses:
        had_error       -> tuvo_error      (booleano de error de la API)
    user_evaluations:
        preference_rank -> rango_preferencia  (orden de preferencia 1-4)
        notes           -> notas              (comentario libre del evaluador)
"""

from alembic import op


revision = "d1e5f9b2c8a4"
down_revision = "b3c5e7a9f1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # llm_responses: had_error -> tuvo_error
    op.alter_column("llm_responses", "had_error", new_column_name="tuvo_error")

    # user_evaluations: preference_rank -> rango_preferencia
    op.alter_column("user_evaluations", "preference_rank", new_column_name="rango_preferencia")

    # user_evaluations: notes -> notas
    op.alter_column("user_evaluations", "notes", new_column_name="notas")


def downgrade() -> None:
    op.alter_column("user_evaluations", "notas", new_column_name="notes")
    op.alter_column("user_evaluations", "rango_preferencia", new_column_name="preference_rank")
    op.alter_column("llm_responses", "tuvo_error", new_column_name="had_error")
