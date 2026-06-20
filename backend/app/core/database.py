"""
Modulo: database
Ruta:   backend/app/core/database.py

Descripcion:
    Motor SQLAlchemy asincrono, fabrica de sesiones y Base declarativa.
    Toda la interaccion con la base de datos en este proyecto usa sesiones
    asincronas mediante asyncpg.

    Uso:
        - Importa Base en los ficheros de modelos para definir tablas ORM.
        - Usa get_db como dependencia FastAPI para obtener una sesion por peticion.

Dependencias:
    - sqlalchemy[asyncio]>=2.0
    - asyncpg>=0.30

Sprint: Sprint 1
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

_configuracion = get_settings()

motor = create_async_engine(
    _configuracion.database_url,
    echo=_configuracion.debug,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Alias en ingles para compatibilidad con imports existentes en conftest
engine = motor

SesionLocalAsincrona: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=motor,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# Alias en ingles para compatibilidad con seed_admin y otros scripts
AsyncSessionLocal = SesionLocalAsincrona


class Base(DeclarativeBase):
    """Base declarativa para todos los modelos ORM de SQLAlchemy.

    Todas las clases de modelo deben heredar de esta Base para que Alembic
    las detecte durante la generacion automatica de migraciones.
    """

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependencia FastAPI que proporciona una sesion de base de datos asincrona por peticion.

    Confirma la transaccion automaticamente cuando la peticion finaliza sin errores.
    Hace rollback ante cualquier excepcion no controlada para que las escrituras
    parciales nunca queden persistidas.

    Yields:
        AsyncSession vinculada al motor PostgreSQL configurado.

    Raises:
        Cualquier excepcion lanzada dentro del handler de ruta, tras el rollback.
    """
    async with SesionLocalAsincrona() as sesion:
        try:
            yield sesion
            await sesion.commit()
        except Exception:
            await sesion.rollback()
            raise
