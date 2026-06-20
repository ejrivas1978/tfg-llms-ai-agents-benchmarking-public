"""Anade valor solicitud_borrado al enum sessionstatus

Revision ID: r7a8b9c0d1e2
Revises: q6f7a8b9c0d1
Create Date: 2026-05-16

Contexto:
    Los usuarios pueden solicitar al administrador el borrado de sus evaluaciones.
    Para reflejar este estado en el ciclo de vida de la evaluacion se anade el
    valor 'solicitud_borrado' al enum sessionstatus de PostgreSQL.
    El administrador ve las solicitudes pendientes en el panel de control y
    puede borrarlas desde la tabla de comparativas con el flujo ya existente.

Esquema:
    sessionstatus (PostgreSQL enum) -> anade valor 'solicitud_borrado'
"""

from alembic import op

revision = 'r7a8b9c0d1e2'
down_revision = 'q6f7a8b9c0d1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE sessionstatus ADD VALUE IF NOT EXISTS 'solicitud_borrado'")


def downgrade() -> None:
    # PostgreSQL no permite eliminar valores de un enum que ya esta en uso.
    # Para revertir: convertir primero las filas con solicitud_borrado a completada,
    # luego recrear el tipo sin ese valor y actualizar la columna. Se omite aqui
    # porque la operacion es destructiva y requiere intervencion manual.
    pass
