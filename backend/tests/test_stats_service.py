"""
Modulo: test_stats_service
Ruta:   backend/tests/test_stats_service.py

Descripcion:
    Tests unitarios para los metodos privados puros de StatsService.
    No requieren base de datos: todos los metodos probados operan sobre
    estructuras de datos Python y realizan calculos deterministicos.

    Metodos cubiertos:
    - _prov_valor: normalizacion de enums de proveedor
    - _combinar_metricas: join en Python de metricas LLM con ratings
    - _construir_heatmap: conversion de datos brutos a celdas de heatmap
    - _construir_metricas_imagen: agrupacion de metricas de imagen
    - _construir_ratings_imagen: lista de ratings de imagen generativa
    - _construir_tasa_rechazo: calculo de tasa = rechazos / total
    - _calcular_pares_jaccard: similitud media por par de proveedores

Sprint: Sprint 4
"""

from unittest.mock import MagicMock

import pytest

from app.models.enums import LLMProvider, TestCategory
from app.services.stats_service import StatsService, _prov_valor


def _servicio() -> StatsService:
    return StatsService(MagicMock())


# ── Tests: _prov_valor ────────────────────────────────────────────────────────


class TestProvValor:
    """Pruebas para la funcion auxiliar _prov_valor."""

    def test_enum_devuelve_su_value(self):
        assert _prov_valor(LLMProvider.claude) == "claude"
        assert _prov_valor(LLMProvider.openai) == "openai"

    def test_cadena_se_devuelve_sin_cambios(self):
        assert _prov_valor("gemini") == "gemini"
        assert _prov_valor("grok") == "grok"


# ── Tests: _combinar_metricas ─────────────────────────────────────────────────


class TestCombinarMetricas:
    """Pruebas para StatsService._combinar_metricas."""

    def _fila_llm(self, provider: str) -> dict:
        return {
            "provider": provider,
            "latencia_ms": 1200.0, "tokens_entrada": 100.0, "tokens_salida": 200.0,
            "tokens_por_segundo": 50.0, "cost_usd": 0.01, "coste_por_100_palabras": 0.005,
            "palabras": 150.0, "diversidad_lexica": 0.8, "parrafos": 3.0,
            "n": 10,
        }

    def test_longitud_igual_a_medias_llm(self):
        medias = [self._fila_llm("claude"), self._fila_llm("openai")]
        resultado = _servicio()._combinar_metricas(medias, [], [])
        assert len(resultado) == 2

    def test_rating_medio_none_cuando_no_hay_ratings(self):
        medias = [self._fila_llm("claude")]
        resultado = _servicio()._combinar_metricas(medias, [], [])
        assert resultado[0].rating_medio is None
        assert resultado[0].rango_preferencia_medio is None

    def test_rating_medio_se_asigna_cuando_existe(self):
        medias = [self._fila_llm("claude")]
        ratings = [{"provider": "claude", "rating_medio": 4.2, "n_puntuadas": 8}]
        resultado = _servicio()._combinar_metricas(medias, ratings, [])
        assert resultado[0].rating_medio == pytest.approx(4.2)
        assert resultado[0].n_puntuadas == 8

    def test_rango_preferencia_se_asigna_cuando_existe(self):
        medias = [self._fila_llm("claude")]
        ranking = [{"provider": "claude", "rango_medio": 1.5}]
        resultado = _servicio()._combinar_metricas(medias, [], ranking)
        assert resultado[0].rango_preferencia_medio == pytest.approx(1.5)

    def test_resultado_ordenado_por_proveedor(self):
        medias = [self._fila_llm("openai"), self._fila_llm("claude")]
        resultado = _servicio()._combinar_metricas(medias, [], [])
        # 'claude' < 'openai' alfabeticamente
        assert resultado[0].proveedor == LLMProvider.claude
        assert resultado[1].proveedor == LLMProvider.openai

    def test_n_evaluaciones_mapeado(self):
        medias = [self._fila_llm("gemini")]
        resultado = _servicio()._combinar_metricas(medias, [], [])
        assert resultado[0].n_evaluaciones == 10


# ── Tests: _construir_heatmap ─────────────────────────────────────────────────


