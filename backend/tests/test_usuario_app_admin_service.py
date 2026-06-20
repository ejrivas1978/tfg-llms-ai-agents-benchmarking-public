"""
Modulo: test_usuario_app_admin_service
Ruta:   backend/tests/test_usuario_app_admin_service.py

Descripcion:
    Tests unitarios para UsuarioAppAdminService.
    Los repositorios y la sesion de base de datos se sustituyen por mocks
    para aislar la logica del servicio.

    Casos cubiertos:
    - listar_usuarios: lista completa y lista vacia
    - conceder_acceso: usuario inexistente (404), acceso concedido
    - ampliar_tokens: usuario inexistente (404), tokens ampliados
    - eliminar_usuario: usuario inexistente (404), eliminacion con cascade

Sprint: Sprint 4
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.models.enums import EstadoUsuarioApp
from app.services.usuario_app_admin_service import UsuarioAppAdminService


# ── Helpers ───────────────────────────────────────────────────────────────────


def _db_mock() -> MagicMock:
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
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
        estado=estado,
        cuota_asignada=cuota_asignada,
        consultas_usadas=consultas_usadas,
        intentos_fallidos=intentos_fallidos,
        created_at=datetime(2026, 5, 1, 10, 0, 0),
    )


def _servicio(repo_mock: MagicMock, eval_repo_mock: MagicMock | None = None) -> UsuarioAppAdminService:
    db = _db_mock()
    servicio = UsuarioAppAdminService(db)
    servicio._repo = repo_mock
    servicio._eval_repo = eval_repo_mock or MagicMock()
    return servicio


# ── Tests: listar_usuarios ────────────────────────────────────────────────────


class TestListarUsuarios:
    """Pruebas para UsuarioAppAdminService.listar_usuarios."""

    async def test_devuelve_lista_con_todos_los_usuarios(self):
        usuarios = [_usuario(id=1, nick="alfa"), _usuario(id=2, nick="beta")]
        repo = MagicMock()
        repo.listar_todos = AsyncMock(return_value=usuarios)

        resultado = await _servicio(repo).listar_usuarios()

        assert resultado.total == 2
        assert len(resultado.items) == 2

    async def test_total_coincide_con_longitud_de_items(self):
        repo = MagicMock()
        repo.listar_todos = AsyncMock(return_value=[_usuario(), _usuario(id=2, nick="beta")])

        resultado = await _servicio(repo).listar_usuarios()
        assert resultado.total == len(resultado.items)

    async def test_lista_vacia_cuando_no_hay_usuarios(self):
        repo = MagicMock()
        repo.listar_todos = AsyncMock(return_value=[])

        resultado = await _servicio(repo).listar_usuarios()
        assert resultado.total == 0
        assert resultado.items == []


# ── Tests: conceder_acceso ────────────────────────────────────────────────────


class TestConcederAcceso:
    """Pruebas para UsuarioAppAdminService.conceder_acceso."""

    async def test_usuario_inexistente_lanza_404(self):
        repo = MagicMock()
        repo.obtener_por_id = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await _servicio(repo).conceder_acceso(99, cuota=10)
        assert exc_info.value.status_code == 404

    async def test_llama_asignar_cuota_con_valor_correcto(self):
        usuario = _usuario(estado=EstadoUsuarioApp.pendiente_acceso)
        usuario_habilitado = _usuario(estado=EstadoUsuarioApp.habilitado, cuota_asignada=10)
        repo = MagicMock()
        repo.obtener_por_id = AsyncMock(return_value=usuario)
        repo.asignar_cuota = AsyncMock(return_value=usuario_habilitado)

        resultado = await _servicio(repo).conceder_acceso(1, cuota=10)

        repo.asignar_cuota.assert_called_once_with(usuario=usuario, cuota=10)
        assert resultado.estado == EstadoUsuarioApp.habilitado
        assert resultado.cuota_asignada == 10

    async def test_devuelve_datos_del_usuario_actualizado(self):
        usuario_orig = _usuario(estado=EstadoUsuarioApp.pendiente_acceso)
        usuario_act = _usuario(estado=EstadoUsuarioApp.habilitado, cuota_asignada=15, nick="evaluador")
        repo = MagicMock()
        repo.obtener_por_id = AsyncMock(return_value=usuario_orig)
        repo.asignar_cuota = AsyncMock(return_value=usuario_act)

        resultado = await _servicio(repo).conceder_acceso(1, cuota=15)
        assert resultado.nick == "evaluador"
        assert resultado.cuota_asignada == 15


# ── Tests: ampliar_tokens ─────────────────────────────────────────────────────


class TestAmpliarTokens:
    """Pruebas para UsuarioAppAdminService.ampliar_tokens."""

    async def test_usuario_inexistente_lanza_404(self):
        repo = MagicMock()
        repo.obtener_por_id = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await _servicio(repo).ampliar_tokens(99, tokens_adicionales=5)
        assert exc_info.value.status_code == 404

    async def test_llama_ampliar_tokens_con_valor_correcto(self):
        usuario = _usuario(estado=EstadoUsuarioApp.pendiente_ampliar_tokens, cuota_asignada=10)
        usuario_ampliado = _usuario(estado=EstadoUsuarioApp.habilitado, cuota_asignada=15)
        repo = MagicMock()
        repo.obtener_por_id = AsyncMock(return_value=usuario)
        repo.ampliar_tokens = AsyncMock(return_value=usuario_ampliado)

        resultado = await _servicio(repo).ampliar_tokens(1, tokens_adicionales=5)

        repo.ampliar_tokens.assert_called_once_with(usuario=usuario, tokens_adicionales=5)
        assert resultado.cuota_asignada == 15
        assert resultado.estado == EstadoUsuarioApp.habilitado

    async def test_devuelve_estado_habilitado_tras_ampliar(self):
        repo = MagicMock()
        repo.obtener_por_id = AsyncMock(return_value=_usuario(estado=EstadoUsuarioApp.pendiente_ampliar_tokens))
        repo.ampliar_tokens = AsyncMock(return_value=_usuario(estado=EstadoUsuarioApp.habilitado, cuota_asignada=20))

        resultado = await _servicio(repo).ampliar_tokens(1, tokens_adicionales=10)
        assert resultado.estado == EstadoUsuarioApp.habilitado


# ── Tests: eliminar_usuario ───────────────────────────────────────────────────


class TestEliminarUsuario:
    """Pruebas para UsuarioAppAdminService.eliminar_usuario."""

    async def test_usuario_inexistente_lanza_404(self):
        repo = MagicMock()
        repo.obtener_por_id = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await _servicio(repo).eliminar_usuario(99)
        assert exc_info.value.status_code == 404

    async def test_elimina_evaluaciones_en_cascade(self):
        usuario = _usuario(nick="borrado")
        repo = MagicMock()
        repo.obtener_por_id = AsyncMock(return_value=usuario)
        eval_repo = MagicMock()
        eval_repo.eliminar_por_nickname = AsyncMock(return_value=7)

        resultado = await _servicio(repo, eval_repo).eliminar_usuario(1)

        eval_repo.eliminar_por_nickname.assert_called_once_with("borrado")
        assert resultado == 7

    async def test_devuelve_numero_evaluaciones_eliminadas(self):
        repo = MagicMock()
        repo.obtener_por_id = AsyncMock(return_value=_usuario())
        eval_repo = MagicMock()
        eval_repo.eliminar_por_nickname = AsyncMock(return_value=12)

        resultado = await _servicio(repo, eval_repo).eliminar_usuario(1)
        assert resultado == 12

    async def test_llama_delete_sobre_el_usuario(self):
        usuario = _usuario()
        repo = MagicMock()
        repo.obtener_por_id = AsyncMock(return_value=usuario)
        eval_repo = MagicMock()
        eval_repo.eliminar_por_nickname = AsyncMock(return_value=0)
        db = _db_mock()
        servicio = UsuarioAppAdminService(db)
        servicio._repo = repo
        servicio._eval_repo = eval_repo

        await servicio.eliminar_usuario(1)
        db.delete.assert_called_once_with(usuario)
