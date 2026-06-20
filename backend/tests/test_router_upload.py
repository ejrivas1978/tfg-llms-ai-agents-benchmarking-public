"""
Modulo: test_router_upload
Ruta:   backend/tests/test_router_upload.py

Descripcion:
    Tests para el endpoint POST /api/v1/upload/extraer-texto y las
    funciones puras de extraccion (_truncar, _extraer_txt, _extraer_pdf, _extraer_docx).

Sprint: Sprint 4
"""

import io
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from httpx import AsyncClient

from app.routers.upload_router import (
    _extraer_docx,
    _extraer_pdf,
    _extraer_txt,
    _truncar,
)


# ── Tests: _truncar ───────────────────────────────────────────────────────────


class TestTruncar:
    """Pruebas para la funcion pura _truncar."""

    def test_texto_corto_no_se_trunca(self):
        texto, truncado = _truncar("uno dos tres", 100)
        assert texto == "uno dos tres"
        assert truncado is False

    def test_texto_exactamente_al_limite_no_se_trunca(self):
        palabras = " ".join(f"w{i}" for i in range(10))
        texto, truncado = _truncar(palabras, 10)
        assert truncado is False
        assert len(texto.split()) == 10

    def test_texto_largo_se_trunca(self):
        palabras = " ".join(f"w{i}" for i in range(20))
        texto, truncado = _truncar(palabras, 10)
        assert truncado is True
        assert len(texto.split()) == 10

    def test_texto_vacio_no_se_trunca(self):
        texto, truncado = _truncar("", 5)
        assert texto == ""
        assert truncado is False


# ── Tests: _extraer_txt ───────────────────────────────────────────────────────


class TestExtraerTxt:
    """Pruebas para _extraer_txt."""

    def test_utf8_se_decodifica(self):
        texto = "hola mundo con utf-8"
        assert _extraer_txt(texto.encode("utf-8")) == texto

    def test_latin1_se_decodifica(self):
        texto = "texto con caracteres latin1: \xe9\xe1\xf3"
        resultado = _extraer_txt(texto.encode("latin-1"))
        assert resultado is not None
        assert len(resultado) > 0

    def test_bytes_0x80_se_decodifican_por_latin1(self):
        """latin-1 cubre todo el rango 0x00-0xFF: nunca lanza 422."""
        resultado = _extraer_txt(bytes([0x80, 0x81, 0x82]))
        assert isinstance(resultado, str)


# ── Tests: _extraer_pdf ───────────────────────────────────────────────────────


class TestExtraerPdf:
    """Pruebas para _extraer_pdf (mockea pdfplumber)."""

    def test_pdf_valido_extrae_texto(self):
        pagina_mock = MagicMock()
        pagina_mock.extract_text.return_value = "contenido de la pagina"

        pdf_mock = MagicMock()
        pdf_mock.__enter__ = MagicMock(return_value=pdf_mock)
        pdf_mock.__exit__ = MagicMock(return_value=False)
        pdf_mock.pages = [pagina_mock]

        with patch("app.routers.upload_router.pdfplumber.open", return_value=pdf_mock):
            resultado = _extraer_pdf(b"pdf_bytes")

        assert "contenido de la pagina" in resultado

    def test_pdf_pagina_sin_texto_devuelve_vacio(self):
        pagina_mock = MagicMock()
        pagina_mock.extract_text.return_value = None

        pdf_mock = MagicMock()
        pdf_mock.__enter__ = MagicMock(return_value=pdf_mock)
        pdf_mock.__exit__ = MagicMock(return_value=False)
        pdf_mock.pages = [pagina_mock]

        with patch("app.routers.upload_router.pdfplumber.open", return_value=pdf_mock):
            resultado = _extraer_pdf(b"pdf_bytes")

        assert resultado == ""

    def test_pdf_corrupto_lanza_422(self):
        with patch("app.routers.upload_router.pdfplumber.open", side_effect=Exception("corrupto")):
            with pytest.raises(HTTPException) as exc:
                _extraer_pdf(b"datos_invalidos")
        assert exc.value.status_code == 422


