# ADR-020: Almacenamiento de miniaturas de imagen generativa para el historial

Estado: Aceptado
Fecha: 03/05/2026
Sprint: Sprint 4
DEF relacionada: ADR-016-dashboard-metricas-visualizacion.md

## Contexto

El estudio incluye evaluaciones de imagen generativa (categoría `imagen`) en las
que tres proveedores (OpenAI DALL-E 3, Gemini Imagen 4, Grok Aurora) generan una
imagen a partir de un prompt en lenguaje natural. El administrador puede consultar
el historial de comparativas en la pantalla de administración. Sin persistencia
explícita, las imágenes generadas no son accesibles desde el historial pasado
un tiempo:

- **OpenAI DALL-E 3** y **Grok Aurora**: devuelven una URL temporal firmada.
  Las URLs de OpenAI expiran en aproximadamente 1 hora. Las de Grok tienen
  caducidad similar. Pasado ese tiempo, cualquier consulta histórica muestra
  un enlace roto.
- **Gemini Imagen 4**: devuelve la imagen codificada en base64 directamente en
  la respuesta HTTP. El backend ya la almacena como data-URI en `response_text`.
  Sin embargo, una data-URI de una imagen 1024×1024 px ocupa ~1,4 MB, lo que
  hace costoso incluirla en listados paginados del historial.

## Opciones evaluadas

### Opción A — Miniatura en columna `imagen_miniatura` (base64 JPEG ~10-20 KB) ✓ Elegida

Al generar la imagen, descargar los bytes para todos los proveedores (GET a la
URL para OpenAI/Grok; decodificación base64 para Gemini), escalar a 200×200 px
con Pillow/LANCZOS y almacenar el JPEG resultante en base64 en una nueva columna
`TEXT` de `llm_responses`. El historial carga la miniatura directamente desde la
base de datos.

**Pros:**
- Miniatura siempre disponible aunque la URL original haya caducado.
- Tamaño manejable: ~12 KB por miniatura frente a ~1,4 MB de la imagen completa.
- Sin servicios externos; no aumenta la superficie de ataque.
- La descarga de la URL (para OpenAI/Grok) se hace inmediatamente después de la
  generación, cuando la URL está garantizadamente activa.

**Contras:**
- Añade Pillow como dependencia del backend.
- La descarga HTTP para OpenAI/Grok añade ~1-3 s al tiempo de ejecución del
  benchmark de imagen. Se acepta porque el benchmark ya tarda varias decenas
  de segundos en total.
- La imagen a resolución completa no queda almacenada. Esto es aceptable para
  el objetivo del historial (prueba visual de qué generó cada modelo), que no
  requiere resolución completa.

### Opción B — Imagen completa en `response_text` (base64, ~1,4 MB)

Descargar y almacenar la imagen completa como data-URI en `response_text` para
todos los proveedores.

**Descartada porque:** las queries del historial cargan todas las respuestas de
una evaluación en el detalle. Con 3 imágenes de ~1,4 MB cada una, el payload
HTTP del detalle superaría los 4 MB, lo que degrada la experiencia en conexiones
lentas y aumenta el coste de transferencia en Cloud Run.

### Opción C — Sin almacenamiento (URL caducable)

No almacenar la imagen; mostrar la URL mientras esté activa y un placeholder
"imagen expirada" cuando no.

**Descartada porque:** el historial es la fuente de evidencia del estudio para
el TFG. Las imágenes generadas son datos del experimento. Perder el acceso visual
pasada 1 hora hace inservible el historial para su propósito académico.

## Decisión

Se elige la **Opción A**. La columna `imagen_miniatura` almacena una miniatura
JPEG de 200×200 px en base64, generada en el momento de la llamada al proveedor
dentro del cliente LLM correspondiente.

## Implementación

### Cambios en el backend

- **`Pillow==11.2.1`** añadido a `requirements.txt`.
- **`metricas.py`**: nueva función `generar_miniatura(imagen_bytes, tamano=200)`
  que usa `Image.open → convert("RGB") → thumbnail → save(JPEG q=85)`. Devuelve
  base64 puro (sin prefijo data-URI). Maneja cualquier excepción de Pillow con
  `return None` para no abortar el benchmark si la miniatura falla.
- **`resultado.py`**: campo `imagen_miniatura: str | None = None` añadido a
  `ResultadoLLM`.
- **`clients/gemini_client.py`**: decodifica el base64 de la respuesta de Imagen 4
  y llama a `generar_miniatura()`.
- **`clients/openai_client.py`** y **`clients/grok_client.py`**: descarga la URL
  con `httpx.AsyncClient(timeout=30.0)` y llama a `generar_miniatura()`. La
  descarga está dentro de un `try/except` para que un fallo de red no propague
  error: la miniatura queda como `None` y el benchmark continúa.
- **`models/llm_response.py`**: columna `imagen_miniatura: Mapped[str | None]`
  de tipo `Text`, `nullable=True`.
- **`repositories/llm_response_repository.py`**: `crear_desde_resultado()` persiste
  `imagen_miniatura`.
- **`schemas/benchmark.py`**: campo `imagen_miniatura: str | None` en
  `RespuestaLLMDTO`.
- **`services/benchmark_service.py`**: `_construir_dto()` mapea `imagen_miniatura`
  desde el ORM al DTO.
- **Migración Alembic `c1d2e3f4a5b6`**: `ADD COLUMN imagen_miniatura TEXT` en
  `llm_responses`.

### Cambios en el frontend

- **`types/benchmark.ts`**: campo `imagen_miniatura: string | null` en
  `RespuestaLLM`.
- **`components/historial/TablaAdmin.tsx`** (`DetalleComparativaModal`): el card de
  respuesta distingue `r.es_imagen`. Si es imagen, muestra el `<img>` con
  `src="data:image/jpeg;base64,{r.imagen_miniatura}"` o el texto "Vista previa no
  disponible" si la miniatura es nula. Si es texto, muestra el scrollable de texto
  como antes.

## Consecuencias

Positivas:
- El historial de comparativas de imagen siempre muestra evidencia visual, sin
  depender de la vigencia de URLs externas.
- El tamaño de cada miniatura (~12 KB) es despreciable frente al payload total
  de las queries del historial.
- La lógica de descarga y generación de miniatura es no bloqueante para el
  benchmark: un fallo produce `None` sin afectar al resto de métricas.
- Pillow es una dependencia estándar y bien mantenida; no introduce riesgo de
  cadena de suministro significativo.

Trade-offs asumidos:
- La imagen a resolución completa no se almacena. Para los fines del TFG (comparar
  visualmente qué generó cada modelo) la miniatura es suficiente. Si en el futuro
  se necesitara la imagen completa, habría que añadir almacenamiento en GCS.
- La descarga de URLs de OpenAI/Grok añade latencia al benchmark de imagen
  (~1-3 s). Se acepta porque la latencia total de generación de imagen ya supera
  los 15-30 s y el usuario espera en la pantalla de carga.
- Las evaluaciones de imagen previas a esta migración tendrán `imagen_miniatura = NULL`
  y mostrarán "Vista previa no disponible". No es posible recuperar las imágenes
  de esas evaluaciones antiguas sin repetir el benchmark.
