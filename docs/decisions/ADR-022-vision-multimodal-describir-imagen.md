# ADR-022: Visión multimodal en la subcategoría "Describir imagen"

Estado: Aceptado
Fecha: 04/05/2026
Sprint: Sprint 4
ADRs relacionados: ADR-011-seleccion-automatica-modelos-por-tarea.md, ADR-014-subcategorias-capa-presentacion.md, ADR-021-carga-ficheros-resumen.md

## Contexto

La categoría imagen del benchmark incluye cuatro subcategorías: generar, describir,
logotipo y modificar. Las tres últimas distintas a "generar" requieren que el
evaluador proporcione una imagen de entrada o una descripción específica.

Hasta este punto la subcategoría "describir imagen" solo permitía introducir una URL
de imagen, que se concatenaba al prompt de texto y se enviaba como llamada de texto
puro a los modelos. Este enfoque tenía dos problemas graves:

1. **Routing incorrecto**: la categoría `imagen` en el backend activa la ruta
   `generar_imagen()` para todos los proveedores. El texto del prompt de "describir"
   llegaba a DALL-E 3 (OpenAI), Imagen 4 (Gemini) y Grok Imagine como si fuera una
   orden de generación, produciendo imágenes aleatorias o errores de política de
   contenidos.

2. **Sin capacidad visual real**: enviar una URL como texto plano a Claude o Grok
   no les permite ver la imagen. Solo GPT-4o puede acceder a URLs externas en su
   ventana de contexto, pero el comportamiento dependía de la disponibilidad de la URL
   y de los permisos CORS del servidor origen.

Se planteó incorporar carga de fichero de imagen con conversión base64 y envío
como mensaje multimodal a los modelos que soportan visión.

## Opciones evaluadas

### Opción A — URL en mensaje multimodal

Construir el mensaje de visión con `{"type":"image_url","image_url":{"url":"https://..."}}` 
para los modelos OpenAI-compatibles y análogo para Claude.

**Pros:**
- No requiere subir ningún fichero.
- El evaluador puede reutilizar imágenes ya publicadas en la web.

**Contras:**
- Claude no puede acceder a URLs externas en la API de mensajes (solo base64 o URLs
  de su propia infraestructura).
- Imágenes en redes privadas, intranets o con protección CORS son inaccesibles.
- La disponibilidad de la imagen en el momento de la llamada no está garantizada.
- Introduce latencia variable y dependencia de red externa durante el benchmark.
- Complica la reproducibilidad del estudio: la misma URL puede devolver contenido
  diferente o caducar antes de que el tribunal revise los resultados.

### Opción B — Carga de fichero con conversión base64 ✓ Elegida

El evaluador sube un fichero de imagen desde su dispositivo. El frontend lo convierte
a base64 mediante la API `FileReader` y lo envía en el cuerpo JSON del benchmark.
El backend pasa el dato a cada cliente LLM como mensaje multimodal.

**Pros:**
- Funciona con los cuatro modelos (incluido Claude, que solo acepta base64).
- Sin dependencias de red externas durante la llamada.
- Reproducibilidad total: la imagen queda fijada en el momento del análisis.
- No se almacena en la base de datos: el campo `imagen_base64` es transitorio,
  solo viaja en la petición HTTP.

**Contras:**
- El payload JSON puede ser grande (imagen de 5 MB → ~6,7 MB en base64).
- Requiere extender el schema `PeticionBenchmark` con dos campos nuevos.

## Decisión

Se elige la **Opción B**. La reproducibilidad del estudio y la compatibilidad
con todos los modelos pesan más que la comodidad de introducir una URL.
El límite de 5 MB es suficiente para imágenes de calidad razonable en pruebas
de análisis visual comparativo.

## Descubrimiento durante la implementación: routing de subcategoría

Al implementar el campo `imagen_base64`, se detectó un segundo bug estructural:
el backend determinaba la ruta de ejecución solo a partir de
`categoria == 'imagen'`, sin distinguir entre subcategorías. Esto hacía que
"describir" (con o sin fichero subido) siempre llamara a `generar_imagen()`.

