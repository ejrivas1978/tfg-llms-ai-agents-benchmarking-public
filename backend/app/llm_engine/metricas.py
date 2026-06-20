"""
Modulo: metricas
Ruta:   backend/app/llm_engine/metricas.py

Descripcion:
    Funciones puras para calcular las metricas automaticas del benchmark.
    No tienen efectos secundarios ni acceso a base de datos: solo reciben
    datos primitivos y devuelven valores numericos.

    DECISION(ADR-016): Se calculan 10 metricas por respuesta LLM:
        - Desde la API: tokens_entrada, tokens_salida, tuvo_error
        - Backend (tokens+tiempo): latency_ms, tokens_por_segundo,
          ratio_sal_ent, coste_usd, coste_por_100_palabras
        - Del texto: palabras, diversidad_lexica, parrafos
        - A nivel sesion: similitud_jaccard_media entre todas las respuestas

Sprint: Sprint 2
"""

import base64
import io
import logging

from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import LLMProvider

logger = logging.getLogger(__name__)

# Cache en memoria de la tarifa vigente de cada proveedor.
# Estructura: { proveedor: {"id": int|None, "entrada": float, "salida": float} }
#   - 'id'      = id de la fila vigente en tarifas_llm; se persiste en
#                 llm_responses.tarifa_id para trazabilidad historica.
#   - 'entrada' = USD por millon de tokens de prompt.
#   - 'salida'  = USD por millon de tokens de generacion.
#
# Defaults hardcoded usados como fallback cuando todavia no se ha hidratado
# desde BD (arranque temprano) o si la BD esta vacia. El id es None en este
# caso porque no hay fila persistida con la que enlazar; los clientes LLM
# guardaran tarifa_id=NULL para esas llamadas hasta que llegue el refresh.
#
# Los valores reales se sobreescriben con refrescar_cache_precios() al
# arrancar la app (lifespan main.py) y tras cada PUT del panel admin
# (TarifaService.actualizar_tarifa).
#
# Las respuestas LLM ya persistidas conservan su tarifa_id original aunque
# se cambien las tarifas: la trazabilidad historica se mantiene intacta.
#
# Valores iniciales (auditoria 13/05/2026 contra webs oficiales).
# Claves 'imagen_generar' / 'imagen_editar' = precio por imagen txt2img / img2img
# (None = el proveedor no soporta esa capacidad o no se ha configurado).
_PRECIOS_POR_MTOKEN: dict[LLMProvider, dict[str, float | int | None]] = {
    LLMProvider.claude: {"id": None, "entrada": 3.00, "salida": 15.00, "entrada_cacheado": 0.30,   "imagen_generar": None,  "imagen_editar": None},
    LLMProvider.openai: {"id": None, "entrada": 2.50, "salida": 10.00, "entrada_cacheado": 1.25,   "imagen_generar": 0.04,  "imagen_editar": 0.04},
    LLMProvider.gemini: {"id": None, "entrada": 0.30, "salida": 2.50,  "entrada_cacheado": 0.03,   "imagen_generar": 0.039, "imagen_editar": 0.039},
    LLMProvider.grok:   {"id": None, "entrada": 1.25, "salida": 2.50,  "entrada_cacheado": 0.625,  "imagen_generar": 0.02,  "imagen_editar": 0.05},
}


async def refrescar_cache_precios(db: AsyncSession) -> None:
    """Recarga _PRECIOS_POR_MTOKEN con las tarifas vigentes desde BD.

    Llamada en dos momentos:
      1. Al arrancar la aplicacion (lifespan en main.py).
      2. Tras cada actualizacion de tarifa desde el panel admin.

    Lee solo las filas con vigente=True (4 filas en operacion normal,
    gracias al indice unico parcial ux_tarifas_llm_proveedor_vigente).
    Guarda el id de cada fila vigente para que llm_responses pueda
    enlazar a la version exacta de tarifa usada en cada llamada LLM.

    Mutacion in-place del diccionario (.clear() + .update()) para que
    cualquier modulo que haya hecho 'from metricas import _PRECIOS_POR_MTOKEN'
    siga viendo los valores actualizados.

    Args:
        db: Sesion asincrona de SQLAlchemy.
    """
    from app.models.tarifa_llm import TarifaLLM  # import diferido (evita ciclo)

    resultado = await db.execute(
        select(TarifaLLM).where(TarifaLLM.vigente.is_(True))
    )
    filas = list(resultado.scalars().all())
    if not filas:
        logger.warning(
            "tarifas_llm vigentes vacio; manteniendo defaults hardcoded en metricas.py"
        )
        return

    nuevo: dict[LLMProvider, dict[str, float | int | None]] = {
        t.proveedor: {
            "id": t.id,
            "entrada": float(t.precio_entrada_usd_por_mtoken),
            "salida": float(t.precio_salida_usd_por_mtoken),
            "entrada_cacheado": (
                float(t.precio_entrada_cacheado_usd_por_mtoken)
                if t.precio_entrada_cacheado_usd_por_mtoken is not None
                else None
            ),
            "imagen_generar": (
                float(t.precio_imagen_generar_usd_por_imagen)
                if t.precio_imagen_generar_usd_por_imagen is not None
                else None
            ),
            "imagen_editar": (
                float(t.precio_imagen_editar_usd_por_imagen)
                if t.precio_imagen_editar_usd_por_imagen is not None
                else None
            ),
        }
        for t in filas
    }
    _PRECIOS_POR_MTOKEN.clear()
    _PRECIOS_POR_MTOKEN.update(nuevo)
    logger.info("Cache de tarifas LLM refrescada (%d proveedores vigentes)", len(nuevo))


