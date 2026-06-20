"""indices_dashboard: indices en llm_responses para queries del dashboard

Revision ID: f2a4c6e8b1d3
Revises: d1e5f9b2c8a4
Create Date: 2026-05-03

Motivacion:
    Las queries del dashboard (StatsService.medias_por_proveedor y
    textos_por_sesion_y_proveedor) agrupan y filtran por provider
    y created_at. Sin indices en estas columnas PostgreSQL hace
    seq-scan sobre toda la tabla llm_responses, lo que degrada con
    el volumen acumulado del estudio TFG.

    Se anade tambien el indice sobre created_at para que los graficos
    de evolucion temporal (sesiones_por_semana) respondan en <50ms
    incluso con miles de registros.

Indices anadidos:
    llm_responses.provider     -> ix_llm_responses_provider
    llm_responses.created_at   -> ix_llm_responses_created_at
"""

from alembic import op


revision = "f2a4c6e8b1d3"
down_revision = "d1e5f9b2c8a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_llm_responses_provider",
        "llm_responses",
        ["provider"],
        unique=False,
    )
    op.create_index(
        "ix_llm_responses_created_at",
        "llm_responses",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_llm_responses_created_at", table_name="llm_responses")
    op.drop_index("ix_llm_responses_provider", table_name="llm_responses")
