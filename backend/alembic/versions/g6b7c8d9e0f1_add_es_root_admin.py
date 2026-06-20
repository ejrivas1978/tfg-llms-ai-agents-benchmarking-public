"""Anade columna es_root a usuarios_app: solo el admin seeded puede gestionar roles

Revision ID: g6b7c8d9e0f1
Revises: f5a6b7c8d9e0
Create Date: 2026-05-10

Contexto:
    Tras la unificacion ADR-027, cualquier admin (incluso un usuario web
    promovido) podria a su vez promover/degradar a otros, lo que diluye
    la idea de control centralizado del estudio. Por requisito del
    responsable del TFG, se introduce un segundo flag 'es_root' que
    distingue al admin original (creado por seed en el despliegue) del
    resto de admins promovidos:

      - es_root=true  -> admin root: tiene todos los privilegios
                          administrativos + puede promover y degradar
                          a otros usuarios (cambia el flag is_admin de
                          terceros). Solo se establece en el seed.
      - es_root=false -> admin promovido: tiene todos los privilegios
                          administrativos EXCEPTO promover/degradar.

    Migracion:
      1. ADD COLUMN es_root BOOLEAN NOT NULL DEFAULT FALSE.
      2. UPDATE para marcar es_root=true al admin con nick='admin' (el
         seeded en despliegues anteriores). En despliegues nuevos el
         seed_admin.py se encarga de poner el flag al insertar.

    Tras esta migracion, el admin original sigue funcionando igual; los
    admins promovidos a partir de este momento conservan is_admin=true
    pero con es_root=false, perdiendo solo el acceso a promover/quitar
    admin.
"""

import sqlalchemy as sa
from alembic import op

revision = 'g6b7c8d9e0f1'
down_revision = 'f5a6b7c8d9e0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'usuarios_app',
        sa.Column('es_root', sa.Boolean(), nullable=False, server_default='false'),
    )
    # Marcar el admin seeded actual (nick='admin') como root, si existe.
    # En despliegues vacios este UPDATE no afecta a ninguna fila.
    op.execute(
        "UPDATE usuarios_app SET es_root = TRUE "
        "WHERE is_admin = TRUE AND nick = 'admin'"
    )


def downgrade() -> None:
    op.drop_column('usuarios_app', 'es_root')