def obtener_id_tarifa_vigente(proveedor: LLMProvider) -> int | None:
    """Devuelve el id de la tarifa vigente cacheada de un proveedor.

    Lo usan los clientes LLM tras calcular coste_usd para enlazar la
    respuesta con la version exacta de tarifa que se le aplico. Si el
    cache aun no se ha hidratado desde BD (arranque temprano) devuelve
    None y la respuesta se persiste con tarifa_id=NULL.

    Args:
        proveedor: Proveedor LLM.

    Returns:
        ID de la fila tarifas_llm vigente, o None si el cache no esta hidratado.
    """
    return _PRECIOS_POR_MTOKEN.get(proveedor, {}).get("id")  # type: ignore[return-value]

# El precio por imagen ya NO esta hardcoded en este modulo. Vive en la tabla
# versionada tarifas_llm con DOS columnas distintas
# (precio_imagen_generar_usd_por_imagen / precio_imagen_editar_usd_por_imagen)
# y se accede a traves del cache _PRECIOS_POR_MTOKEN[prov]['imagen_generar']
# o ['imagen_editar']. Auditoria 13/05/2026 contra webs oficiales:
#
# GENERAR (txt2img):
#   OpenAI  dall-e-3                   -> $0.04/img  (1024x1024 standard, deprecada)
#   Google  gemini-2.5-flash-image     -> ~$0.039/img (Nano Banana; sustituye a Imagen 4, ADR-034)
#   xAI     grok-imagine-image         -> $0.02/img
#
# EDITAR (img2img, con imagen de referencia):
#   OpenAI  gpt-image-1                -> ~$0.04/img (default quality, variable)
#   Google  gemini-2.5-flash-image     -> $0.039/img (1290 tok output, Nano Banana)
#   xAI     grok-imagine-image-quality -> $0.05/img
#
# Anthropic Claude no soporta imagen en ningun camino (ADR-011).


def calcular_coste_usd(
    proveedor: LLMProvider,
    tokens_entrada: int,
    tokens_salida: int,
    tokens_entrada_cacheados: int = 0,
) -> float:
    """Calcula el coste en USD aplicando el descuento de cache si procede.

    Formula:
        coste_in  = (tokens_entrada - cacheados) * precio_entrada
                  + cacheados * precio_entrada_cacheado
        coste     = (coste_in + tokens_salida * precio_salida) / 1_000_000

    Si la tarifa cacheada esta a None (no se ha configurado para el proveedor)
    o si la API no devolvio tokens cacheados (=0), la formula colapsa al
    calculo estandar (todo al precio de entrada normal). Esto garantiza
    compatibilidad hacia atras: si nadie configura precios cacheados, el
    sistema sigue cobrando como hasta ahora.

    He redondeado a 8 decimales para no perder precision en llamadas baratas
    (Gemini cuesta del orden de 0.000001 USD por llamada corta), pero sin
    acumular decimales irrelevantes en la representacion.

    Args:
        proveedor: Proveedor LLM para obtener la tarifa.
        tokens_entrada: Total de tokens del prompt (incluyendo cacheados).
        tokens_salida: Tokens del completado.
        tokens_entrada_cacheados: Subconjunto de tokens_entrada servidos
            desde cache (cache hit). 0 si la API no lo expone o no hubo hit.

    Returns:
        Coste estimado en USD redondeado a 8 decimales.
    """
    precios = _PRECIOS_POR_MTOKEN[proveedor]
    precio_in: float = precios["entrada"]            # type: ignore[assignment]
    precio_out: float = precios["salida"]            # type: ignore[assignment]
    precio_cached = precios.get("entrada_cacheado")  # float | None

    tokens_no_cacheados = max(0, tokens_entrada - tokens_entrada_cacheados)

    if precio_cached is not None and tokens_entrada_cacheados > 0:
        # Aplicamos el descuento solo si tenemos tarifa cacheada Y la API
        # confirmo cache hits. En cualquier otro caso cobramos todo al precio
        # de entrada estandar.
        coste_in = (
            tokens_no_cacheados * precio_in
            + tokens_entrada_cacheados * precio_cached
        )
    else:
        coste_in = tokens_entrada * precio_in

    coste = (coste_in + tokens_salida * precio_out) / 1_000_000
    return round(coste, 8)


