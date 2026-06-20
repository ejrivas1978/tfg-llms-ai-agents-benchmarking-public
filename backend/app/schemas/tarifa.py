"""
Modulo: schemas.tarifa
Ruta:   backend/app/schemas/tarifa.py

Descripcion:
    Esquemas Pydantic v2 para los endpoints de gestion de tarifas
    (panel admin). El backend devuelve los precios crudos y ademas los
    dos costes relativos calculados, para que el frontend no tenga que
    duplicar la formula.

    Versionado: cada fila tiene su propio id; las antiguas se conservan
    con vigente=False. El historial completo de un proveedor se obtiene
    por el endpoint GET /admin/tarifas/{proveedor}/historial.

Sprint: Sprint 4
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import LLMProvider


class TarifaDTO(BaseModel):
    """Tarifa vigente de un proveedor con costes relativos ya calculados.

    Atributos:
        id: ID de la fila en tarifas_llm. Util para mostrar la version
            actual y para vincular llm_responses.tarifa_id en el CSV.
        proveedor: Identificador del proveedor.
        precio_entrada_usd_por_mtoken: USD por millon de tokens de prompt.
        precio_salida_usd_por_mtoken: USD por millon de tokens de generacion.
        coste_relativo_entrada: Ratio frente al mas barato en entrada.
        coste_relativo_salida: Ratio frente al mas barato en salida.
        vigente: Siempre True en este DTO (es la vigente del proveedor),
            pero se incluye para uniformidad con HistorialTarifaItem.
        actualizado_en: Fecha de creacion de esta version (UTC).
        actualizado_por: Nick del admin que la creo (o 'seed').
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    proveedor: LLMProvider
    precio_entrada_usd_por_mtoken: Decimal
    precio_salida_usd_por_mtoken: Decimal
    # Precio editable para tokens de prompt servidos desde cache (cache hit).
    # None = sin descuento configurado: las llamadas cobran todo al precio base
    # aunque la API devuelva cached_tokens > 0.
    precio_entrada_cacheado_usd_por_mtoken: Decimal | None
    # Precio por imagen GENERADA desde texto (txt2img). None = no soporta o no
    # se ha configurado. Modelos: dall-e-3, gemini-2.5-flash-image,
    # grok-imagine-image. Claude=None (ADR-011).
    precio_imagen_generar_usd_por_imagen: Decimal | None
    # Precio por imagen EDITADA con imagen de referencia (img2img). None = no
    # soporta. Modelos: gpt-image-1, gemini-2.5-flash-image,
    # grok-imagine-image-quality.
    precio_imagen_editar_usd_por_imagen: Decimal | None
    coste_relativo_entrada: float
    coste_relativo_salida: float
    vigente: bool
    actualizado_en: datetime
    actualizado_por: str | None


class RespuestaListaTarifas(BaseModel):
    """Listado de tarifas vigentes devuelto por GET /admin/tarifas.

    Atributos:
        items: Las 4 tarifas vigentes con sus relativos.
        baseline_entrada_usd_por_mtoken: Tarifa minima de entrada usada como
            baseline para coste_relativo_entrada.
        baseline_salida_usd_por_mtoken: Tarifa minima de salida usada como
            baseline para coste_relativo_salida.
    """

    items: list[TarifaDTO]
    baseline_entrada_usd_por_mtoken: Decimal
    baseline_salida_usd_por_mtoken: Decimal


class PeticionActualizarTarifa(BaseModel):
    """Cuerpo de PUT /admin/tarifas/{proveedor}.

    Solo se permiten valores estrictamente positivos: una tarifa de 0 daria
    coste 0 y un baseline = 0 rompera la division del coste relativo.

    Atributos:
        precio_entrada_usd_por_mtoken: Nueva tarifa de entrada.
        precio_salida_usd_por_mtoken: Nueva tarifa de salida.
    """

    precio_entrada_usd_por_mtoken: Decimal = Field(..., gt=0, le=Decimal("9999.99999999"))
    precio_salida_usd_por_mtoken: Decimal = Field(..., gt=0, le=Decimal("9999.99999999"))
    # Si se omite (None), la nueva version queda sin descuento de cache: las
    # llamadas con cached_tokens > 0 cobraran todo al precio_entrada estandar.
    # Si se pasa, debe ser estrictamente positivo y normalmente menor que el
    # precio de entrada (un cache hit nunca cuesta MAS que un token nuevo).
    precio_entrada_cacheado_usd_por_mtoken: Decimal | None = Field(
        None, gt=0, le=Decimal("9999.99999999")
    )
    # Precio por imagen GENERADA (txt2img). None = no soporta / no se cobra.
    precio_imagen_generar_usd_por_imagen: Decimal | None = Field(
        None, gt=0, le=Decimal("9999.99999999")
    )
    # Precio por imagen EDITADA (img2img). None = no soporta / no se cobra.
    precio_imagen_editar_usd_por_imagen: Decimal | None = Field(
        None, gt=0, le=Decimal("9999.99999999")
    )


class HistorialTarifaItem(BaseModel):
    """Una version (vigente o historica) de la tarifa de un proveedor.

    Atributos:
        id: ID de la fila.
        proveedor: Identificador del proveedor.
        precio_entrada_usd_por_mtoken: USD/Mtok de entrada en esa version.
        precio_salida_usd_por_mtoken: USD/Mtok de salida en esa version.
        vigente: True si es la version actualmente vigente.
        actualizado_en: Cuando se creo la version.
        actualizado_por: Quien la creo ('seed' o nick admin).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    proveedor: LLMProvider
    precio_entrada_usd_por_mtoken: Decimal
    precio_salida_usd_por_mtoken: Decimal
    precio_entrada_cacheado_usd_por_mtoken: Decimal | None
    precio_imagen_generar_usd_por_imagen: Decimal | None
    precio_imagen_editar_usd_por_imagen: Decimal | None
    vigente: bool
    actualizado_en: datetime
    actualizado_por: str | None


class RespuestaHistorialTarifa(BaseModel):
    """Historial completo de versiones de tarifa de un proveedor.

    Atributos:
        proveedor: Proveedor del historial.
        items: Versiones ordenadas por fecha descendente (la vigente la primera).
    """

    proveedor: LLMProvider
    items: list[HistorialTarifaItem]
