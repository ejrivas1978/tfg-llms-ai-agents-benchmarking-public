"""
Modulo: tarifa_repository
Ruta:   backend/app/repositories/tarifa_repository.py

Descripcion:
    Repositorio para la tabla versionada tarifas_llm. Cada actualizacion
    crea una nueva fila (vigente=True) y marca la anterior del mismo
    proveedor como historica (vigente=False). El indice unico parcial
    ux_tarifas_llm_proveedor_vigente garantiza la invariante 'una unica
    tarifa vigente por proveedor'.

Sprint: Sprint 4
"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import LLMProvider
from app.models.tarifa_llm import TarifaLLM


class TarifaRepository:
    """Repositorio de operaciones sobre TarifaLLM versionado.

    Atributos:
        _db: Sesion asincrona de SQLAlchemy.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Inicializa el repositorio con la sesion de base de datos.

        Args:
            db: Sesion asincrona de SQLAlchemy.
        """
        self._db = db

    async def listar_vigentes(self) -> list[TarifaLLM]:
        """Devuelve solo las tarifas vigentes (vigente=True), ordenadas por proveedor.

        En operacion normal devuelve exactamente 4 filas, una por proveedor,
        gracias al indice unico parcial. Es lo que se muestra en la pestana
        Tarifas del panel admin y lo que carga el cache _PRECIOS_POR_MTOKEN.

        Returns:
            Lista de TarifaLLM vigentes ordenada por proveedor.
        """
        resultado = await self._db.execute(
            select(TarifaLLM)
            .where(TarifaLLM.vigente.is_(True))
            .order_by(TarifaLLM.proveedor)
        )
        return list(resultado.scalars().all())

    async def obtener_vigente(self, proveedor: LLMProvider) -> TarifaLLM | None:
        """Devuelve la tarifa vigente del proveedor indicado.

        Args:
            proveedor: Proveedor LLM.

        Returns:
            TarifaLLM vigente o None si no existe.
        """
        resultado = await self._db.execute(
            select(TarifaLLM).where(
                TarifaLLM.proveedor == proveedor,
                TarifaLLM.vigente.is_(True),
            )
        )
        return resultado.scalar_one_or_none()

    async def listar_historial(self, proveedor: LLMProvider) -> list[TarifaLLM]:
        """Devuelve todas las versiones (vigentes e historicas) de un proveedor.

        Ordenadas por actualizado_en descendente: la vigente queda arriba
        seguida de las versiones anteriores en orden cronologico inverso.

        Args:
            proveedor: Proveedor LLM.

        Returns:
            Lista de TarifaLLM del proveedor, recientes primero.
        """
        resultado = await self._db.execute(
            select(TarifaLLM)
            .where(TarifaLLM.proveedor == proveedor)
            .order_by(TarifaLLM.actualizado_en.desc(), TarifaLLM.id.desc())
        )
        return list(resultado.scalars().all())

    async def crear_nueva_version(
        self,
        proveedor: LLMProvider,
        precio_entrada: Decimal,
        precio_salida: Decimal,
        actualizado_por: str,
        precio_entrada_cacheado: Decimal | None = None,
        precio_imagen_generar: Decimal | None = None,
        precio_imagen_editar: Decimal | None = None,
    ) -> TarifaLLM:
        """Crea una nueva version vigente y marca la anterior como historica.

        Ejecuta dos operaciones en la misma transaccion:
          1. UPDATE de la vigente actual del proveedor: vigente=False.
          2. INSERT de la nueva fila con vigente=True.

        El orden es importante: si insertasemos primero, violariamos el
        indice unico parcial ux_tarifas_llm_proveedor_vigente. Al marcar
        primero la antigua como historica liberamos el slot 'vigente'
        para que la nueva pueda entrar.

        Args:
            proveedor: Proveedor LLM.
            precio_entrada: Nueva tarifa de entrada (USD/Mtok).
            precio_salida: Nueva tarifa de salida (USD/Mtok).
            actualizado_por: Nick del admin que crea la version.
            precio_entrada_cacheado: Tarifa para tokens servidos desde cache.
                None = sin descuento configurado (calcular_coste_usd cobra todo
                al precio base aunque la API devuelva cached_tokens > 0).

        Returns:
            TarifaLLM recien creada (vigente=True).
        """
        actual = await self.obtener_vigente(proveedor)
        if actual is not None:
            actual.vigente = False
            await self._db.flush()

        nueva = TarifaLLM(
            proveedor=proveedor,
            precio_entrada_usd_por_mtoken=precio_entrada,
            precio_salida_usd_por_mtoken=precio_salida,
            precio_entrada_cacheado_usd_por_mtoken=precio_entrada_cacheado,
            precio_imagen_generar_usd_por_imagen=precio_imagen_generar,
            precio_imagen_editar_usd_por_imagen=precio_imagen_editar,
            vigente=True,
            actualizado_en=datetime.now(timezone.utc),
            actualizado_por=actualizado_por,
        )
        self._db.add(nueva)
        await self._db.flush()
        await self._db.refresh(nueva)
        return nueva
