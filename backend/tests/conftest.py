"""
Modulo: conftest
Ruta:   backend/tests/conftest.py

Descripcion:
    Fixtures de pytest compartidas por todos los modulos de test.
    Utiliza una base de datos SQLite en memoria (via aiosqlite) para que
    los tests se ejecuten sin necesitar una instancia PostgreSQL activa.
    El esquema se crea desde cero para cada sesion de tests usando
    SQLAlchemy async create_all.

    Las cuentas de administrador para tests se crean directamente en la BD
    via la capa de repositorio, sin pasar por la capa HTTP (no existe endpoint
    publico de registro).

Dependencias:
    - pytest-asyncio
    - httpx
    - aiosqlite

Sprint: Sprint 1
"""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_db
from app.core.security import hash_password
# Importar modelos para poblar Base.metadata; user_evaluations excluido (tipo ARRAY).
from app.models.benchmark_evaluacion import BenchmarkEvaluacion  # noqa: F401
from app.models.llm_response import LLMResponse  # noqa: F401
from app.models.user_evaluation import UserEvaluation  # noqa: F401
from app.models.usuario_app import UsuarioApp
from app.main import app

URL_BD_TEST = "sqlite+aiosqlite:///:memory:"

_motor_test = create_async_engine(URL_BD_TEST, echo=False)
_SesionLocalTest: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=_motor_test,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# Solo tablas compatibles con SQLite (user_evaluations excluida: usa tipo ARRAY de PostgreSQL)
_TABLAS_SQLITE = [UsuarioApp.__table__]


@pytest_asyncio.fixture(scope="session", autouse=True)
async def crear_tablas():
    """Crea las tablas compatibles con SQLite una unica vez por sesion de tests."""
    async with _motor_test.begin() as conn:
        for tabla in _TABLAS_SQLITE:
            await conn.run_sync(tabla.create, checkfirst=True)
    yield
    async with _motor_test.begin() as conn:
        for tabla in reversed(_TABLAS_SQLITE):
            await conn.run_sync(tabla.drop, checkfirst=True)


@pytest_asyncio.fixture
async def sesion_db():
    """Devuelve una sesion asincrona fresca para cada test, con rollback al finalizar."""
    async with _SesionLocalTest() as sesion:
        yield sesion
        await sesion.rollback()


@pytest_asyncio.fixture
async def client(sesion_db: AsyncSession):
    """Devuelve un AsyncClient con la base de datos de test inyectada."""

    async def override_get_db():
        yield sesion_db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_credentials(sesion_db: AsyncSession) -> dict:
    """Crea una cuenta de administrador directamente en la BD y devuelve sus credenciales.

    Tras la unificacion (ADR-027) el admin es un registro de usuarios_app
    con is_admin=True. El login se hace por nick + password.

    Returns:
        Diccionario con las claves 'nick' y 'password' para login.
    """
    from app.models.enums import EstadoUsuarioApp
    admin = UsuarioApp(
        nick="testadmin",
        password_hash=hash_password("adminpass123"),
        email="admin@test.com",
        is_admin=True,
        estado=EstadoUsuarioApp.habilitado,
    )
    sesion_db.add(admin)
    await sesion_db.flush()
    return {"nick": "testadmin", "password": "adminpass123"}
