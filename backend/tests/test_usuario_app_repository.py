"""
Modulo: test_usuario_app_repository
Ruta:   backend/tests/test_usuario_app_repository.py

Descripcion:
    Tests unitarios para UsuarioAppRepository.
    La sesion de base de datos se sustituye por mocks para aislar
    la logica del repositorio sin necesidad de PostgreSQL.

    Casos cubiertos:
    - obtener_por_nick: usuario encontrado y no encontrado
    - obtener_por_id: usuario encontrado y no encontrado
    - listar_todos: lista completa y lista vacia
    - actualizar_estado: modifica atributo y llama flush/refresh
    - asignar_cuota: asigna cuota y habilita usuario
    - ampliar_tokens: suma tokens y habilita usuario
    - incrementar_consultas: suma 1 a consultas_usadas
    - incrementar_intentos: suma 1 a intentos_fallidos
    - resetear_intentos: pone intentos_fallidos a 0
    - regenerar_contrasena: actualiza hash y estado

Sprint: Sprint 4
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import EstadoUsuarioApp
from app.repositories.usuario_app_repository import UsuarioAppRepository


# ── Helpers ───────────────────────────────────────────────────────────────────


def _db_mock() -> MagicMock:
    db = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    return db


def _usuario(
    id: int = 1,
    nick: str = "evaluador",
    estado: EstadoUsuarioApp = EstadoUsuarioApp.habilitado,
    cuota_asignada: int = 20,
    consultas_usadas: int = 5,
    intentos_fallidos: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        nick=nick,
        password_hash="$2b$hash",
        estado=estado,
        cuota_asignada=cuota_asignada,
        consultas_usadas=consultas_usadas,
        intentos_fallidos=intentos_fallidos,
    )


def _repo(db: MagicMock | None = None) -> UsuarioAppRepository:
    return UsuarioAppRepository(db or _db_mock())


# ── Tests: obtener_por_nick ───────────────────────────────────────────────────


class TestObtenerPorNick:
    """Pruebas para UsuarioAppRepository.obtener_por_nick."""

    async def test_devuelve_usuario_cuando_existe(self):
        db = _db_mock()
        usuario = _usuario()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = usuario
        db.execute = AsyncMock(return_value=result_mock)

        resultado = await _repo(db).obtener_por_nick("evaluador")
        assert resultado is usuario

    async def test_devuelve_none_cuando_no_existe(self):
        db = _db_mock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)

        resultado = await _repo(db).obtener_por_nick("inexistente")
        assert resultado is None


# ── Tests: obtener_por_id ─────────────────────────────────────────────────────


class TestObtenerPorId:
    """Pruebas para UsuarioAppRepository.obtener_por_id."""

    async def test_devuelve_usuario_cuando_existe(self):
        db = _db_mock()
        usuario = _usuario(id=7)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = usuario
        db.execute = AsyncMock(return_value=result_mock)

        resultado = await _repo(db).obtener_por_id(7)
        assert resultado is usuario

    async def test_devuelve_none_cuando_no_existe(self):
        db = _db_mock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)

        resultado = await _repo(db).obtener_por_id(999)
        assert resultado is None


# ── Tests: listar_todos ───────────────────────────────────────────────────────


class TestListarTodos:
    """Pruebas para UsuarioAppRepository.listar_todos."""

    async def test_devuelve_lista_de_usuarios(self):
        db = _db_mock()
        usuarios = [_usuario(id=1), _usuario(id=2, nick="beta")]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = usuarios
        db.execute = AsyncMock(return_value=result_mock)

        resultado = await _repo(db).listar_todos()
        assert len(resultado) == 2

    async def test_devuelve_lista_vacia(self):
        db = _db_mock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=result_mock)

        resultado = await _repo(db).listar_todos()
        assert resultado == []


# ── Tests: actualizar_estado ──────────────────────────────────────────────────


class TestActualizarEstado:
    """Pruebas para UsuarioAppRepository.actualizar_estado."""

    async def test_cambia_estado_del_usuario(self):
        db = _db_mock()
        usuario = _usuario(estado=EstadoUsuarioApp.habilitado)

        resultado = await _repo(db).actualizar_estado(usuario, EstadoUsuarioApp.pendiente_acceso)
        assert resultado.estado == EstadoUsuarioApp.pendiente_acceso

    async def test_llama_flush_y_refresh(self):
        db = _db_mock()
        usuario = _usuario()

        await _repo(db).actualizar_estado(usuario, EstadoUsuarioApp.pendiente_ampliar_tokens)
        db.flush.assert_called_once()
        db.refresh.assert_called_once_with(usuario)


# ── Tests: asignar_cuota ──────────────────────────────────────────────────────


class TestAsignarCuota:
    """Pruebas para UsuarioAppRepository.asignar_cuota."""

    async def test_asigna_cuota_al_usuario(self):
        db = _db_mock()
        usuario = _usuario(cuota_asignada=0, estado=EstadoUsuarioApp.pendiente_acceso)

        resultado = await _repo(db).asignar_cuota(usuario, cuota=15)
        assert resultado.cuota_asignada == 15

    async def test_cambia_estado_a_habilitado(self):
        db = _db_mock()
        usuario = _usuario(estado=EstadoUsuarioApp.pendiente_acceso)

        resultado = await _repo(db).asignar_cuota(usuario, cuota=10)
        assert resultado.estado == EstadoUsuarioApp.habilitado


# ── Tests: ampliar_tokens ─────────────────────────────────────────────────────


class TestAmpliarTokens:
    """Pruebas para UsuarioAppRepository.ampliar_tokens."""

    async def test_incrementa_cuota_asignada(self):
        db = _db_mock()
        usuario = _usuario(cuota_asignada=10)

        resultado = await _repo(db).ampliar_tokens(usuario, tokens_adicionales=5)
        assert resultado.cuota_asignada == 15

    async def test_cambia_estado_a_habilitado(self):
        db = _db_mock()
        usuario = _usuario(estado=EstadoUsuarioApp.pendiente_ampliar_tokens)

        resultado = await _repo(db).ampliar_tokens(usuario, tokens_adicionales=10)
        assert resultado.estado == EstadoUsuarioApp.habilitado


# ── Tests: incrementar_consultas ─────────────────────────────────────────────


class TestIncrementarConsultas:
    """Pruebas para UsuarioAppRepository.incrementar_consultas."""

    async def test_suma_uno_a_consultas_usadas(self):
        db = _db_mock()
        usuario = _usuario(consultas_usadas=3)

        resultado = await _repo(db).incrementar_consultas(usuario)
        assert resultado.consultas_usadas == 4

    async def test_llama_flush_y_refresh(self):
        db = _db_mock()
        usuario = _usuario()

        await _repo(db).incrementar_consultas(usuario)
        db.flush.assert_called_once()
        db.refresh.assert_called_once_with(usuario)


# ── Tests: incrementar_intentos ──────────────────────────────────────────────


class TestIncrementarIntentos:
    """Pruebas para UsuarioAppRepository.incrementar_intentos."""

    async def test_suma_uno_a_intentos_fallidos(self):
        db = _db_mock()
        usuario = _usuario(intentos_fallidos=2)

        resultado = await _repo(db).incrementar_intentos(usuario)
        assert resultado.intentos_fallidos == 3


# ── Tests: resetear_intentos ──────────────────────────────────────────────────


class TestResetearIntentos:
    """Pruebas para UsuarioAppRepository.resetear_intentos."""

    async def test_pone_intentos_a_cero(self):
        db = _db_mock()
        usuario = _usuario(intentos_fallidos=4)

        resultado = await _repo(db).resetear_intentos(usuario)
        assert resultado.intentos_fallidos == 0


# ── Tests: regenerar_contrasena ───────────────────────────────────────────────


class TestRegenerarContrasena:
    """Pruebas para UsuarioAppRepository.regenerar_contrasena."""

    async def test_actualiza_hash_de_contrasena(self):
        db = _db_mock()
        usuario = _usuario()
        nuevo_hash = "$2b$nuevo_hash_bcrypt"

        resultado = await _repo(db).regenerar_contrasena(usuario, nuevo_hash)
        assert resultado.password_hash == nuevo_hash

    async def test_cambia_estado_a_pendiente_acceso(self):
        db = _db_mock()
        usuario = _usuario(estado=EstadoUsuarioApp.habilitado)

        resultado = await _repo(db).regenerar_contrasena(usuario, "$2b$hash")
        assert resultado.estado == EstadoUsuarioApp.pendiente_acceso

    async def test_resetea_intentos_fallidos(self):
        db = _db_mock()
        usuario = _usuario(intentos_fallidos=3)

        resultado = await _repo(db).regenerar_contrasena(usuario, "$2b$hash")
        assert resultado.intentos_fallidos == 0
