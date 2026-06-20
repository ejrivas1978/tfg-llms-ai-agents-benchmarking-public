"""
Modulo: admin_export_service
Ruta:   backend/app/services/admin_export_service.py

Descripcion:
    Servicio que serializa las evaluaciones del estudio en formato CSV.
    Una fila por LLMResponse en formato tidy/largo (estandar academico),
    con datos de la evaluacion padre denormalizados en cada fila para
    que el CSV sea autocontenido y se pueda cargar directamente en
    pandas, R o Excel sin necesidad de joins posteriores.

    DECISION(ADR-009): el CSV se genera en backend con el modulo csv
    estandar de Python en lugar de en frontend porque permite usar
    Numeric con precision decimal sin perdida y porque centraliza el
    contrato de columnas para que el formato no dependa del cliente.

    Por requisito explicito del responsable del TFG (reunion 2026-05-09)
    se omiten los campos de texto largo (prompt y response_text) para
    que el CSV sea legible directamente en Excel sin saltos de linea.

    Para evaluaciones de categoria=imagen se deriva una columna
    tipo_imagen ('generar' o 'describir') a partir del flag
    es_generacion_imagen, ya que la subcategoria (ADR-014) solo existe
    en la capa de presentacion del frontend.

    Formato CSV europeo (Revision 2026-05-14): delimitador ';' y coma
    decimal ','. Evita que Excel en locales con coma decimal interprete
    '3.00000000' como '300.000.000'. Para pandas / R hace falta pasar
    sep=';' y decimal=',' al leer el fichero.

Sprint: Sprint 4
"""

import csv
import io
from collections.abc import Iterator

from app.models.benchmark_evaluacion import BenchmarkEvaluacion
from app.models.enums import TestCategory


# Lista canonica de columnas del CSV, en el orden en el que se escriben.
# Cualquier cambio aqui debe reflejarse en la documentacion de ADR-009.
COLUMNAS_CSV: list[str] = [
    # Identificacion de la evaluacion
    "evaluacion_id",
    "nickname",
    "fecha_creacion",
    "fecha_completado",
    # Categorizacion
    "categoria",
    "subcategoria",
    "tipo_imagen",
    "estado",
    "similitud_jaccard_media",
    # Respuesta LLM
    "proveedor",
    "modelo",
    "idioma_prompt",
    "tuvo_error",
    "error_message",
    # Metricas API
    "input_tokens",
    "input_tokens_cached",
    "output_tokens",
    # Metricas calculadas
    "latencia_ms",
    "tokens_por_segundo",
    "ratio_sal_ent",
    "coste_usd",
    "coste_por_100_palabras",
    # Tarifa aplicada en el momento de la llamada (FK a tarifas_llm)
    "tarifa_id",
    "tarifa_precio_entrada_usd_por_mtoken",
    "tarifa_precio_salida_usd_por_mtoken",
    "tarifa_precio_entrada_cacheado_usd_por_mtoken",
    "tarifa_precio_imagen_generar_usd_por_imagen",
    "tarifa_precio_imagen_editar_usd_por_imagen",
    # Metricas del texto
    "palabras",
    "diversidad_lexica",
    "parrafos",
    # Evaluacion humana
    "valoracion_estado",
    "evaluador_nickname",
    "rating",
    "rango_preferencia",
    "fecha_evaluacion",
]


def _formatear_fecha(valor) -> str:  # type: ignore[no-untyped-def]
    """Convierte un datetime UTC a ISO 8601 (sin microsegundos) o cadena vacia."""
    if valor is None:
        return ""
    return valor.replace(microsecond=0).isoformat()


def _num(valor, decimales: int) -> str:  # type: ignore[no-untyped-def]
    """Formatea un numero con coma decimal estilo europeo.

    Devuelve cadena vacia para None y reemplaza el separador decimal '.' por
    ',' para que Excel en locales europeos (Espana, Francia, Alemania) no
    interprete por error '3.00000000' como '300.000.000' (3 mil millones).

    El CSV completo se escribe con delimitador ';' por la misma razon: es el
    formato CSV europeo estandar que Excel auto-importa sin pasos de mago de
    texto. Para consumirlo desde pandas o R hay que pasar 'decimal="," y
    'sep=";"' explicitamente (documentado en ADR-009).
    """
    if valor is None:
        return ""
    return f"{float(valor):.{decimales}f}".replace(".", ",")


def _derivar_tipo_imagen(evaluacion: BenchmarkEvaluacion) -> str:
    """Deriva la subcategoria de imagen para CSV.

    'generar' si es_generacion_imagen=True, 'describir' si False y la
    categoria es imagen, cadena vacia para categorias de texto.
    """
    if evaluacion.category != TestCategory.imagen:
        return ""
    return "generar" if evaluacion.es_generacion_imagen else "describir"


