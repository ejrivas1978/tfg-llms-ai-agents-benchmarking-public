"""
Modulo: test_metricas
Ruta:   backend/tests/test_metricas.py

Descripcion:
    Tests unitarios para las funciones puras del modulo llm_engine/metricas.py.
    No requieren base de datos ni fixtures asincronas: son tests de caja blanca
    sobre funciones matematicas deterministicas.

Sprint: Sprint 2
"""

import pytest

from app.llm_engine.metricas import (
    calcular_coste_imagen_usd,
    calcular_coste_usd,
    calcular_metricas_texto,
    calcular_similitud_jaccard_media,
    generar_miniatura,
    jaccard_bigramas,
)
from app.models.enums import LLMProvider


class TestCalcularCosteUsd:
    """Pruebas para calcular_coste_usd."""

    def test_claude_calcula_correctamente(self):
        # 1000 tokens entrada a 3.00$/M + 500 tokens salida a 15.00$/M
        # = (1000 * 3.00 + 500 * 15.00) / 1_000_000 = 0.0105
        resultado = calcular_coste_usd(LLMProvider.claude, 1000, 500)
        assert resultado == pytest.approx(0.0105, abs=1e-7)

    def test_gemini_es_mas_barato_que_claude(self):
        coste_claude = calcular_coste_usd(LLMProvider.claude, 1000, 1000)
        coste_gemini = calcular_coste_usd(LLMProvider.gemini, 1000, 1000)
        assert coste_gemini < coste_claude

    def test_cero_tokens_devuelve_cero(self):
        assert calcular_coste_usd(LLMProvider.openai, 0, 0) == 0.0

    def test_resultado_redondeado_a_8_decimales(self):
        resultado = calcular_coste_usd(LLMProvider.grok, 1, 1)
        assert len(str(resultado).split(".")[-1]) <= 8


class TestCalcularCosteImagenUsd:
    """Pruebas para calcular_coste_imagen_usd."""

    def test_openai_devuelve_precio_imagen(self):
        assert calcular_coste_imagen_usd(LLMProvider.openai) == pytest.approx(0.04)

    def test_claude_no_soporta_imagen_devuelve_cero(self):
        assert calcular_coste_imagen_usd(LLMProvider.claude) == 0.0


class TestCalcularMetricasTexto:
    """Pruebas para calcular_metricas_texto."""

    def test_palabras_se_cuentan_correctamente(self):
        metricas = calcular_metricas_texto("uno dos tres", 10, 3, 1000, 0.001)
        assert metricas["palabras"] == 3

    def test_diversidad_lexica_texto_unico(self):
        # Todas las palabras distintas -> diversidad = 1.0
        metricas = calcular_metricas_texto("alfa beta gamma", 10, 3, 1000, 0.001)
        assert metricas["diversidad_lexica"] == pytest.approx(1.0)

    def test_diversidad_lexica_texto_repetido(self):
        # "a a a" -> 1 unica de 3 -> diversidad = 1/3
        metricas = calcular_metricas_texto("a a a", 10, 3, 1000, 0.001)
        assert metricas["diversidad_lexica"] == pytest.approx(1 / 3, abs=0.001)

    def test_tokens_por_segundo_se_calcula(self):
        # 100 tokens en 2000 ms = 50 t/s
        metricas = calcular_metricas_texto("texto de prueba", 10, 100, 2000, 0.001)
        assert metricas["tokens_por_segundo"] == pytest.approx(50.0)

    def test_texto_vacio_devuelve_ceros(self):
        metricas = calcular_metricas_texto("", 0, 0, 0, 0.0)
        assert metricas["palabras"] == 0
        assert metricas["diversidad_lexica"] == 0.0
        assert metricas["tokens_por_segundo"] == 0.0

    def test_parrafos_se_cuentan(self):
        texto = "Primer parrafo.\n\nSegundo parrafo.\n\nTercero."
        metricas = calcular_metricas_texto(texto, 10, 10, 1000, 0.001)
        assert metricas["parrafos"] == 3


