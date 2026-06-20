"""
Modulo: test_usuario_auth_service
Ruta:   backend/tests/test_usuario_auth_service.py

Descripcion:
    Tests unitarios para UsuarioAppAuthService.
    Los repositorios y la sesion de base de datos se sustituyen por mocks
    para aislar la logica del servicio de la capa de persistencia y del ENUM
    PostgreSQL (incompatible con SQLite).

    Casos cubiertos:
    - registrar: nick nuevo y nick duplicado (409)
    - login: nick inexistente (401), cuenta bloqueada (423), contrasena
      incorrecta (401), pendiente_acceso (403), login exitoso
    - login: M1 (401 unificado) y M2 (mensaje sin contador de intentos)
    - solicitar_mas_tokens: cambio de estado
    - regenerar_contrasena: nick inexistente (404) y flujo exitoso

Sprint: Sprint 4
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.core.security import hash_password
from app.models.enums import EstadoUsuarioApp
from app.services.usuario_app_auth_service import UsuarioAppAuthService


# ── Helpers ───────────────────────────────────────────────────────────────────


def _db_mock() -> MagicMock:
    """Devuelve un mock de AsyncSession con commit y refresh asyncronos."""
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


def _usuario(
    id: int = 1,
    nick: str = "evaluador",
    password: str = "contrasena_real",
    estado: EstadoUsuarioApp = EstadoUsuarioApp.habilitado,
    intentos_fallidos: int = 0,
    cuota_asignada: int = 20,
    consultas_usadas: int = 5,
) -> SimpleNamespace:
    """Construye un objeto que imita UsuarioApp con los atributos minimos necesarios."""
    return SimpleNamespace(
        id=id,
        nick=nick,
        password_hash=hash_password(password),
        estado=estado,
        intentos_fallidos=intentos_fallidos,
        cuota_asignada=cuota_asignada,
        consultas_usadas=consultas_usadas,
        created_at=datetime(2026, 5, 1, 10, 0, 0),
    )


def _servicio(repo_mock: MagicMock) -> UsuarioAppAuthService:
    """Instancia el servicio con un repositorio mockeado."""
    db = _db_mock()
    servicio = UsuarioAppAuthService(db)
    servicio._repo = repo_mock
    return servicio


# ── Tests: registrar ──────────────────────────────────────────────────────────


class TestRegistrar:
    """Pruebas para UsuarioAppAuthService.registrar."""

    async def test_nick_nuevo_devuelve_respuesta_publica(self):
        """Registrar un nick que no existe crea el usuario y devuelve RespuestaUsuarioApp."""
        usuario_creado = _usuario()
        repo = MagicMock()
        repo.obtener_por_nick = AsyncMock(return_value=None)
        repo.crear = AsyncMock(return_value=usuario_creado)

        resultado = await _servicio(repo).registrar("nuevonick", "password12")

        repo.crear.assert_called_once()
        assert resultado.nick == "evaluador"
        assert resultado.estado == EstadoUsuarioApp.habilitado

    async def test_nick_nuevo_hashea_contrasena(self):
        """La contrasena enviada al repositorio es un hash, nunca texto plano."""
        usuario_creado = _usuario()
        repo = MagicMock()
        repo.obtener_por_nick = AsyncMock(return_value=None)
        repo.crear = AsyncMock(return_value=usuario_creado)

        await _servicio(repo).registrar("nuevonick", "password12")

        _nick, hash_enviado = repo.crear.call_args.kwargs["nick"], repo.crear.call_args.kwargs["password_hash"]
        assert hash_enviado != "password12"
        assert hash_enviado.startswith("$2b$")

    async def test_nick_duplicado_lanza_409(self):
        repo = MagicMock()
        repo.obtener_por_nick = AsyncMock(return_value=_usuario())

        with pytest.raises(HTTPException) as exc_info:
            await _servicio(repo).registrar("evaluador", "password12")
        assert exc_info.value.status_code == 409


# ── Tests: login ──────────────────────────────────────────────────────────────


class TestLogin:
    """Pruebas para UsuarioAppAuthService.login."""

    async def test_nick_inexistente_devuelve_401(self):
        """M1-seguridad: nick inexistente debe devolver 401, no 404, para evitar enumeracion."""
        repo = MagicMock()
        repo.obtener_por_nick = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await _servicio(repo).login("nadie", "contrasena")
        assert exc_info.value.status_code == 401

    async def test_nick_inexistente_mensaje_generico(self):
        """M2-seguridad: el mensaje de error no revela si el nick existe o no."""
        repo = MagicMock()
        repo.obtener_por_nick = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await _servicio(repo).login("nadie", "contrasena")
        assert exc_info.value.detail == "Credenciales incorrectas."
        assert "restantes" not in exc_info.value.detail.lower()

    async def test_cuenta_bloqueada_devuelve_423(self):
        usuario = _usuario(intentos_fallidos=5)
        repo = MagicMock()
        repo.obtener_por_nick = AsyncMock(return_value=usuario)

        with pytest.raises(HTTPException) as exc_info:
            await _servicio(repo).login("evaluador", "cualquier")
        assert exc_info.value.status_code == 423

    async def test_contrasena_incorrecta_devuelve_401(self):
        """M1-seguridad: contrasena incorrecta devuelve 401, igual que nick inexistente."""
        usuario = _usuario(password="real")
        repo = MagicMock()
        repo.obtener_por_nick = AsyncMock(return_value=usuario)
        repo.incrementar_intentos = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await _servicio(repo).login("evaluador", "incorrecta")
        assert exc_info.value.status_code == 401

    async def test_contrasena_incorrecta_mensaje_generico(self):
        """M2-seguridad: mensaje de contrasena incorrecta no revela intentos restantes."""
        usuario = _usuario(password="real", intentos_fallidos=3)
        repo = MagicMock()
        repo.obtener_por_nick = AsyncMock(return_value=usuario)
        repo.incrementar_intentos = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await _servicio(repo).login("evaluador", "incorrecta")
        assert exc_info.value.detail == "Credenciales incorrectas."
        assert "restantes" not in exc_info.value.detail.lower()
        assert "1" not in exc_info.value.detail

    async def test_contrasena_incorrecta_incrementa_intentos(self):
        usuario = _usuario(password="real")
        repo = MagicMock()
        repo.obtener_por_nick = AsyncMock(return_value=usuario)
        repo.incrementar_intentos = AsyncMock()

        with pytest.raises(HTTPException):
            await _servicio(repo).login("evaluador", "incorrecta")
        repo.incrementar_intentos.assert_called_once_with(usuario)

    async def test_pendiente_acceso_devuelve_403(self):
        usuario = _usuario(estado=EstadoUsuarioApp.pendiente_acceso)
        repo = MagicMock()
        repo.obtener_por_nick = AsyncMock(return_value=usuario)
        repo.resetear_intentos = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await _servicio(repo).login("evaluador", "contrasena_real")
        assert exc_info.value.status_code == 403

    async def test_login_exitoso_devuelve_token_jwt(self):
        usuario = _usuario()
        repo = MagicMock()
        repo.obtener_por_nick = AsyncMock(return_value=usuario)
        repo.resetear_intentos = AsyncMock()

        resultado = await _servicio(repo).login("evaluador", "contrasena_real")

        assert resultado.access_token is not None
        assert resultado.access_token.count(".") == 2
        assert resultado.nick == "evaluador"

    async def test_login_exitoso_resetea_intentos_fallidos(self):
        usuario = _usuario(intentos_fallidos=3)
        repo = MagicMock()
        repo.obtener_por_nick = AsyncMock(return_value=usuario)
        repo.resetear_intentos = AsyncMock()

        await _servicio(repo).login("evaluador", "contrasena_real")
        repo.resetear_intentos.assert_called_once_with(usuario)

    async def test_login_exitoso_incluye_estado_cuota(self):
        usuario = _usuario(cuota_asignada=15, consultas_usadas=7)
        repo = MagicMock()
        repo.obtener_por_nick = AsyncMock(return_value=usuario)
        repo.resetear_intentos = AsyncMock()

        resultado = await _servicio(repo).login("evaluador", "contrasena_real")

        assert resultado.cuota_asignada == 15
        assert resultado.consultas_usadas == 7

    async def test_token_contiene_claim_tipo_usuario_app(self):
        """El JWT de evaluador incluye el claim 'tipo': 'usuario_app'."""
        from app.core.security import decode_access_token

        usuario = _usuario()
        repo = MagicMock()
        repo.obtener_por_nick = AsyncMock(return_value=usuario)
        repo.resetear_intentos = AsyncMock()

        resultado = await _servicio(repo).login("evaluador", "contrasena_real")
        payload = decode_access_token(resultado.access_token)
        assert payload.get("tipo") == "usuario_app"


# ── Tests: solicitar_mas_tokens ───────────────────────────────────────────────


class TestSolicitarMasTokens:
    """Pruebas para UsuarioAppAuthService.solicitar_mas_tokens."""

    async def test_cambia_estado_a_pendiente_ampliar(self):
        usuario = _usuario()
        usuario_actualizado = _usuario(estado=EstadoUsuarioApp.pendiente_ampliar_tokens)
        repo = MagicMock()
        repo.actualizar_estado = AsyncMock(return_value=usuario_actualizado)

        resultado = await _servicio(repo).solicitar_mas_tokens(usuario)
        assert resultado.estado == EstadoUsuarioApp.pendiente_ampliar_tokens

    async def test_llama_repo_con_estado_correcto(self):
        usuario = _usuario()
        repo = MagicMock()
        repo.actualizar_estado = AsyncMock(return_value=_usuario(estado=EstadoUsuarioApp.pendiente_ampliar_tokens))

        await _servicio(repo).solicitar_mas_tokens(usuario)
        repo.actualizar_estado.assert_called_once_with(usuario, EstadoUsuarioApp.pendiente_ampliar_tokens)


# ── Tests: regenerar_contrasena ───────────────────────────────────────────────


class TestRegenerarContrasena:
    """Pruebas para UsuarioAppAuthService.regenerar_contrasena."""

    async def test_nick_inexistente_lanza_404(self):
        repo = MagicMock()
        repo.obtener_por_nick = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await _servicio(repo).regenerar_contrasena("nadie", "nueva_pass12")
        assert exc_info.value.status_code == 404

    async def test_nick_existente_llama_repo_regenerar(self):
        usuario = _usuario()
        usuario_regenerado = _usuario(estado=EstadoUsuarioApp.pendiente_acceso)
        repo = MagicMock()
        repo.obtener_por_nick = AsyncMock(return_value=usuario)
        repo.regenerar_contrasena = AsyncMock(return_value=usuario_regenerado)

        resultado = await _servicio(repo).regenerar_contrasena("evaluador", "nueva_pass12")

        repo.regenerar_contrasena.assert_called_once()
        assert resultado.estado == EstadoUsuarioApp.pendiente_acceso

    async def test_nuevo_hash_no_es_texto_plano(self):
        """La nueva contrasena se hashea antes de pasarla al repositorio."""
        usuario = _usuario()
        repo = MagicMock()
        repo.obtener_por_nick = AsyncMock(return_value=usuario)
        repo.regenerar_contrasena = AsyncMock(return_value=_usuario(estado=EstadoUsuarioApp.pendiente_acceso))

        await _servicio(repo).regenerar_contrasena("evaluador", "nueva_pass12")

        nuevo_hash = repo.regenerar_contrasena.call_args.kwargs["nuevo_password_hash"]
        assert nuevo_hash != "nueva_pass12"
        assert nuevo_hash.startswith("$2b$")
