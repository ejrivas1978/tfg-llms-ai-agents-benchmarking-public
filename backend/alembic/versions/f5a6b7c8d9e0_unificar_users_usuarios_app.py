"""Unifica las tablas users y usuarios_app en una sola

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-05-10

Contexto:
    Por requerimiento del responsable del TFG (reunion 10/05/2026) se
    unifica la tabla legacy 'users' (administradores) con 'usuarios_app'
    (usuarios web). Las dos coexistian por contexto historico (Sprint 1
    solo habia admin, Sprint 4 aparecieron usuarios web) pero divergian
    en hash, login, estados y cuota sin justificacion estructural.

    Esquema final: una unica tabla 'usuarios_app' con un flag is_admin
    que controla si el registro tiene privilegios de administracion.
    El email pasa a ser obligatorio solo para administradores; los
    usuarios regulares pueden tenerlo o no (opcional, contacto).

    Hash de contrasena: bcrypt para todos los registros (admin y
    usuarios web ya compartian la misma funcion centralizada en
    app.core.security; el comentario inicial del modelo UsuarioApp
    mencionaba Argon2 pero era una declaracion aspiracional, no la
    implementacion real). El password_hash del admin se copia tal cual.

    Esta migracion supersede ADR-024 -> ADR-027.

Pasos del upgrade:
    1. ADD COLUMN email VARCHAR(255) UNIQUE NULL en usuarios_app.
    2. ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE.
    3. INSERT del admin existente en users -> usuarios_app
       (nick = users.username, conservando password_hash bcrypt).
    4. ADD CHECK ck_admin_requires_email: si is_admin=true, email NOT NULL.
    5. DROP TABLE users.

Downgrade:
    Recrea users con el esquema original, copia los registros con
    is_admin=true desde usuarios_app, elimina las columnas anadidas
    y la check constraint. La perdida de columnas durante el downgrade
    no destruye datos del admin: se preservan en la tabla recreada.
"""

import sqlalchemy as sa
from alembic import op

revision = 'f5a6b7c8d9e0'
down_revision = 'e4f5a6b7c8d9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Anadir columnas a usuarios_app
    op.add_column(
        'usuarios_app',
        sa.Column('email', sa.String(length=255), nullable=True),
    )
    op.create_unique_constraint('uq_usuarios_app_email', 'usuarios_app', ['email'])
    op.add_column(
        'usuarios_app',
        sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='false'),
    )

    # 2) Copiar el admin (o admins) desde la tabla legacy users.
    # estado='habilitado' por defecto; cuota=0 (irrelevante para admin pero la
    # columna es NOT NULL); consultas_usadas=0; intentos_fallidos=0;
    # guia_vista=false (volvera a verla si cambia a usuario regular).
    # Conservamos created_at/updated_at originales para preservar la auditoria.
    op.execute("""
        INSERT INTO usuarios_app (
            nick, password_hash, email, is_admin, estado,
            cuota_asignada, consultas_usadas, intentos_fallidos,
            guia_vista, created_at, updated_at
        )
        SELECT
            username, password_hash, email, true, 'habilitado',
            0, 0, 0,
            false, created_at, updated_at
        FROM users
    """)

    # 3) Check constraint: si is_admin, email NOT NULL.
    op.create_check_constraint(
        'ck_admin_requires_email',
        'usuarios_app',
        '(NOT is_admin) OR (email IS NOT NULL)',
    )

    # 4) Drop tabla legacy.
    op.drop_table('users')


def downgrade() -> None:
    # Recrear tabla users con el esquema original.
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username'),
    )

    # Copiar admins de vuelta. nick -> username, email -> email.
    op.execute("""
        INSERT INTO users (
            email, username, password_hash, is_active, is_admin,
            created_at, updated_at
        )
        SELECT
            email, nick, password_hash, true, true,
            created_at, updated_at
        FROM usuarios_app
        WHERE is_admin = true
    """)

    # Quitar admins de usuarios_app (solo los que volvimos a users).
    op.execute("DELETE FROM usuarios_app WHERE is_admin = true")

    op.drop_constraint('ck_admin_requires_email', 'usuarios_app', type_='check')
    op.drop_column('usuarios_app', 'is_admin')
    op.drop_constraint('uq_usuarios_app_email', 'usuarios_app', type_='unique')
    op.drop_column('usuarios_app', 'email')
