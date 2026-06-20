"""
Modulo: test_router_benchmark
Ruta:   backend/tests/test_router_benchmark.py

Descripcion:
    Tests de integracion para los endpoints de benchmark publicos.

    Endpoints cubiertos:
    - GET  /api/v1/benchmarks/{id}
    - GET  /api/v1/benchmarks/imagen/descargar
    - POST /api/v1/benchmarks/run

Sprint: Sprint 4
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from httpx import AsyncClient

from app.core.database import get_db
from app.core.dependencies import get_actor_benchmark
from app.main import app
from app.models.enums import SessionStatus, TestCategory
from app.schemas.benchmark import RespuestaBenchmark


def _benchmark_dto(id: int = 1) -> RespuestaBenchmark:
    return RespuestaBenchmark(
        id=id,
        nickname="tester",
        prompt="prompt de prueba",
        categoria=TestCategory.razonamiento,
        estado=SessionStatus.completada,
        similitud_jaccard_media=0.75,
        created_at=datetime(2026, 5, 1, 10, 0, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 5, 1, 10, 1, 0, tzinfo=timezone.utc),
        respuestas=[],
    )


class TestRouterObtenerBenchmark:
    """Tests para GET /api/v1/benchmarks/{id}."""

    async def test_devuelve_benchmark_existente(self, client: AsyncClient):
        with patch("app.routers.benchmark.BenchmarkService") as mock_cls:
            mock_svc = AsyncMock()
            mock_svc.obtener_por_id = AsyncMock(return_value=_benchmark_dto(7))
            mock_cls.return_value = mock_svc

            respuesta = await client.get("/api/v1/benchmarks/7")

        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["id"] == 7
        assert cuerpo["nickname"] == "tester"

    async def test_benchmark_inexistente_lanza_404(self, client: AsyncClient):
        with patch("app.routers.benchmark.BenchmarkService") as mock_cls:
            mock_svc = AsyncMock()
            mock_svc.obtener_por_id = AsyncMock(side_effect=HTTPException(status_code=404))
            mock_cls.return_value = mock_svc

            respuesta = await client.get("/api/v1/benchmarks/9999")

        assert respuesta.status_code == 404

    async def test_no_requiere_auth(self, client: AsyncClient):
        with patch("app.routers.benchmark.BenchmarkService") as mock_cls:
            mock_svc = AsyncMock()
            mock_svc.obtener_por_id = AsyncMock(return_value=_benchmark_dto(1))
            mock_cls.return_value = mock_svc

            respuesta = await client.get("/api/v1/benchmarks/1")
        assert respuesta.status_code == 200


class TestRouterDescargarImagen:
    """Tests para GET /api/v1/benchmarks/imagen/descargar."""

    async def test_url_invalida_devuelve_400(self, client: AsyncClient):
        respuesta = await client.get(
            "/api/v1/benchmarks/imagen/descargar",
            params={"url": "ftp://no_es_http.com/img.png"},
        )
        assert respuesta.status_code == 400

    async def test_descarga_exitosa_devuelve_bytes(self, client: AsyncClient):
        mock_http = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.content = b"\xff\xd8\xff"  # cabecera JPEG minima
        mock_resp.headers = {"content-type": "image/jpeg"}
        mock_resp.raise_for_status = MagicMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.get = AsyncMock(return_value=mock_resp)

        with patch("app.routers.benchmark.httpx.AsyncClient", return_value=mock_http):
            respuesta = await client.get(
                "/api/v1/benchmarks/imagen/descargar",
                params={"url": "https://cdn.ejemplo.com/imagen.jpg"},
            )

        assert respuesta.status_code == 200
        assert respuesta.content == b"\xff\xd8\xff"

    async def test_proxy_falla_devuelve_502(self, client: AsyncClient):
        import httpx as httpx_mod

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.get = AsyncMock(side_effect=httpx_mod.ConnectError("timeout"))

        with patch("app.routers.benchmark.httpx.AsyncClient", return_value=mock_http):
            respuesta = await client.get(
                "/api/v1/benchmarks/imagen/descargar",
                params={"url": "https://cdn.ejemplo.com/imagen.jpg"},
            )

        assert respuesta.status_code == 502


class TestRouterEjecutarBenchmark:
    """Tests para POST /api/v1/benchmarks/run."""

    async def test_run_como_admin_devuelve_201(self, client: AsyncClient):
        """Admin (get_actor_benchmark -> None) ejecuta benchmark correctamente."""
        app.dependency_overrides[get_actor_benchmark] = lambda: None

        try:
            with patch("app.routers.benchmark.BenchmarkService") as mock_cls:
                mock_svc = AsyncMock()
                mock_svc.ejecutar = AsyncMock(return_value=_benchmark_dto(99))
                mock_cls.return_value = mock_svc

                respuesta = await client.post(
                    "/api/v1/benchmarks/run",
                    json={
                        "nickname": "admin",
                        "prompt": "prompt de prueba para el benchmark",
                        "categoria": "razonamiento",
                    },
                )
        finally:
            app.dependency_overrides.pop(get_actor_benchmark, None)

        assert respuesta.status_code == 201
        assert respuesta.json()["id"] == 99

    async def test_run_sin_auth_devuelve_401(self, client: AsyncClient):
        """Sin token JWT el rate-limiter aun pasa, pero el auth guard falla."""
        respuesta = await client.post(
            "/api/v1/benchmarks/run",
            json={
                "nickname": "anonimo",
                "prompt": "prompt",
                "categoria": "razonamiento",
            },
        )
        # Sin JWT el oauth2 scheme devuelve 401
        assert respuesta.status_code == 401

    async def test_run_cuota_agotada_devuelve_402(self, client: AsyncClient):
        from types import SimpleNamespace

        usuario_mock = SimpleNamespace(consultas_usadas=10, cuota_asignada=10)
        app.dependency_overrides[get_actor_benchmark] = lambda: usuario_mock

        try:
            with patch("app.routers.benchmark.BenchmarkService") as mock_cls:
                mock_svc = AsyncMock()
                mock_svc.ejecutar = AsyncMock(side_effect=HTTPException(status_code=402))
                mock_cls.return_value = mock_svc

                respuesta = await client.post(
                    "/api/v1/benchmarks/run",
                    json={
                        "nickname": "usuario_sin_cuota",
                        "prompt": "prompt",
                        "categoria": "razonamiento",
                    },
                )
        finally:
            app.dependency_overrides.pop(get_actor_benchmark, None)

        assert respuesta.status_code == 402