def generar_csv(evaluaciones: list[BenchmarkEvaluacion]) -> Iterator[bytes]:
    """Genera el contenido CSV como secuencia de bloques bytes.

    El primer bloque incluye el BOM UTF-8 (\\ufeff) para que Excel en Windows
    detecte el encoding correctamente y muestre caracteres acentuados sin
    necesidad de configuracion manual del usuario.

    Una fila por LLMResponse en formato tidy/largo: los datos de la
    BenchmarkEvaluacion padre se repiten en cada fila para que el CSV
    sea autocontenido.

    Args:
        evaluaciones: Lista de evaluaciones con respuestas y valoraciones
            cargadas eagerly (selectinload) para evitar N+1.

    Yields:
        Bloques bytes UTF-8 con BOM al inicio. Pensado para StreamingResponse.
    """
    buffer = io.StringIO()
    # Delimitador ';' + decimales con ',' = formato CSV europeo. Excel en
    # locales con coma decimal (es, fr, de) lo abre como tabla numerica sin
    # interpretar mal cifras como '3.00000000'. Para pandas/R: sep=';',
    # decimal=','.
    escritor = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL)

    # BOM UTF-8 para Excel + cabecera
    yield "﻿".encode("utf-8")
    escritor.writerow(COLUMNAS_CSV)
    yield buffer.getvalue().encode("utf-8")
    buffer.seek(0)
    buffer.truncate(0)

    for evaluacion in evaluaciones:
        tipo_imagen = _derivar_tipo_imagen(evaluacion)
        fecha_creacion = _formatear_fecha(evaluacion.created_at)
        fecha_completado = _formatear_fecha(evaluacion.completed_at)
        jaccard = _num(evaluacion.similitud_jaccard_media, 6)
        # Estado y categoria son enums: usamos .value para el texto plano.
        categoria = (
            evaluacion.category.value
            if hasattr(evaluacion.category, "value")
            else str(evaluacion.category)
        )
        estado = (
            evaluacion.status.value
            if hasattr(evaluacion.status, "value")
            else str(evaluacion.status)
        )

        for respuesta in evaluacion.respuestas:
            valoracion = respuesta.evaluacion  # 1:1 puede ser None
            # Estado explicito de valoracion para facilitar el filtrado en Excel:
            #   - 'no_aplica': el LLM fallo, no hay nada que valorar
            #   - 'valorada':  existe UserEvaluation enlazada
            #   - 'pendiente': el LLM respondio pero el humano no la valoro aun
            if respuesta.tuvo_error:
                valoracion_estado = "no_aplica"
            elif valoracion is not None:
                valoracion_estado = "valorada"
            else:
                valoracion_estado = "pendiente"
            proveedor = (
                respuesta.provider.value
                if hasattr(respuesta.provider, "value")
                else str(respuesta.provider)
            )
            # Tarifa aplicada: si la respuesta tiene tarifa_id sacamos los
            # precios congelados de aquel momento (no los vigentes hoy). Si
            # tarifa_id=NULL (caso de error de API o respuesta legacy sin
            # backfill) las celdas quedan vacias.
            tarifa = respuesta.tarifa
            tarifa_id_csv = respuesta.tarifa_id if respuesta.tarifa_id is not None else ""
            tarifa_entrada_csv = (
                _num(tarifa.precio_entrada_usd_por_mtoken, 8) if tarifa is not None else ""
            )
            tarifa_salida_csv = (
                _num(tarifa.precio_salida_usd_por_mtoken, 8) if tarifa is not None else ""
            )
            # Precio cacheado puede ser NULL en la version de tarifa: dejamos
            # celda vacia para indicar 'sin descuento configurado'.
            tarifa_cacheado_csv = (
                _num(tarifa.precio_entrada_cacheado_usd_por_mtoken, 8)
                if tarifa is not None
                else ""
            )
            # Precios por imagen: NULL para proveedores sin soporte (Claude
            # en ambos; algunos proveedores podrian no soportar uno de los dos).
            tarifa_imagen_gen_csv = (
                _num(tarifa.precio_imagen_generar_usd_por_imagen, 8)
                if tarifa is not None
                else ""
            )
            tarifa_imagen_edit_csv = (
                _num(tarifa.precio_imagen_editar_usd_por_imagen, 8)
                if tarifa is not None
                else ""
            )
            fila = [
                evaluacion.id,
                evaluacion.nickname,
                fecha_creacion,
                fecha_completado,
                categoria,
                evaluacion.subcategoria_csv or "",
                tipo_imagen,
                estado,
                jaccard,
                proveedor,
                respuesta.model_name,
                respuesta.idioma_prompt,
                "true" if respuesta.tuvo_error else "false",
                respuesta.error_message or "",
                respuesta.input_tokens,
                respuesta.input_tokens_cached,
                respuesta.output_tokens,
                respuesta.latency_ms,
                _num(respuesta.tokens_por_segundo, 4),
                _num(respuesta.ratio_sal_ent, 4),
                _num(respuesta.cost_usd, 8),
                _num(respuesta.coste_por_100_palabras, 8),
                tarifa_id_csv,
                tarifa_entrada_csv,
                tarifa_salida_csv,
                tarifa_cacheado_csv,
                tarifa_imagen_gen_csv,
                tarifa_imagen_edit_csv,
                respuesta.palabras,
                _num(respuesta.diversidad_lexica, 4),
                respuesta.parrafos,
                valoracion_estado,
                valoracion.nickname if valoracion else "",
                valoracion.rating if valoracion else "",
                valoracion.rango_preferencia
                if valoracion and valoracion.rango_preferencia is not None
                else "",
                _formatear_fecha(valoracion.created_at) if valoracion else "",
            ]
            escritor.writerow(fila)
            yield buffer.getvalue().encode("utf-8")
            buffer.seek(0)
            buffer.truncate(0)