**Solución**: se añadió el campo `subcat_imagen: str | None` a `PeticionBenchmark`.
Cuando `subcat_imagen == 'describir'`, el servicio usa `completar()` en todos
los modelos (incluido Claude) en lugar de `generar_imagen()`. La lógica en el
servicio es:

```python
es_descripcion = subcat_imagen == "describir" or bool(imagen_base64)
es_imagen = categoria == TestCategory.imagen and not es_descripcion
```

## Descubrimiento: soporte de visión por modelo

Durante las pruebas se comprobó que `grok-3` no acepta entradas multimodales
(`error 400 "Image inputs are not supported by this model"`). Se intentó usar
`grok-2-vision-1212` y `grok-2-vision-latest`, ambos devuelven `"Model not found"`.

Consultando el panel de modelos de console.x.ai, se constató que la cuenta solo
tiene disponibles modelos de la generación **Grok 4**: `grok-4.3`, `grok-4.20-*`,
`grok-4-1-*`. Los modelos `grok-2-*` y `grok-3` no están disponibles en la API
pública a 05/2026.

`grok-4.3` es el modelo flagship de xAI y unifica texto y visión en un único punto
de entrada. Usa el formato OpenAI-compat con texto primero e imagen después (data URI
base64). Solo admite JPG y PNG (no GIF ni WebP).

La tabla de soporte definitiva queda:

| Proveedor | Soporte visión | Modelo texto/visión | Formato entrada |
|-----------|---------------|---------------------|-----------------|
| Claude Sonnet 4.6 | ✅ | `claude-sonnet-4-6` | Anthropic base64 |
| GPT-4o | ✅ | `gpt-4o` | data URI OpenAI |
| Gemini 2.5 Flash | ✅ | `gemini-2.5-flash` | data URI OpenAI-compat |
| Grok 4.3 | ✅ | `grok-4.3` | data URI OpenAI-compat (jpg/png) |

**Implementación**: `GrokClient` usa `grok-4.3` tanto para `_MODELO_TEXTO` como para
`_MODELO_VISION`, ya que el mismo modelo gestiona ambas modalidades.

## Implementación

### Backend

**`backend/app/schemas/benchmark.py`**:
- `PeticionBenchmark.imagen_base64: str | None = Field(None)` — base64 sin prefijo data-URI
- `PeticionBenchmark.imagen_mime_type: str | None = Field(None)` — ej. `image/jpeg`
- `PeticionBenchmark.subcat_imagen: str | None = Field(None)` — para distinguir describir de generar

**`backend/app/llm_engine/clients/base_client.py`**:
- `completar()` acepta `imagen_base64` e `imagen_mime_type` (opcionales).

**`backend/app/llm_engine/clients/claude_client.py`**:
- Construye mensaje multimodal Anthropic cuando `imagen_base64` está presente:
  `[{"type":"image","source":{"type":"base64","media_type":mime,"data":b64}}, {"type":"text","text":prompt}]`

**`backend/app/llm_engine/clients/openai_client.py`** y **`gemini_client.py`**:
- Construyen mensaje multimodal OpenAI-compat:
  `[{"type":"image_url","image_url":{"url":"data:mime;base64,b64"}}, {"type":"text","text":prompt}]`

**`backend/app/llm_engine/clients/grok_client.py`**:
- `_MODELO_TEXTO = _MODELO_VISION = "grok-4.3"` — mismo modelo unifica texto y visión.
- Mismo formato OpenAI-compat que OpenAI y Gemini (texto primero, imagen después).

**`backend/app/llm_engine/runner.py`**:
- Tres ramas de ejecución:
  1. `imagen_base64` presente → `completar()` multimodal en todos los clientes.
  2. `es_imagen=True` (generar/logotipo/modificar) → `generar_imagen()` en SOPORTA_IMAGEN.
  3. Resto → `completar()` texto puro.

**`backend/app/services/benchmark_service.py`** y **`routers/benchmark.py`**:
- Propagan `imagen_base64`, `imagen_mime_type` y `subcat_imagen` por la cadena.

### Frontend

**`frontend/src/types/benchmark.ts`**:
- `PeticionBenchmark` extendida con `imagen_base64?`, `imagen_mime_type?`, `subcat_imagen?`.

