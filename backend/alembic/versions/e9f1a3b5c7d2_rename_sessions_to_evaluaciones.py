"""rename_sessions_to_evaluaciones

Descripcion:
    Renombra la tabla benchmark_sessions a benchmark_evaluaciones y
    la columna llm_responses.session_id a llm_responses.evaluacion_id,
    actualizando la FK constraint y el indice asociado.

Revision ID: e9f1a3b5c7d2
Revises: c4d6e8f0a2b3
Create Date: 2026-05-03

"""

from alembic import op

revision = 'e9f1a3b5c7d2'
down_revision = 'c4d6e8f0a2b3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Eliminar el indice sobre session_id antes de renombrar la columna
    op.drop_index('ix_llm_responses_session_id', table_name='llm_responses')

    # 2. Eliminar la FK constraint existente
    op.drop_constraint(
        'llm_responses_session_id_fkey',
        table_name='llm_responses',
        type_='foreignkey',
    )

    # 3. Renombrar la columna session_id -> evaluacion_id
    op.alter_column(
        'llm_responses',
        'session_id',
        new_column_name='evaluacion_id',
    )

    # 4. Renombrar la tabla principal
    op.rename_table('benchmark_sessions', 'benchmark_evaluaciones')

    # 5. Recrear la FK apuntando a la tabla con el nuevo nombre
    op.create_foreign_key(
        'llm_responses_evaluacion_id_fkey',
        source_table='llm_responses',
        referent_table='benchmark_evaluaciones',
        local_cols=['evaluacion_id'],
        remote_cols=['id'],
        ondelete='CASCADE',
    )

    # 6. Recrear el indice sobre evaluacion_id
    op.create_index(
        'ix_llm_responses_evaluacion_id',
        'llm_responses',
        ['evaluacion_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_llm_responses_evaluacion_id', table_name='llm_responses')
    op.drop_constraint(
        'llm_responses_evaluacion_id_fkey',
        table_name='llm_responses',
        type_='foreignkey',
    )
    op.alter_column(
        'llm_responses',
        'evaluacion_id',
        new_column_name='session_id',
    )
    op.rename_table('benchmark_evaluaciones', 'benchmark_sessions')
    op.create_foreign_key(
        'llm_responses_session_id_fkey',
        source_table='llm_responses',
        referent_table='benchmark_sessions',
        local_cols=['session_id'],
        remote_cols=['id'],
        ondelete='CASCADE',
    )
    op.create_index(
        'ix_llm_responses_session_id',
        'llm_responses',
        ['session_id'],
    )