class TestConstruirHeatmap:
    """Pruebas para StatsService._construir_heatmap."""

    def _fila(self, provider: str, categoria: TestCategory, rating: float, n: int) -> dict:
        return {"provider": provider, "categoria": categoria, "rating_medio": rating, "n": n}

    def test_longitud_igual_a_input(self):
        datos = [
            self._fila("claude", TestCategory.razonamiento, 4.0, 5),
            self._fila("openai", TestCategory.codigo, 3.5, 3),
        ]
        resultado = _servicio()._construir_heatmap(datos)
        assert len(resultado) == 2

    def test_lista_vacia_devuelve_lista_vacia(self):
        assert _servicio()._construir_heatmap([]) == []

    def test_ordenacion_por_proveedor_luego_categoria(self):
        datos = [
            self._fila("openai", TestCategory.codigo, 3.5, 2),
            self._fila("claude", TestCategory.razonamiento, 4.0, 5),
        ]
        resultado = _servicio()._construir_heatmap(datos)
        # claude < openai
        assert resultado[0].proveedor == LLMProvider.claude

    def test_rating_medio_none_cuando_falta(self):
        fila = {"provider": "claude", "categoria": TestCategory.libre, "rating_medio": None, "n": 0}
        resultado = _servicio()._construir_heatmap([fila])
        assert resultado[0].rating_medio is None


# ── Tests: _construir_metricas_imagen ─────────────────────────────────────────


class TestConstruirMetricasImagen:
    """Pruebas para StatsService._construir_metricas_imagen."""

    def _fila(self, provider: str, n: int = 5, lat: float = 3000.0, cost: float = 0.04) -> dict:
        return {"provider": provider, "n": n, "latencia_ms": lat, "cost_usd": cost}

    def test_longitud_igual_a_input(self):
        datos = [self._fila("openai"), self._fila("gemini")]
        resultado = _servicio()._construir_metricas_imagen(datos)
        assert len(resultado) == 2

    def test_lista_vacia_devuelve_lista_vacia(self):
        assert _servicio()._construir_metricas_imagen([]) == []

    def test_campos_mapeados_correctamente(self):
        datos = [self._fila("openai", n=7, lat=2500.0, cost=0.04)]
        resultado = _servicio()._construir_metricas_imagen(datos)
        assert resultado[0].proveedor == LLMProvider.openai
        assert resultado[0].n_evaluaciones == 7
        assert resultado[0].latencia_ms == pytest.approx(2500.0)
        assert resultado[0].cost_usd == pytest.approx(0.04)

    def test_ordenado_por_proveedor(self):
        datos = [self._fila("openai"), self._fila("gemini")]
        resultado = _servicio()._construir_metricas_imagen(datos)
        assert resultado[0].proveedor == LLMProvider.gemini
        assert resultado[1].proveedor == LLMProvider.openai


# ── Tests: _construir_ratings_imagen ─────────────────────────────────────────


class TestConstruirRatingsImagen:
    """Pruebas para StatsService._construir_ratings_imagen."""

    def test_rating_none_cuando_falta(self):
        datos = [{"provider": "grok", "rating_medio": None, "n": 3}]
        resultado = _servicio()._construir_ratings_imagen(datos)
        assert resultado[0].rating_medio is None

    def test_rating_mapeado_cuando_existe(self):
        datos = [{"provider": "openai", "rating_medio": 3.8, "n": 5}]
        resultado = _servicio()._construir_ratings_imagen(datos)
        assert resultado[0].rating_medio == pytest.approx(3.8)

    def test_ordenado_por_proveedor(self):
        datos = [
            {"provider": "openai", "rating_medio": 3.5, "n": 4},
            {"provider": "gemini", "rating_medio": 4.0, "n": 4},
        ]
        resultado = _servicio()._construir_ratings_imagen(datos)
        assert resultado[0].proveedor == LLMProvider.gemini


# ── Tests: _construir_tasa_rechazo ────────────────────────────────────────────


