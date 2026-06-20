"""
Modulo: test_runner
Ruta:   backend/tests/test_runner.py

Descripcion:
    Tests unitarios para el orquestador del motor LLM (runner.py).
    Los clientes LLM se sustituyen por mocks para evitar llamadas reales a la API.
    Se verifican el comportamiento de tolerancia a fallos parciales y el filtrado
    de clientes segun el tipo de tarea (texto vs imagen generativa).

Sprint: Sprint 2
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.llm_engine.resultado import ResultadoLLM
from app.llm_engine.runner import ejecutar_benchmark
from app.models.enums import LLMProvider


def _mock_cliente(proveedor: LLMProvider, soporta_imagen: bool = False) -> MagicMock:
    """Construye un mock de BaseLLMClient con proveedor y respuesta configurable."""
    cliente = MagicMock()
    cliente.proveedor = proveedor
    cliente.SOPORTA_IMAGEN = soporta_imagen
    return cliente


@pytest.mark.asyncio
class TestEjecutarBenchmark:
    """Pruebas para la funcion ejecutar_benchmark del runner."""

    async def test_devuelve_resultados_de_todos_los_clientes(self):
        clientes = [
            _mock_cliente(LLMProvider.claude),
            _mock_cliente(LLMProvider.openai),
        ]
        respuesta_claude = ResultadoLLM(proveedor=LLMProvider.claude, modelo="claude-3-5-sonnet")
        respuesta_openai = ResultadoLLM(proveedor=LLMProvider.openai, modelo="gpt-4o")
        clientes[0].completar = AsyncMock(return_value=respuesta_claude)
        clientes[1].completar = AsyncMock(return_value=respuesta_openai)

        resultados = await ejecutar_benchmark(clientes, "test prompt")

        assert len(resultados) == 2
        assert resultados[0].proveedor == LLMProvider.claude
        assert resultados[1].proveedor == LLMProvider.openai

    async def test_excepcion_se_convierte_en_resultado_con_error(self):
        cliente = _mock_cliente(LLMProvider.claude)
        cliente.completar = AsyncMock(side_effect=RuntimeError("fallo de red"))

        resultados = await ejecutar_benchmark([cliente], "test prompt")

        assert len(resultados) == 1
        assert resultados[0].tuvo_error is True
        assert "fallo de red" in resultados[0].mensaje_error

    async def test_fallo_parcial_no_cancela_otros_clientes(self):
        cliente_bueno = _mock_cliente(LLMProvider.openai)
        cliente_malo = _mock_cliente(LLMProvider.claude)
        respuesta_buena = ResultadoLLM(proveedor=LLMProvider.openai, modelo="gpt-4o")
        cliente_bueno.completar = AsyncMock(return_value=respuesta_buena)
        cliente_malo.completar = AsyncMock(side_effect=ConnectionError("timeout"))

        resultados = await ejecutar_benchmark([cliente_bueno, cliente_malo], "prompt")

        assert len(resultados) == 2
        exitosos = [r for r in resultados if not r.tuvo_error]
        fallidos = [r for r in resultados if r.tuvo_error]
        assert len(exitosos) == 1
        assert len(fallidos) == 1

    async def test_tarea_imagen_filtra_clientes_sin_soporte(self):
        cliente_texto = _mock_cliente(LLMProvider.claude, soporta_imagen=False)
        cliente_imagen = _mock_cliente(LLMProvider.openai, soporta_imagen=True)
        respuesta_imagen = ResultadoLLM(
            proveedor=LLMProvider.openai,
            modelo="dall-e-3",
            es_imagen=True,
        )
        cliente_imagen.generar_imagen = AsyncMock(return_value=respuesta_imagen)

        resultados = await ejecutar_benchmark(
            [cliente_texto, cliente_imagen], "un gato espacial", es_imagen=True
        )

        assert len(resultados) == 1
        assert resultados[0].proveedor == LLMProvider.openai
        # El cliente sin soporte de imagen no debe haber sido llamado
        cliente_texto.generar_imagen.assert_not_called() if hasattr(cliente_texto, "generar_imagen") else None

    async def test_lista_vacia_de_clientes_devuelve_lista_vacia(self):
        resultados = await ejecutar_benchmark([], "prompt")
        assert resultados == []


@pytest.mark.asyncio
class TestRutaVision:
    """Pruebas para ejecutar_benchmark con imagen_base64 (vision multimodal)."""

    async def test_llama_completar_con_imagen_base64(self):
        """Ruta vision: imagen_base64 presente, es_imagen=False -> completar() con imagen."""
        cliente = _mock_cliente(LLMProvider.claude)
        cliente.SOPORTA_VISION = True
        respuesta = ResultadoLLM(proveedor=LLMProvider.claude, modelo="claude-sonnet")
        cliente.completar = AsyncMock(return_value=respuesta)

        resultados = await ejecutar_benchmark(
            [cliente], "describe la imagen",
            imagen_base64="base64data",
            imagen_mime_type="image/jpeg",
        )

        assert len(resultados) == 1
        cliente.completar.assert_called_once_with(
            "describe la imagen",
            max_tokens=2048,
            imagen_base64="base64data",
            imagen_mime_type="image/jpeg",
        )

    async def test_excluye_clientes_sin_vision(self):
        con_vision = _mock_cliente(LLMProvider.claude)
        con_vision.SOPORTA_VISION = True
        con_vision.completar = AsyncMock(
            return_value=ResultadoLLM(proveedor=LLMProvider.claude, modelo="c")
        )
        sin_vision = _mock_cliente(LLMProvider.gemini)
        sin_vision.SOPORTA_VISION = False

        resultados = await ejecutar_benchmark(
            [con_vision, sin_vision], "describe",
            imagen_base64="imgdata",
        )

        assert len(resultados) == 1
        assert resultados[0].proveedor == LLMProvider.claude


@pytest.mark.asyncio
class TestRutaEdicionImagen:
    """Pruebas para ejecutar_benchmark con es_imagen=True + imagen_base64 (edicion)."""

    async def test_llama_editar_imagen_en_clientes_con_soporte(self):
        """Ruta edicion: es_imagen=True + imagen_base64 -> editar_imagen()."""
        cliente = _mock_cliente(LLMProvider.openai, soporta_imagen=True)
        respuesta = ResultadoLLM(proveedor=LLMProvider.openai, modelo="gpt-image-1", es_imagen=True)
        cliente.editar_imagen = AsyncMock(return_value=respuesta)

        resultados = await ejecutar_benchmark(
            [cliente], "anade un sombrero",
            es_imagen=True,
            imagen_base64="imgbase64",
            imagen_mime_type="image/png",
        )

        assert len(resultados) == 1
        cliente.editar_imagen.assert_called_once_with(
            "anade un sombrero", "imgbase64", "image/png"
        )

    async def test_excluye_clientes_sin_imagen_en_edicion(self):
        sin_imagen = _mock_cliente(LLMProvider.claude, soporta_imagen=False)

        resultados = await ejecutar_benchmark(
            [sin_imagen], "instruccion",
            es_imagen=True, imagen_base64="data",
        )

        assert resultados == []


class TestConstruirClientes:
    """Pruebas para la funcion construir_clientes."""

    def test_sin_keys_devuelve_lista_vacia(self):
        from app.llm_engine.runner import construir_clientes

        clientes = construir_clientes(None, None, None, None)
        assert clientes == []

    def test_con_key_anthropic_crea_cliente_claude(self):
        from app.llm_engine.runner import construir_clientes

        clientes = construir_clientes("sk-ant-test", None, None, None)
        assert len(clientes) == 1
        assert clientes[0].proveedor == LLMProvider.claude

    def test_con_key_openai_crea_cliente_openai(self):
        from app.llm_engine.runner import construir_clientes

        clientes = construir_clientes(None, "sk-oa-test", None, None)
        assert len(clientes) == 1
        assert clientes[0].proveedor == LLMProvider.openai

    def test_con_todas_las_keys_crea_cuatro_clientes(self):
        from app.llm_engine.runner import construir_clientes

        clientes = construir_clientes("sk-ant", "sk-oa", "gkey", "xkey")
        assert len(clientes) == 4
