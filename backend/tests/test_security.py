"""
Modulo: test_security
Ruta:   backend/tests/test_security.py

Descripcion:
    Tests unitarios para las utilidades criptograficas del modulo core/security.py.
    Cubre hash/verificacion de contrasenas, creacion de JWT y decodificacion.
    No requieren base de datos: son funciones puras deterministicas.

Sprint: Sprint 4
"""

from datetime import timedelta

import pytest
from jose import JWTError

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class TestHashVerifyPassword:
    """Pruebas para hash_password y verify_password."""

    def test_hash_devuelve_cadena_bcrypt(self):
        """El hash generado comienza con el prefijo bcrypt estandar."""
        resultado = hash_password("mi_contrasena_segura")
        assert isinstance(resultado, str)
        assert resultado.startswith("$2b$")

    def test_verify_contrasena_correcta_devuelve_true(self):
        h = hash_password("secreto123")
        assert verify_password("secreto123", h) is True

    def test_verify_contrasena_incorrecta_devuelve_false(self):
        h = hash_password("secreto123")
        assert verify_password("otra_cosa", h) is False

    def test_verify_cadena_vacia_devuelve_false(self):
        h = hash_password("secreto123")
        assert verify_password("", h) is False

    def test_mismo_texto_produce_hashes_distintos(self):
        """bcrypt usa salt aleatorio: dos hashes del mismo texto no son iguales."""
        h1 = hash_password("igual")
        h2 = hash_password("igual")
        assert h1 != h2

    def test_ambos_hashes_verifican_correctamente(self):
        """Aunque los hashes sean distintos, ambos verifican la misma contrasena."""
        h1 = hash_password("igual")
        h2 = hash_password("igual")
        assert verify_password("igual", h1) is True
        assert verify_password("igual", h2) is True


class TestCreateAccessToken:
    """Pruebas para create_access_token."""

    def test_devuelve_cadena_no_vacia(self):
        token = create_access_token({"sub": "123"})
        assert isinstance(token, str)
        assert len(token) > 20

    def test_token_tiene_tres_segmentos_jwt(self):
        """Un JWT valido siempre tiene exactamente tres segmentos separados por puntos."""
        token = create_access_token({"sub": "1"})
        assert token.count(".") == 2

    def test_claim_tipo_usuario_app_incluido(self):
        token = create_access_token({"sub": "42", "tipo": "usuario_app"})
        payload = decode_access_token(token)
        assert payload["tipo"] == "usuario_app"

    def test_claim_sub_incluido(self):
        token = create_access_token({"sub": "99"})
        payload = decode_access_token(token)
        assert payload["sub"] == "99"

    def test_claim_exp_presente(self):
        token = create_access_token({"sub": "1"})
        payload = decode_access_token(token)
        assert "exp" in payload

    def test_duracion_personalizada_produce_exp_mayor(self):
        token_corto = create_access_token({"sub": "1"}, duracion=timedelta(hours=1))
        token_largo = create_access_token({"sub": "1"}, duracion=timedelta(hours=4))
        exp_corto = decode_access_token(token_corto)["exp"]
        exp_largo = decode_access_token(token_largo)["exp"]
        assert exp_largo > exp_corto

    def test_admin_no_incluye_claim_tipo(self):
        """El token de administrador no debe incluir el claim 'tipo'."""
        token = create_access_token({"sub": "admin@test.com"})
        payload = decode_access_token(token)
        assert "tipo" not in payload


class TestDecodeAccessToken:
    """Pruebas para decode_access_token."""

    def test_token_invalido_lanza_jwterror(self):
        with pytest.raises(JWTError):
            decode_access_token("token.completamente.invalido")

    def test_token_vacio_lanza_jwterror(self):
        with pytest.raises(JWTError):
            decode_access_token("")

    def test_token_expirado_lanza_jwterror(self):
        """Un token con duracion negativa ya esta expirado al crearse."""
        token = create_access_token({"sub": "1"}, duracion=timedelta(seconds=-1))
        with pytest.raises(JWTError):
            decode_access_token(token)

    def test_token_manipulado_lanza_jwterror(self):
        """Modificar cualquier parte del JWT invalida la firma."""
        token = create_access_token({"sub": "1"})
        partes = token.split(".")
        token_manipulado = partes[0] + ".MANIPULADO." + partes[2]
        with pytest.raises(JWTError):
            decode_access_token(token_manipulado)