def calcular_coste_imagen_usd(proveedor: LLMProvider, editar: bool = False) -> float:
    """Devuelve el coste fijo por imagen para el proveedor y modo dado.

    Lee del cache la clave 'imagen_generar' o 'imagen_editar' segun corresponda.
    Si la tarifa esta a None (Claude no soporta imagen, ADR-011; o un proveedor
    no soporta uno de los dos modos) devuelve 0.0; el resultado se persiste
    como LLMResponse.cost_usd = 0 y queda claro en CSV que no hubo cobro.

    Args:
        proveedor: Proveedor LLM con capacidad de imagen generativa.
        editar: True para imagen editar (img2img, ej. gemini-2.5-flash-image,
            grok-imagine-image-quality, gpt-image-1). False (default) para
            generar (txt2img, ej. dall-e-3, gemini-2.5-flash-image,
            grok-imagine-image).

    Returns:
        Coste en USD por imagen. 0.0 si el proveedor no tiene precio definido.
    """
    clave = "imagen_editar" if editar else "imagen_generar"
    precio = _PRECIOS_POR_MTOKEN.get(proveedor, {}).get(clave)
    return float(precio) if precio is not None else 0.0


def calcular_metricas_texto(
    texto: str,
    tokens_entrada: int,
    tokens_salida: int,
    latencia_ms: int,
    coste_usd: float,
) -> dict[str, float | int]:
    """Calcula las siete metricas derivadas del texto y de la relacion tokens/tiempo.

    He elegido palabras (split por espacio) como unidad base en lugar de caracteres
    porque es mas intuitiva para el usuario final y comparable entre modelos que
    usan tokenizaciones diferentes (BPE, SentencePiece, etc.). Un token de OpenAI
    equivale aprox. a 0.75 palabras, pero ese factor varia por idioma.

    La diversidad lexica (type-token ratio) mide que porcion del vocabulario
    de la respuesta es unico: 1.0 significa que no hay palabras repetidas (improbable
    en textos largos), 0.0 seria un texto identico de una sola palabra repetida.
    Es util para detectar respuestas muy repetitivas o boilerplate.

    Args:
        texto: Texto de la respuesta del LLM.
        tokens_entrada: Tokens del prompt.
        tokens_salida: Tokens del completado.
        latencia_ms: Latencia total de la llamada en milisegundos.
        coste_usd: Coste de la llamada ya calculado.

    Returns:
        Diccionario con tokens_por_segundo, ratio_sal_ent, coste_por_100_palabras,
        palabras, diversidad_lexica y parrafos.
    """
    lista_palabras = texto.split() if texto else []
    num_palabras = len(lista_palabras)

    # Diversidad lexica: palabras unicas / palabras totales.
    # He usado lower() para que 'El' y 'el' cuenten como la misma palabra.
    palabras_unicas = len(set(w.lower() for w in lista_palabras))
    diversidad = round(palabras_unicas / num_palabras, 4) if num_palabras > 0 else 0.0

    # Parrafos: lineas no vacias.
    num_parrafos = len([p for p in texto.split("\n") if p.strip()]) if texto else 0

    segundos = latencia_ms / 1000
    # tokens_por_segundo mide la velocidad de generacion del modelo, no la latencia
    # total. Es la metrica mas relevante para comparar velocidad entre proveedores.
    tps = round(tokens_salida / segundos, 2) if segundos > 0 else 0.0
    # ratio salida/entrada: indica si el modelo tiende a responder con mas o menos
    # tokens de los que recibio. Un ratio alto puede indicar verbosidad.
    ratio = round(tokens_salida / tokens_entrada, 4) if tokens_entrada > 0 else 0.0
    # Coste por 100 palabras: normalizo el coste por volumen de respuesta para poder
    # comparar el precio relativo entre proveedores independientemente de la longitud.
    coste_x100 = round(coste_usd / num_palabras * 100, 8) if num_palabras > 0 else 0.0

    return {
        "tokens_por_segundo": tps,
        "ratio_sal_ent": ratio,
        "coste_por_100_palabras": coste_x100,
        "palabras": num_palabras,
        "diversidad_lexica": diversidad,
        "parrafos": num_parrafos,
    }


