"""
Modulo: test_router_evaluacion
Ruta:   backend/tests/test_router_evaluacion.py

Descripcion:
    Tests de integracion para los endpoints de evaluacion de respuestas LLM.
    Se mockea EvaluacionService para evitar accesos a tablas PostgreSQL.

    Endpoints cubiertos:
    - GET  /api/v1/evaluaciones/evaluacion/{id}
    - POST /api/v1/evaluaciones

Sprint: Sprint 4
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from httpx import AsyncClient

from app.schemas.evaluacion import RespuestaEvaluacion


def _evaluacion_dto(id: int = 1) -> RespuestaEvaluacion:
    return RespuestaEvaluacion(
        id=id,
        response_id=10,
        nickname="tester",
        rating=4,
        rango_preferencia=1,
        created_at=datetime(2026, 5, 1, 10, 0, 0, tzinfo=timezone.utc),
    )


class TestRouterObtenerEvaluaciones:
    """Tests para GET /api/v1/evaluaciones/evaluacion/{id}."""

    async def test_devuelve_lista_vacia(self, client: AsyncClient):
        with patch("app.routers.evaluacion.EvaluacionService") as mock_cls:
            mock_svc = AsyncMock()
            mock_svc.obtener_por_evaluacion = AsyncMock(return_value=[])
            mock_cls.return_value = mock_svc

            respuesta = await client.get("/api/v1/evaluaciones/evaluacion/1")

        assert respuesta.status_code == 200
        assert respuesta.json() == []

    async def test_devuelve_lista_con_evaluaciones(self, client: AsyncClient):
        with patch("app.routers.evaluacion.EvaluacionService") as mock_cls:
            mock_svc = AsyncMock()
            mock_svc.obtener_por_evaluacion = AsyncMock(
                return_value=[_evaluacion_dto(1), _evaluacion_dto(2)]
            )
            mock_cls.return_value = mock_svc

            respuesta = await client.get("/api/v1/evaluaciones/evaluacion/42")

        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert len(cuerpo) == 2
        assert cuerpo[0]["nickname"] == "tester"


class TestRouterCrearEvaluacion:
    """Tests para POST /api/v1/evaluaciones."""

    async def test_crea_evaluacion_devuelve_201(self, client: AsyncClient):
        with patch("app.routers.evaluacion.EvaluacionService") as mock_cls:
            mock_svc = AsyncMock()
            mock_svc.crear = AsyncMock(return_value=_evaluacion_dto(5))
            mock_cls.return_value = mock_svc

            respuesta = await client.post(
                "/api/v1/evaluaciones",
                json={
                    "response_id": 10,
                    "nickname": "tester",
                    "rating": 4,
                    "rango_preferencia": 1,
                },
            )

        assert respuesta.status_code == 201
        cuerpo = respuesta.json()
        assert cuerpo["id"] == 5
        assert cuerpo["rating"] == 4

    async def test_payload_invalido_devuelve_422(self, client: AsyncClient):
        respuesta = await client.post(
            "/api/v1/evaluaciones",
            json={"response_id": "no_es_numero", "nickname": "", "rating": 99},
        )
        assert respuesta.status_code == 422

    async def test_servicio_lanza_404_se_propaga(self, client: AsyncClient):
        with patch("app.routers.evaluacion.EvaluacionService") as mock_cls:
            mock_svc = AsyncMock()
            mock_svc.crear = AsyncMock(side_effect=HTTPException(status_code=404))
            mock_cls.return_value = mock_svc

            respuesta = await client.post(
                "/api/v1/evaluaciones",
                json={
                    "response_id": 999,
                    "nickname": "tester",
                    "rating": 3,
                    "rango_preferencia": 1,
                },
            )

        assert respuesta.status_code == 404

    async def test_rating_fuera_de_rango_devuelve_422(self, client: AsyncClient):
        """Rating > 5 viola la validacion del schema."""
        respuesta = await client.post(
            "/api/v1/evaluaciones",
            json={"response_id": 1, "nickname": "tester", "rating": 6},
        )
        assert respuesta.status_code == 422
