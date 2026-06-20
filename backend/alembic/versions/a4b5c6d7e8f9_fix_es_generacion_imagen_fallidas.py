"""Corrige es_generacion_imagen=False en evaluaciones de imagen fallidas (rechazos)

Revision ID: a4b5c6d7e8f9
Revises: f3b4c5d6e7a8
Create Date: 2026-05-04

Contexto:
    La migracion anterior (f3b4c5d6e7a8) marcó es_generacion_imagen=TRUE solo para
    evaluaciones con imagen_miniatura IS NOT NULL, lo que identificaba correctamente
    las generaciones exitosas.

    Sin embargo, las evaluaciones rechazadas por politica de contenido tienen
    tuvo_error=True e imagen_miniatura=NULL en TODAS sus respuestas (no se llego
    a generar ningun archivo). Por tanto, el UPDATE anterior las dejo con
    es_generacion_imagen=FALSE cuando deberia ser TRUE.

    Las evaluaciones de 'describir imagen' (es_generacion_imagen debe permanecer FALSE)
    usan completar() para analisis de vision y NUNCA resultan en status='fallida' por
    politica de contenido. Por tanto, cualquier evaluacion con category='imagen' y
    status='fallida' es, sin excepcion, un rechazo de generacion de imagen.
"""

from alembic import op


revision = "a4b5c6d7e8f9"
down_revision = "f3b4c5d6e7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE benchmark_evaluaciones
        SET es_generacion_imagen = TRUE
        WHERE category = 'imagen'
          AND status = 'fallida'
          AND es_generacion_imagen = FALSE
        """
    )


def downgrade() -> None:
    # No se puede revertir sin saber cuales eran FALSE antes; se deja como no-op.
    pass
