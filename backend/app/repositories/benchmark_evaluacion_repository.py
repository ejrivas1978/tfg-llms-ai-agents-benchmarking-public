"""
Modulo: benchmark_evaluacion_repository
Ruta:   backend/app/repositories/benchmark_evaluacion_repository.py

Descripcion:
    Repository para BenchmarkEvaluacion. Encapsula todas las queries SQLAlchemy
    relacionadas con las evaluaciones de benchmark.
    DECISION(ADR-003): El patron Repository desacopla la logica de negocio
    del ORM, facilitando los tests con mocks de la interfaz del repositorio.

Sprint: Sprint 2
"""

from datetime import datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.benchmark_evaluacion import BenchmarkEvaluacion
from app.models.enums import SessionStatus, TestCategory
from app.models.llm_response import LLMResponse
from app.models.user_evaluation import UserEvaluation


class BenchmarkEvaluacionRepository:
    """Repositorio de operaciones de base de datos para BenchmarkEvaluacion.

    Atributos:
        _db: Sesion asincrona de SQLAlchemy inyectada en cada peticion.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Inicializa el repositorio con la sesion de base de datos.

        Args:
            db: Sesion asincrona de SQLAlchemy.
        """
        self._db = db

    async def crear(
        self,
        nickname: str,
        prompt: str,
        categoria: TestCategory,
        es_generacion_imagen: bool = False,
        subcategoria_csv: str | None = None,
        texto_entrada: str | None = None,
        texto_entrada_autogenerado: bool = False,
    ) -> BenchmarkEvaluacion:
        """Crea una nueva evaluacion en estado pendiente.

        Args:
            nickname: Alias del evaluador anonimo.
            prompt: Texto del prompt.
            categoria: Categoria de la tarea.
            es_generacion_imagen: True si la evaluacion es de generacion de imagen
                (subcategorias generar, logotipo, modificar). False para describir
                imagen y todas las categorias de texto.
            subcategoria_csv: Etiqueta human-readable de la subcategoria seleccionada
                en la UI; se usa solo en el CSV de admin (no afecta runner ni metricas).
            texto_entrada: Texto original de entrada sin el prefijo de instruccion.
                Solo se persiste en resumen con texto autogenerado.
            texto_entrada_autogenerado: True si texto_entrada fue generado por LLM.

        Returns:
            Instancia de BenchmarkEvaluacion persistida y refrescada.
        """
        evaluacion = BenchmarkEvaluacion(
            nickname=nickname,
            prompt=prompt,
            category=categoria,
            es_generacion_imagen=es_generacion_imagen,
            subcategoria_csv=subcategoria_csv,
            texto_entrada=texto_entrada,
            texto_entrada_autogenerado=texto_entrada_autogenerado,
            status=SessionStatus.pendiente,
        )
        self._db.add(evaluacion)
        await self._db.flush()
        await self._db.refresh(evaluacion)
        return evaluacion

    async def obtener_por_id(self, evaluacion_id: int) -> BenchmarkEvaluacion | None:
        """Obtiene una evaluacion con todas sus respuestas cargadas.

        Args:
            evaluacion_id: Identificador de la evaluacion.

        Returns:
            BenchmarkEvaluacion con respuestas cargadas o None si no existe.
        """
        resultado = await self._db.execute(
            select(BenchmarkEvaluacion)
            .where(BenchmarkEvaluacion.id == evaluacion_id)
            .options(selectinload(BenchmarkEvaluacion.respuestas))
        )
        return resultado.scalar_one_or_none()

    async def listar_por_nickname(
        self,
        nickname: str,
        limite: int = 50,
        offset: int = 0,
    ) -> list[BenchmarkEvaluacion]:
        """Lista las evaluaciones de un evaluador anonimo ordenadas por fecha desc.

        Args:
            nickname: Alias del evaluador.
            limite: Numero maximo de resultados.
            offset: Desplazamiento para paginacion.

        Returns:
            Lista de BenchmarkEvaluacion (sin respuestas cargadas).
        """
        resultado = await self._db.execute(
            select(BenchmarkEvaluacion)
            .where(BenchmarkEvaluacion.nickname == nickname)
            .order_by(BenchmarkEvaluacion.created_at.desc())
            .limit(limite)
            .offset(offset)
        )
        return list(resultado.scalars().all())

    async def listar_historial_usuario(
        self,
        nickname: str,
        limite: int = 50,
    ) -> list[tuple[BenchmarkEvaluacion, bool]]:
        """Lista las evaluaciones de un usuario junto con el flag evaluada.

        Variante de listar_por_nickname que incluye si cada evaluacion tiene
        al menos una UserEvaluation enlazada. Permite que el frontend use la BD
        como fuente de verdad en lugar de depender del localStorage.

        Args:
            nickname: Alias del evaluador anonimo.
            limite: Maximo de resultados (por defecto 50).

        Returns:
            Lista de tuplas (BenchmarkEvaluacion, evaluada) ordenada por fecha desc.
        """
        evaluada_subq = (
            select(UserEvaluation.id)
            .join(LLMResponse, LLMResponse.id == UserEvaluation.response_id)
            .where(LLMResponse.evaluacion_id == BenchmarkEvaluacion.id)
            .correlate(BenchmarkEvaluacion)
            .exists()
        )
        resultado = await self._db.execute(
            select(BenchmarkEvaluacion, evaluada_subq.label("evaluada"))
            .where(func.lower(BenchmarkEvaluacion.nickname) == nickname.lower())
            .order_by(BenchmarkEvaluacion.created_at.desc())
            .limit(limite)
        )
        return [(row[0], bool(row[1])) for row in resultado.all()]

    async def listar_todas(
        self,
        limite: int = 10,
        offset: int = 0,
        nickname: str | None = None,
        categoria: TestCategory | None = None,
        prompt: str | None = None,
        estado: SessionStatus | None = None,
        evaluada: bool | None = None,
        fecha_desde: datetime | None = None,
        fecha_hasta: datetime | None = None,
    ) -> tuple[list[tuple[BenchmarkEvaluacion, bool]], int]:
        """Lista todas las evaluaciones con paginacion y filtros opcionales (solo admin).

        Incluye el flag evaluada: True si la evaluacion tiene al menos una
        UserEvaluation enlazada a traves de sus LLMResponse.

        Args:
            limite: Numero de evaluaciones por pagina.
            offset: Desplazamiento.
            nickname: Filtro parcial por nickname (ILIKE).
            categoria: Filtro exacto por categoria.
            prompt: Filtro parcial por texto del prompt (ILIKE).
            estado: Filtro exacto por estado.
            evaluada: True/False para filtrar por si tiene valoracion humana.
            fecha_desde: Filtro de fecha-hora de inicio (inclusive).
            fecha_hasta: Filtro de fecha-hora de fin (inclusive).

        Returns:
            Tupla (lista de (evaluacion, evaluada), total de registros filtrados).
        """
        # Subconsulta correlacionada: existe alguna evaluacion de usuario para esta evaluacion?
        evaluada_subq = (
            select(UserEvaluation.id)
            .join(LLMResponse, LLMResponse.id == UserEvaluation.response_id)
            .where(LLMResponse.evaluacion_id == BenchmarkEvaluacion.id)
            .correlate(BenchmarkEvaluacion)
            .exists()
        )

        # Construir condiciones de filtro
        condiciones = []
        if nickname:
            condiciones.append(BenchmarkEvaluacion.nickname.ilike(f'%{nickname}%'))
        if categoria:
            condiciones.append(BenchmarkEvaluacion.category == categoria)
        if prompt:
            condiciones.append(BenchmarkEvaluacion.prompt.ilike(f'%{prompt}%'))
        if estado:
            condiciones.append(BenchmarkEvaluacion.status == estado)
        if evaluada is True:
            condiciones.append(evaluada_subq)
        elif evaluada is False:
            condiciones.append(~evaluada_subq)
        if fecha_desde:
            # Si llega naive (sin tz), asumimos UTC (created_at se almacena en UTC).
            desde = fecha_desde if fecha_desde.tzinfo else fecha_desde.replace(tzinfo=timezone.utc)
            condiciones.append(BenchmarkEvaluacion.created_at >= desde)
        if fecha_hasta:
            hasta = fecha_hasta if fecha_hasta.tzinfo else fecha_hasta.replace(tzinfo=timezone.utc)
            condiciones.append(BenchmarkEvaluacion.created_at <= hasta)

        where_clause = and_(*condiciones) if condiciones else True

        total_res = await self._db.execute(
            select(func.count()).select_from(BenchmarkEvaluacion).where(where_clause)
        )
        total = total_res.scalar_one()

        evaluaciones_res = await self._db.execute(
            select(BenchmarkEvaluacion, evaluada_subq.label("evaluada"))
            .where(where_clause)
            .order_by(BenchmarkEvaluacion.created_at.desc())
            .limit(limite)
            .offset(offset)
        )
        return [(row[0], bool(row[1])) for row in evaluaciones_res.all()], total

    async def listar_para_export(
        self,
        nickname: str | None = None,
        categoria: TestCategory | None = None,
        prompt: str | None = None,
        estado: SessionStatus | None = None,
        evaluada: bool | None = None,
        fecha_desde: datetime | None = None,
        fecha_hasta: datetime | None = None,
    ) -> list[BenchmarkEvaluacion]:
        """Lista evaluaciones para exportacion CSV con respuestas y valoraciones eager.

        A diferencia de listar_todas, no aplica paginacion: devuelve todas las
        evaluaciones que coinciden con los filtros, con sus LLMResponse y las
        UserEvaluation 1:1 cargadas en una unica round-trip de queries para
        evitar el problema N+1 al iterar al construir el CSV.

        Args:
            nickname: Filtro parcial por nickname (ILIKE).
            categoria: Filtro exacto por categoria.
            prompt: Filtro parcial por texto del prompt (ILIKE).
            estado: Filtro exacto por estado.
            evaluada: True/False para filtrar por si tiene valoracion humana.
            fecha_desde: Filtro de fecha-hora de inicio (inclusive).
            fecha_hasta: Filtro de fecha-hora de fin (inclusive).

        Returns:
            Lista de BenchmarkEvaluacion con respuestas y evaluaciones cargadas,
            ordenadas por fecha de creacion descendente.
        """
        evaluada_subq = (
            select(UserEvaluation.id)
            .join(LLMResponse, LLMResponse.id == UserEvaluation.response_id)
            .where(LLMResponse.evaluacion_id == BenchmarkEvaluacion.id)
            .correlate(BenchmarkEvaluacion)
            .exists()
        )

        condiciones = []
        if nickname:
            condiciones.append(BenchmarkEvaluacion.nickname.ilike(f'%{nickname}%'))
        if categoria:
            condiciones.append(BenchmarkEvaluacion.category == categoria)
        if prompt:
            condiciones.append(BenchmarkEvaluacion.prompt.ilike(f'%{prompt}%'))
        if estado:
            condiciones.append(BenchmarkEvaluacion.status == estado)
        if evaluada is True:
            condiciones.append(evaluada_subq)
        elif evaluada is False:
            condiciones.append(~evaluada_subq)
        if fecha_desde:
            desde = fecha_desde if fecha_desde.tzinfo else fecha_desde.replace(tzinfo=timezone.utc)
            condiciones.append(BenchmarkEvaluacion.created_at >= desde)
        if fecha_hasta:
            hasta = fecha_hasta if fecha_hasta.tzinfo else fecha_hasta.replace(tzinfo=timezone.utc)
            condiciones.append(BenchmarkEvaluacion.created_at <= hasta)

        where_clause = and_(*condiciones) if condiciones else True

        resultado = await self._db.execute(
            select(BenchmarkEvaluacion)
            .where(where_clause)
            .options(
                selectinload(BenchmarkEvaluacion.respuestas).selectinload(
                    LLMResponse.evaluacion
                ),
                # Eager-load de la tarifa aplicada en cada respuesta para que
                # el exportador CSV pueda leer r.tarifa sin disparar I/O
                # (LLMResponse.tarifa esta declarado como lazy='raise').
                selectinload(BenchmarkEvaluacion.respuestas).selectinload(
                    LLMResponse.tarifa
                ),
            )
            .order_by(BenchmarkEvaluacion.created_at.desc())
        )
        return list(resultado.scalars().all())

    async def actualizar_estado(
        self,
        evaluacion: BenchmarkEvaluacion,
        estado: SessionStatus,
    ) -> BenchmarkEvaluacion:
        """Actualiza el estado de la evaluacion.

        Args:
            evaluacion: Instancia de BenchmarkEvaluacion a modificar.
            estado: Nuevo estado.

        Returns:
            Evaluacion con estado actualizado.
        """
        evaluacion.status = estado
        await self._db.flush()
        return evaluacion

    async def actualizar_jaccard(
        self,
        evaluacion: BenchmarkEvaluacion,
        valor: float | None,
    ) -> BenchmarkEvaluacion:
        """Actualiza la similitud Jaccard media de la evaluacion.

        Args:
            evaluacion: Instancia de BenchmarkEvaluacion.
            valor: Valor del indice Jaccard medio calculado.

        Returns:
            Evaluacion actualizada.
        """
        evaluacion.similitud_jaccard_media = valor
        await self._db.flush()
        return evaluacion

    async def contar_evaluaciones(self) -> int:
        """Devuelve el numero total de evaluaciones de benchmark.

        Returns:
            Total de registros en la tabla benchmark_evaluaciones.
        """
        resultado = await self._db.execute(
            select(func.count(BenchmarkEvaluacion.id))
        )
        return resultado.scalar_one()

    async def contar_evaluaciones_imagen_generativa(self) -> int:
        """Devuelve el total de evaluaciones de generacion de imagen (todos los estados).

        Incluye completadas y fallidas (rechazos por politica de contenido) para
        reflejar todos los intentos de generacion. Sin filtro de status para que
        texto_vision + imagen_generativa == total_evaluaciones.

        Returns:
            Total de evaluaciones con es_generacion_imagen=True.
        """
        resultado = await self._db.execute(
            select(func.count(BenchmarkEvaluacion.id))
            .where(BenchmarkEvaluacion.es_generacion_imagen.is_(True))
        )
        return resultado.scalar_one()

    async def contar_evaluadores(self) -> int:
        """Devuelve el numero de evaluadores anonimos distintos (nicknames unicos).

        Returns:
            Numero de nicknames distintos en la tabla benchmark_evaluaciones.
        """
        resultado = await self._db.execute(
            select(func.count(func.distinct(BenchmarkEvaluacion.nickname)))
        )
        return resultado.scalar_one()

    async def contar_evaluaciones_puntuadas(self) -> int:
        """Devuelve el numero de evaluaciones completadas con al menos una valoracion humana.

        Solo cuenta evaluaciones con status=completada que tengan UserEvaluation registradas.
        Las evaluaciones fallidas (con rechazo por politica de contenido) no se incluyen.

        Returns:
            Numero de evaluaciones con valoracion humana real.
        """
        resultado = await self._db.execute(
            select(func.count(func.distinct(BenchmarkEvaluacion.id)))
            .join(LLMResponse, LLMResponse.evaluacion_id == BenchmarkEvaluacion.id)
            .join(UserEvaluation, UserEvaluation.response_id == LLMResponse.id)
            .where(
                BenchmarkEvaluacion.status == SessionStatus.completada,
                UserEvaluation.rango_preferencia.isnot(None),
            )
        )
        return resultado.scalar_one()

    async def evaluaciones_por_semana(self) -> list[dict]:
        """Devuelve el conteo de evaluaciones completadas agrupadas por semana ISO.

        Filtra por status completada para que el grafico de progreso refleje
        evaluaciones con datos reales, no intentos fallidos que inflarian la actividad.
        Usa la funcion PostgreSQL to_char con formato IYYY-"W"IW para
        obtener el identificador de semana ISO 8601.

        Returns:
            Lista de dicts con semana (formato 'YYYY-WNN') y total.
        """
        resultado = await self._db.execute(
            select(
                func.to_char(BenchmarkEvaluacion.created_at, 'IYYY-"W"IW').label("semana"),
                func.count(BenchmarkEvaluacion.id).label("total"),
            )
            .where(BenchmarkEvaluacion.status == SessionStatus.completada)
            .group_by("semana")
            .order_by("semana")
        )
        return [row._asdict() for row in resultado.all()]

    async def evaluaciones_por_categoria(self) -> dict[str, int]:
        """Devuelve el conteo de evaluaciones completadas agrupadas por categoria.

        Filtra por status completada para que el donut del dashboard muestre
        la distribucion real de datos recogidos, excluyendo intentos fallidos
        que inflarian artificialmente categorias con mayor tasa de error.

        Returns:
            Diccionario {categoria: total} con todas las categorias presentes.
        """
        resultado = await self._db.execute(
            select(
                BenchmarkEvaluacion.category,
                func.count(BenchmarkEvaluacion.id).label("total"),
            )
            .where(BenchmarkEvaluacion.status == SessionStatus.completada)
            .group_by(BenchmarkEvaluacion.category)
        )
        return {row.category.value: row.total for row in resultado.all()}

    async def marcar_solicitud_borrado(
        self,
        evaluacion_id: int,
        nickname: str,
    ) -> BenchmarkEvaluacion:
        """Marca una evaluacion propia como pendiente de borrado por el admin.

        Cambia el status a solicitud_borrado para que el administrador lo vea
        en el panel de comparativas y proceda al borrado si lo considera adecuado.

        Args:
            evaluacion_id: ID de la evaluacion a marcar.
            nickname: Nick del usuario autenticado que solicita el borrado.

        Returns:
            Evaluacion con status solicitud_borrado.

        Raises:
            ValueError: Si la evaluacion no existe, no pertenece al usuario
                o ya tiene una solicitud de borrado activa.
        """
        evaluacion = await self.obtener_por_id(evaluacion_id)
        if evaluacion is None:
            raise ValueError("no_encontrada")
        if evaluacion.nickname != nickname:
            raise ValueError("sin_permiso")
        if evaluacion.status == SessionStatus.solicitud_borrado:
            raise ValueError("ya_solicitada")
        evaluacion.status = SessionStatus.solicitud_borrado
        await self._db.flush()
        return evaluacion

    async def eliminar(self, evaluacion: BenchmarkEvaluacion) -> None:
        """Elimina una evaluacion y todas sus respuestas (cascade).

        Args:
            evaluacion: Instancia de BenchmarkEvaluacion a eliminar.
        """
        await self._db.delete(evaluacion)
        await self._db.flush()

    async def eliminar_por_nickname(self, nickname: str) -> int:
        """Elimina todas las evaluaciones de un usuario identificado por su nickname.

        Cada evaluacion eliminada arrastra en cascade sus llm_responses y
        user_evaluations. Se usa al borrar un usuario del sistema.

        Args:
            nickname: Nick del usuario cuyas evaluaciones se eliminan.

        Returns:
            Numero de evaluaciones eliminadas.
        """
        resultado = await self._db.execute(
            select(BenchmarkEvaluacion).where(BenchmarkEvaluacion.nickname == nickname)
        )
        evaluaciones = list(resultado.scalars().all())
        for e in evaluaciones:
            await self._db.delete(e)
        await self._db.flush()
        return len(evaluaciones)

    async def eliminar_todas(self) -> int:
        """Elimina todas las evaluaciones del estudio (reset completo, solo admin).

        Returns:
            Numero de evaluaciones eliminadas.
        """
        resultado = await self._db.execute(select(BenchmarkEvaluacion))
        evaluaciones = list(resultado.scalars().all())
        for e in evaluaciones:
            await self._db.delete(e)
        await self._db.flush()
        return len(evaluaciones)
