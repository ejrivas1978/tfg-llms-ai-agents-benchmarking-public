"""
Modulo: test_router_usuarios
Ruta:   backend/tests/test_router_usuarios.py

Descripcion:
    Tests de integracion para los endpoints de autenticacion de usuarios web.
    Los endpoints con rate limiting se prueban con pocas peticiones para
    no alcanzar el limite durante la ejecucion del suite.

    Endpoints cubiertos:
    - GET  /api/v1/usuarios/verificar/{nick}
    - POST /api/v1/usuarios/registrar
    - POST /api/v1/usuarios/login
    - POST /api/v1/usuarios/solicitar-mas-tokens
    - POST /api/v1/usuarios/regenerar-contrasena

Sprint: Sprint 4
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from httpx import AsyncClient

from app.core.dependencies import get_current_usuario_app
from app.main import app
from app.models.enums import EstadoUsuarioApp
from app.schemas.usuario_app import (
    RespuestaTokenUsuarioApp,
    RespuestaUsuarioApp,
)


def _respuesta_usuario(nick: str = "usuarioweb") -> RespuestaUsuarioApp:
    return RespuestaUsuarioApp(
        id=1,
        nick=nick,
        estado=EstadoUsuarioApp.pendiente_acceso,
        cuota_asignada=0,
        consultas_usadas=0,
        intentos_fallidos=0,
        created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )


def _respuesta_token(nick: str = "usuarioweb") -> RespuestaTokenUsuarioApp:
    return RespuestaTokenUsuarioApp(
        access_token="jwt.token.fake",
        token_type="bearer",
        expires_in=3600,
        nick=nick,
        estado=EstadoUsuarioApp.habilitado,
        consultas_usadas=0,
        cuota_asignada=20,
    )


# ── Tests: verificar nick ─────────────────────────────────────────────────────


class TestRouterVerificarNick:
    """Tests para GET /api/v1/usuarios/verificar/{nick}."""

    async def test_nick_no_registrado_devuelve_false(self, client: AsyncClient):
        # UsuarioAppRepository se importa localmente dentro de la funcion
        with patch("app.repositories.usuario_app_repository.UsuarioAppRepository.obtener_por_nick", new=AsyncMock(return_value=None)):
            respuesta = await client.get("/api/v1/usuarios/verificar/nuevouser")

        assert respuesta.status_code == 200
        assert respuesta.json() == {"existe": False}

    async def test_nick_registrado_devuelve_true(self, client: AsyncClient):
        usuario_mock = SimpleNamespace(nick="existente")

        with patch("app.repositories.usuario_app_repository.UsuarioAppRepository.obtener_por_nick", new=AsyncMock(return_value=usuario_mock)):
            respuesta = await client.get("/api/v1/usuarios/verificar/existente")

        assert respuesta.status_code == 200
        assert respuesta.json() == {"existe": True}


# ── Tests: registrar ──────────────────────────────────────────────────────────


class TestRouterRegistrar:
    """Tests para POST /api/v1/usuarios/registrar."""

    async def test_registro_exitoso_devuelve_201(self, client: AsyncClient):
        with patch("app.routers.usuarios.UsuarioAppAuthService") as mock_cls:
            mock_svc = AsyncMock()
            mock_svc.registrar = AsyncMock(return_value=_respuesta_usuario("nuevo"))
            mock_cls.return_value = mock_svc

            respuesta = await client.post(
                "/api/v1/usuarios/registrar",
                json={"nick": "nuevousuario", "password": "contrasena123"},
            )

        assert respuesta.status_code == 201
        assert respuesta.json()["nick"] == "nuevo"

    async def test_nick_corto_devuelve_422(self, client: AsyncClient):
        respuesta = await client.post(
            "/api/v1/usuarios/registrar",
            json={"nick": "ab", "password": "contrasena123"},
        )
        assert respuesta.status_code == 422

    async def test_password_corta_devuelve_422(self, client: AsyncClient):
        respuesta = await client.post(
            "/api/v1/usuarios/registrar",
            json={"nick": "usuarionuevo", "password": "corta"},
        )
        assert respuesta.status_code == 422

    async def test_nick_duplicado_lanza_409(self, client: AsyncClient):
        with patch("app.routers.usuarios.UsuarioAppAuthService") as mock_cls:
            mock_svc = AsyncMock()
            mock_svc.registrar = AsyncMock(side_effect=HTTPException(status_code=409))
            mock_cls.return_value = mock_svc

            respuesta = await client.post(
                "/api/v1/usuarios/registrar",
                json={"nick": "yaexiste", "password": "contrasena123"},
            )

        assert respuesta.status_code == 409


# ── Tests: login ──────────────────────────────────────────────────────────────


class TestRouterLoginUsuario:
    """Tests para POST /api/v1/usuarios/login."""

    async def test_login_exitoso_devuelve_200_con_token(self, client: AsyncClient):
        with patch("app.routers.usuarios.UsuarioAppAuthService") as mock_cls:
            mock_svc = AsyncMock()
            mock_svc.login = AsyncMock(return_value=_respuesta_token("miusuario"))
            mock_cls.return_value = mock_svc

            respuesta = await client.post(
                "/api/v1/usuarios/login",
                json={"nick": "miusuario", "password": "contrasena123"},
            )

        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert "access_token" in cuerpo
        assert cuerpo["nick"] == "miusuario"

    async def test_credenciales_invalidas_lanza_401(self, client: AsyncClient):
        with patch("app.routers.usuarios.UsuarioAppAuthService") as mock_cls:
            mock_svc = AsyncMock()
            mock_svc.login = AsyncMock(side_effect=HTTPException(status_code=401))
            mock_cls.return_value = mock_svc

            respuesta = await client.post(
                "/api/v1/usuarios/login",
                json={"nick": "usuario", "password": "incorrecta"},
            )

        assert respuesta.status_code == 401


# ── Tests: solicitar-mas-tokens ───────────────────────────────────────────────


class TestRouterSolicitarMasTokens:
    """Tests para POST /api/v1/usuarios/solicitar-mas-tokens."""

    async def test_solicitud_exitosa_devuelve_200(self, client: AsyncClient):
        usuario_mock = SimpleNamespace(
            id=1, nick="miusuario", estado=EstadoUsuarioApp.habilitado,
            cuota_asignada=10, consultas_usadas=9, intentos_fallidos=0,
        )
        app.dependency_overrides[get_current_usuario_app] = lambda: usuario_mock

        try:
            usuario_pendiente = _respuesta_usuario("miusuario")
            with patch("app.routers.usuarios.UsuarioAppAuthService") as mock_cls:
                mock_svc = AsyncMock()
                mock_svc.solicitar_mas_tokens = AsyncMock(return_value=usuario_pendiente)
                mock_cls.return_value = mock_svc

                respuesta = await client.post("/api/v1/usuarios/solicitar-mas-tokens")
        finally:
            app.dependency_overrides.pop(get_current_usuario_app, None)

        assert respuesta.status_code == 200

    async def test_sin_auth_devuelve_401(self, client: AsyncClient):
        respuesta = await client.post("/api/v1/usuarios/solicitar-mas-tokens")
        assert respuesta.status_code == 401


# ── Tests: regenerar-contrasena ───────────────────────────────────────────────


class TestRouterRegenerarContrasena:
    """Tests para POST /api/v1/usuarios/regenerar-contrasena."""

    async def test_regeneracion_exitosa_devuelve_200(self, client: AsyncClient):
        with patch("app.routers.usuarios.UsuarioAppAuthService") as mock_cls:
            mock_svc = AsyncMock()
            mock_svc.regenerar_contrasena = AsyncMock(return_value=_respuesta_usuario("miusuario"))
            mock_cls.return_value = mock_svc

            respuesta = await client.post(
                "/api/v1/usuarios/regenerar-contrasena",
                json={"nick": "miusuario", "nueva_password": "nuevacontrasena123"},
            )

        assert respuesta.status_code == 200

    async def test_nick_inexistente_lanza_404(self, client: AsyncClient):
        with patch("app.routers.usuarios.UsuarioAppAuthService") as mock_cls:
            mock_svc = AsyncMock()
            mock_svc.regenerar_contrasena = AsyncMock(side_effect=HTTPException(status_code=404))
            mock_cls.return_value = mock_svc

            respuesta = await client.post(
                "/api/v1/usuarios/regenerar-contrasena",
                json={"nick": "noexiste", "nueva_password": "nuevacontrasena123"},
            )

        assert respuesta.status_code == 404
