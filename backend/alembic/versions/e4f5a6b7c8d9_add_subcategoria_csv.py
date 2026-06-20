"""Anade columna subcategoria_csv a benchmark_evaluaciones

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-05-09

Contexto:
    Persiste la subcategoria seleccionada en la UI para que el CSV de
    administrador (GET /api/v1/admin/evaluaciones/exportar-csv) pueda
    incluirla. Es el nombre human-readable del prompt elegido (ej.
    "2. Efecto Doppler"), del idioma de traduccion ("Ingles"), de la
    opcion de resumen ("Resumen en 20 palabras") o de imagen ("generar",
    "logotipo", etc.). Para texto libre siempre vale "Texto Libre".

    No se usa en dashboard, runner ni metricas: campo puramente
    informativo para el analisis estadistico del estudio.

    Nullable porque las evaluaciones existentes (anteriores a esta
    migracion) no tendran valor; el alumno acepta dejarlas vacias en el
    CSV en lugar de hacer un backfill, ya que estamos en periodo de pruebas.

    Limite 150 chars: las etiquetas mas largas en SubcatPanel rondan los
    50 chars; 150 deja holgura para futuros prompts y para el prefijo
    numerico ("10. ...") sin truncar.
"""

import sqlalchemy as sa
from alembic import op

revision = 'e4f5a6b7c8d9'
down_revision = 'd3e4f5a6b7c8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'benchmark_evaluaciones',
        sa.Column('subcategoria_csv', sa.String(length=150), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('benchmark_evaluaciones', 'subcategoria_csv')
