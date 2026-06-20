"""
Modulo: test_auth
Ruta:   backend/tests/test_auth.py

Descripcion:
    Tests de integracion para los endpoints de autenticacion (solo administrador).
    Los usuarios regulares son anonimos; unicamente los administradores usan login JWT.

    Las cuentas de administrador se crean directamente en la BD via el fixture
    admin_credentials (no existe endpoint publico de registro).

Dependencias:
    - pytest-asyncio
    - httpx
    - fixtures de conftest: client, admin_credentials

Sprint: Sprint 1
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

URL_LOGIN = "/api/v1/auth/login"
URL_ME = "/api/v1/auth/me"
URL_REGISTRO = "/api/v1/auth/register"


async def test_login_devuelve_token(client: AsyncClient, admin_credentials: dict):
    """POST /auth/login con credenciales validas devuelve un token JWT."""
    respuesta = await client.post(URL_LOGIN, json=admin_credentials)
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert "access_token" in cuerpo
    assert cuerpo["token_type"] == "bearer"
    assert cuerpo["expires_in"] > 0


async def test_login_contrasena_incorrecta_devuelve_401(client: AsyncClient, admin_credentials: dict):
    """POST /auth/login con contrasena incorrecta devuelve 401."""
    respuesta = await client.post(
        URL_LOGIN,
        json={"email": admin_credentials["email"], "password": "contrasena_incorrecta"},
    )
    assert respuesta.status_code == 401


async def test_login_email_desconocido_devuelve_401(client: AsyncClient):
    """POST /auth/login con correo no registrado devuelve 401."""
    respuesta = await client.post(
        URL_LOGIN,
        json={"email": "nadie@ejemplo.com", "password": "contrasena123"},
    )
    assert respuesta.status_code == 401


async def test_me_devuelve_perfil_admin(client: AsyncClient, admin_credentials: dict):
    """GET /auth/me con token valido devuelve el perfil del administrador."""
    resp_login = await client.post(URL_LOGIN, json=admin_credentials)
    assert resp_login.status_code == 200
    token = resp_login.json()["access_token"]

    respuesta = await client.get(URL_ME, headers={"Authorization": f"Bearer {token}"})
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["email"] == admin_credentials["email"]
    assert cuerpo["is_admin"] is True
    assert "password" not in cuerpo
    assert "password_hash" not in cuerpo


async def test_me_sin_token_devuelve_401(client: AsyncClient):
    """GET /auth/me sin encabezado Authorization devuelve 401."""
    respuesta = await client.get(URL_ME)
    assert respuesta.status_code == 401


async def test_me_token_invalido_devuelve_401(client: AsyncClient):
    """GET /auth/me con token malformado devuelve 401."""
    respuesta = await client.get(URL_ME, headers={"Authorization": "Bearer tokeninvalido"})
    assert respuesta.status_code == 401


async def test_endpoint_registro_no_existe(client: AsyncClient):
    """POST /auth/register devuelve 404 — no existe registro publico."""
    respuesta = await client.post(
        URL_REGISTRO,
        json={"email": "nuevo@ejemplo.com", "username": "nuevousuario", "password": "contrasena123"},
    )
    assert respuesta.status_code == 404
