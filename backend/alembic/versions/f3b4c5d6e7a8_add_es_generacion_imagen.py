"""Anade columna es_generacion_imagen a benchmark_evaluaciones

Revision ID: f3b4c5d6e7a8
Revises: e1f2a3b4c5d6
Create Date: 2026-05-04

Contexto:
    La columna es_generacion_imagen distingue las subcategorias de imagen que generan
    una imagen (generar, logotipo, modificar — 3 LLMs, salida imagen URL/miniatura)
    de las que producen texto (describir imagen — 4 LLMs, salida texto).

    Sin este flag, todas las subcategorias de categoria='imagen' comparten el mismo
    filtro en las consultas de dashboard, lo que hace que Claude aparezca en las
    metricas de generacion de imagen (donde no participa) porque si participa en
    'describir imagen'.

    La migracion de datos infiere es_generacion_imagen=True para los registros
    existentes que tengan al menos una LLMResponse con imagen_miniatura IS NOT NULL,
    lo que identifica de forma fiable las evaluaciones de generar/logotipo/modificar
    (las unicas que producen miniaturas). Las evaluaciones de describir imagen y todas
    las de texto quedan con el valor por defecto False.
"""

from alembic import op
import sqlalchemy as sa


revision = "f3b4c5d6e7a8"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "benchmark_evaluaciones",
        sa.Column(
            "es_generacion_imagen",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
    )

    # Retroactivamente marca como generacion de imagen los registros existentes
    # que tienen al menos una respuesta con miniatura (solo generar/logotipo/modificar
    # producen miniaturas; los rechazos por politica quedan con tuvo_error=True pero
    # imagen_miniatura=NULL, asi que no se marcan incorrectamente).
    op.execute(
        """
        UPDATE benchmark_evaluaciones be
        SET es_generacion_imagen = TRUE
        WHERE be.category = 'imagen'
          AND EXISTS (
              SELECT 1 FROM llm_responses lr
              WHERE lr.evaluacion_id = be.id
                AND lr.imagen_miniatura IS NOT NULL
          )
        """
    )


def downgrade() -> None:
    op.drop_column("benchmark_evaluaciones", "es_generacion_imagen")
