"""add_imagen_miniatura

Descripcion:
    Anade la columna imagen_miniatura (TEXT, nullable) a la tabla llm_responses.

    Motivo: se almacena una miniatura JPEG de 200x200 px en base64 (~10-20 KB)
    para cada respuesta de imagen generativa, de forma que el historial de
    comparativas pueda mostrar una vista previa persistente de las imagenes
    independientemente de si la URL original ha caducado (OpenAI/Grok expiran
    en ~1 hora; Gemini devuelve data-URI ya almacenado en response_text pero
    su tamano completo no es eficiente para miniaturas en lista).

    La columna es NULL para todas las respuestas de texto (es_imagen=False).
    Solo se rellena cuando el cliente LLM genera una imagen con exito.

Revision ID: c1d2e3f4a5b6
Revises: f3a5b7c9d1e2
Create Date: 2026-05-03

"""

import sqlalchemy as sa
from alembic import op

revision = 'c1d2e3f4a5b6'
down_revision = 'f3a5b7c9d1e2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'llm_responses',
        sa.Column('imagen_miniatura', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('llm_responses', 'imagen_miniatura')