class TestConstruirTasaRechazo:
    """Pruebas para StatsService._construir_tasa_rechazo."""

    def test_tasa_se_calcula_correctamente(self):
        """4 rechazos de 17 total = 0.2353."""
        datos = [{"provider": "openai", "total": 17, "rechazos": 4}]
        resultado = _servicio()._construir_tasa_rechazo(datos)
        assert resultado[0].tasa == pytest.approx(4 / 17, abs=0.0001)
        assert resultado[0].total_participaciones == 17
        assert resultado[0].total_rechazos == 4

    def test_tasa_cero_cuando_sin_rechazos(self):
        datos = [{"provider": "gemini", "total": 10, "rechazos": 0}]
        resultado = _servicio()._construir_tasa_rechazo(datos)
        assert resultado[0].tasa == 0.0

    def test_tasa_cero_cuando_total_es_cero(self):
        """Division por cero protegida: total=0 devuelve tasa=0."""
        datos = [{"provider": "grok", "total": 0, "rechazos": None}]
        resultado = _servicio()._construir_tasa_rechazo(datos)
        assert resultado[0].tasa == 0.0

    def test_lista_vacia_devuelve_lista_vacia(self):
        assert _servicio()._construir_tasa_rechazo([]) == []

    def test_ordenado_por_proveedor(self):
        datos = [
            {"provider": "openai", "total": 10, "rechazos": 2},
            {"provider": "gemini", "total": 10, "rechazos": 1},
        ]
        resultado = _servicio()._construir_tasa_rechazo(datos)
        assert resultado[0].proveedor == LLMProvider.gemini


# ── Tests: _calcular_pares_jaccard ────────────────────────────────────────────


class TestCalcularParesJaccard:
    """Pruebas para StatsService._calcular_pares_jaccard."""

    def test_lista_vacia_devuelve_lista_vacia(self):
        assert _servicio()._calcular_pares_jaccard([]) == []

    def test_un_solo_proveedor_devuelve_lista_vacia(self):
        textos = [{"evaluacion_id": 1, "provider": "claude", "response_text": "hola mundo"}]
        assert _servicio()._calcular_pares_jaccard(textos) == []

    def test_textos_vacios_se_ignoran(self):
        textos = [
            {"evaluacion_id": 1, "provider": "claude", "response_text": ""},
            {"evaluacion_id": 1, "provider": "openai", "response_text": "   "},
        ]
        assert _servicio()._calcular_pares_jaccard(textos) == []

    def test_dos_proveedores_producen_un_par(self):
        textos = [
            {"evaluacion_id": 1, "provider": "claude", "response_text": "alfa beta gamma delta"},
            {"evaluacion_id": 1, "provider": "openai", "response_text": "alfa beta gamma delta"},
        ]
        resultado = _servicio()._calcular_pares_jaccard(textos)
        assert len(resultado) == 1
        assert resultado[0].proveedor_a == LLMProvider.claude
        assert resultado[0].proveedor_b == LLMProvider.openai

    def test_textos_identicos_jaccard_uno(self):
        texto = "alfa beta gamma delta epsilon"
        textos = [
            {"evaluacion_id": 1, "provider": "claude", "response_text": texto},
            {"evaluacion_id": 1, "provider": "openai", "response_text": texto},
        ]
        resultado = _servicio()._calcular_pares_jaccard(textos)
        assert resultado[0].jaccard_medio == pytest.approx(1.0)

    def test_multiples_evaluaciones_se_promedian(self):
        """Jaccard medio sobre dos evaluaciones: una identica (1.0) y una distinta (0.0)."""
        textos = [
            {"evaluacion_id": 1, "provider": "claude", "response_text": "alfa beta gamma"},
            {"evaluacion_id": 1, "provider": "openai", "response_text": "alfa beta gamma"},
            {"evaluacion_id": 2, "provider": "claude", "response_text": "uno dos tres"},
            {"evaluacion_id": 2, "provider": "openai", "response_text": "cuatro cinco seis"},
        ]
        resultado = _servicio()._calcular_pares_jaccard(textos)
        assert resultado[0].n == 2
        assert resultado[0].jaccard_medio == pytest.approx(0.5, abs=0.05)

    def test_pares_ordenados_alfabeticamente(self):
        """El par siempre se indexa con proveedor_a < proveedor_b alfabeticamente."""
        textos = [
            {"evaluacion_id": 1, "provider": "openai", "response_text": "texto de prueba aqui"},
            {"evaluacion_id": 1, "provider": "claude", "response_text": "texto de prueba aqui"},
        ]
        resultado = _servicio()._calcular_pares_jaccard(textos)
        # 'claude' < 'openai'
        assert resultado[0].proveedor_a.value < resultado[0].proveedor_b.value
