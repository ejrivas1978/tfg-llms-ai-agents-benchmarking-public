"""Renombrar autor 'seed' a 'root' en tarifas_llm.actualizado_por

Revision ID: m2b3c4d5e6f7
Revises: l1a2b3c4d5e6
Create Date: 2026-05-13

Contexto:
    Las filas iniciales (vigentes y historicas) de tarifas_llm tenian
    actualizado_por='seed' como marcador de "fila sembrada por Alembic
    durante el despliegue, no editada por un admin". Por coherencia con
    el resto del proyecto, donde el admin canonico se llama 'root'
    (es_root=True en usuarios_app, ADR-027 § rol root), se renombra el
    marcador a 'root'.

    Solo afecta a la cadena de texto en actualizado_por. No toca ningun
    otro campo. Las versiones audit (actualizado_por='audit-2026-05-13')
    se quedan tal cual; solo se renombra el marcador 'seed'.
"""

from alembic import op

revision = 'm2b3c4d5e6f7'
down_revision = 'l1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE tarifas_llm SET actualizado_por = 'root' "
        "WHERE actualizado_por = 'seed'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE tarifas_llm SET actualizado_por = 'seed' "
        "WHERE actualizado_por = 'root'"
    )