# ── Tests: _extraer_docx ──────────────────────────────────────────────────────


class TestExtraerDocx:
    """Pruebas para _extraer_docx (mockea python-docx)."""

    def test_docx_valido_extrae_parrafos(self):
        parrafo1 = MagicMock()
        parrafo1.text = "Primer parrafo con contenido"
        parrafo2 = MagicMock()
        parrafo2.text = "Segundo parrafo"
        parrafo_vacio = MagicMock()
        parrafo_vacio.text = "   "

        doc_mock = MagicMock()
        doc_mock.paragraphs = [parrafo1, parrafo_vacio, parrafo2]

        with patch("app.routers.upload_router.docx.Document", return_value=doc_mock):
            resultado = _extraer_docx(b"docx_bytes")

        assert "Primer parrafo" in resultado
        assert "Segundo parrafo" in resultado

    def test_docx_corrupto_lanza_422(self):
        with patch("app.routers.upload_router.docx.Document", side_effect=Exception("fichero corrupto")):
            with pytest.raises(HTTPException) as exc:
                _extraer_docx(b"no_es_docx")
        assert exc.value.status_code == 422


# ── Tests: endpoint HTTP ──────────────────────────────────────────────────────


class TestEndpointExtraerTexto:
    """Tests de integracion para POST /api/v1/upload/extraer-texto."""

    async def test_txt_valido_devuelve_200(self, client: AsyncClient):
        contenido = "Este es el texto de prueba para el benchmark."
        respuesta = await client.post(
            "/api/v1/upload/extraer-texto",
            files={"archivo": ("documento.txt", contenido.encode("utf-8"), "text/plain")},
        )
        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert "texto" in cuerpo
        assert cuerpo["palabras"] > 0
        assert cuerpo["truncado"] is False

    async def test_extension_no_soportada_devuelve_415(self, client: AsyncClient):
        respuesta = await client.post(
            "/api/v1/upload/extraer-texto",
            files={"archivo": ("imagen.jpg", b"\xff\xd8\xff", "image/jpeg")},
        )
        assert respuesta.status_code == 415

    async def test_fichero_vacio_devuelve_422(self, client: AsyncClient):
        respuesta = await client.post(
            "/api/v1/upload/extraer-texto",
            files={"archivo": ("vacio.txt", b"   \n  ", "text/plain")},
        )
        assert respuesta.status_code == 422

    async def test_pdf_extrae_texto(self, client: AsyncClient):
        pagina = MagicMock()
        pagina.extract_text.return_value = "texto desde el PDF de prueba"
        pdf_mock = MagicMock()
        pdf_mock.__enter__ = MagicMock(return_value=pdf_mock)
        pdf_mock.__exit__ = MagicMock(return_value=False)
        pdf_mock.pages = [pagina]

        with patch("app.routers.upload_router.pdfplumber.open", return_value=pdf_mock):
            respuesta = await client.post(
                "/api/v1/upload/extraer-texto",
                files={"archivo": ("documento.pdf", b"pdf_bytes", "application/pdf")},
            )

        assert respuesta.status_code == 200
        assert "PDF" in respuesta.json()["texto"]

    async def test_texto_largo_se_trunca(self, client: AsyncClient):
        # 9000 palabras > LIMITE_PALABRAS (8000)
        contenido = " ".join(f"palabra{i}" for i in range(9000))
        respuesta = await client.post(
            "/api/v1/upload/extraer-texto",
            files={"archivo": ("largo.txt", contenido.encode("utf-8"), "text/plain")},
        )
        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["truncado"] is True
        assert cuerpo["palabras"] == 8000

    async def test_sin_extension_devuelve_415(self, client: AsyncClient):
        respuesta = await client.post(
            "/api/v1/upload/extraer-texto",
            files={"archivo": ("sin_extension", b"texto", "text/plain")},
        )
        assert respuesta.status_code == 415