**`frontend/src/components/benchmark/SubcatPanel.tsx`**:
- Nuevas props: `onImagenChange` y `onSubcatImagenChange`.
- `elegirOpImagen(id)` llama `onSubcatImagenChange(id)`.
- Subpanel "describir": solo botón `📸 Subir imagen` (el input URL fue eliminado).
- `manejarImagenDescribir`: `FileReader.readAsDataURL()` → extrae base64 y MIME type → llama `onImagenChange(b64, mime)`.
- Validación: máximo 5 MB, formatos `.jpg .jpeg .png` (GIF y WebP excluidos por restricción de Grok 4.3).
- Preview thumbnail 56×56 px de la imagen subida.

**`frontend/src/pages/BenchmarkPage.tsx`**:
- Estados `imagenBase64`, `imagenMimeType`, `subcatImagen`.
- Mutación incluye los tres campos en el cuerpo JSON.
- `cambiarCategoria()` limpia los tres estados.

## Consecuencias

Positivas:
- Las cuatro tarjetas muestran respuestas de texto con descripción de la imagen,
  comparables con las mismas métricas que el resto de categorías.
- La subcategoría "describir" incluye Claude, a diferencia de las subcategorías de
  generación (generar, logotipo, modificar) donde Claude sigue excluido.
- Sin dependencias de red externas: reproducibilidad garantizada.

Trade-offs asumidos:
- Payload JSON hasta ~6,7 MB para imágenes de 5 MB. Aceptable en entorno local
  y con la infraestructura de Cloud Run prevista.
- Grok usa `grok-4.3` tanto para texto como para visión. Los modelos `grok-3` y
  `grok-2-vision-*` no están disponibles en la API pública a 05/2026.
- La imagen no se almacena en la base de datos: los resultados históricos de "describir
  imagen" no permiten recuperar la imagen original. El prompt guardado describe la
  instrucción enviada, no la imagen.

---

## Revisión posterior — Sustitución de "Imagen similar" por "Logotipo"

Fecha: 04/05/2026

### Problema detectado

Durante las pruebas de la interfaz se observó que la subcategoría **"Imagen similar"**
era funcionalmente indistinguible de **"Generar imagen"**: ambas reciben una descripción
textual del usuario y envían una orden de generación libre al modelo. La diferencia era
únicamente el prefijo del prompt (`"Genera una imagen con el mismo estilo…"`), que en
la práctica los modelos ignoraban en favor de la descripción literal del usuario. Desde
el punto de vista del evaluador no existía ninguna dimensión diferencial que justificara
mantener ambas opciones.

### Decisión

Se sustituye la subcategoría "Imagen similar" por **"Logotipo"**.

### Argumentario

1. **Diferenciación de capacidad**: la generación de logotipos activa un modo de salida
   fundamentalmente distinto al fotorrealista — composición gráfica minimalista,
   equilibrio figura-fondo, tipografía implícita — que pone de manifiesto diferencias
   claras entre modelos que en una generación libre quedarían ocultas.

2. **Comparabilidad objetiva**: un logotipo tiene criterios de éxito evaluables sin
   subjetividad extrema: limpieza visual, escalabilidad, ausencia de ruido, coherencia
   con el brief. Esto enriquece la evaluación humana del benchmark con criterios más
   concretos que en la generación libre.

3. **Caso de uso real**: el diseño de identidad visual es uno de los usos productivos
   más frecuentes de la IA generativa en 2025-2026. Incluirlo hace el benchmark más
   relevante para el tribunal.

4. **Sin impacto en el backend**: `subcat_imagen = 'logotipo'` es tratado como una
   subcategoría de generación estándar (`es_imagen=True`, ruta `generar_imagen()`),
   igual que lo era `similar`. El cambio es exclusivamente de presentación y prompt.

### Cambios aplicados

- `frontend/src/components/benchmark/SubcatPanel.tsx` — `OPCIONES_IMAGEN`: entrada
  `similar` sustituida por `logotipo` con prompt de instrucción explícita de diseño.
- `backend/app/schemas/benchmark.py` — comentario de valores válidos de `subcat_imagen`.
- `backend/app/services/benchmark_service.py` — comentario de routing de subcategorías.
- `docs/decisions/ADR-011` — tabla de selección automática de modelos por subcategoría.
