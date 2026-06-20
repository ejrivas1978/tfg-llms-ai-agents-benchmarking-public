"""
Module: env
Path:   backend/alembic/env.py

Description:
    Alembic migration environment. Configured for async SQLAlchemy (asyncpg).
    Reads the database URL from app.core.config so credentials never live
    in alembic.ini. Imports all models via app.models so autogenerate
    can detect schema changes automatically.

Sprint: Sprint 1
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.core.config import get_settings
from app.core.database import Base
import app.models  # noqa: F401 — registers all models with Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    """Return the async database URL from application settings."""
    return get_settings().database_url


def run_migrations_offline() -> None:
    """Run migrations without a live database connection (generates SQL script).

    Useful for reviewing changes before applying them, or for environments
    where direct DB access is not available during the migration step.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """Execute migrations using an existing synchronous connection.

    Args:
        connection: Synchronous DBAPI connection provided by the async engine.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations inside it.

    Uses NullPool so no connections are held open after migrations complete,
    which is important for short-lived migration scripts.
    """
    settings = get_settings()
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = settings.database_url

    connectable = async_engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migrations (normal mode)."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