def jaccard_bigramas(texto1: str, texto2: str) -> float:
    """Calcula el indice de Jaccard sobre bigramas de dos textos.

    He elegido bigramas en lugar de unigramas porque capturan mejor la similitud
    de frases: 'el gato' y 'el perro' tienen un unigrama en comun ('el') pero
    ningun bigrama en comun, lo que refleja mejor que son frases distintas.
    Con unigramas, textos muy diferentes podrian tener Jaccard alto simplemente
    por compartir articulos y preposiciones frecuentes.

    El indice de Jaccard mide similitud de conjuntos, no semantica:
    dos textos con el mismo vocabulario pero en orden muy distinto tendran
    bigramas diferentes y Jaccard bajo. Es una metrica lexica, no semantica.
    La he elegido por su simplicidad de interpretacion y coste computacional nulo.

    Args:
        texto1: Primer texto de respuesta.
        texto2: Segundo texto de respuesta.

    Returns:
        Valor entre 0.0 (sin solapamiento) y 1.0 (textos identicos).
    """
    palabras1 = texto1.lower().split()
    palabras2 = texto2.lower().split()
    # zip con desplazamiento: zip(lista, lista[1:]) genera todos los pares consecutivos.
    # Es el truco clasico para bigramas sin dependencias externas.
    bigramas1 = set(zip(palabras1, palabras1[1:]))
    bigramas2 = set(zip(palabras2, palabras2[1:]))
    if not bigramas1 and not bigramas2:
        return 0.0
    interseccion = bigramas1 & bigramas2
    union = bigramas1 | bigramas2
    return round(len(interseccion) / len(union), 4)


def generar_miniatura(imagen_bytes: bytes, tamano: int = 512) -> str | None:
    """Genera una miniatura JPEG en base64 a partir de los bytes de una imagen.

    He elegido JPEG para las miniaturas (no PNG) porque el objetivo es reducir
    el tamano en base de datos: JPEG a quality=85 da una imagen visualmente
    equivalente pero 3-5 veces mas pequena que PNG para fotografias.
    Las miniaturas se guardan en la columna imagen_miniatura de llm_responses
    (tipo Text en PostgreSQL), que no tiene limite de tamano practico, pero
    prefiero mantenerlas razonablemente compactas para no hinchar la BB.DD.

    He elegido 512px como lado maximo: suficiente para mostrar una previsualizacion
    nítida en el lightbox del historial cuando la URL del proveedor ha caducado
    (~1h en DALL-E 3 y grok-imagine-image). Genera un JPEG de aprox. 60-100 KB
    en base64. Para el volumen del estudio (~50-100 sesiones, 3-4 imagenes cada una)
    el impacto en base de datos es menor de 40 MB.

    LANCZOS (antiguo ANTIALIAS en Pillow) es el mejor filtro de reescalado
    para reducir imagenes: aplica un kernel anti-aliasing que evita el efecto
    pixelado que da el filtro por defecto (NEAREST).

    Convierto a RGB antes de guardar porque JPEG no soporta canal alfa (RGBA).
    Los PNGs generados por Imagen 4 de Google vienen en RGBA, y sin esta
    conversion Pillow lanzaria un error al intentar guardarlos como JPEG.

    Args:
        imagen_bytes: Bytes crudos de la imagen (PNG, JPEG o cualquier formato
                      soportado por Pillow).
        tamano: Lado maximo del thumbnail en pixeles. Por defecto 200.

    Returns:
        Cadena base64 del JPEG miniatura, o None si la conversion falla.
    """
    try:
        with Image.open(io.BytesIO(imagen_bytes)) as img:
            img = img.convert("RGB")
            img.thumbnail((tamano, tamano), Image.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85, optimize=True)
            return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as exc:
        logger.warning("No se pudo generar miniatura: %s", exc)
        return None


def calcular_similitud_jaccard_media(textos: list[str | None]) -> float | None:
    """Calcula la media del indice Jaccard entre todos los pares de textos validos.

    He calculado la similitud sobre todos los pares posibles (no solo pares
    consecutivos) para obtener una medida global de diversidad de respuestas.
    Con N textos validos hay N*(N-1)/2 pares. Para el caso habitual de 4
    proveedores son 6 pares, un numero manejable.

    Esta metrica es util para detectar si los modelos estan generando respuestas
    muy similares (Jaccard alto → poca diversidad) o muy distintas (Jaccard bajo).
    Un Jaccard medio alto puede indicar que el prompt esta muy guiado o que
    los modelos han memorizado la misma respuesta del training set.

    Args:
        textos: Lista de textos de respuesta (puede contener None para errores).

    Returns:
        Media del Jaccard sobre todos los pares, o None si hay menos de dos textos.
    """
    validos = [t for t in textos if t and t.strip()]
    if len(validos) < 2:
        return None
    similitudes = [
        jaccard_bigramas(validos[i], validos[j])
        for i in range(len(validos))
        for j in range(i + 1, len(validos))
    ]
    return round(sum(similitudes) / len(similitudes), 4)
