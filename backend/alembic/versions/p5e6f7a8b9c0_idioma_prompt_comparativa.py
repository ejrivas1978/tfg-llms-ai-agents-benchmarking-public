"""Anade idioma_prompt a llm_responses para comparativa ES vs EN

Revision ID: p5e6f7a8b9c0
Revises: o4d5e6f7a8b9
Create Date: 2026-05-14

Contexto:
    Para la comparativa de rendimiento de los LLMs entre castellano e ingles
    se introduce un sub-experimento controlado en TRES categorias de prompts:
    razonamiento, creativa y concretas.

    Cuando el usuario lanza un benchmark en una de estas categorias con un
    prompt predefinido, el backend hace DOS rondas paralelas:
      1) prompt en castellano -> 4 LLMResponse con idioma_prompt='es'
      2) prompt en ingles     -> 4 LLMResponse con idioma_prompt='en'

    El usuario solo valora las 4 respuestas en castellano (rating + ranking).
    Las 4 en ingles sirven exclusivamente para comparar metricas automaticas
    (latencia, tokens, coste, tps). Asi se obtiene un experimento controlado
    sin doblar el esfuerzo de evaluacion humana.

    La columna se aplica a TODAS las filas de llm_responses (incluyendo las
    que NO son de las 3 categorias bilingues) porque facilita filtros SQL
    universales sin necesidad de JOINs adicionales.

Esquema:
    llm_responses.idioma_prompt VARCHAR(2) NOT NULL DEFAULT 'es'
                                CHECK (idioma_prompt IN ('es', 'en'))

Backfill:
    Todos los registros existentes -> 'es' (solo se ha ejecutado en castellano
    antes de esta migracion).
"""

import sqlalchemy as sa
from alembic import op

revision = 'p5e6f7a8b9c0'
down_revision = 'o4d5e6f7a8b9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Anadir columna con default 'es' (DEFAULT cubre el backfill implicitamente).
    op.add_column(
        'llm_responses',
        sa.Column(
            'idioma_prompt',
            sa.String(length=2),
            nullable=False,
            server_default='es',
        ),
    )

    # 2. CHECK constraint para limitar valores a 'es'/'en'.
    op.create_check_constraint(
        'ck_llm_responses_idioma_prompt',
        'llm_responses',
        "idioma_prompt IN ('es', 'en')",
    )

    # 3. Indice por idioma para acelerar agregaciones del dashboard
    #    (medias por proveedor + idioma).
    op.create_index(
        'ix_llm_responses_idioma_prompt',
        'llm_responses',
        ['idioma_prompt'],
    )


def downgrade() -> None:
    op.drop_index('ix_llm_responses_idioma_prompt', table_name='llm_responses')
    op.drop_constraint('ck_llm_responses_idioma_prompt', 'llm_responses', type_='check')
    op.drop_column('llm_responses', 'idioma_prompt')