class TestJaccardBigramas:
    """Pruebas para jaccard_bigramas."""

    def test_textos_identicos_devuelven_uno(self):
        assert jaccard_bigramas("hola mundo hoy", "hola mundo hoy") == 1.0

    def test_textos_sin_solapamiento_devuelven_cero(self):
        assert jaccard_bigramas("alfa beta gamma", "uno dos tres") == 0.0

    def test_solapamiento_parcial(self):
        # "a b c d" vs "b c d e"
        # bigramas1: {(a,b),(b,c),(c,d)}  bigramas2: {(b,c),(c,d),(d,e)}
        # interseccion: {(b,c),(c,d)} = 2, union: 4 -> 0.5
        resultado = jaccard_bigramas("a b c d", "b c d e")
        assert resultado == pytest.approx(0.5)

    def test_texto_de_una_sola_palabra_devuelve_cero(self):
        # Sin bigramas posibles
        assert jaccard_bigramas("hola", "hola mundo") == 0.0

    def test_insensible_a_mayusculas(self):
        assert jaccard_bigramas("Hola Mundo", "hola mundo") == 1.0

    def test_ambos_textos_una_palabra_devuelve_cero(self):
        """Ambos conjuntos de bigramas vacios: cubre la rama return 0.0."""
        assert jaccard_bigramas("hola", "mundo") == pytest.approx(0.0)

    def test_ambos_textos_vacios_devuelve_cero(self):
        assert jaccard_bigramas("", "") == pytest.approx(0.0)


# ── Tests: generar_miniatura ──────────────────────────────────────────────────


class TestGenerarMiniatura:
    """Pruebas para generar_miniatura (requiere Pillow)."""

    def _jpeg_bytes(self, ancho: int = 20, alto: int = 20) -> bytes:
        import io

        from PIL import Image

        img = Image.new("RGB", (ancho, alto), color=(200, 100, 50))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()

    def _png_rgba_bytes(self) -> bytes:
        import io

        from PIL import Image

        img = Image.new("RGBA", (10, 10), color=(0, 128, 255, 180))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def test_jpeg_valido_devuelve_cadena(self):
        resultado = generar_miniatura(self._jpeg_bytes())
        assert resultado is not None
        assert isinstance(resultado, str)
        assert len(resultado) > 0

    def test_resultado_es_base64_decodificable(self):
        import base64

        resultado = generar_miniatura(self._jpeg_bytes())
        decoded = base64.b64decode(resultado)
        assert len(decoded) > 0

    def test_png_con_alpha_se_convierte_a_rgb(self):
        """La conversion RGB evita errores al guardar como JPEG (sin canal alfa)."""
        resultado = generar_miniatura(self._png_rgba_bytes())
        assert resultado is not None

    def test_bytes_invalidos_devuelven_none(self):
        resultado = generar_miniatura(b"datos_invalidos_no_son_imagen")
        assert resultado is None

    def test_tamano_personalizado(self):
        resultado = generar_miniatura(self._jpeg_bytes(200, 200), tamano=50)
        assert resultado is not None


class TestCalcularSimilitudJaccardMedia:
    """Pruebas para calcular_similitud_jaccard_media."""

    def test_menos_de_dos_textos_devuelve_none(self):
        assert calcular_similitud_jaccard_media([]) is None
        assert calcular_similitud_jaccard_media(["texto"]) is None
        assert calcular_similitud_jaccard_media([None, None]) is None

    def test_ignora_textos_none(self):
        resultado = calcular_similitud_jaccard_media(["a b c", None, "a b c"])
        assert resultado == pytest.approx(1.0)

    def test_dos_textos_identicos(self):
        resultado = calcular_similitud_jaccard_media(["hola mundo hoy", "hola mundo hoy"])
        assert resultado == pytest.approx(1.0)

    def test_cuatro_textos_distintos(self):
        textos = ["alfa beta", "gamma delta", "epsilon zeta", "eta theta"]
        resultado = calcular_similitud_jaccard_media(textos)
        assert resultado is not None
        assert 0.0 <= resultado <= 1.0
