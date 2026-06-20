"""
Modulo: tarifa_service
Ruta:   backend/app/services/tarifa_service.py

Descripcion:
    Logica de negocio para la gestion de tarifas LLM versionadas (panel admin).

    Responsabilidades:
      - Listar las tarifas vigentes (4 filas) calculando los dos costes
        relativos (entrada y salida) frente al minimo de su columna.
      - Crear una nueva version de tarifa para un proveedor: marca la
        anterior como historica y refresca el cache en memoria que usa
        metricas.calcular_coste_usd().
      - Listar el historial completo de versiones de un proveedor.

Sprint: Sprint 4
"""

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm_engine.metricas import refrescar_cache_precios
from app.models.enums import LLMProvider
from app.models.tarifa_llm import TarifaLLM
from app.repositories.tarifa_repository import TarifaRepository
from app.schemas.tarifa import (
    HistorialTarifaItem,
    RespuestaHistorialTarifa,
    RespuestaListaTarifas,
    TarifaDTO,
)


class TarifaService:
    """Servicio de tarifas LLM versionadas con costes relativos y cache refresh.

    Atributos:
        _db: Sesion asincrona de SQLAlchemy.
        _repo: Repositorio de tarifas.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Inicializa el servicio con la sesion de base de datos.

        Args:
            db: Sesion asincrona de SQLAlchemy.
        """
        self._db = db
        self._repo = TarifaRepository(db)

    async def listar_con_relativos(self) -> RespuestaListaTarifas:
        """Devuelve las 4 tarifas vigentes con sus dos costes relativos calculados.

        coste_relativo_entrada = precio_entrada[p] / min(precio_entrada vigentes)
        coste_relativo_salida  = precio_salida[p]  / min(precio_salida vigentes)

        Returns:
            RespuestaListaTarifas con items vigentes + baselines usados.
        """
        vigentes = await self._repo.listar_vigentes()
        if not vigentes:
            return RespuestaListaTarifas(
                items=[],
                baseline_entrada_usd_por_mtoken=Decimal("0"),
                baseline_salida_usd_por_mtoken=Decimal("0"),
            )

        baseline_entrada = min(t.precio_entrada_usd_por_mtoken for t in vigentes)
        baseline_salida = min(t.precio_salida_usd_por_mtoken for t in vigentes)

        items = [
            TarifaDTO(
                id=t.id,
                proveedor=t.proveedor,
                precio_entrada_usd_por_mtoken=t.precio_entrada_usd_por_mtoken,
                precio_salida_usd_por_mtoken=t.precio_salida_usd_por_mtoken,
                precio_entrada_cacheado_usd_por_mtoken=t.precio_entrada_cacheado_usd_por_mtoken,
                precio_imagen_generar_usd_por_imagen=t.precio_imagen_generar_usd_por_imagen,
                precio_imagen_editar_usd_por_imagen=t.precio_imagen_editar_usd_por_imagen,
                coste_relativo_entrada=float(
                    t.precio_entrada_usd_por_mtoken / baseline_entrada
                ),
                coste_relativo_salida=float(
                    t.precio_salida_usd_por_mtoken / baseline_salida
                ),
                vigente=t.vigente,
                actualizado_en=t.actualizado_en,
                actualizado_por=t.actualizado_por,
            )
            for t in vigentes
        ]
        return RespuestaListaTarifas(
            items=items,
            baseline_entrada_usd_por_mtoken=baseline_entrada,
            baseline_salida_usd_por_mtoken=baseline_salida,
        )

    async def actualizar_tarifa(
        self,
        proveedor: LLMProvider,
        precio_entrada: Decimal,
        precio_salida: Decimal,
        actualizado_por: str,
        precio_entrada_cacheado: Decimal | None = None,
        precio_imagen_generar: Decimal | None = None,
        precio_imagen_editar: Decimal | None = None,
    ) -> TarifaLLM | None:
        """Crea una nueva version de tarifa y refresca el cache en memoria.

        Despues del commit, las llamadas LLM siguientes:
          - Calcularan coste_usd con los nuevos precios (via cache).
          - Persistiran llm_responses.tarifa_id apuntando a la nueva fila.
        Las respuestas LLM ya persistidas no se recalculan ni se reapuntan:
        siguen asociadas a la version de tarifa con la que se cobraron.

        Orden critico: commit ANTES de refrescar cache. Si refrescasemos
        antes, un commit fallido dejaria cache con valor nuevo y BD con
        valor viejo (cobrarian llamadas con precios no persistidos).

        Args:
            proveedor: Proveedor LLM a actualizar.
            precio_entrada: Nueva tarifa de entrada.
            precio_salida: Nueva tarifa de salida.
            actualizado_por: Nick del admin que hace el cambio.

        Returns:
            TarifaLLM recien creada como vigente. None si el proveedor no
            tenia ninguna fila previa (caso anomalo: en operacion normal
            siempre existen las 4 del seed).
        """
        # Si no hay tarifa previa para este proveedor, no hacemos nada:
        # significa que algo se sembro mal. Devolver None permite al router
        # responder 404.
        actual = await self._repo.obtener_vigente(proveedor)
        if actual is None:
            return None

        nueva = await self._repo.crear_nueva_version(
            proveedor=proveedor,
            precio_entrada=precio_entrada,
            precio_salida=precio_salida,
            actualizado_por=actualizado_por,
            precio_entrada_cacheado=precio_entrada_cacheado,
            precio_imagen_generar=precio_imagen_generar,
            precio_imagen_editar=precio_imagen_editar,
        )

        # Commit explicito antes del refresh para garantizar consistencia
        # cache<->BD. El doble commit con get_db (al cerrar la peticion)
        # es inocuo: el segundo encuentra la transaccion vacia.
        await self._db.commit()
        await refrescar_cache_precios(self._db)

        return nueva

    async def listar_historial(
        self, proveedor: LLMProvider
    ) -> RespuestaHistorialTarifa:
        """Devuelve todo el historial de versiones de un proveedor.

        Args:
            proveedor: Proveedor LLM.

        Returns:
            RespuestaHistorialTarifa con todas las versiones (recientes primero).
        """
        filas = await self._repo.listar_historial(proveedor)
        items = [
            HistorialTarifaItem(
                id=t.id,
                proveedor=t.proveedor,
                precio_entrada_usd_por_mtoken=t.precio_entrada_usd_por_mtoken,
                precio_salida_usd_por_mtoken=t.precio_salida_usd_por_mtoken,
                precio_entrada_cacheado_usd_por_mtoken=t.precio_entrada_cacheado_usd_por_mtoken,
                precio_imagen_generar_usd_por_imagen=t.precio_imagen_generar_usd_por_imagen,
                precio_imagen_editar_usd_por_imagen=t.precio_imagen_editar_usd_por_imagen,
                vigente=t.vigente,
                actualizado_en=t.actualizado_en,
                actualizado_por=t.actualizado_por,
            )
            for t in filas
        ]
        return RespuestaHistorialTarifa(proveedor=proveedor, items=items)
