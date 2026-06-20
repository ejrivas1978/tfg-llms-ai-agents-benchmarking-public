"""
Modulo: user_evaluation_repository
Ruta:   backend/app/repositories/user_evaluation_repository.py

Descripcion:
    Repository para UserEvaluation. Gestiona la persistencia de las
    evaluaciones humanas y las consultas de agregacion de ratings.

Sprint: Sprint 2
"""

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.benchmark_evaluacion import BenchmarkEvaluacion
from app.models.enums import SessionStatus, TestCategory
from app.models.llm_response import LLMResponse
from app.models.user_evaluation import UserEvaluation


class UserEvaluationRepository:
    """Repositorio de operaciones de base de datos para UserEvaluation."""

    def __init__(self, db: AsyncSession) -> None:
        """Inicializa el repositorio con la sesion de base de datos.

        Args:
            db: Sesion asincrona de SQLAlchemy.
        """
        self._db = db

    async def crear(
        self,
        response_id: int,
        nickname: str,
        rating: int,
        rango_preferencia: int | None,
    ) -> UserEvaluation:
        """Persiste una nueva evaluacion del evaluador.

        Args:
            response_id: ID de la LLMResponse evaluada.
            nickname: Alias del evaluador.
            rating: Puntuacion del 1 al 5.
            rango_preferencia: Posicion ordinal de preferencia (1 = mejor).

        Returns:
            Instancia de UserEvaluation persistida.
        """
        evaluacion = UserEvaluation(
            response_id=response_id,
            nickname=nickname,
            rating=rating,
            rango_preferencia=rango_preferencia,
        )
        self._db.add(evaluacion)
        await self._db.flush()
        await self._db.refresh(evaluacion)
        return evaluacion

    async def obtener_por_response_id(self, response_id: int) -> UserEvaluation | None:
        """Obtiene la evaluacion asociada a una respuesta LLM si existe.

        Args:
            response_id: ID de la LLMResponse.

        Returns:
            UserEvaluation o None si la respuesta aun no ha sido evaluada.
        """
        resultado = await self._db.execute(
            select(UserEvaluation).where(UserEvaluation.response_id == response_id)
        )
        return resultado.scalar_one_or_none()

    async def obtener_por_evaluacion_id(self, evaluacion_id: int) -> list[UserEvaluation]:
        """Devuelve todas las evaluaciones de las respuestas de una evaluacion.

        Args:
            evaluacion_id: ID de la BenchmarkEvaluacion.

        Returns:
            Lista de UserEvaluation ordenada por rango_preferencia ascendente.
        """
        resultado = await self._db.execute(
            select(UserEvaluation)
            .join(LLMResponse, LLMResponse.id == UserEvaluation.response_id)
            .where(LLMResponse.evaluacion_id == evaluacion_id)
            .order_by(UserEvaluation.rango_preferencia.asc().nullslast())
        )
        return list(resultado.scalars().all())

    async def actualizar(
        self,
        evaluacion: UserEvaluation,
        rating: int,
        rango_preferencia: int | None,
    ) -> UserEvaluation:
        """Actualiza los campos de una evaluacion existente.

        Args:
            evaluacion: Instancia ORM a modificar.
            rating: Nueva puntuacion del 1 al 5.
            rango_preferencia: Nueva posicion ordinal de preferencia.

        Returns:
            Instancia de UserEvaluation actualizada.
        """
        evaluacion.rating = rating
        evaluacion.rango_preferencia = rango_preferencia
        await self._db.flush()
        await self._db.refresh(evaluacion)
        return evaluacion

    async def ratings_por_proveedor_y_categoria(self) -> list[dict]:
        """Devuelve la media de rating por (proveedor, categoria) para el heatmap.

        Solo evaluaciones completadas con valoracion de usuario (INNER JOIN UserEvaluation).
        Para la categoria imagen solo se incluyen evaluaciones de VISION (es_generacion_imagen=False),
        es decir 'describir imagen', que participa los 4 LLMs y produce texto.
        Las evaluaciones de generacion (generar/logotipo/modificar) se excluyen del heatmap porque
        ya disponen de su propia grafica en la seccion de imagen (ratings_generacion_imagen_por_proveedor).
        Se excluyen respuestas con error (tuvo_error=True) para evitar que el rating=1
        asignado automaticamente a fallos sesge la media hacia abajo por proveedor.

        Returns:
            Lista de dicts con proveedor, categoria, rating_medio y n.
        """
        resultado = await self._db.execute(
            select(
                LLMResponse.provider,
                BenchmarkEvaluacion.category.label("categoria"),
                func.avg(UserEvaluation.rating).label("rating_medio"),
                func.count(UserEvaluation.id).label("n"),
            )
            .join(UserEvaluation, UserEvaluation.response_id == LLMResponse.id)
            .join(BenchmarkEvaluacion, BenchmarkEvaluacion.id == LLMResponse.evaluacion_id)
            .where(
                LLMResponse.tuvo_error.is_(False),
                BenchmarkEvaluacion.status == SessionStatus.completada,
                or_(
                    BenchmarkEvaluacion.category != TestCategory.imagen,
                    BenchmarkEvaluacion.es_generacion_imagen.is_(False),
                ),
            )
            .group_by(LLMResponse.provider, BenchmarkEvaluacion.category)
        )
        return [row._asdict() for row in resultado.all()]

    async def ratings_generacion_imagen_por_proveedor(self) -> list[dict]:
        """Devuelve la media de rating por proveedor para evaluaciones de generacion de imagen.

        Solo subcategorias generar/logotipo/modificar (es_generacion_imagen=True).
        Alimenta la grafica de valoracion en la seccion de imagen del dashboard,
        independiente del heatmap general que muestra 'describir imagen' como Vision.
        Se excluyen respuestas con error (tuvo_error=True): los rechazos por politica
        de contenido ya tienen su propia grafica en tasa_rechazo_por_proveedor.

        Returns:
            Lista de dicts con provider, rating_medio y n.
        """
        resultado = await self._db.execute(
            select(
                LLMResponse.provider,
                func.avg(UserEvaluation.rating).label("rating_medio"),
                func.count(UserEvaluation.id).label("n"),
            )
            .join(UserEvaluation, UserEvaluation.response_id == LLMResponse.id)
            .join(BenchmarkEvaluacion, BenchmarkEvaluacion.id == LLMResponse.evaluacion_id)
            .where(
                LLMResponse.tuvo_error.is_(False),
                BenchmarkEvaluacion.status == SessionStatus.completada,
                BenchmarkEvaluacion.es_generacion_imagen.is_(True),
            )
            .group_by(LLMResponse.provider)
        )
        return [row._asdict() for row in resultado.all()]

    async def ranking_medio_por_proveedor(self) -> list[dict]:
        """Devuelve la posicion media de preferencia por proveedor (solo evaluaciones de texto completadas).

        Excluye evaluaciones de imagen para no mezclar el ranking de generacion visual
        con el de respuestas de texto, que son de naturaleza distinta.
        Solo evaluaciones completadas con valoracion del usuario (INNER JOIN UserEvaluation).

        Returns:
            Lista de dicts con provider, rango_medio y n.
            Excluye filas donde rango_preferencia es NULL (respuestas con error).
        """
        resultado = await self._db.execute(
            select(
                LLMResponse.provider,
                func.avg(UserEvaluation.rango_preferencia).label("rango_medio"),
                func.count(UserEvaluation.id).label("n"),
            )
            .join(UserEvaluation, UserEvaluation.response_id == LLMResponse.id)
            .join(BenchmarkEvaluacion, BenchmarkEvaluacion.id == LLMResponse.evaluacion_id)
            .where(
                UserEvaluation.rango_preferencia.isnot(None),
                BenchmarkEvaluacion.status == SessionStatus.completada,
                BenchmarkEvaluacion.es_generacion_imagen.is_(False),
            )
            .group_by(LLMResponse.provider)
        )
        return [row._asdict() for row in resultado.all()]

    async def ranking_generacion_imagen_por_proveedor(self) -> list[dict]:
        """Devuelve la posicion media de preferencia por proveedor en evaluaciones de imagen.

        Equivalente a ranking_medio_por_proveedor pero limitado a generacion de
        imagen (es_generacion_imagen=True). Permite comparar en la seccion de
        imagen del dashboard si el modelo mejor posicionado en el ranking coincide
        con el mejor valorado (rating), igual que en resultados totales agrupados.
        Solo evaluaciones completadas con rango asignado (no NULL); las respuestas
        con error no tienen rango y quedan fuera de forma natural.

        Returns:
            Lista de dicts con provider, rango_medio y n.
        """
        resultado = await self._db.execute(
            select(
                LLMResponse.provider,
                func.avg(UserEvaluation.rango_preferencia).label("rango_medio"),
                func.count(UserEvaluation.id).label("n"),
            )
            .join(UserEvaluation, UserEvaluation.response_id == LLMResponse.id)
            .join(BenchmarkEvaluacion, BenchmarkEvaluacion.id == LLMResponse.evaluacion_id)
            .where(
                UserEvaluation.rango_preferencia.isnot(None),
                BenchmarkEvaluacion.status == SessionStatus.completada,
                BenchmarkEvaluacion.es_generacion_imagen.is_(True),
            )
            .group_by(LLMResponse.provider)
        )
        return [row._asdict() for row in resultado.all()]

    async def metricas_humanas_imagen_por_subcategoria(self) -> list[dict]:
        """Rating y ranking medios por (subcategoria de imagen, proveedor).

        Cubre las cuatro opciones de la categoria imagen: generar, describir,
        logotipo y modificar. Alimenta el panel de imagen del dashboard que
        permite elegir una subcategoria y alternar entre valoracion media y
        ranking de preferencia. 'describir' (vision multimodal) incluye a Claude;
        las otras tres solo a los tres proveedores con imagen generativa.

        rating_medio excluye respuestas con error (tuvo_error=True) para no sesgar
        la calidad con los rechazos; rango_medio ignora los rango NULL de forma
        natural (las respuestas con error no tienen rango asignado).

        Returns:
            Lista de dicts con subcategoria, provider, rating_medio, rango_medio y n.
        """
        resultado = await self._db.execute(
            select(
                BenchmarkEvaluacion.subcategoria_csv.label("subcategoria"),
                LLMResponse.provider,
                func.avg(UserEvaluation.rating)
                .filter(LLMResponse.tuvo_error.is_(False))
                .label("rating_medio"),
                func.avg(UserEvaluation.rango_preferencia).label("rango_medio"),
                func.count(UserEvaluation.id).label("n"),
            )
            .join(UserEvaluation, UserEvaluation.response_id == LLMResponse.id)
            .join(BenchmarkEvaluacion, BenchmarkEvaluacion.id == LLMResponse.evaluacion_id)
            .where(
                BenchmarkEvaluacion.status == SessionStatus.completada,
                BenchmarkEvaluacion.subcategoria_csv.in_(
                    ("generar", "describir", "logotipo", "modificar")
                ),
            )
            .group_by(BenchmarkEvaluacion.subcategoria_csv, LLMResponse.provider)
        )
        return [row._asdict() for row in resultado.all()]

    async def ratings_por_proveedor(self) -> list[dict]:
        """Devuelve la media de rating por proveedor sobre evaluaciones de texto completadas.

        Excluye evaluaciones de imagen para evitar mezclar valoraciones de respuestas
        textuales con las de imagenes generadas, que tienen naturaleza distinta.
        Solo evaluaciones completadas con valoracion del usuario (INNER JOIN UserEvaluation).
        Se excluyen respuestas con error (tuvo_error=True) para evitar que el rating=1
        asignado automaticamente a fallos sesge la media: un proveedor con mas fallos
        no debe penalizarse en la metrica de calidad humana.
        Los ratings de imagen son visibles en el heatmap por categoria.

        Returns:
            Lista de dicts con proveedor, rating_medio y n_puntuadas.
        """
        resultado = await self._db.execute(
            select(
                LLMResponse.provider,
                func.avg(UserEvaluation.rating).label("rating_medio"),
                func.count(UserEvaluation.id).label("n_puntuadas"),
            )
            .join(UserEvaluation, UserEvaluation.response_id == LLMResponse.id)
            .join(BenchmarkEvaluacion, BenchmarkEvaluacion.id == LLMResponse.evaluacion_id)
            .where(
                LLMResponse.tuvo_error.is_(False),
                BenchmarkEvaluacion.status == SessionStatus.completada,
                BenchmarkEvaluacion.es_generacion_imagen.is_(False),
            )
            .group_by(LLMResponse.provider)
        )
        return [row._asdict() for row in resultado.all()]

    async def tasa_rechazo_por_proveedor(self) -> list[dict]:
        """Devuelve la tasa de rechazo por politica de contenido en evaluaciones de generacion de imagen.

        Solo se consideran evaluaciones con es_generacion_imagen=True (subcategorias generar,
        logotipo, modificar), que son las unicas en las que puede producirse un rechazo por
        politica de contenido. 'Describir imagen' (es_generacion_imagen=False) usa completar()
        y nunca se rechaza, por lo que excluirla del denominador es correcto.
        Claude queda excluido de forma natural al no participar en generacion de imagen.

        Denominador: numero de evaluaciones distintas (BenchmarkEvaluacion) con
                     es_generacion_imagen=True en las que participo cada proveedor.
        Numerador:   evaluaciones fallidas donde ese proveedor tuvo tuvo_error=True.

        Returns:
            Lista de dicts con provider, total y rechazos (solo proveedores de imagen generativa).
        """
        resultado = await self._db.execute(
            select(
                LLMResponse.provider,
                func.count(func.distinct(BenchmarkEvaluacion.id)).label("total"),
                func.sum(
                    case(
                        (
                            and_(
                                BenchmarkEvaluacion.status == SessionStatus.fallida,
                                LLMResponse.tuvo_error.is_(True),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("rechazos"),
            )
            .join(BenchmarkEvaluacion, BenchmarkEvaluacion.id == LLMResponse.evaluacion_id)
            .where(
                BenchmarkEvaluacion.status.in_(
                    [SessionStatus.completada, SessionStatus.fallida]
                ),
                BenchmarkEvaluacion.es_generacion_imagen.is_(True),
            )
            .group_by(LLMResponse.provider)
        )
        return [row._asdict() for row in resultado.all()]
