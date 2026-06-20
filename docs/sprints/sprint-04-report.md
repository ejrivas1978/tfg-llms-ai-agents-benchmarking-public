# Sprint 4 — CERRADO
Periodo: 01/05/2026 - 14/05/2026 (cierre anticipado — desarrollo funcional completado)
Última actualización: 14/05/2026

---

## Objetivo del sprint

Conectar el frontend React al backend real, completar la integración
end-to-end, preparar el despliegue en Cloud Run y cerrar los flecos de
UX detectados durante las pruebas del prototipo. Al término del sprint
la aplicación debe ser demostrable ante el tribunal con datos reales.

---

## Items completados

| ID    | Tarea                                                                  | Puntos | Estado     |
|-------|------------------------------------------------------------------------|--------|------------|
| S4-01 | Bug: eliminar botón "Limpiar historial" en vista usuario no admin      | 1      | Completado |
| S4-02 | Eliminar campos tags/notas del proyecto completo                       | 3      | Completado |
| S4-03 | Migración Alembic: drop columns tags y notas en user_evaluations       | 2      | Completado |
| S4-04 | Rediseño flujo evaluación: modal emergente, solo lectura, sin edición  | 5      | Completado |
| S4-05 | Labels historial: "Finalizar Evaluación" rojo / "Ver Evaluación"       | 1      | Completado |
| S4-06 | Label estado benchmark: "Ejecutada" en lugar de "Completada"           | 1      | Completado |
| S4-07 | BatLoader: componente de carga animada con murciélago SVG              | 8      | Completado |
| S4-08 | BatLoader: overlay modal encima del formulario benchmark               | 3      | Completado |
| S4-15 | Endpoint backend extracción de texto desde ficheros (.txt/.pdf/.docx)  | 5      | Completado |
| S4-16 | UI carga de fichero en categoría resumen con contador y aviso de coste | 5      | Completado |
| S4-17 | UX: doble clic para ampliar/contraer respuesta en BenchmarkCard        | 2      | Completado |
| S4-18 | Bug: textarea resumen acumulaba contenido al cargar segundo fichero     | 1      | Completado |
| S4-19 | Bug: schema max_length 8 000 → 65 000 caracteres para prompts largos   | 1      | Completado |
| S4-20 | Bug: llave de cierre perdida en cambiarCategoria (error compilación)    | 1      | Completado |
| S4-21 | Visión multimodal: carga de fichero en subcategoría "describir imagen"  | 8      | Completado |
| S4-22 | Bug: routing "describir" → generar_imagen() · campo subcat_imagen       | 3      | Completado |
| S4-23 | Bug: Grok sin visión estable → SOPORTA_VISION=False, excluido del runner | 1      | Completado |
| S4-24 | Bug: eliminar input URL en "describir imagen" (solo carga de fichero)   | 1      | Completado |
| S4-25 | Normalización errores de política de seguridad en los 4 clientes LLM   | 5      | Completado |
| S4-26 | Schema: ampliar rating `ge=0` para permitir 0 estrellas en censurados  | 1      | Completado |

### Detalle de S4-02 / S4-03 — Eliminación tags y notas

Los campos `tags` (ARRAY de texto) y `notas` (Text) existían en el modelo
`UserEvaluation` desde el diseño inicial pero nunca se usaron en el
dashboard ni en ninguna vista. Mantenerlos suponía deuda técnica sin
retorno. Se eliminaron de:

- `backend/app/models/user_evaluation.py`
- `backend/app/schemas/evaluacion.py`
- `backend/app/repositories/user_evaluation_repository.py`
- `backend/app/services/evaluacion_service.py`
- `backend/app/routers/evaluacion.py`
- `frontend/src/types/evaluacion.ts`
- Migración Alembic `a3b5c7d9e1f2_drop_tags_notas_evaluacion.py`

La migración encadenó correctamente sobre la cabeza activa
`b1c3e5f7a9d2` (se corrigió un error inicial de `down_revision` al
detectar múltiples cabezas con `alembic current`).

### Detalle de S4-04 — Rediseño del flujo de evaluación

El comportamiento anterior permitía navegar a `/evaluar/{id}` y
modificar una evaluación ya guardada. Esto es problemáticamente para
la validez del estudio: las evaluaciones deben reflejar la primera
impresión del usuario, no un valor corregido a posteriori.

Solución adoptada (ADR-019):

- Se elimina la navegación a página separada. Todo ocurre en una
  ventana emergente (`EvalViewModal`) que se abre sobre la pantalla
  de historial.
- Si la sesión **no está evaluada**: muestra el formulario de
  evaluación (estrellas + ranking DnD) con el botón "Guardar".
- Si la sesión **ya está evaluada**: muestra una vista de solo lectura
  ordenada por `rango_preferencia`. No hay botón de modificar.
- La sincronización entre el estado del servidor y el store local de
  Zustand (`historialStore`) se resuelve con un `useEffect` que llama
  a `marcarEvaluada` cuando el servidor confirma que ya existe
  evaluación (cubre sesiones antiguas que no tienen el flag en
  localStorage).

### Detalle de S4-07 / S4-08 — BatLoader

Componente `BatLoader` (ADR-018) que reemplaza el spinner genérico
durante las llamadas a las APIs de LLMs. Características:

- Murciélago SVG articulado (alas, orejas, ojos con parpadeo, colmillos,
  patas) animado con CSS puro dentro de una esfera de 320×320 px.
- Mientras `isLoading=true`: murciélago flota (`bat-hover`) y alas
  aletean (`bat-flap-l/r`).
- Cuando `isLoading` pasa a `false`: secuencia de completado por cada
  modelo (giro 360°, toast emergente, punto verde) a intervalos de
  1.100 ms, seguido de llamada a `onComplete`.
- Renderizado como overlay `position: fixed` con `backdrop-filter: blur`
  encima del formulario de benchmark —el formulario queda visible y
  atenuado detrás, lo que refuerza visualmente el contexto de la espera.

**Bug corregido durante la implementación** (relevante para el Capítulo 5):
El `useEffect` que iniciaba la secuencia de completado tenía `modelos`
y `onComplete` como dependencias. Como el padre los recrea en cada
render (array inline, función anónima), la función de cleanup del efecto
cancelaba los timers recién programados antes de que se ejecutaran.
La solución fue acceder a `modelos` y `onComplete` mediante refs
(`modelosRef`, `onCompleteRef`) actualizadas en efectos sin dependencias,
de modo que el efecto de completado solo depende de `[isLoading,
triggerSpin]` y no se ve afectado por los re-renders del padre.

### Detalle de S4-15 / S4-16 — Carga de ficheros para la categoría resumen

**Contexto:** la categoría resumen requería que el usuario pegase a mano el texto
a analizar en el textarea del SubcatPanel. Para documentos largos esto era inviable.
Se implementó la opción de subir un fichero `.txt`, `.pdf` o `.docx` directamente
desde la interfaz (ADR-021).

**Backend — `upload_router.py`** (nuevo):

- Endpoint `POST /api/v1/upload/extraer-texto` que recibe un fichero como
  `multipart/form-data` y devuelve `TextoExtraido { texto, palabras, truncado }`.
- Límites: 10 MB por fichero, 8 000 palabras máximo extraídas.
- Extracción por formato: `.txt` con fallback de codificaciones (UTF-8 → latin-1 →
  cp1252); `.pdf` con pdfplumber; `.docx` con python-docx.
- Las dependencias `pdfplumber==0.11.4` y `python-docx==1.1.2` se añadieron a
  `requirements.txt`.
- El router se registró en `main.py` con prefijo `/api/v1`.

**Frontend — `services/uploadApi.ts`** (nuevo):

- Función `extraerTextoFichero(archivo: File): Promise<TextoExtraido>` que envía el
  fichero como `FormData` al endpoint de extracción.

**Frontend — `SubcatPanel.tsx`** (modificado, solo bloque resumen):

- Botón **📎 Subir fichero** junto a la etiqueta "Texto a analizar". El input `type="file"`
  es oculto y se activa mediante ref para evitar el estilo nativo del navegador.
- Al cargar el fichero:
  - El texto extraído reemplaza el contenido del textarea.
  - El textarea queda bloqueado para edición (`readOnly`, fondo oscuro).
  - Se muestra un badge con el nombre del fichero y el número de palabras
    en el color de la categoría.
  - Si el texto supera las 8 000 palabras, se trunca y aparece un aviso.
- **Aviso de coste:** si el fichero supera las 5 000 palabras (umbral a partir del
  cual el coste empieza a ser perceptible, ~0,07 USD), se muestra el coste estimado
  de la ejecución entre los 4 modelos. La fórmula y su justificación están
  documentadas en `refinamiento_metricas_sesgo.md`.
- Si el usuario selecciona un segundo fichero, el contenido anterior se borra antes
  de la llamada asíncrona (fix S4-18).

**Schema — `PeticionBenchmark`** (fix S4-19):

- El campo `prompt` tenía `max_length=8000` caracteres, pensado para prompts escritos
  a mano. Un documento de 8 000 palabras genera un prompt ensamblado de ~60 000
  caracteres (template + texto). Se amplió a `max_length=65000`.

---

### Detalle de S4-17 — Doble clic para ampliar/contraer BenchmarkCard

Las respuestas largas de los modelos se muestran truncadas con un degradado inferior
y un botón "▼ Ampliar respuesta" al pie de la tarjeta. Para contraer la respuesta
había que hacer scroll hasta el fondo de la tarjeta, lo que resultaba incómodo con
respuestas muy extensas.

**Solución:** se añadió `onDoubleClick` al div exterior de `BenchmarkCard`.
El handler comprueba que el clic no proceda de un botón (`e.target.closest('button')`)
y, si la respuesta es larga y no es imagen, alterna el estado `ampliado`. Además,
en la cabecera de la tarjeta aparece un indicador `▼`/`▲` con tooltip
"Doble clic para ampliar/contraer" que hace visible la función.

Este cambio no requiere ADR porque es un ajuste de interacción dentro de un
componente existente, sin impacto en la arquitectura ni en los datos.

---

### Detalle de S4-21 a S4-24 — Visión multimodal en "describir imagen"

**Contexto:** la subcategoría "describir imagen" solo disponía de un input de URL
que concatenaba la dirección al prompt y lo enviaba como texto puro. El backend
enrutaba cualquier llamada con `categoria='imagen'` a `generar_imagen()`, de modo
que la "descripción" llegaba a DALL-E 3, Imagen 4 o Grok Imagine como si fuera
una orden de generación, produciendo imágenes aleatorias o errores de política de
contenidos (ADR-022).

**Implementación — S4-21 (cadena completa de visión multimodal):**

- `PeticionBenchmark` extendida con `imagen_base64`, `imagen_mime_type` y `subcat_imagen`.
- `BaseLLMClient.completar()` acepta los dos primeros campos opcionales.
- Cada cliente construye el mensaje multimodal cuando `imagen_base64` está presente:
  - Claude: formato Anthropic `"source":{"type":"base64","media_type":…,"data":…}`.
  - GPT-4o, Gemini, Grok vision: formato OpenAI-compat `"image_url":{"url":"data:mime;base64,…"}`.
- `runner.ejecutar_benchmark()` tiene tres ramas: vision multimodal, generación de imagen y texto puro.
- El servicio propaga los tres campos nuevos por toda la cadena hasta el runner.
- Frontend: `SubcatPanel` convierte el fichero con `FileReader.readAsDataURL()`, extrae
  base64 y MIME type sin pasar por el backend, y los sube al estado de `BenchmarkPage`
  vía callbacks `onImagenChange` y `onSubcatImagenChange`.
- Preview thumbnail 56×56 px visible antes de ejecutar el benchmark.
- Límite: 5 MB · formatos: JPG, PNG (GIF y WebP excluidos por restricción de Grok 4.3).

**Bug S4-22 — routing erróneo de "describir":**
El servicio calculaba `es_imagen = categoria == 'imagen'` sin distinguir subcategorías.
"Describir" con URL o con fichero subido llegaba siempre a `generar_imagen()`.
Fix: campo `subcat_imagen` propagado del frontend; el servicio usa:
```python
es_descripcion = subcat_imagen == "describir" or bool(imagen_base64)
es_imagen = categoria == TestCategory.imagen and not es_descripcion
```

**Bug S4-23 — grok-3 y grok-2-vision-* no disponibles en la API pública:**
Error 400 al llamar a `grok-3` con imagen (`"Image inputs are not supported"`).
Los modelos `grok-2-vision-1212` y `grok-2-vision-latest` devuelven `"Model not found"`.
Consultando el panel de console.x.ai se constató que la cuenta solo tiene acceso a
modelos de la generación Grok 4. Fix definitivo: `_MODELO_TEXTO = _MODELO_VISION = "grok-4.3"`,
que unifica texto y visión en un único modelo. Solo admite JPG y PNG.

**Bug S4-24 — input URL eliminado:**
El input de URL se eliminó después de verificar que nunca funcionó correctamente
(Claude no accede a URLs externas; el routing siempre enrutaba a generar_imagen()).
La subcategoría "describir imagen" queda exclusivamente con carga de fichero.

**Tabla de soporte de visión por modelo (resultado del análisis):**

| Proveedor | Modelo texto | Visión | Modelo generación |
|-----------|-------------|--------|-------------------|
| Claude | claude-sonnet-4-6 | ✅ claude-sonnet-4-6 | ❌ excluido |
| OpenAI | gpt-4o | ✅ gpt-4o | dall-e-3 |
| Gemini | gemini-2.5-flash | ✅ gemini-2.5-flash | imagen-4.0-generate-001 |
| xAI (Grok) | grok-4.3 | ✅ grok-4.3 (jpg/png) | grok-imagine-image |

---

### Detalle de S4-25 — Normalización de errores de política de seguridad en los 4 clientes

**Problema detectado en pruebas:** al enviar prompts con contenido vetado, los
clientes devolvían el texto crudo del error HTTP en el campo `mensaje_error`,
incluyendo JSON sin parsear, códigos de estado y vocabulario interno de cada API.
Ejemplos reales capturados:

- Grok imagen: `Error code: 400 - {'code': 'Client specified an invalid argument', 'error': 'Generated image rejected by content moderation.', 'usage': {'cost_in_usd_ticks': 200000000}}`
- OpenAI imagen: cuerpo JSON completo de la respuesta de error 400.
- Gemini texto: `str(KeyError("predictions"))` = `'predictions'` — el cliente intentaba acceder a una clave ausente cuando Gemini devuelve HTTP 200 sin `predictions` para bloqueos por RAI.

**Alcance del fix:** los cuatro clientes (`claude_client.py`, `openai_client.py`,
`gemini_client.py`, `grok_client.py`) en ambos métodos públicos (`completar()` y,
donde aplica, `generar_imagen()`).

**Patrón implementado en cada cliente:**

```python
except APIStatusError as exc:
    raw = str(exc)
    if <patron_censura_del_proveedor> in raw.lower():
        mensaje = "Contenido rechazado por las politicas de seguridad de <Proveedor>."
    else:
        body = exc.body
        mensaje = (<extraer_message_limpio>) or raw
    return ResultadoLLM(tuvo_error=True, mensaje_error=mensaje, ...)
except APIConnectionError as exc:
    return ResultadoLLM(tuvo_error=True, mensaje_error=str(exc), ...)
```

**Patrones de detección por proveedor:**

| Proveedor | Patrón en `str(exc)` | Mensaje normalizado |
|-----------|---------------------|---------------------|
| Claude | `content filtering`, `safety classifier`, `output blocked`, `filtered`, `safety system`, `content_policy` | `"...politicas de seguridad de Anthropic."` |
| OpenAI | `content_policy_violation`, `safety system` | `"...politicas de seguridad de OpenAI (content_policy_violation)."` |
| Gemini | `safety`, `content_policy`, `unsafe`, `violat`, `filtered` | `"...filtros de seguridad de Google."` |
| Grok | `content moderation`, `content_policy` | `"...politicas de seguridad de xAI (content moderation)."` |

**Caso especial Gemini texto (`finish_reason`):** Gemini puede devolver HTTP 200
con respuesta vacía y `finish_reason == "content_filter"` sin lanzar excepción.
Se añadió detección previa al acceso al texto:

```python
if respuesta.choices[0].finish_reason == "content_filter":
    return ResultadoLLM(tuvo_error=True,
        mensaje_error="Contenido bloqueado por los filtros de seguridad de Google.", ...)
```

**Caso especial Gemini imagen (`predictions` ausente):** Gemini devuelve HTTP 200
sin la clave `predictions` en el body cuando bloquea por RAI. El acceso directo
`datos["predictions"]` producía `KeyError` cuyo `str()` era la cadena `'predictions'`.
Fix: `datos.get("predictions") or []` con retorno limpio si vacío.

Todos los mensajes normalizados contienen las cadenas `"politicas de seguridad"`
o `"filtros de seguridad"`, que son exactamente los patrones que la función
`esCensura()` del frontend detecta para activar el tratamiento visual especial
(icono 🚫, 0 estrellas automáticas, flujo sin puntuación). **Decisión de diseño:
ADR-023.**

---

### Detalle de S4-26 — Schema `rating`: `ge=1` → `ge=0`

El campo `rating` del schema `EvaluacionCreate` tenía validación `ge=1`
(mínimo 1 estrella) para impedir que el usuario guardara sin valorar.
Con la introducción de los modelos censurados —que deben recibir exactamente
0 estrellas— esta restricción impedía guardar evaluaciones con algún modelo
rechazado. Se amplió a `ge=0` en `backend/app/schemas/evaluacion.py`.

La restricción de "mínimo 1 estrella para respuestas no erróneas" se trasladó
al frontend, que filtra los modelos evaluables antes de habilitar el botón de
guardar. El backend acepta 0 en cualquier circunstancia.

---

### Detalle de S4-27 — Rediseño del flujo de evaluaciones con rechazo por política de contenido

**Problema con el diseño anterior (S4-25/S4-26):**
El sistema almacenaba `UserEvaluation` con `rating=0` para los modelos censurados
y marcaba la evaluación como `completada`. Dos problemas graves:

1. Si el usuario cerraba el navegador sin pulsar "Guardar como fallida", la evaluación
   quedaba como `completada` en la BD sin ninguna `UserEvaluation`, creando un
   registro huérfano que podía contaminar métricas en el futuro.
2. Los repositorios necesitaban subqueries `NOT IN` para excluir evaluaciones con
   `rating=0`, acoplando la lógica de exclusión a una representación física frágil.

**Solución implementada:**

El método `BenchmarkService.ejecutar()` detecta al final del benchmark si alguna
respuesta fue rechazada por política usando el nuevo método `_es_rechazo_politica()`:

```python
_CENSURA_KW = (
    "content moderation", "content_policy", "politicas de seguridad",
    "filtros de seguridad", "safety system", "contenido bloqueado", "contenido rechazado",
)

def _es_rechazo_politica(self, resultado: ResultadoLLM) -> bool:
    if not resultado.tuvo_error or not resultado.mensaje_error:
        return False
    return any(kw in resultado.mensaje_error.lower() for kw in self._CENSURA_KW)
```

Si cualquier modelo fue rechazado, el backend marca la evaluación como `fallida`
antes de devolver la respuesta HTTP, sin requerir acción del usuario.

**Simplificación de repositorios:** los subqueries `NOT IN` se eliminaron de
`ratings_por_proveedor()`, `ranking_medio_por_proveedor()` y
`ratings_por_proveedor_y_categoria()`. El filtro `status == completada` que ya
existía garantiza por construcción la exclusión de evaluaciones fallidas.

**Nuevo comportamiento del frontend:** cuando `sesion.estado === 'fallida'`,
`BenchmarkPage` y `EvaluationPage` muestran una vista informativa con la lista de
modelos (🚫 los rechazados, ✓ los que respondieron) y un único botón "Cerrar y
volver al menú". No hay StarRating ni formulario. El botón es puramente
navegacional: la evaluación ya está persistida correctamente en la BD.

---

### Detalle de S4-28 — Nuevo gráfico GraficoRestrictividad en el dashboard

Se añadió el gráfico **"Tasa de rechazo por política de contenido — imagen (%)"**
dentro del bloque de generación de imagen del dashboard, como tercer elemento
debajo del grid de latencia y valoración.

**Decisión de ubicación:** los rechazos por política de contenido en este estudio
se producen exclusivamente durante la generación de imágenes. Colocar el gráfico
en una sección independiente habría generado la impresión de que afecta a
evaluaciones de texto, que no es el caso. Al estar dentro del bloque imagen, el
contexto es inmediato: Claude no aparece porque no genera imágenes; los tres
proveedores con imagen (OpenAI, Gemini, Grok) son los únicos comparados.

**Query de soporte — `tasa_rechazo_por_proveedor()`:**
Calcula por proveedor el cociente rechazos / participaciones, acotado a
`category == imagen`:
- Denominador: participaciones de cada proveedor en evaluaciones de imagen
  `completada` o `fallida`.
- Numerador: participaciones con `tuvo_error=True` en evaluaciones de imagen `fallida`.

La lógica usa `CASE WHEN` con `status=fallida AND tuvo_error=True` para aislar
los errores por política de los errores técnicos aislados.

**Tipo y DTO:**
- Backend: `TasaRechazo(proveedor, total_participaciones, total_rechazos, tasa)` en `schemas/stats.py`.
- Frontend: `TasaRechazo` en `types/stats.ts` + campo `tasa_rechazo` en `RespuestaStats`.

**Componente `GraficoRestrictividad`:** barras horizontales de Recharts con
formato de porcentaje en el eje X y el nombre del modelo en el eje Y. Incluye
un banner informativo rojo que contextualiza la métrica. Se renderiza
condicionalmente si `stats.tasa_rechazo.length > 0`.

---

### Detalle de S4-29 — Migración Alembic: rating ge=1, limpieza de rating=0

La transición al nuevo flujo requería limpiar los registros históricos creados
por el mecanismo anterior (S4-26 había ampliado el constraint a `ge=0`).

**Migración `e1f2a3b4c5d6_rating_min_uno_revert_censura.py`:**

```sql
-- 1. Reclasificar evaluaciones completadas con rating=0 como fallidas
UPDATE benchmark_evaluaciones
SET status = 'fallida'
WHERE status = 'completada'
  AND id IN (
    SELECT DISTINCT lr.evaluacion_id
    FROM llm_responses lr
    JOIN user_evaluations ue ON ue.response_id = lr.id
    WHERE ue.rating = 0
  );

-- 2. Eliminar los registros rating=0
DELETE FROM user_evaluations WHERE rating = 0;

-- 3. Restaurar constraint CHECK (rating >= 1 AND rating <= 5)
ALTER TABLE user_evaluations DROP CONSTRAINT ck_rating_range;
ALTER TABLE user_evaluations ADD CONSTRAINT ck_rating_range
    CHECK (rating >= 1 AND rating <= 5);
```

La migración falló en el primer intento porque se intentó aplicar el constraint
antes de limpiar los datos. El orden de las tres operaciones es estricto y
necesario: primero actualizar estados, luego eliminar filas, por último añadir
la restricción.

---

### Detalle de S4-30 — Refactorización naming: sesiones → evaluaciones

El término "sesión" era un residuo del nombre original del modelo de datos
(`BenchmarkSession → BenchmarkEvaluacion`). Pervivía en nombres de símbolos
de código (métodos, parámetros, variables, funciones TypeScript) y en algún
texto visible al usuario.

**Ámbito del renombrado:**

| Antes | Después | Archivos |
|---|---|---|
| `obtener_por_sesion_id()` | `obtener_por_evaluacion_id()` | `user_evaluation_repository.py` |
| `obtener_por_sesion()` | `obtener_por_evaluacion()` | `evaluacion_service.py` |
| `sesion_id` (parámetro) | `evaluacion_id` | `evaluacion_service.py`, `benchmark.py` (router) |
| `obtener_sesion` (función router) | `obtener_evaluacion` | `benchmark.py` (router) |
| `/sesion/{sesion_id}` (URL) | `/evaluacion/{evaluacion_id}` | `evaluacion.py` (router) + `evaluacionApi.ts` |
| `obtenerSesion()` | `obtenerEvaluacion()` | `benchmarkApi.ts` |
| `obtenerEvaluacionesSesion()` | `obtenerEvaluacionesPorEvaluacion()` | `evaluacionApi.ts` |
| `:sesionId` (route param) | `:evaluacionId` | `App.tsx`, `EvaluationPage.tsx` |
| `"Sesion #X"` (texto UI) | `"Evaluacion #X"` | `EvalViewModal.tsx`, `EvaluationPage.tsx` |
| docstrings con "sesion de benchmark" | "evaluacion de benchmark" | `benchmark_service.py`, `stats_service.py`, `evaluacion_service.py` y routers |

El renombrado no afecta al tipo `SesionBenchmark` de TypeScript (pendiente de
refactorización mayor), ni a las referencias de "inicio de sesión" del módulo
de administrador (que hacen referencia a una sesión HTTP/JWT, no a una evaluación
de benchmark, y son terminología correcta).

---

### Detalle de S4-31 — Columna discriminadora `es_generacion_imagen`

La categoría `imagen` del enum `TestCategory` abarca dos subcategorías con naturaleza radicalmente distinta:

- **Generación de imagen** (subcategorías `generar`, `logotipo`, `modificar`): el modelo recibe un prompt en texto y devuelve una imagen generada. Solo tres proveedores participan; Claude no implementa esta función (`SOPORTA_IMAGEN=False`).
- **Descripción de imagen — visión** (subcategoría `describir`): el modelo recibe una imagen codificada en base64 y la describe en texto. Los cuatro proveedores participan, incluido Claude.

Ambas subcategorías producen evaluaciones con `category='imagen'` en la base de datos. Hasta este item todos los filtros del sistema usaban `category == TestCategory.imagen` para identificar evaluaciones de imagen, mezclando ambos tipos. El resultado es que Claude —que no genera imágenes pero sí describe imágenes— aparecía en gráficas de generación de imagen, y los denominadores de métricas de imagen contaban evaluaciones de descripción de imagen que no debían estar ahí.

**Solución:** se añadió la columna `es_generacion_imagen: Mapped[bool]` al modelo `BenchmarkEvaluacion`. El valor lo establece `BenchmarkService.ejecutar()` a partir de la subcategoría recibida: `True` para generar/logotipo/modificar; `False` para describir y para todas las categorías que no son imagen.

**Migraciones Alembic para datos existentes:**

- **`f3b4c5d6e7a8_add_es_generacion_imagen.py`**: ADD COLUMN con `server_default='FALSE'` + UPDATE para marcar como `True` las evaluaciones de imagen con `imagen_miniatura IS NOT NULL` (evaluaciones de generación completadas exitosamente).

- **`a4b5c6d7e8f9_fix_es_generacion_imagen_fallidas.py`**: segunda migración que corrige las evaluaciones de generación rechazadas por política de contenido. Estas tienen `status='fallida'` e `imagen_miniatura=NULL` en todas sus respuestas (no se produjo ninguna imagen), por lo que la primera migración no las marcaba. La subcategoría `describir imagen` usa `completar()` y nunca termina en estado `fallida`; por tanto, cualquier evaluación con `category='imagen'` y `status='fallida'` es necesariamente una evaluación de generación rechazada. La migración aplica: `UPDATE SET es_generacion_imagen=TRUE WHERE category='imagen' AND status='fallida' AND es_generacion_imagen=FALSE`.

Tras la aplicación de ambas migraciones, la distribución verificada en base de datos fue: 13 evaluaciones de generación completadas, 4 rechazadas (`fallida`), 7 evaluaciones de descripción de imagen (`completada`, `es_generacion_imagen=FALSE`). Esta distribución es coherente con los datos del estudio.

**Actualización de repositorios:** todos los filtros `category == TestCategory.imagen` se sustituyeron por `BenchmarkEvaluacion.es_generacion_imagen.is_(True)` y `category != TestCategory.imagen` por `es_generacion_imagen.is_(False)` en `LLMResponseRepository`, `UserEvaluationRepository` y `BenchmarkEvaluacionRepository`.

---

### Detalle de S4-32 — Exclusión de Claude de las gráficas de generación de imagen

Claude no implementa la función de generación de imagen (`SOPORTA_IMAGEN=False` en `ClaudeClient`). Con anterioridad, el modelo aparecía en las gráficas de imagen porque sus evaluaciones de descripción de imagen (`category='imagen'`) superaban los filtros basados en `category`. La exclusión se implementó en tres capas independientes:

| Capa | Mecanismo | Efectividad |
|---|---|---|
| Runtime | `SOPORTA_IMAGEN=False` en `ClaudeClient` (preexistente) | Claude nunca genera imágenes; no existen filas de imagen generativa de Claude en la BD |
| Base de datos | Filtro `es_generacion_imagen.is_(True)` en todos los métodos de imagen (S4-31) | Las consultas no devuelven filas de Claude porque sus evaluaciones de descripción tienen `es_generacion_imagen=False` |
| Frontend | `.filter((m) => m.proveedor !== 'claude')` en 3 componentes | Salvaguarda defensiva ante cualquier cambio futuro en las capas de datos |

Los tres componentes afectados en la capa de frontend son `GraficoImagenLatencia`, `GraficoImagenRating` y `GraficoRestrictividad`. La triple capa garantiza defensa en profundidad: incluso si el pipeline de datos cambiase, Claude no podría aparecer en las gráficas de generación de imagen.

---

### Detalle de S4-33 — Fix denominador en la tasa de rechazo por imagen

**Problema:** el método `tasa_rechazo_por_proveedor()` calculaba el denominador de la tasa con `COUNT(LLMResponse.id)`. En una evaluación de imagen participan tres proveedores generando tres filas en `llm_responses`. El total de filas era ~50 (tres proveedores × 17 evaluaciones de imagen), pero el gráfico mostraba el denominador "50" como si fuera el número de evaluaciones, produciendo el ratio incorrecto "4 rechazos / 50" en lugar de "4 / 17".

**Corrección:**

```python
func.count(func.distinct(BenchmarkEvaluacion.id)).label("total"),
```

El denominador pasa a ser el número de evaluaciones únicas de generación de imagen en las que participó cada proveedor. El valor correcto, verificado con una consulta directa a la base de datos, es 17 evaluaciones de imagen por proveedor, con 4 rechazadas.

**Diagnóstico del error:** la primera inspección apuntaba a que el filtro `es_generacion_imagen` no estaba funcionando (el texto mostraba "4 / 50" antes y después del cambio de filtro). La causa real era que el servidor `uvicorn` no había recargado el código actualizado —la recarga automática no siempre detecta cambios en módulos profundos—. La consulta directa a PostgreSQL confirmó que la lógica SQL era correcta y devolvía 17 por proveedor; el problema era de caché de proceso, no de lógica.

---

### Detalle de S4-34 — Heatmap: etiqueta 'Visión' y nuevo `ratings_imagen_generativa`

**Motivación:** tras la corrección del sesgo 7 (S4-31), la celda 'Imagen' del heatmap pasó a reflejar exclusivamente evaluaciones de descripción de imagen (visión multimodal). El nombre 'Imagen' era ambiguo respecto al bloque de generación de imagen que aparece más abajo en el dashboard.

**Cambios implementados:**

1. **Etiqueta:** `ETIQ_CAT['imagen']` en `DashboardPage.tsx` pasó de `'Imagen'` a `'Visión'`.

2. **Filtro del heatmap** en `ratings_por_proveedor_y_categoria()`: el heatmap incluye ahora todas las categorías de texto y la subcategoría describir imagen, y excluye las evaluaciones de generación de imagen:

```python
.where(or_(
    BenchmarkEvaluacion.category != TestCategory.imagen,
    BenchmarkEvaluacion.es_generacion_imagen.is_(False),  # incluye describir imagen
))
```

3. **Nuevo `ratings_generacion_imagen_por_proveedor()`** en `UserEvaluationRepository`: agrega los ratings de evaluaciones con `es_generacion_imagen=True`. Claude no tiene filas de este tipo por construcción del sistema, por lo que el método devuelve solo los tres proveedores de generación de imagen.

4. **Nuevo DTO `RatingImagenModelo`** (`proveedor`, `rating_medio`, `n`) en `schemas/stats.py` y tipo homónimo en `types/stats.ts`. Campo `ratings_imagen_generativa: list[RatingImagenModelo]` añadido a `RespuestaStats`.

5. **`GraficoImagenRating`** del dashboard usa ahora el nuevo campo `ratings_imagen_generativa` en lugar de filtrar el heatmap, garantizando que solo refleja valoraciones de los tres proveedores que generan imágenes.

---

### Detalle de S4-35 — Desglose del KPI de evaluaciones totales

El contador "Evaluaciones totales" del dashboard mostraba únicamente el número total de evaluaciones ejecutadas. Dado que el dashboard separa visualmente el dominio texto/visión del dominio generación de imagen, se mejoró el KPI para comunicar esta distinción.

**Cambios:**

- Nuevo método `contar_evaluaciones_imagen_generativa()` en `BenchmarkEvaluacionRepository`: devuelve `COUNT(id) WHERE es_generacion_imagen=True` sin filtro de estado, garantizando que `texto_vision + imagen_gen == total_evaluaciones`.
- Campos `total_texto_vision: int` y `total_imagen_generativa: int` en `RespuestaStats`. El primero se computa en el servicio como `total_evaluaciones - total_imagen_generativa` (aritmética exacta por construcción).
- Subtítulo del KPI card actualizado: `N texto/visión · N imagen gen.`

---

### Detalle de S4-09 — Dashboard conectado al endpoint real `/api/v1/stats`

**Contexto:** el prototipo del Sprint 3 mostraba los gráficos del dashboard con datos
simulados (arrays hardcodeados). El objetivo de S4-09 era sustituirlos por datos reales
del backend.

**Implementación:**

`DashboardPage.tsx` usa un único `useQuery` de TanStack Query que llama a `obtenerStats()`
del servicio `src/services/statsApi.ts`:

```typescript
const { data, isLoading, isError } = useQuery({
  queryKey: ['stats'],
  queryFn: obtenerStats,
  staleTime: 30_000,  // 30 s de caché; evita repetir la petición en cada navegación
  retry: 1,
})
```

El componente maneja tres estados:
- **Cargando:** esqueleto animado de 4 KPI cards con `animate-pulse`.
- **Error:** banner rojo "No se pudo cargar el dashboard. Comprueba que el backend está activo."
- **Datos:** renderizado completo de los 13 gráficos con los datos reales.

`RespuestaStats` (tipado en `types/stats.ts`) incluye los campos que alimentan cada
sección del dashboard:

| Campo | Uso |
|---|---|
| `total_evaluaciones`, `evaluaciones_puntuadas`, `total_texto_vision`, `total_imagen_generativa` | KPI cards superiores |
| `evaluaciones_por_categoria` | Gráfico de barras por categoría |
| `metricas_por_modelo` | Latencia, tokens/s, coste, diversidad, palabras por modelo |
| `heatmap` | Matriz valoración humana modelo × categoría |
| `jaccard` | Matriz de similitud Jaccard 4×4 |
| `ratings_imagen_generativa` | Gráfico de valoración de imagen generativa |
| `tasa_rechazo` | Gráfico de restrictividad por proveedor |

El backend expone el endpoint en `GET /api/v1/stats` (router `stats.py`, registrado en
`main.py` con prefijo `/api/v1`). El servicio `StatsService` agrega todos los datos
en una única llamada para minimizar latencia.

---

### Detalle de S4-13 — Detalle de evaluación expandible en historial admin

**Contexto:** la vista de administrador (`TablaAdmin`) mostraba cada evaluación como
una fila en una tabla paginada, con operaciones de selección y borrado por lotes.
No había forma de ver el contenido completo de una evaluación (prompt, respuestas de
los modelos, valoración del usuario) desde la vista admin.

**Implementación — `DetalleComparativaModal` en `TablaAdmin.tsx`:**

El componente interno `DetalleComparativaModal` se activa con el botón "Ver comparativa"
de cada fila. Controla su visibilidad mediante `verDetalleId: number | null`:

```typescript
const [verDetalleId, setVerDetalleId] = useState<number | null>(null)
// ...
onClick={() => setVerDetalleId(s.id)}   // abrir
onClose={() => setVerDetalleId(null)}   // cerrar
```

El modal hace **dos queries en paralelo**:
1. `obtenerEvaluacion(sesionId)` → datos de la comparativa: prompt, categoría, estado,
   respuestas de cada modelo (texto o imagen), métricas automáticas.
2. `obtenerEvaluacionesPorEvaluacion(sesionId)` → evaluación del usuario: estrellas y
   rango de preferencia por modelo.

Las filas de evaluación se ordenan por `rango_preferencia` para mostrarlas en el orden
que el usuario estableció. Los datos de proveedor (nombre, color) se enriquecen con
`PROV_INFO` para mantener coherencia visual con el resto de la interfaz.

**Funcionalidades del modal:**
- Cabecera: `Comparativa #ID`, prompt (truncado a 2 líneas), badge de categoría,
  botón de cierre y botón de borrado con confirmación.
- Cuerpo scrolleable (máx. 90 vh): tarjetas de respuesta por modelo con métricas y,
  si hay evaluación de usuario, estrellas y rango de preferencia en vista de solo lectura.
- Cierre con tecla `Escape` (listener en `useEffect` con cleanup).
- Cierre al hacer clic fuera del panel (`onClick` en el overlay con `stopPropagation`
  en el panel interior).
- Borrado: `useMutation` llama a `eliminarEvaluacion(token, sesionId)`, muestra toast
  de confirmación y refresca la lista de la tabla.

---

### Detalle de S4-36 — Bug "Modificar imagen": routing, `editar_imagen()` y gpt-image-1

**Problema raíz:** la subcategoría "Modificar imagen" recibía respuestas de texto en lugar
de imágenes. El flujo completo fallaba en tres puntos encadenados:

1. **`benchmark_service.py`**: la condición `es_descripcion = subcat_imagen == "describir" or bool(imagen_base64)`
   convertía cualquier evaluación con imagen subida (incluyendo "modificar") en modo visión.
   Como "modificar" sube la imagen de referencia, `bool(imagen_base64)` era `True`, haciendo
   `es_imagen=False` e invocando `completar()` en lugar de `generar_imagen()`.

2. **`runner.py`**: la condición `if imagen_base64:` se evaluaba antes de `elif es_imagen:`,
   por lo que incluso con `es_imagen=True` cualquier request con imagen pasaba a la ruta
   de visión multimodal.

3. **Clientes LLM**: `generar_imagen()` no aceptaba imagen de entrada; no existía un método
   para edición imagen-a-imagen.

**Correcciones implementadas:**

- **`benchmark_service.py`**: `es_descripcion = subcat_imagen == "describir"` (eliminada la
  cláusula `or bool(imagen_base64)`). "Modificar" sube imagen de referencia pero la ruta
  es edición de imagen, no visión.

- **`runner.py`**: nueva ruta prioritaria `if es_imagen and imagen_base64` → llama a
  `editar_imagen()`. Las tres rutas restantes quedan intactas:

  ```python
  if es_imagen and imagen_base64:   # edición imagen-a-imagen
      clientes_activos = [c for c in clientes if c.SOPORTA_IMAGEN]
      tareas = [c.editar_imagen(prompt, imagen_base64, imagen_mime_type or "image/jpeg")
                for c in clientes_activos]
  elif imagen_base64:               # visión multimodal (describir)
      ...
  elif es_imagen:                   # generación desde texto (generar, logotipo)
      ...
  else:                             # texto puro
      ...
  ```

- **`base_client.py`**: nuevo flag `SOPORTA_EDICION_IMAGEN: bool = False` y método
  `editar_imagen()` que extrae la instrucción del usuario (elimina el prefijo estándar
  "Modifica la imagen adjunta aplicando el siguiente cambio: ") y delega en `generar_imagen()`.
  Los clientes sin soporte nativo generan una imagen nueva desde la instrucción como prompt.

- **`openai_client.py`**: override `editar_imagen()` con `SOPORTA_EDICION_IMAGEN=True`.
  Usa `gpt-image-1` vía `client.images.edit()`, que soporta edición real sin necesidad de
  máscara. La respuesta llega en `b64_json` (no URL), se decodifica y se genera miniatura.

**Resultado por proveedor en "Modificar imagen":**

| Proveedor | Implementación | Output |
|---|---|---|
| OpenAI | `gpt-image-1` `images.edit()` | Imagen editada real |
| Gemini | Fallback → `generar_imagen(instruccion)` | Imagen generada desde instrucción |
| Grok | Fallback → `generar_imagen(instruccion)` | Imagen generada desde instrucción |

---

### Detalle de S4-37 — Fix timeout AsyncOpenAI 120s + conversión JPEG→PNG

**Problema:** durante las pruebas de "Modificar imagen", el backend se quedaba bloqueado
indefinidamente. El log mostraba `status='en_curso'` y después ninguna actividad hasta
que el usuario forzaba el cierre (`CTRL+C`). Causa: `AsyncOpenAI` usa timeout de 600s
por defecto; las llamadas a `gpt-image-1` `images.edit()` y a `grok-imagine-image`
podían tardar más de lo esperado o colgarse sin responder.

**Correcciones:**

- **`openai_client.py`** y **`grok_client.py`**: `AsyncOpenAI(timeout=120.0)`. Si el servidor
  no responde en 120s, el SDK lanza `APIConnectionError`, que ya está capturado en los
  bloques `except` de cada cliente y devuelve `ResultadoLLM(tuvo_error=True)`. El timeout
  aplica globalmente al cliente (texto e imagen), siendo 120s suficiente para cualquier
  operación de texto y razonable para edición de imagen.

- **`openai_client.py` — `editar_imagen()`**: `gpt-image-1` requiere PNG como formato de
  entrada. Si el usuario sube un JPEG, la API puede fallar en silencio. Se añadió
  conversión automática mediante Pillow antes de la llamada:

  ```python
  if "jpeg" in imagen_mime_type or "jpg" in imagen_mime_type:
      img = Image.open(io.BytesIO(imagen_bytes))
      buf = io.BytesIO()
      img.convert("RGBA").save(buf, format="PNG")
      imagen_bytes = buf.getvalue()
      imagen_mime_type = "image/png"
  ```

- **`base_client.py` — `editar_imagen()` fallback**: el prompt que llega es
  `"Modifica la imagen adjunta aplicando el siguiente cambio: {instruccion}"`. Gemini e
  Imagen 4 / grok-imagine-image reciben este prompt en `generar_imagen()` sin la imagen
  de referencia, lo que confundiría al generador. Se extrae solo la instrucción del usuario:

  ```python
  _PREFIJO = "Modifica la imagen adjunta aplicando el siguiente cambio: "
  instruccion = prompt[len(_PREFIJO):] if prompt.startswith(_PREFIJO) else prompt
  return await self.generar_imagen(instruccion)
  ```

---

### Detalle de S4-38 — Modelo `UsuarioApp`, migración Alembic, repositorio y enum de estados

Se introdujo el sistema de usuarios de la aplicación web, separado del administrador
del sistema. El administrador gestiona las cuentas a través de la interfaz admin;
los evaluadores se registran con nick y contraseña.

**Modelo `UsuarioApp` (`backend/app/models/usuario_app.py`):**

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer PK | Clave primaria autoincremental |
| `nick` | String(100) UNIQUE | Identificador público del usuario |
| `password_hash` | String | Hash bcrypt de la contraseña |
| `estado` | Enum `EstadoUsuarioApp` | Estado del ciclo de vida |
| `cuota_asignada` | Integer | Máximo de comparaciones permitidas |
| `consultas_usadas` | Integer | Comparaciones completadas exitosamente |
| `intentos_fallidos` | Integer | Intentos de login incorrectos consecutivos |
| `created_at` / `updated_at` | DateTime | Trazabilidad |

**Enum `EstadoUsuarioApp` (`backend/app/models/enums.py`):**

```
pendiente_acceso          → registro recibido, pendiente de aprobación del admin
habilitado                → cuenta operativa, puede ejecutar comparaciones
pendiente_ampliar_tokens  → cuota agotada, el usuario ha solicitado ampliación
```

**Repositorio `UsuarioAppRepository`:** 11 métodos — crear, obtener por nick/id,
listar todos, actualizar estado, asignar cuota, ampliar cuota, incrementar consultas,
incrementar/resetear intentos fallidos, regenerar contraseña.

**Migración Alembic `8515120b6649_add_usuarios_app_table.py`:**
Crea la tabla `usuarios_app`, el tipo ENUM `estadousuarioapp` en PostgreSQL,
e índice único sobre `nick`. Verificada con `alembic upgrade head`.

**Cascade al eliminar usuario:** el repositorio `BenchmarkEvaluacionRepository`
recibió el método `eliminar_por_nickname(nick)` que borra todas las evaluaciones
del usuario (cascade a `llm_responses` y `user_evaluations`) antes de que el
servicio elimine el registro de `usuarios_app`.

---

### Detalle de S4-39 — Backend auth: registro, login JWT 1h, bloqueo 5 intentos, regenerar contraseña

**Servicio `UsuarioAppAuthService`:**

- `registrar()`: verifica unicidad de nick, aplica hash bcrypt, crea usuario con
  estado `pendiente_acceso`.
- `login()`:
  - 5 o más `intentos_fallidos` → HTTP 423 (cuenta bloqueada).
  - Contraseña incorrecta → incrementar `intentos_fallidos`, HTTP 401.
  - Estado `pendiente_acceso` → HTTP 403 (pendiente de aprobación).
  - Login correcto → resetear `intentos_fallidos`, emitir JWT con claim
    `{"sub": str(id), "tipo": "usuario_app"}` y duración 1h.
- `solicitar_mas_tokens()`: transición `habilitado → pendiente_ampliar_tokens`.
- `regenerar_contrasena()`: nuevo hash, estado → `pendiente_acceso` (requiere
  reaprobación del admin); mantiene `consultas_usadas` y `cuota_asignada`.

**Router `/api/v1/usuarios`:**

| Endpoint | Auth | Descripción |
|---|---|---|
| `GET /verificar/{nick}` | Pública | `{"existe": bool}` |
| `POST /registrar` | Pública, rate 5/min | Crear cuenta |
| `POST /login` | Pública, rate 10/min | JWT + estado cuota |
| `POST /solicitar-mas-tokens` | JWT usuario | Solicitar ampliación |
| `POST /regenerar-contrasena` | Pública, rate 5/min | Resetear contraseña |

**Dependencia `get_actor_benchmark`** en `dependencies.py`: intenta validar
el JWT como `usuario_app` primero; si falla, lo trata como admin. Devuelve
`UsuarioApp | None` (None = admin, cuota ilimitada).

---

### Detalle de S4-40 — Backend cuota: consumo por comparación exitosa

**Lógica de cuota en `BenchmarkService.ejecutar()`:**

- Antes de llamar a los LLMs: si `consultas_usadas >= cuota_asignada` → HTTP 402
  con mensaje `"Cuota de consultas agotada"`.
- Tras completar: si `estado_final == completada` → `incrementar_consultas(usuario_app)`.
- Si el benchmark termina en estado `fallida` (censura de contenido) → no se
  consume cuota. Decisión: solo las comparaciones con resultados evaluables consumen
  cuota, lo que es coherente con el propósito del estudio.
- El admin (`usuario_app = None`) no tiene cuota; el check se omite.

**HTTP 402 en el frontend:** `BenchmarkPage` detecta el status 402 en
`mutacion.isError` y no muestra el mensaje genérico de error —el banner de
cuota agotada ya informa al usuario de la situación.

---

### Detalle de S4-41 — Endpoints admin gestión de usuarios

Cuatro endpoints bajo `/api/v1/admin/usuarios` (requieren JWT de administrador):

| Endpoint | Descripción |
|---|---|
| `GET /usuarios` | Lista todos los usuarios con su estado actual |
| `POST /usuarios/{id}/conceder-acceso` | Transición `pendiente_acceso → habilitado` + asignar cuota |
| `POST /usuarios/{id}/ampliar-tokens` | Suma `tokens_adicionales` a `cuota_asignada`; estado → `habilitado` |
| `DELETE /usuarios/{id}` | Elimina usuario y todas sus evaluaciones; devuelve `{"evaluaciones_eliminadas": N}` |

**Servicio `UsuarioAppAdminService`:** encapsula las cuatro operaciones,
delegando en `UsuarioAppRepository` y `BenchmarkEvaluacionRepository`.

---

### Detalle de S4-42 — Frontend NickPage: flujo completo de autenticación

La pantalla de entrada (`NickPage.tsx`) se rediseñó completamente para gestionar
cuatro flujos mediante una variable de estado `vista`:

| Vista | Cuándo aparece | Acción |
|---|---|---|
| `inicio` | Primer acceso | Nick → verificar existencia |
| `login` | Nick ya registrado | Contraseña → JWT |
| `registro` | Nick nuevo | Contraseña + confirmación → solicitar acceso |
| `regenerar` | Olvidó contraseña | Nick + nueva contraseña → estado pendiente |
| `login_admin` | Nick = `'admin'` | Email + contraseña admin → JWT admin |

**Tratamiento de errores HTTP en login:**
- 403 → "Tu solicitud está pendiente de aprobación."
- 423 → "Cuenta bloqueada por múltiples intentos fallidos."
- 401 → "Contraseña incorrecta."

**Vista `login_admin`:** cuando el nick es exactamente `'admin'`, se omite
la verificación en `usuarios_app` y se muestra formulario de email + contraseña
de administrador. El JWT obtenido se almacena en `adminStore`; el nick `'admin'`
se guarda en `nickStore` para la detección de rol en `HistorialPage`.

**Stores afectados:** `usuarioStore` (persist localStorage, token + nick + estado +
consultasUsadas + cuotaAsignada), `nickStore` (compatibilidad legacy).

**`RutaProtegida` en `App.tsx`:** acepta `usuarioStore.token` O `adminStore.token`;
redirige a `/` si ninguno está presente.

**`benchmarkApi.ts`:** interceptor de petición inyecta `Authorization: Bearer`
con el token del usuario web o del admin.

---

### Detalle de S4-43 — Frontend BenchmarkPage: contador de consultas y bloqueo de cuota

**Widget de cuota** (visible solo para usuarios web con cuota asignada):

- Posición: esquina superior derecha del encabezado de la página.
- Colores dinámicos: verde (< 80%), amarillo (≥ 80%), rojo (100%).
- Mini barra de progreso horizontal.
- Etiqueta "Cuota agotada" cuando `consultasUsadas >= cuotaAsignada`.

**Bloqueo de envío:** `puedeEnviar` incorpora `!cuotaAgotada`; el botón
"Comparar modelos" queda deshabilitado cuando la cuota está agotada.

**Banner de cuota agotada:** panel rojo con mensaje explicativo y botón
"SOLICITAR MAS CONSULTAS" que llama a `POST /usuarios/solicitar-mas-tokens`.
Tras la solicitud, el botón se sustituye por "✓ Solicitud enviada. El admin
revisará tu petición."

**Actualización local de cuota:** en `mutacion.onSuccess`, si
`esUsuarioWeb && data.estado === 'completada'`, el store local incrementa
`consultasUsadas + 1` sin necesidad de un segundo endpoint. Si el servidor
devuelve HTTP 402 no se muestra mensaje de error duplicado.

---

### Detalle de S4-44 — Frontend panel admin gestión de usuarios

**`TablaUsuarios.tsx`** (nuevo componente en `components/historial/`):

Tabla de todos los usuarios ordenados por urgencia: primero `pendiente_acceso`,
luego `pendiente_ampliar_tokens`, luego `habilitado`.

**Columnas:** nick + id, estado (badge con color), consultas usadas/cuota con
mini barra de progreso, intentos fallidos (naranja si > 0, rojo + 🔒 si ≥ 5),
fecha de registro, acciones.

**Acciones por estado:**
- `pendiente_acceso` → botón verde "✓ Conceder acceso" (abre `FormModal`)
- `habilitado` → botón índigo "+ Ampliar cuota" (abre `FormModal`)
- `pendiente_ampliar_tokens` → botón índigo animado (pulse) "+ Ampliar cuota"
- Cualquier estado → botón rojo "✕" (abre `ConfirmModal` con advertencia de
  cascade a evaluaciones)

**`FormModal`** (componente local): muestra el nick del usuario, cuota actual
(si procede) y un input numérico con valor por defecto (10 para acceso inicial,
5 para ampliaciones). En la vista de ampliar, calcula y muestra en tiempo real
la nueva cuota total resultante.

**Integración en `HistorialPage`:** se añadieron pestañas "Comparativas" /
"Usuarios" encima de la tabla del admin mediante un estado `pestanaAdmin`.
La URL `/historial?tab=usuarios` activa directamente la pestaña de usuarios
gracias a `useSearchParams`.

**API functions en `adminApi.ts`:** `listarUsuariosAdmin`, `concederAccesoAdmin`,
`ampliarConsultasAdmin`, `eliminarUsuarioAdmin`.

---

### Detalle de S4-45 — Correcciones UX y terminología post-validación

Cinco ajustes detectados durante las primeras pruebas reales del sistema de
autenticación:

**1. Formulario de registro oculto tras envío exitoso**
Después de enviar la solicitud de acceso (`POST /usuarios/registrar`), el
mensaje de confirmación aparecía junto al formulario de contraseña que
permanecía visible. Se añadió la condición `{!info ? <form> : <botonVolver>}`
en la vista `registro` de `NickPage`: cuando `info` está presente (solicitud
enviada), solo se muestra el mensaje de confirmación y el botón "← Volver al inicio".

**2. Terminología unificada: tokens → consultas**
El botón "SOLICITAR MAS TOKENS" y el mensaje de apoyo usaban "tokens",
mientras que el contador del widget y el resto de la UI usaban "consultas".
Se renombró el botón a "SOLICITAR MAS CONSULTAS", se actualizó el mensaje
de apoyo ("amplie tus consultas"), y se renombraron las variables internas
`solicitandoTokens` → `solicitandoConsultas`, `tokenssolicitados` →
`consultasSolicitadas`, `pedirMasTokens()` → `pedirMasConsultas()` en
`BenchmarkPage.tsx`.

**3. Historial localStorage huérfano al re-registrarse**
Cuando el admin elimina un usuario y ese nick se vuelve a registrar y
aprobar, el historial local almacenado en `localStorage` (Zustand persist)
del nick anterior seguía apareciendo. Al hacer login, si `consultas_usadas === 0`
(cuenta nueva o cuenta recreada), `NickPage` llama a `limpiar(nick)` del
`historialStore`, eliminando las entradas de localStorage para ese nick.

**4. Popup de notificación de usuarios pendientes al login admin**
Tras un login de administrador correcto, el sistema consulta
`GET /admin/usuarios` con el token recién obtenido. Si hay usuarios en
estado `pendiente_acceso` o `pendiente_ampliar_tokens`, se muestra un modal
informativo con el recuento por tipo. El modal ofrece dos acciones:
- "Revisar ahora" → navega a `/historial?tab=usuarios`
- "Más tarde" → navega a `/historial`
Si la consulta falla (timeout, error de red), se navega directamente a
`/historial` sin popup, de modo que el fallo no bloquea el flujo de login.

**5. Nomenclatura "Mis sesiones" → "Mis comparativas"**
El encabezado de la vista de historial del usuario regular mostraba
"Mis sesiones". Se actualizó a "Mis comparativas" para unificar con el
resto de la terminología del proyecto (el término "sesión" quedó reservado
para sesiones HTTP/JWT del módulo de autenticación).

---

## Items en curso

| ID    | Tarea                                                             | Puntos | Estado    |
|-------|-------------------------------------------------------------------|--------|-----------|
| S4-27 | Rediseño flujo censura: backend marca automáticamente estado fallida | 8      | Completado |
| S4-28 | Nuevo gráfico GraficoRestrictividad en el dashboard               | 3      | Completado |
| S4-29 | Migración Alembic: revertir rating ge=1, limpiar rating=0 histórico | 3     | Completado |
| S4-30 | Refactorización naming: sesiones → evaluaciones en todo el codebase | 3      | Completado |
| S4-31 | Columna discriminadora `es_generacion_imagen` + 2 migraciones Alembic de backfill | 5      | Completado |
| S4-32 | Exclusión de Claude de las 3 gráficas de generación de imagen (3 capas) | 2      | Completado |
| S4-33 | Fix denominador tasa de rechazo: `COUNT(DISTINCT evaluacion_id)`    | 2      | Completado |
| S4-34 | Heatmap: etiqueta 'Visión' + nuevo campo `ratings_imagen_generativa` | 5      | Completado |
| S4-35 | Desglose KPI evaluaciones totales: texto/visión · imagen gen.       | 2      | Completado |
| S4-36 | Bug "Modificar imagen": routing, `editar_imagen()` y gpt-image-1   | 8      | Completado |
| S4-37 | Fix timeout AsyncOpenAI 120s + conversión JPEG→PNG gpt-image-1     | 3      | Completado |
| S4-09 | Conexión frontend → endpoint /api/v1/stats (dashboard real)       | 8      | Completado |
| S4-13 | Detalle de evaluación expandible en historial admin               | 3      | Completado |
| S4-10 | Exportación CSV end-to-end                                        | 3      | Descartado |
| S4-11 | Tests unitarios backend (pytest, cobertura 96%, 389 tests)        | 8      | Completado |
| S4-12 | Despliegue Cloud Run (backend + frontend)                         | 8      | Pendiente |
| S4-14 | Relanzar benchmark desde historial                                | 3      | Descartado |
| S4-38 | Modelo `UsuarioApp` + migración Alembic + repositorio + enum estados | 5    | Completado |
| S4-39 | Backend auth usuarios: registro, login JWT 1h, bloqueo 5 intentos, regenerar contraseña | 8 | Completado |
| S4-40 | Backend cuota: endpoint solicitar-más-tokens + consumo por comparación exitosa | 5 | Completado |
| S4-41 | Endpoints admin usuarios: listar, conceder acceso + cuota, ampliar tokens | 5  | Completado |
| S4-42 | Frontend NickPage: nick + password, flujo solicitar acceso, JWT 1h, admin login directo | 8 | Completado |
| S4-43 | Frontend BenchmarkPage: contador consultas (X de Y), bloqueo cuota, solicitar más consultas | 5 | Completado |
| S4-44 | Frontend panel admin gestión usuarios: tabla estados + acciones conceder/ampliar | 8 | Completado |
| S4-45 | Correcciones UX: formulario registro, terminología consultas, historial huérfano, popup pendientes | 3 | Completado |
| S4-46 | Auditoría de seguridad y endurecimiento del sistema de autenticación | 5 | Completado |
| S4-47 | Fix producción: interceptor 401 en benchmarkApi + guard BatLoader.onComplete | 3 | Completado |
| S4-48 | Fix subida ficheros: nginx client_max_body_size + FileSizeModal + validación cliente | 5 | Completado |
| S4-49 | Tratamiento visual de censura en historial (TablaAdmin + EvalViewModal) | 3 | Completado |
| S4-50 | Dashboard: estado vacío con acceso a primera valoración tras reset del estudio | 2 | Completado |
| S4-51 | Bloqueo benchmark si hay evaluación pendiente + popup al iniciar sesión | 5 | Completado |
| S4-52 | Fix: admin veía banner de evaluación pendiente + limpiar token usuario al login admin | 2 | Completado |
| S4-53 | UX: cerrar sesión movido al dropdown del nick pill en la topbar | 2 | Completado |
| S4-54 | AutoStats: cabecera con chips de modelos + columnas con icono y nombre completo | 3 | Completado |
| S4-55 | BenchmarkCard imagen: eliminar coste (valor fijo no informativo) | 1 | Completado |
| S4-56 | BenchmarkCard imagen: doble clic abre/cierra lightbox | 1 | Completado |
| S4-57 | Identidad visual: logo LOGO_TFG.png + favicon + textos UI actualizados | 2 | Completado |
| S4-58 | Limpieza código muerto: renombrado Mermaid→MapaMental, React.X types, imports flake8 | 2 | Completado |
| S4-59 | Fix imágenes rotas en historial: URL expiry DALL-E/Grok + fallback base64 + miniatura 512px | 3 | Completado |
| S4-60 | Filtrado panel admin en servidor (backend query params + WHERE SQLAlchemy dinámico) | 5 | Completado |
| S4-61 | Ajuste bidireccional de cuota admin (ampliar y reducir, clamping a 0) | 2 | Completado |
| S4-62 | Reset evaluaciones de usuario específico con nueva cuota (endpoint + ResetModal destructivo) | 5 | Completado |
| S4-63 | Guía bienvenida: eliminar logo watermark + fondo índigo #0e0b22 | 1 | Completado |
| S4-64 | Topbar nav: etiqueta "Gestiones Administrador" para admin + borde blanco + sombra glow | 2 | Completado |
| S4-65 | Pestañas admin "Comparativas/Usuarios": borde blanco + sombra glow (mismo estilo topbar) | 1 | Completado |
| S4-66 | Responsive móvil: grids BenchmarkCard, valoración, EvalViewModal, ranking DnD | 3 | Completado |
| S4-67 | Tabla admin: overflow-x-auto + min-w-[860px] para scroll horizontal en móvil | 1 | Completado |
| S4-68 | Historial usuario: columnas de ancho fijo + overflow-x-auto para alineación entre filas | 2 | Completado |
| S4-69 | Ranking DnD: TouchSensor + rectSortingStrategy + grid 2×4 para funcionamiento en móvil | 3 | Completado |
| S4-70 | Tabla usuarios y comparativa AutoStats: scroll horizontal en móvil (extensión de S4-67) | 1 | Completado |
| S4-71 | Export CSV admin: endpoint `/admin/evaluaciones/exportar-csv` + botón en TablaAdmin con respeto a filtros | 8 | Completado |
| S4-72 | Sanitización de credenciales en `mensaje_error` de `ResultadoLLM` (defensa centralizada en `__post_init__`) | 5 | Completado |
| S4-73 | Subcategoría persistida (`subcategoria_csv`) en BD para CSV — revisión parcial de ADR-014 | 5 | Completado |
| S4-74 | CSV: columna `valoracion_estado` (`valorada`/`pendiente`/`no_aplica`) para filtrado explícito | 2 | Completado |
| S4-75 | Filtros de fecha admin: precisión de hora y minuto con `datetime-local` + ISO UTC | 3 | Completado |
| S4-76 | DateTimePicker custom (react-day-picker + date-fns): DD/MM/YYYY garantizado + selector hora/minuto en modal expandido | 5 | Completado |
| S4-77 | Unificación tablas `users` + `usuarios_app` con flag `is_admin` y promover/degradar (supersede ADR-024 → ADR-027) | 13 | Completado |
| S4-78 | Rol root vs admin promovido: solo el seeded root puede gestionar roles + Secret Manager para ADMIN_PASSWORD + migración pre-seed en deploy guide | 5 | Completado |
| S4-79 | Reorganización catálogo diagramas UML: naming descriptivo, catálogo Mermaid editable y script `render_puml.py` para regenerar PNGs | 3 | Completado |
| S4-80 | Estética uniforme en todos los PlantUML: fondo blanco, fuente negra, rellenos pastel, separación flujo admin/usuario, troceado para A4 | 3 | Completado |
| S4-81 | Memoria TFG V2 + inventario 31 RFs por actor + docx final con 24 UMLs embebidos | 8 | Completado |
| S4-82 | Ranking anti-sesgo: slots vacíos + pool sin orden predefinido — elimina el sesgo de posición inicial (ADR-028) | 5 | Completado |
| S4-83 | Nick case-insensitive en login, registro y verificación de cuota | 2 | Completado |
| S4-84 | UX flujo guiado por pasos: bloqueo secuencial + parpadeos de atención en el paso activo | 5 | Completado |
| S4-85 | Cuarto paso unificado en BenchmarkPage + botón cerrar en EvalViewModal | 3 | Completado |
| S4-86 | Tarifas LLM versionadas con caché + auditoría de precios oficiales + precisión Decimal en coste | 5 | Completado |
| S4-87 | Edición imagen nativa Gemini/Grok (API Files + upload base64) + gráfica coste por modo de imagen en dashboard | 5 | Completado |
| S4-88 | Sub-experimento bilingüe ES vs EN: doble ronda de llamadas + métricas comparativas en dashboard con selector lateral (ADR-029) | 8 | Completado |
| S4-89 | Pulido UX bilingüe: `BotonVerEn` con hover/glow, toggle ampliar/contraer textos ES y EN, admin modal filtra respuestas por idioma, CSV europeo (`;` + `,` decimal) | 3 | Completado |
| S4-90 | UX: renombrar pestaña nav a "Benchmark" + botón "Nueva Comparativa" en paso 4 con reset completo y scroll al inicio | 1 | Completado |
| S4-91 | Auditoría completa de fórmulas de métricas + fix sesgo: excluir `tuvo_error=True` de las tres consultas de media de rating humano | 3 | Completado |
| S4-92 | UX traducción: sin idioma por defecto + parpadeo + mínimo 10 palabras          | 2      | Completado |
| S4-93 | UX resumen: contador 300 palabras + parpadeo + botón "Generar texto" con selector LLM | 5 | Completado |
| S4-94 | Backend endpoint GET /benchmarks/texto-ejemplo + RespuestaTextoEjemplo + lógica Auto=más barato | 5 | Completado |
| S4-95 | RF-17: persistir texto_entrada autogenerado + migración Alembic q6f7a8b9c0d1 + acordeón historial | 8 | Completado |
| S4-96 | Dashboard: añadir "Generación de código" al texto del sub-experimento bilingüe | 1 | Completado |
| S4-97 | BatLoader: modal de carga con murciélago al pulsar "✨ Generar texto" en resumen   | 3 | Completado |
| S4-98 | BatLoader: gotas sangre → iconos LLM a mitad de trayecto + balanceo al caer       | 5 | Completado |
| S4-99 | UX resumen: readonly texto autogenerado + mínimo 305 palabras + "Limpiar Texto" + acordeón en resultados | 5 | Completado |
| S4-100 | UX: cohesión visual botones sección resumen (borde blanco roto, sombra hover/pulse/selected) | 2 | Completado |
| S4-101 | Backend: estado `solicitud_borrado` en enum `SessionStatus` + migración Alembic r7a8b9c0d1e2 | 3 | Completado |
| S4-102 | Backend: endpoint POST /usuarios/evaluaciones/{id}/solicitar-borrado + rechazar-borrado admin | 5 | Completado |
| S4-103 | Frontend historial usuario: botón "Solicitar borrado" (rojo/glow), ConfirmModal, resincronización localStorage | 5 | Completado |
| S4-104 | Frontend panel admin: badge naranja clickable de solicitudes + resaltado filas + botón "Rechazar" | 3 | Completado |
| S4-105 | Refactor SOLID frontend: llmProviders.ts + tokens.ts + tailwind tokens (ADR-032) | 8 | Completado |
| S4-106 | Fix cuota obsoleta al recargar: GET /usuarios/me + useEffect en Layout.tsx (ADR-033) | 3 | Completado |
| S4-107 | Documentación alineada: Cap 4/5, ADR-032/033, diagrama arq_componentes_frontend_p1 actualizado | 3 | Completado |

---

### Detalle de S4-46 — Auditoría de seguridad y endurecimiento del sistema de autenticación

Tras completar el sistema de control de acceso (ADR-024), se realizó una auditoría
formal del sistema de autenticación completo (administrador + evaluadores), identificando
8 vulnerabilidades y aplicando todas las correcciones viables en el alcance del TFG.

**Vulnerabilidades críticas corregidas:**

- **C1 — `secret_key` insegura por defecto:** se añadió comentario prominente en
  `config.py` con el comando `openssl rand -hex 32` para recordar que la clave debe
  sobreescribirse obligatoriamente antes del despliegue.
- **C2 — Enumeración de nicks sin límite:** `GET /usuarios/verificar/{nick}` no tenía
  decorador `@limitador.limit`. Se añade `@limitador.limit("20/minute")` + parámetro
  `request: Request` requerido por slowapi.

**Vulnerabilidades medias corregidas:**

- **M1 — Enumeración via código HTTP:** login devolvía 404 para nick inexistente y 401
  para contraseña incorrecta, permitiendo distinguir ambos casos. Unificado a 401 con
  mensaje genérico `"Credenciales incorrectas."` en ambos caminos.
- **M2 — Contador de intentos expuesto:** el mensaje de 401 incluía `"Intentos restantes: X"`.
  Eliminado. El mensaje es ahora invariante: `"Credenciales incorrectas."`.
- **M3 — DoS selectivo en regenerar-contraseña:** reducido el rate limit de `5/minute`
  a `2/minute` para dificultar el forzado repetido de cuentas a `pendiente_acceso`.
- **M4 — Token admin de 8 horas:** `access_token_expire_minutes` reducido de 480 a 120
  (2 horas) para limitar la ventana de exposición de un JWT de administrador comprometido.

**Vulnerabilidades bajas corregidas:**

- **B1 — CORS permisivo:** `allow_methods=["*"]` → `["GET", "POST", "PUT", "DELETE", "PATCH"]`;
  `allow_headers=["*"]` → `["Authorization", "Content-Type"]`.
- **B2 — Swagger en producción:** `docs_url`, `redoc_url` y `openapi_url` pasan a `None`
  cuando `ENVIRONMENT=production`, deshabilitando la exposición del esquema de la API.

**Vulnerabilidades aceptadas para el alcance del TFG:**
JWT en localStorage (vs. cookies HttpOnly), sin invalidación de tokens en logout,
sin política de complejidad de contraseñas.

**Documentación generada:**
- `docs/decisions/ADR-025-endurecimiento-seguridad-autenticacion.md`
- `docs/guides/03_seguridad_autenticacion.md`

---

### Detalle de S4-11 — Tests unitarios backend (pytest, cobertura ≥ 70 %)

**Objetivo final alcanzado: 96 % de cobertura, 389 tests, 0 fallos.**
(Fase 1: 215 tests, 71 %; Fase 2: 389 tests, 96 %.)

#### Estrategia de aislamiento

PostgreSQL nativo impide usar SQLite en pruebas de integración (ENUMs y tipos
específicos del motor). Por eso todos los tests de Sprint 4 usan la estrategia
de **mocks puros**: los repositorios y la sesión `AsyncSession` se sustituyen por
`MagicMock` + `AsyncMock` (stdlib). Los objetos ORM se emulan con `SimpleNamespace`,
que permite acceder a atributos directamente sin el overhead de SQLAlchemy.

Los tests de routers usan `dependency_overrides` de FastAPI para inyectar mocks
directamente (omitiendo la capa JWT/base de datos), evitando interferencias del
rate limiter en el conjunto completo de tests.

#### Archivos de test añadidos (Fase 1 — 71 %)

| Archivo | Módulo cubierto | Tests |
|---|---|---|
| `test_security.py` | `core/security.py` | 17 |
| `test_usuario_auth_service.py` | `services/usuario_app_auth_service.py` | 20 |
| `test_evaluacion_service.py` | `services/evaluacion_service.py` | 8 |
| `test_benchmark_service.py` | `services/benchmark_service.py` (métodos puros) | 18 |
| `test_stats_service.py` | `services/stats_service.py` (métodos privados) | 26 |
| `test_usuario_app_admin_service.py` | `services/usuario_app_admin_service.py` | 13 |
| `test_auth_service.py` | `services/auth_service.py` | 9 |
| `test_metricas.py` | `llm_engine/metricas.py` | 31 |
| `test_base_client.py` | `llm_engine/clients/base_client.py` | 11 |
| `test_runner.py` | `llm_engine/runner.py` | 20 |
| `test_usuario_app_repository.py` | `repositories/usuario_app_repository.py` | 20 |
| `test_user_repository.py` | `repositories/user_repository.py` | 10 |
| `test_benchmark_service_dto.py` | `benchmark_service._construir_dto`, `obtener_por_id`, `ejecutar` (guards) | 12 |

#### Archivos de test añadidos (Fase 2 — de 71 % a 96 %)

| Archivo | Módulo cubierto | Tests |
|---|---|---|
| `test_claude_client.py` | `llm_engine/clients/claude_client.py` | 10 |
| `test_openai_client.py` | `llm_engine/clients/openai_client.py` | 17 |
| `test_gemini_client.py` | `llm_engine/clients/gemini_client.py` | 13 |
| `test_grok_client.py` | `llm_engine/clients/grok_client.py` | 13 |
| `test_router_stats.py` | `routers/stats.py` | 3 |
| `test_router_evaluacion.py` | `routers/evaluacion.py` | 6 |
| `test_router_benchmark.py` | `routers/benchmark.py` | 8 |
| `test_router_admin.py` | `routers/admin.py` | 11 |
| `test_router_usuarios.py` | `routers/usuarios.py` | 12 |
| `test_router_upload.py` | `routers/upload_router.py` | 16 |
| `test_dependencies.py` | `core/dependencies.py` | 15 |
| `test_stats_service_obtener.py` | `services/stats_service.obtener()` | 6 |
| `test_benchmark_evaluacion_repository.py` | `repositories/benchmark_evaluacion_repository.py` | 18 |
| `test_llm_response_repository.py` | `repositories/llm_response_repository.py` | 14 |
| `test_user_evaluation_repository.py` | `repositories/user_evaluation_repository.py` | 17 |

#### Cobertura por módulo clave (resultado final)

| Módulo | Cobertura |
|---|---|
| `core/security.py` | 100 % |
| `services/auth_service.py` | 100 % |
| `services/evaluacion_service.py` | 100 % |
| `services/usuario_app_admin_service.py` | 100 % |
| `services/usuario_app_auth_service.py` | 100 % |
| `services/stats_service.py` | 100 % |
| `llm_engine/runner.py` | 100 % |
| `llm_engine/clients/base_client.py` | 100 % |
| `llm_engine/clients/claude_client.py` | 100 % |
| `llm_engine/clients/openai_client.py` | 96 % |
| `llm_engine/clients/gemini_client.py` | 100 % |
| `llm_engine/clients/grok_client.py` | 96 % |
| `repositories/llm_response_repository.py` | 100 % |
| `repositories/user_evaluation_repository.py` | 100 % |
| `repositories/usuario_app_repository.py` | 92 % |
| `repositories/user_repository.py` | 81 % |
| `repositories/benchmark_evaluacion_repository.py` | 90 % |
| `routers/admin.py` | 100 % |
| `routers/benchmark.py` | 100 % |
| `routers/evaluacion.py` | 100 % |
| `routers/stats.py` | 100 % |
| `routers/upload_router.py` | 100 % |
| `routers/usuarios.py` | 100 % |
| `core/dependencies.py` | ~85 % |
| `services/benchmark_service.py` | 71 % |
| **TOTAL** | **96 %** |

El 4 % restante corresponde a rutas de `benchmark_service.py` (líneas 141–192,
ejecución real multi-LLM) que requieren llamadas reales a las APIs externas,
y dos métodos de repositorio (`listar_por_nickname`, `listar_todas`) no invocados
en el flujo de tests mock.

#### Decisiones de diseño de los tests

- **Mock de `AsyncSession`:** se crea con `MagicMock()` y se le añaden
  `db.flush = AsyncMock()`, `db.refresh = AsyncMock()`, `db.execute = AsyncMock(...)`.
  El resultado de `execute` es un `MagicMock` con `.scalar_one_or_none()` o
  `.scalars().all()` configurados según el caso.

- **`asyncio_mode = auto` en `pytest.ini`:** todos los tests `async def` se ejecutan
  sin decorador `@pytest.mark.asyncio`, lo que reduce el boilerplate.

- **`dependency_overrides` para routers:** los endpoints protegidos con JWT se testean
  inyectando un mock de admin/usuario directamente, sin pasar por el rate limiter.
  Esto evita que el límite `10/minute` del endpoint `/auth/login` bloquee el conjunto
  completo de tests cuando se ejecutan en paralelo.

- **Mocks de clientes LLM SDK:** `AsyncAnthropic.messages.create`, `AsyncOpenAI.chat.completions.create`
  y `AsyncOpenAI.images.generate/edit` se reemplazan con `AsyncMock` asignando
  directamente al atributo del cliente (`cliente._client.messages.create = AsyncMock(...)`).

- **`httpx.AsyncClient` para Gemini/Grok imagen:** se parchea como context manager con
  `__aenter__`/`__aexit__` como `AsyncMock` para simular llamadas HTTP a las APIs de imagen.

- **Tests de `generar_miniatura`:** usan `PIL.Image.new()` en memoria para crear
  imágenes de prueba sin tocar el disco. El test de fallo pasa bytes inválidos para
  ejercitar la rama `except`.

- **`construir_clientes` con todas las keys:** instancia los cuatro clientes reales
  (SDK) con claves ficticias `"sk-ant"`, etc. Los SDKs solo almacenan la clave en
  `__init__` sin llamar a la API, por lo que la prueba es segura en CI.

---

### Detalle de S4-47 — Fix producción: interceptor 401 en `benchmarkApi.ts` + guard `BatLoader.onComplete`

**Síntoma detectado en producción:** al ejecutar un benchmark desde la web
desplegada en Cloud Run, el resultado mostraba "Error al conectar con el servidor.
Comprueba que el backend está activo." Los logs de Cloud Run revelaban respuestas
401 en menos de 3 ms —tiempo incompatible con un error de red— y sin ninguna
petición registrada en el backend de base de datos.

**Causa raíz:** el JWT almacenado en `localStorage` (store `usuarioStore`) había
caducado (TTL 1 h). El valor seguía presente como cadena no nula, por lo que el
guard `RutaProtegida` lo daba por válido y permitía renderizar la página. En el
primer envío al backend, FastAPI devolvía 401 de inmediato al verificar la firma
del token.

**Corrección 1 — interceptor de response en `benchmarkApi.ts`:**

Antes del fix, `benchmarkApi.ts` solo tenía un interceptor de petición que
inyectaba el JWT en la cabecera `Authorization`. Se añadió un interceptor de
respuesta que captura el código 401 y limpia ambos stores:

```typescript
api.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error.response?.status === 401) {
      useUsuarioStore.getState().logout()
      useAdminStore.getState().clearToken()
    }
    return Promise.reject(error)
  },
)
```

Al limpiar los tokens, `RutaProtegida` detecta en el siguiente render que no hay
sesión activa y ejecuta `<Navigate to="/" replace />`, redirigiendo al usuario
a la pantalla de login sin intervención manual.

**Corrección 2 — guard en `BatLoader.onComplete`:**

El callback `onComplete` del `BatLoader` navega de la vista de carga a la vista
de resultados. Sin el guard, la transición se ejecutaba incluso si `useMutation`
había terminado con error, mostrando la pantalla de resultados vacía junto al
mensaje de error. El fix aplica la condición:

```typescript
onComplete={() => {
  setShowLoader(false)
  if (!mutacion.isError) setVista('resultados')
}}
```

Cuando la mutación termina con error (incluyendo 401), el loader desaparece pero
la vista permanece en el formulario, donde el banner de error es visible.

**Corrección 3 — mensaje de error diferenciado:**

El mensaje genérico "Error al conectar con el servidor" no distinguía entre un
backend caído y una sesión expirada. Se añadió detección del código HTTP:

```typescript
{st === 401
  ? 'Sesion expirada. Recarga la pagina para volver a iniciar sesion.'
  : 'Error al conectar con el servidor. Comprueba que el backend esta activo.'}
```

**Limpieza del path de acceso anónimo legado:**

`BenchmarkPage` aún leía el nick de `nickStore` (store legado sin JWT) como
fallback, lo que permitía cargar la página sin sesión activa. Se eliminó esa
referencia: el nick se obtiene exclusivamente de `usuarioStore` (usuario web
autenticado) o se infiere de `adminStore` (administrador):

```typescript
const nick = nickUsuario || (tokenAdmin ? 'admin' : '')
```

El `useEffect` de redirección `if (!nick) navigate('/')` se eliminó también,
ya que `RutaProtegida` en `App.tsx` es el guard canónico y hacerlo en dos
sitios creaba comportamiento impredecible.

---

### Detalle de S4-48 — Fix subida de ficheros: nginx `client_max_body_size` + `FileSizeModal` + validación cliente

**Problema 1 — PDFs bloqueados en nginx:**

La categoría Resumen permite subir un fichero `.pdf`, `.txt` o `.docx`. En
producción (Cloud Run), la subida fallaba con el mensaje "No se pudo extraer
el texto del fichero" para cualquier PDF mayor de 1 MB. El endpoint de backend
`POST /api/v1/upload/extraer-texto` no registraba ninguna petición en sus logs,
lo que descartó un error de FastAPI y apuntó directamente a la capa de nginx.

El valor por defecto de `client_max_body_size` en nginx es **1 MB**. Los ficheros
multipart que superaban ese límite recibían una respuesta HTTP 413 generada por
nginx —HTML, no JSON— antes de llegar al backend. Como el frontend esperaba JSON,
`err.response.data.detail` era `undefined`, y el mensaje de error mostrado al
usuario era el genérico "No se pudo extraer el texto".

**Fix — `nginx.conf.template`:**

```nginx
client_max_body_size 11m;
```

Se establece en 11 MB para dar margen al overhead de multipart (headers, boundary)
sobre el límite real de FastAPI de 10 MB. El comentario en el fichero explica la
relación entre ambos valores para que futuros cambios en el límite del backend se
propaguen correctamente a nginx.

**Problema 2 — sin feedback para ficheros > 10 MB:**

Si el usuario seleccionaba un fichero mayor de 10 MB, la petición pasaba nginx
(< 11 MB en base64) pero FastAPI devolvía error. No había ningún aviso previo.
Para imágenes > 5 MB, el error era aún más silencioso.

**Fix — validación cliente en `SubcatPanel.tsx`:**

```typescript
// Documentos (resumen)
if (archivo.size > 10 * 1024 * 1024) {
  setModalTamano({ tipo: 'documento', limite: '10 MB' })
  setArchivoNombre(null)
  return
}

// Imágenes (describir / modificar)
if (archivo.size > LIMITE_BYTES) {   // LIMITE_BYTES = 5 * 1024 * 1024
  setModalTamano({ tipo: 'imagen', limite: '5 MB' })
  return
}
```

La validación se ejecuta antes de cualquier llamada a la API, lo que evita
completamente la petición de red fallida.

**Nuevo componente `FileSizeModal.tsx`:**

Modal de aviso emergente con dos variantes (`'documento'` / `'imagen'`). Sustituye
a los mensajes de error en línea que pasaban desapercibidos. Características:

- Backdrop oscuro con `backdropFilter: blur(4px)` que oscurece el fondo.
- Ilustración con emoji a 72 px y escena `📁 ➡️ 🚧` para comunicar el problema
  sin necesidad de leer el texto.
- Variante documento: emoji 🐋 + "¡El fichero es enorme!"; variante imagen: emoji
  🐘 + "¡La imagen pesa demasiado!".
- Cierre con el botón "Entendido" (con `autoFocus`), con la tecla Escape delegada
  al `onClick` del backdrop, o haciendo clic fuera del panel.

La tabla de contenidos por variante se define estáticamente fuera del componente
(`CONTENIDO: Record<Props['tipo'], {...}>`) para evitar recreaciones en cada render.

---

### Detalle de S4-49 — Tratamiento visual de censura en historial

**Problema detectado:** al consultar el historial de una evaluación fallida por
política de contenido, los errores se mostraban como texto plano. El formato visible
en `DetalleComparativaModal` del panel de administrador era:

```
dall-e-3           [badge Error]
────────────────────
Contenido rechazado por las politicas de seguridad de OpenAI (content_policy_violation).
```

En cambio, la vista de resultados inmediatos (`BenchmarkCard`) mostraba el
tratamiento visual especial: icono 🚫, etiqueta "Política de seguridad" y
descripción breve. La inconsistencia hacía que el historial pareciera un
listado técnico de excepciones en lugar de una vista de usuario.

**Fix — función `esCensura()` extraída a los dos componentes:**

Se definió la misma función en `TablaAdmin.tsx` y `EvalViewModal.tsx`:

```typescript
function esCensura(msg: string | null | undefined): boolean {
  if (!msg) return false
  const m = msg.toLowerCase()
  return (
    m.includes('content_policy') ||
    m.includes('politicas de seguridad') ||
    m.includes('filtros de seguridad') ||
    m.includes('safety system')
  )
}
```

Los patrones coinciden con los mensajes normalizados por S4-25, garantizando
coherencia entre la detección del backend y la del frontend.

**`TablaAdmin.tsx` — `DetalleComparativaModal`:**

El bloque de contenido de cada tarjeta de modelo en el modal de detalle pasa de
mostrar texto plano a diferenciar dos casos:

- **Censura:** `<div>` centrado con 🚫 a 3xl + "Politica de seguridad" en rojo +
  descripción breve "Este modelo rechazo el prompt por sus filtros de contenido."
- **Error técnico:** `<div>` alineado a la izquierda con ⚠ + mensaje de error en
  cursiva, mismo patrón que `BenchmarkCard`.

**`EvalViewModal.tsx` — formulario de evaluación:**

Las tarjetas de modelos con error en el formulario de rating mostraban solo el
nombre tachado + "Error" en pequeño, sin ninguna indicación del motivo. Con el fix,
si `esCensura(r.mensaje_error)` es verdadero, la tarjeta muestra 🚫 a 1.25rem +
"Politica de seguridad" en rojo. Si es otro tipo de error, permanece el texto
"Error" original.

---

### Detalle de S4-50 — Dashboard: estado vacío con acceso a primera valoración

**Problema:** tras ejecutar el "Reset estudio" desde el panel de administrador
(`TablaAdmin`), navegar a `/dashboard` producía una pantalla completamente en
blanco —sin header, sin mensaje, sin menú de navegación—. No había ningún
`ErrorBoundary` que capturara la excepción, y React desmontaba el árbol completo.

**Causa raíz:** con el estudio reseteado, el endpoint `/api/v1/stats` devuelve
`metricas_por_modelo: []`. Los componentes de gráfico (`GraficoRating`,
`GraficoScatter`, `GraficoLatencia`, etc.) llaman a `.reduce()` sobre ese array
vacío sin valor inicial, lo que lanza `TypeError: Reduce of empty array with no
initial value`. React no captura esta excepción en producción y desmonta la
página completa, incluyendo el `Layout` que contiene el header.

**Fix — guardia de estado vacío en `DashboardPage`:**

Se añadió un bloque de retorno temprano, después de las comprobaciones de carga
y error, que detecta la condición antes de que ningún gráfico intente renderizarse:

```typescript
if (data.metricas_por_modelo.length === 0) {
  return (
    <div className="max-w-[1200px] mx-auto">
      <div className="card flex flex-col items-center justify-center py-20 gap-4 text-center">
        <span style={{ fontSize: 72, lineHeight: 1 }}>📊</span>
        <p className="text-lg font-semibold text-text">Sin datos todavia</p>
        <p className="text-sm text-muted leading-relaxed max-w-sm">
          El estudio no tiene ninguna evaluacion completada.
          Ejecuta la primera comparativa para empezar a ver resultados.
        </p>
        <Link to="/benchmark" className="btn-primary mt-2">
          Crear primera valoracion
        </Link>
      </div>
    </div>
  )
}
```

La guardia usa `metricas_por_modelo.length === 0` en lugar de
`total_evaluaciones === 0` porque ese campo es el que alimenta directamente los
gráficos que lanzan la excepción. Si hubiera evaluaciones en curso o fallidas pero
sin datos de métricas agregadas, la pantalla también se protege.

El `Link` de React Router evita una recarga completa de la aplicación al navegar
a `/benchmark`, manteniendo el estado de los stores Zustand.

---

### Detalle de S4-51 — Bloqueo de benchmark si hay evaluación pendiente + popup al iniciar sesión

**Motivación:** la validez del estudio requiere que cada evaluador valore cada
comparativa antes de lanzar otra nueva. Sin este control, un usuario podría
ejecutar diez benchmarks seguidos sin evaluar ninguno, lo que haría que las
puntuaciones del dashboard reflejasen solo los usuarios que recordaron evaluar
de forma voluntaria.

**Fuente de verdad:** `historialStore` (Zustand, persiste en `localStorage`).
Cada sesión almacenada tiene `estado: SessionStatus` y `evaluada?: boolean`.
Una sesión está pendiente cuando `estado === 'completada' && !evaluada`.
- Las sesiones con `estado === 'fallida'` (censura de contenido) no bloquean:
  son el resultado de un prompt rechazado y ya están marcadas correctamente
  en la base de datos sin necesidad de valoración del usuario.
- El administrador no tiene restricción: `esUsuarioWeb === false` → `evaluacionPendiente = null`.

**`BenchmarkPage.tsx` — selector reactivo y bloqueo:**

```typescript
const sesionesHistorial   = useHistorialStore((s) => s.sesiones[nick] ?? [])
const evaluacionPendiente = esUsuarioWeb
  ? (sesionesHistorial.find((s) => s.estado === 'completada' && !s.evaluada) ?? null)
  : null
```

El selector es reactivo: cuando `marcarEvaluada(nick, id)` se llama en
`evalMutacion.onSuccess`, Zustand notifica el cambio y `evaluacionPendiente`
pasa de un objeto a `null` en el mismo render, habilitando el botón sin
necesidad de recarga.

`puedeEnviar` se actualiza para incluir la condición:
```typescript
const puedeEnviar = prompt.trim().length >= 10
  && !mutacion.isPending
  && !cuotaAgotada
  && !evaluacionPendiente
```

**Banner informativo:**

Cuando `evaluacionPendiente !== null`, aparece un banner amarillo entre el
contador de cuota y el selector de categoría, con el id de la comparativa
pendiente y un botón "Ir a evaluarla →" que navega a `/historial`. El
botón "Comparar modelos" queda deshabilitado con el texto normal —el banner
ya explica el motivo, por lo que no se cambia el texto del botón para no
generar confusión.

**`NickPage.tsx` — popup al iniciar sesión:**

Tras un login exitoso (`entrar()`), y una vez hidratado el store (tanto si se
llamó a `limpiarHistorial` como si no), se consulta el estado actual del
historial antes de navegar:

```typescript
const sesiones  = useHistorialStore.getState().sesiones[respuesta.nick] ?? []
const pendiente = sesiones.find((s) => s.estado === 'completada' && !s.evaluada)
if (pendiente) {
  setTienePendienteEval(true)
  return           // no navegar todavía
}
navigate('/benchmark')
```

Si hay sesión pendiente, en lugar de navegar se activa el estado
`tienePendienteEval`, que muestra un modal de pantalla completa con:
- Icono ⏳ en recuadro amarillo semitransparente.
- Título "Tienes una evaluacion pendiente" + descripción.
- Único botón "Ir a evaluarla →" que navega a `/historial`.
- Sin botón de cerrar ni opción de omitir: el benchmark estará bloqueado
  igualmente, por lo que el único flujo útil es ir a evaluar.

**Flujo completo verificado:**
1. Usuario evalúa benchmark → `marcarEvaluada` → `evaluacionPendiente = null` → puede crear otro.
2. Usuario lanza benchmark sin evaluar → en formulario aparece banner → botón deshabilitado.
3. Usuario vuelve a iniciar sesión con benchmark pendiente → popup → va a historial → evalúa → popup no vuelve a aparecer en el siguiente login.
4. Admin: sin restricción en ningún paso.
5. Sesiones `fallida`: no bloquean (check `estado === 'completada'` las excluye).

---

## Impedimentos y resoluciones

**Múltiples cabezas en Alembic**
Al crear la migración de eliminación de tags/notas se produjo un error
de múltiples cabezas porque existía una rama ya aplicada
(`b1c3e5f7a9d2`). Se resolvió inspeccionando `alembic current` para
identificar la cabeza activa y ajustando `down_revision` a ese valor.
Lección: antes de crear una migración nueva, siempre ejecutar
`alembic current` para confirmar el estado real de la base de datos.

**grok-3 no soporta visión multimodal**
Al implementar la carga de imagen para "describir imagen", las llamadas a `grok-3`
con `imagen_base64` devolvían error 400 `"Image inputs are not supported by this model"`.
xAI mantiene un modelo separado `grok-2-vision-1212` para visión. Se añadió
`_MODELO_VISION` en `GrokClient` con selección dinámica en `completar()`. Lección:
verificar capacidades de visión de cada modelo antes de asumir compatibilidad entre
el modelo de texto y el de visión del mismo proveedor.

**Bug TDZ en BenchmarkPage**
En la primera implementación del BatLoader, el `useEffect` que activaba
el loader referenciaba `mutacion.isPending` antes de que la constante
`mutacion` estuviera declarada (violación Temporal Dead Zone). TypeScript
no detectó el error en ese momento porque el check no se ejecutó
inmediatamente. Se corrigió moviendo el `useEffect` a después de la
declaración de `useMutation`.

---

## Artefactos entregados (parcial)

- `frontend/src/components/shared/BatLoader.tsx` — componente carga animada
- `frontend/src/components/shared/BatLoader.css` — animaciones CSS del murciélago
- `frontend/src/components/historial/EvalViewModal.tsx` — modal evaluación
- `backend/alembic/versions/a3b5c7d9e1f2_drop_tags_notas_evaluacion.py`
- `docs/decisions/ADR-018-batloader-animacion-carga.md`
- `docs/decisions/ADR-019-evaluacion-solo-lectura.md`
- `backend/app/routers/upload_router.py` — extracción de texto desde ficheros
- `frontend/src/services/uploadApi.ts` — cliente del endpoint de extracción
- `docs/decisions/ADR-021-carga-ficheros-resumen.md`
- `docs/decisions/ADR-022-vision-multimodal-describir-imagen.md`
- `docs/decisions/ADR-023-manejo-errores-politica-seguridad-llm.md` (actualizado — Fase 2 añadida)
- `backend/alembic/versions/e1f2a3b4c5d6_rating_min_uno_revert_censura.py`
- `docs/memoria/chapters/refinamiento_metricas_sesgo.md` (actualizado — Sesgos 6 y 7 + condiciones de filtrado + tabla de trazabilidad)
- `backend/alembic/versions/f3b4c5d6e7a8_add_es_generacion_imagen.py` — ADD COLUMN + backfill evaluaciones completadas
- `backend/alembic/versions/a4b5c6d7e8f9_fix_es_generacion_imagen_fallidas.py` — fix backfill evaluaciones `fallida` no marcadas
- `backend/app/llm_engine/clients/base_client.py` — SOPORTA_EDICION_IMAGEN flag + editar_imagen() con limpieza de prefijo
- `backend/app/llm_engine/clients/openai_client.py` — editar_imagen() con gpt-image-1, conversión JPEG→PNG, timeout 120s
- `backend/app/llm_engine/clients/grok_client.py` — timeout AsyncOpenAI 120s
- `backend/app/llm_engine/runner.py` — 4ª ruta es_imagen AND imagen_base64 → editar_imagen()
- `backend/app/services/benchmark_service.py` — fix es_descripcion: elimina `or bool(imagen_base64)`
- `frontend/src/services/benchmarkApi.ts` — interceptor response 401: logout + clearToken (S4-47)
- `frontend/src/pages/BenchmarkPage.tsx` — guard `if (!mutacion.isError)` en BatLoader.onComplete; mensaje 401 diferenciado; limpieza path anónimo legado (S4-47)
- `frontend/nginx.conf.template` — `client_max_body_size 11m` para ficheros hasta 10 MB (S4-48)
- `frontend/src/components/shared/FileSizeModal.tsx` — modal emergente con emoji para límite de tamaño superado (S4-48, nuevo fichero)
- `frontend/src/components/benchmark/SubcatPanel.tsx` — validación cliente antes de llamada API: docs > 10 MB, imágenes > 5 MB (S4-48)
- `frontend/src/components/historial/TablaAdmin.tsx` — función esCensura() + render 🚫/⚠ en DetalleComparativaModal (S4-49)
- `frontend/src/components/historial/EvalViewModal.tsx` — función esCensura() + icono 🚫 en formulario de rating (S4-49)
- `frontend/src/pages/DashboardPage.tsx` — guardia estado vacío + Link "Crear primera valoracion" cuando metricas_por_modelo es vacío (S4-50)
- `frontend/src/pages/NickPage.tsx` — estado tienePendienteEval + popup ⏳ al login si hay evaluacion sin valorar (S4-51)
- `frontend/src/pages/BenchmarkPage.tsx` — selector evaluacionPendiente + banner amarillo + puedeEnviar incluye !evaluacionPendiente (S4-51)
- `frontend/src/pages/BenchmarkPage.tsx` — guard `esUsuarioWeb && !tokenAdmin` en evaluacionPendiente; guard admin en selector (S4-52)
- `frontend/src/pages/NickPage.tsx` — `logoutUsuario()` al inicio de `entrarAdmin()` para limpiar token usuario web residual (S4-52)
- `frontend/src/components/shared/Layout.tsx` — dropdown nick pill con "Cerrar sesion"; importa adminStore + usuarioStore; `cerrarSesion()` limpia ambos tokens (S4-53)
- `frontend/src/components/historial/TablaAdmin.tsx` — eliminado prop `onLogout` e interfaz + botón "Cerrar sesion" de cabecera (S4-53)
- `frontend/src/components/historial/TablaUsuarios.tsx` — eliminado prop `onLogout` e interfaz + botón "Cerrar sesion" de cabecera (S4-53)
- `frontend/src/pages/HistorialPage.tsx` — eliminado selector `clearToken` y props `onLogout` en TablaAdmin y TablaUsuarios (S4-53)
- `frontend/src/pages/BenchmarkPage.tsx` — `AutoStats`: cabecera con chips de modelo al estilo "Modelos que participan" + columnas con icono 20px + nombre completo coloreado (S4-54)
- `frontend/src/components/benchmark/BenchmarkCard.tsx` — eliminado `<Metrica label="Coste" ...>` de la rama `es_imagen`; grid pasa de 2 cols a flex (S4-55)
- `frontend/src/components/benchmark/BenchmarkCard.tsx` — `onDoubleClick` en tarjeta abre lightbox si `es_imagen && url_imagen`; `onDoubleClick` en imagen del lightbox llama `cerrarModal()` (S4-56)
- `frontend/public/logo-tfg.png` — PNG del logo copiado a public/ para favicon (S4-57, nuevo fichero)
- `frontend/index.html` — `<link rel="icon" type="image/png" href="/logo-tfg.png">` (S4-57)
- `frontend/src/components/shared/Layout.tsx` — sustituye `<LogoSvg>` por `<img src={logoTfg}>`, texto "de LLMs", enlace nav "Nueva Comparativa" (S4-57)
- `frontend/src/pages/NickPage.tsx` — sustituye `<LogoSvg>` por `<img src={logoTfg}>` en pantalla de login (S4-57)
- `backend/app/llm_engine/resultado.py` — eliminado import `field` no usado (S4-58)
- `backend/app/llm_engine/runner.py` — eliminado import `LLMProvider` no usado (S4-58)
- `backend/app/routers/auth.py` — eliminado import `status` no usado (S4-58)
- `frontend/src/components/historial/VisorImagen.tsx` — fallback state-based: `imagenMiniatura` primero, URL como respaldo con `onError` (S4-59)
- `backend/app/repositories/benchmark_evaluacion_repository.py` — `listar_todas()` con 7 parámetros de filtro y `and_(*condiciones)` dinámico (S4-60)
- `backend/app/routers/admin.py` — Query params de filtro en `listar_evaluaciones` + endpoint `resetear-evaluaciones` (S4-60, S4-62)
- `frontend/src/services/adminApi.ts` — interfaz `FiltrosAdmin` + `listarEvaluacionesAdmin` con params dinámicos + `resetearEvaluacionesUsuario()` (S4-60, S4-62)
- `frontend/src/components/historial/TablaAdmin.tsx` — filtros en servidor, eliminado `useMemo` client-side, queryKey incluye `filtrosActivos` (S4-60)
- `backend/app/schemas/usuario_app.py` — `tokens_adicionales` sin `ge=1` + `PeticionResetearEvaluaciones` + `RespuestaResetearEvaluaciones` (S4-61, S4-62)
- `backend/app/repositories/usuario_app_repository.py` — `ampliar_tokens()` con `max(0, ...)` + método `resetear_cuota()` (S4-61, S4-62)
- `backend/app/services/usuario_app_admin_service.py` — método `resetear_evaluaciones_usuario()` (S4-62)
- `frontend/src/components/historial/TablaUsuarios.tsx` — input sin min, texto dinámico ampliar/reducir, `ResetModal` destructivo, botón "↺ Reset" naranja (S4-61, S4-62)
- `frontend/src/components/shared/OnboardingGuide.tsx` — eliminado div watermark logo-tfg.png; fondo modal `#0e0b22` (S4-63)
- `frontend/src/components/shared/Layout.tsx` — `tokenAdmin` selector + label condicional "Gestiones Administrador"; borde `border-white/25` + sombra `shadow-[0_0_14px_4px_rgba(255,255,255,0.45)]` en nav activo (S4-64)
- `frontend/src/pages/HistorialPage.tsx` — pestañas admin: borde blanco + sombra glow; columnas historial usuario con ancho fijo (S4-65, S4-68)
- `frontend/src/pages/BenchmarkPage.tsx` — grids `grid-cols-1 sm:grid-cols-2 xl:grid-cols-4` en tarjetas y cajitas valoración; chips estado `grid-cols-2 sm:grid-cols-4` (S4-66)
- `frontend/src/components/historial/EvalViewModal.tsx` — puntuación `grid-cols-1 sm:grid-cols-2`; ranking `flex-wrap`; `RankingChip` con `minWidth: 5rem`; padding `px-4 sm:px-5` (S4-66)
- `frontend/src/components/historial/TablaAdmin.tsx` — contenedor tabla `overflow-x-auto` + `min-w-[860px]` (S4-67)
- `frontend/src/pages/BenchmarkPage.tsx` — `TouchSensor` + `activationConstraint: { distance: 5 }` + `rectSortingStrategy`; `touch-action: none` en RankingChip button; ranking container `grid grid-cols-2 sm:grid-cols-4` (S4-69)
- `frontend/src/components/historial/EvalViewModal.tsx` — mismos cambios DnD que BenchmarkPage; eliminado `minWidth: 5rem` + `flex: 1` en RankingChip (S4-69)

---

### Detalle de S4-52 — Fix: admin veía banner de evaluación pendiente

**Problema:** tras el despliegue de S4-51, el administrador que hubiera iniciado sesión como
usuario web en el mismo navegador en un momento anterior veía el banner amarillo "Tienes una
evaluacion pendiente" en `BenchmarkPage`, aunque el administrador no tiene restricción de cuota
ni de evaluación.

**Causa raíz:** el selector `esUsuarioWeb = useUsuarioStore((s) => s.token !== null)` devolvía
`true` para el administrador porque un JWT de usuario web anterior permanecía en `localStorage`
(el store `usuarioStore` persiste en localStorage). Al hacer login como admin, el flujo de
`entrarAdmin()` no limpiaba el token de usuario web residual.

**Corrección 1 — guard en `BenchmarkPage`:**

```typescript
const evaluacionPendiente = esUsuarioWeb && !tokenAdmin
  ? (sesionesHistorial.find((s) => s.estado === 'completada' && !s.evaluada) ?? null)
  : null
```

La condición adicional `&& !tokenAdmin` garantiza que si hay un token de admin activo la
restricción queda desactivada, independientemente del estado del token de usuario web.

**Corrección 2 — limpiar token usuario web al hacer login admin:**

```typescript
const entrarAdmin = async () => {
  ...
  const respuesta = await loginAdmin({ email, password })
  logoutUsuario()   // limpiar token de usuario web residual en localStorage
  setTokenAdmin(respuesta.access_token)
  ...
}
```

`logoutUsuario()` del store `usuarioStore` limpia token, nick, estado y contadores de cuota
del usuario web antes de guardar el token de administrador.

---

### Detalle de S4-53 — UX: cerrar sesión movido al dropdown del nick pill

**Motivación:** el botón "Cerrar sesion" aparecía en la cabecera de `TablaAdmin` (junto a
"Reset estudio") y de `TablaUsuarios`. Esta ubicación era incongruente: el logout es una
acción de sesión, no una acción de tabla. Además, el usuario podía no encontrarlo si
estaba en la pestaña equivocada del historial.

**Solución:** el nick pill de la topbar (esquina superior derecha) pasa de ser un botón
directo que llamaba `cambiarNick()` a ser un toggle de un menú desplegable.

**`Layout.tsx` — dropdown:**

- Estado `menuAbierto` (useState).
- Ref `menuRef` para detectar clic fuera y cerrar el menú (mousedown listener en document,
  activo solo mientras `menuAbierto === true`).
- El dropdown muestra: cabecera con "Sesion activa" + nick, botón "Cerrar sesion".
- `cerrarSesion()` llama a `clearToken()` (adminStore) + `logoutUser()` (usuarioStore) +
  `clearNick()` + `navigate('/')`. Los dos primeros son seguros de llamar juntos:
  un admin tendrá token de usuario vacío y viceversa.

**Limpieza en `TablaAdmin` y `TablaUsuarios`:**

- Eliminado el prop `onLogout: () => void` de la interfaz `Props` y de la firma del componente.
- Eliminado el botón `<button onClick={onLogout}>Cerrar sesion</button>` de la cabecera de cada tabla.
- En `HistorialPage`, eliminado el selector `clearToken` del adminStore y los props `onLogout`
  en los dos usos de los componentes.

---

### Detalle de S4-54 — AutoStats: rediseño visual de cabecera y columnas

**Motivación:** la cabecera de la tabla de métricas comparativas mostraba solo el texto plano
"Comparacion automatica de metricas" y las columnas identificaban cada modelo únicamente con
la primera palabra del nombre (`chip.nombre.split(' ')[0]`), lo que generaba encabezados
ambiguos como "Claude", "GPT-4o", "Gemini", "Grok" sin contexto visual.

**Cambios en `AutoStats` dentro de `BenchmarkPage.tsx`:**

1. **Cabecera de la card:** debajo del título, se añade una fila de chips idéntica a la
   sección "3. Modelos que participan" del formulario. Cada chip muestra icono + nombre
   completo con el color del proveedor y borde de ese color. Los chips solo incluyen los
   proveedores que participaron en la evaluación concreta (`provEnTabla`).

2. **Columnas de la tabla:** cada `<th>` muestra icono del modelo (20×20 px con bordes
   redondeados) sobre el nombre completo coloreado. Antes mostraba solo el primer token.

3. **Iteración corregida:** la tabla y los chips iteran sobre `provEnTabla` (proveedores
   con al menos una respuesta sin error en esa evaluación), en lugar de `PROVEEDORES_ORDER`
   completo, de modo que si un modelo falla completamente no aparece columna vacía.

---

### Detalle de S4-55 — BenchmarkCard imagen: eliminación del coste

**Problema:** en las tarjetas de imagen generativa, el pie de métricas mostraba siempre
el mismo valor de coste (`$0.04000`) para todos los modelos. Este valor es un coste fijo
por imagen que no varía entre generaciones de un mismo modelo, por lo que no aportaba
información comparativa útil y creaba la impresión de que la métrica estaba rota.

**Corrección en `BenchmarkCard.tsx`:** en la rama `respuesta.es_imagen` del bloque de
métricas, se elimina `<Metrica label="Coste" valor={...}>` y el contenedor cambia de
`grid grid-cols-2` a `flex gap-4`, conservando únicamente `<Metrica label="Latencia">`.

La latencia sí varía entre modelos y evaluaciones, y es la métrica de rendimiento
relevante para la generación de imagen.

---

### Detalle de S4-56 — BenchmarkCard imagen: doble clic abre/cierra lightbox

**Motivación:** las respuestas de texto largas ya soportaban doble clic para ampliar/contraer
desde S4-17. Las tarjetas de imagen no tenían este atajo, lo que obligaba a usar el botón
"⤢ Ampliar" explícito.

**Correcciones en `BenchmarkCard.tsx`:**

1. **Apertura (tarjeta):** en el `onDoubleClick` del div exterior de la tarjeta, se añade
   un nuevo caso antes del texto largo:

```typescript
if (respuesta?.es_imagen && respuesta?.url_imagen) { abrirModal(); return }
```

2. **Cierre (lightbox):** en el div contenedor de la imagen ampliada dentro del lightbox,
   se añade:

```tsx
onDoubleClick={(e) => { e.stopPropagation(); cerrarModal() }}
```

El `stopPropagation` es necesario porque el div padre tiene `onClick={cerrarModal}` (que
ya cierra al hacer clic fuera de la imagen). Sin él, un doble clic en la imagen lanzaría
el handler del div padre dos veces.

El clic simple sobre la imagen en el lightbox sigue alternando el estado de zoom (`zoomActivo`)
sin interferencia: los eventos click y dblclick son independientes y no se solapan.

---

### Detalle de S4-57 — Identidad visual: logo LOGO_TFG.png + favicon + textos UI

**Motivación:** el logo SVG original (murciélago abstracto con fondo blanco) se creó como
placeholder en Sprint 3. El alumno generó el logo definitivo del TFG usando la subcategoría
de generación de imagen de la propia herramienta, exportando el resultado como `LOGO_TFG.png`.

**Cambios implementados:**

1. **Favicon del navegador:** el PNG se copió a `frontend/public/logo-tfg.png`. La ruta
   `public/` en Vite sirve ficheros estáticos directamente en la raíz del dominio. Se
   actualizó `index.html`:
   ```html
   <link rel="icon" type="image/png" href="/logo-tfg.png" />
   ```

2. **Logo en la topbar (`Layout.tsx`):** se elimina el componente `LogoSvg` y se sustituye
   por `<img src={logoTfg} className="w-9 h-9 rounded-xl">`. Como el PNG tiene fondo oscuro
   que encaja con el tema de la aplicación, se elimina el contenedor blanco que usaba el SVG.
   El import usa el alias `@/utils/LOGO_TFG.png` (Vite procesa imports de PNG mediante el
   tipo declarado en `vite-env.d.ts` a través de `/// <reference types="vite/client" />`).

3. **Logo en la pantalla de login (`NickPage.tsx`):** mismo cambio; la imagen se muestra a
   96×96 px con bordes redondeados y sombra.

4. **Textos de identidad actualizados:**
   - Topbar: "Benchmarking de Modelos de Lenguaje" → **"Benchmarking de LLMs"**
   - Enlace de navegación: "Nuevo benchmark" → **"Nueva Comparativa"** (en `ENLACES` del
     Layout y en el botón de la vista de resultados de `BenchmarkPage`)

---

### Detalle de S4-58 — Limpieza de código muerto y corrección de imports flake8

**Motivación:** varios imports no utilizados en el backend generaban advertencias de flake8 que habrían bloqueado el linter en CI. En el frontend, residuos de la fase de prototipado (nombre incorrecto del componente de mapa mental, referencias de tipo `React.X` y un componente `TooltipPersonalizado` sin uso) reducían la legibilidad sin aportar funcionalidad.

**Limpieza backend — imports no usados (flake8 F401):**

| Archivo | Import eliminado | Motivo |
|---|---|---|
| `backend/app/llm_engine/resultado.py` | `field` (de `dataclasses`) | Solo se usa `dataclass`; `field` era residuo de una versión anterior con campos con valor por defecto |
| `backend/app/llm_engine/runner.py` | `LLMProvider` (de `app.models.enums`) | El enum se eliminó del flujo del runner en una refactorización anterior |
| `backend/app/routers/auth.py` | `status` (de `fastapi`) | El router de autenticación del administrador usa respuestas sin código explícito; `status` no se referenciaba |

**Limpieza frontend:**

- **Renombrado `Mermaid` → `MapaMental`:** el componente de mapa mental de resultados llevaba el nombre interno `Mermaid` por razones históricas (en la fase de prototipado se exploró Mermaid.js como motor de renderizado antes de optar por una implementación propia). El nombre era confuso porque el componente definitivo no usa Mermaid.js en absoluto. Se renombró el fichero y todas sus referencias a `MapaMental`.
- **Referencias de tipo `React.FC` / `React.ReactNode`:** se sustituyeron por el patrón moderno con imports explícitos (`import { type FC, type ReactNode } from 'react'`), eliminando las referencias de prefijo `React.X` que requerían mantener el import del namespace completo aunque solo se usara para tipos.
- **`TooltipPersonalizado`:** componente creado en Sprint 3 como alternativa a los tooltips de la librería de componentes. Nunca se integró en la interfaz definitiva. Se eliminó el fichero y su exportación del barrel de componentes compartidos.

---

### Detalle de S4-59 — Fix imágenes rotas en historial (caducidad de URLs)

**Problema detectado:** las imágenes generadas por DALL-E 3 (OpenAI) y `grok-imagine-image` (xAI) se devuelven por sus APIs como URLs temporales firmadas con una ventana de acceso de aproximadamente 1 hora. Una vez expirada esa ventana, la URL devuelve HTTP 403 y el elemento `<img>` del historial muestra el icono de imagen rota. `Imagen 4` de Gemini devuelve la imagen directamente en base64, por lo que sus imágenes no se veían afectadas.

El campo `imagen_miniatura` (introducido en S4-21 para la vista de resultados inmediatos) ya almacenaba una versión JPEG de 512×512 px en base64. Sin embargo, el componente del historial cargaba `url_imagen` directamente sin intentar usar la miniatura.

**Corrección — miniatura a 512 px como fuente primaria:**

Se ajustó el flujo de persistencia en los clientes OpenAI y Grok para garantizar que `imagen_miniatura` se genere siempre antes de persistir el resultado, usando `generar_miniatura()` en `base_client.py`. La resolución de 512 px ofrece suficiente calidad para la vista de historial (las tarjetas muestran imágenes a un máximo de ~300 px de ancho) con un coste de almacenamiento razonable (JPEG 512×512 ≈ 25–60 KB en base64).

**Corrección — `VisorImagen` con fallback de estado:**

El componente `VisorImagen.tsx` recibe tanto `imagen_miniatura` como `url_imagen`. La lógica de selección de fuente:

```typescript
const [imgSrc, setImgSrc] = useState(imagenMiniatura ?? urlImagen ?? '')

const onError = () => {
  if (imgSrc !== imagenMiniatura && imagenMiniatura) {
    setImgSrc(imagenMiniatura)   // fallback a base64 si la URL caduca
  }
}
```

Si `imagen_miniatura` está disponible, se usa directamente sin caducidad. Si solo hay `url_imagen` (evaluaciones antiguas), se intenta la URL y ante cualquier error de carga se promueve la miniatura como fallback. Esto garantiza retrocompatibilidad con evaluaciones anteriores persistidas solo con URL.

---

### Detalle de S4-60 — Filtrado del panel admin trasladado al servidor

**Problema:** el filtro de evaluaciones en `TablaAdmin` se aplicaba mediante `useMemo` sobre los ítems de la página activa. El endpoint devolvía hasta 15 ítems paginados; el `useMemo` filtraba esos 15 por el valor del selector. Si los ítems que coincidían con el filtro estaban en páginas distintas a la activa, el resultado aparecía vacío. El caso observable: la categoría "Razonamiento" devolvía cero resultados porque todas sus evaluaciones se encontraban en páginas 2 y 3; otras categorías con evaluaciones en página 1 funcionaban aparentemente bien, lo que hacía el bug difícil de diagnosticar.

**Corrección backend — `listar_todas()` con WHERE dinámico:**

`BenchmarkEvaluacionRepository.listar_todas()` acepta ahora siete parámetros de filtro opcionales:

| Parámetro | Tipo | Filtro SQL |
|---|---|---|
| `nickname` | `str \| None` | `ilike('%nickname%')` sobre `BenchmarkEvaluacion.nickname` |
| `categoria` | `TestCategory \| None` | `== categoria` (coincidencia exacta) |
| `prompt` | `str \| None` | `ilike('%prompt%')` sobre `BenchmarkEvaluacion.prompt` |
| `estado` | `SessionStatus \| None` | `== estado` (coincidencia exacta) |
| `evaluada` | `bool \| None` | subquery `IN` sobre `user_evaluations` |
| `fecha_desde` | `date \| None` | `>= datetime(fecha, tzinfo=UTC)` |
| `fecha_hasta` | `date \| None` | `< datetime(fecha + 1 día, tzinfo=UTC)` |

Las condiciones activas se acumulan en una lista `condiciones` y se combinan con `and_(*condiciones)` de SQLAlchemy. Si la lista está vacía, se omite la cláusula WHERE (`where_clause = True`). El mismo `where_clause` se aplica a la consulta COUNT (que devuelve el total filtrado para la paginación) y a la consulta de datos. Gracias a esto, `data.total` refleja el número real de evaluaciones que coinciden con los filtros activos, no el total global.

**Corrección endpoint `listar_evaluaciones`:**

Se añadieron siete `Query(default=None)` al endpoint. El parámetro `valoracion: str | None` se convierte a `evaluada_filtro: bool | None` antes de pasarlo al repositorio:

```python
evaluada_filtro: bool | None = None
if valoracion == 'valorada':
    evaluada_filtro = True
elif valoracion == 'sin_valorar':
    evaluada_filtro = False
```

**Corrección frontend:**

- `FiltrosAdmin` (interfaz TypeScript): campos `nick`, `categoria`, `prompt`, `estado`, `valoracion`, `fechaDesde`, `fechaHasta`.
- `listarEvaluacionesAdmin` construye el objeto `params` incluyendo solo los campos con valor definido.
- En `TablaAdmin.tsx`: `queryKey: ['admin-comparativas', pagina, filtrosActivos]` hace que TanStack Query relance la petición en cuanto cambia cualquier filtro o la página.
- Se eliminó el `useMemo` de filtrado client-side; `itemsFiltrados` pasa a ser simplemente `data?.items ?? []`.
- El contador de resultados muestra `data.total` (total filtrado en servidor) en lugar del número de ítems de la página.

---

### Detalle de S4-61 — Ajuste bidireccional de cuota (ampliar y reducir)

**Motivación:** el flujo original solo permitía incrementar la cuota de un usuario. Para corregir una cuota asignada por error, o para reducirla a un evaluador que acapara recursos del estudio, el administrador tenía que eliminar la cuenta y volver a crearla, perdiendo el historial de evaluaciones del usuario.

**Cambios backend:**

- `PeticionAmpliarTokens.tokens_adicionales`: se eliminó la restricción `ge=1`. El campo acepta ahora cualquier entero, incluidos valores negativos.
- `UsuarioAppRepository.ampliar_tokens()`: el cálculo pasa de `cuota += adicionales` a `cuota = max(0, cuota + adicionales)`. Esto garantiza que, aunque el administrador envíe un delta cuya magnitud supere la cuota actual, el resultado nunca sea negativo. El estado del usuario permanece `habilitado` independientemente del signo del ajuste.

**Cambios frontend:**

- **Modal "Ajustar cuota de consultas":** título actualizado. El input numérico no tiene atributo `min`, admitiendo valores negativos sin restricción HTML5.
- **Vista previa en tiempo real:** la expresión `cuotaActual + nuevaCuota` calcula y muestra la nueva cuota resultante. Si el resultado sería 0 o negativo (antes del clamp), se muestra un aviso naranja para que el admin lo advierta antes de confirmar.
- **Validación:** `resultadoValido = nuevaCuota !== 0` (el valor 0 no tiene efecto y se deshabilita el botón).
- **Texto del botón dinámico:** "Ampliar cuota" si `nuevaCuota > 0`, "Reducir cuota" si `nuevaCuota < 0`.
- **Toast de confirmación:** diferenciado según el signo ("Cuota reducida" / "Cuota ampliada").
- **Botón en la tabla de usuarios:** texto cambiado de "+ Ampliar cuota" a "± Ajustar cuota" para comunicar visualmente que admite ambas direcciones.

---

### Detalle de S4-62 — Reset de evaluaciones de un usuario específico con nueva cuota

**Motivación:** el sistema ya permitía eliminar un usuario completo (con cascade de evaluaciones) o resetear el estudio global entero. Faltaba una operación intermedia: resetear a un usuario concreto sin eliminar su cuenta —borrando sus evaluaciones y asignándole una nueva cuota de inicio—. Resulta útil cuando un evaluador quiere repetir el estudio desde cero sin perder el acceso, o cuando el administrador quiere limpiar evaluaciones de prueba de un usuario antes del estudio definitivo.

**Cambios backend:**

*`UsuarioAppRepository.resetear_cuota()`* (nuevo método):
```python
async def resetear_cuota(self, usuario, nueva_cuota: int):
    usuario.consultas_usadas = 0
    usuario.cuota_asignada   = nueva_cuota
    usuario.estado           = EstadoUsuarioApp.habilitado
    await self._db.flush()
    await self._db.refresh(usuario)
    return usuario
```

*Schemas `usuario_app.py`* — dos nuevas clases:
- `PeticionResetearEvaluaciones`: campo `nueva_cuota: int = Field(ge=0)`. El valor 0 está permitido para dejar al usuario sin cuota hasta la próxima asignación explícita.
- `RespuestaResetearEvaluaciones`: campos `usuario: RespuestaUsuarioApp` (estado actualizado) y `evaluaciones_eliminadas: int`.

*`UsuarioAppAdminService.resetear_evaluaciones_usuario()`*:
1. Obtiene el usuario por ID; lanza HTTP 404 si no existe.
2. Llama a `BenchmarkEvaluacionRepository.eliminar_por_nickname(usuario.nick)` (reutiliza el método existente; aplica cascade a `llm_responses` y `user_evaluations`).
3. Llama a `UsuarioAppRepository.resetear_cuota(usuario, nueva_cuota)`.
4. Commit + refresh en la misma transacción.
5. Devuelve `RespuestaResetearEvaluaciones(usuario=..., evaluaciones_eliminadas=N)`.

*Endpoint* `POST /api/v1/admin/usuarios/{usuario_id}/resetear-evaluaciones` → `RespuestaResetearEvaluaciones`.

**Cambios frontend:**

*`adminApi.ts`* — función `resetearEvaluacionesUsuario(token, id, nueva_cuota)`.

*`TablaUsuarios.tsx`* — dos adiciones:

1. **Botón "↺ Reset"** (color naranja) en la fila de usuarios con estado `habilitado` o `pendiente_ampliar_tokens`. El botón de eliminación permanente (rojo "✕") sigue disponible para todos los estados.

2. **`ResetModal`** (componente local con estética destructiva):
   - Banner de advertencia ⚠️ con fondo rojo semitransparente: "Esta acción eliminará TODAS las evaluaciones de `{nick}`. Esta operación es irreversible."
   - Párrafo informativo: "El usuario seguirá siendo válido y podrá realizar nuevas comparativas con la nueva cuota."
   - Input numérico para la nueva cuota (valor por defecto: cuota actual del usuario).
   - Botón rojo "Confirmar reset" + botón neutro "Cancelar".
   - `mutReset` (`useMutation`): llama a `resetearEvaluacionesUsuario`, invalida tanto `'admin-usuarios'` (tabla de usuarios) como `'admin-comparativas'` (tabla de evaluaciones) para que ambas vistas reflejen el estado actualizado.
   - Toast de éxito: "Evaluaciones de `{nick}` reseteadas. Se eliminaron N evaluaciones."

---

### Detalle de S4-69 — Ranking DnD funcional en móvil

El ranking de preferencia usa `@dnd-kit` para arrastrar y soltar modelos.
Hasta esta corrección existían dos problemas independientes que impedían
el arrastre en pantallas táctiles:

**Problema 1 — Sin sensor táctil registrado**
`@dnd-kit` no declaraba ningún sensor; el comportamiento por defecto solo
usa `PointerSensor`, que no procesa eventos `touchstart`/`touchmove`.
El gesto de arrastre nunca llegaba a activarse.

**Problema 2 — `touch-action` no establecido (causa raíz del bloqueo)**
Aunque se añada `TouchSensor`, el navegador intercepta los eventos táctiles
para su propio sistema de scroll antes de que lleguen a JavaScript, a menos
que el elemento arrastrable declare explícitamente `touch-action: none`.
Sin esta propiedad CSS el sensor táctil se registra pero sigue sin recibir
los eventos, por lo que el arrastre continuaba sin funcionar.

**Cambios aplicados en `BenchmarkPage.tsx` y `EvalViewModal.tsx`:**

1. Importados `useSensor`, `useSensors`, `PointerSensor`, `TouchSensor`
   desde `@dnd-kit/core`.
2. Añadido hook `useSensors` con `TouchSensor` y
   `activationConstraint: { distance: 5 }`. El arrastre se activa cuando
   el dedo se desplaza 5 px, lo que resulta natural y no interfiere con
   el scroll vertical de la página.
3. Prop `sensors={sensors}` en `<DndContext>`.
4. Añadido `style={{ touchAction: 'none' }}` en el `<button>` de
   `RankingChip` (el elemento con `{...listeners}`). Esta es la corrección
   definitiva: indica al navegador que no gestione los gestos táctiles en
   ese elemento, cediendo el control a `@dnd-kit`.
5. Estrategia cambiada de `horizontalListSortingStrategy` a
   `rectSortingStrategy`, compatible con layouts en grid 2D.
6. Contenedor de chips: `flex gap-2.5` → `grid grid-cols-2 sm:grid-cols-4 gap-2`.
   En móvil los chips se muestran en 2 columnas; en pantallas ≥640 px,
   en una fila de 4 chips.
7. Eliminado `flex: 1` (y `minWidth: 5rem` en EvalViewModal) del wrapper
   de `RankingChip`; el grid controla el ancho de cada celda.

---

## Nota para la memoria TFG — Diagramas de flujo de autenticación pendientes

Al redactar el **Capítulo 5 (Implementación)** y el **Capítulo 4 (Análisis y Diseño)**,
se deberán incluir los siguientes diagramas que aún no están generados:

### Diagrama 1 — Flujo de login usuario web (con JWT)

Secuencia desde que el evaluador abre la aplicación hasta que accede al benchmark:

```
Usuario → NickPage: introduce nick
NickPage → Backend GET /verificar/{nick}: ¿existe?
Backend → NickPage: {existe: true/false}

[Si existe]
NickPage → Usuario: pide contraseña
Usuario → NickPage: introduce contraseña
NickPage → Backend POST /usuarios/login: {nick, password}
Backend → Backend: bcrypt.verify(password, hash)
Backend → Backend: si ok → JWT HS256, sub=id, tipo=usuario_app, exp=+1h
Backend → NickPage: {access_token, nick, estado, consultas_usadas, cuota_asignada}
NickPage → usuarioStore: login(respuesta) — persiste en localStorage
NickPage → historialStore: comprobar evaluaciones pendientes
[Si pendiente] → NickPage muestra popup ⏳ → navega a /historial
[Si no] → navega a /benchmark

[Si no existe]
NickPage → Usuario: formulario registro (nick + password)
NickPage → Backend POST /usuarios/registrar: {nick, password}
Backend → Backend: bcrypt.hash(password), estado=pendiente_acceso
Backend → NickPage: 201 Created
NickPage → Usuario: mensaje "Pendiente de aprobación"
```

### Diagrama 2 — Flujo de login administrador (con JWT)

```
Admin → NickPage: introduce "admin" como nick
NickPage: detecta nick === 'admin' → muestra formulario email + password
Admin → NickPage: email + password
NickPage → Backend POST /auth/login: {email, password}
Backend → Backend: verifica credenciales admin (tabla distinta)
Backend → Backend: JWT HS256, sub=admin_id, tipo=admin, exp=+2h
Backend → NickPage: {access_token}
NickPage → usuarioStore: logout() — limpia cualquier token de usuario web
NickPage → adminStore: setToken(access_token) — sessionStorage
NickPage → Backend GET /admin/usuarios: listar usuarios pendientes
[Si hay pendientes] → popup 🔔 con recuento → "Revisar ahora" / "Más tarde"
[Si no] → navega a /historial
```

### Diagrama 3 — Uso del JWT en peticiones autenticadas

```
Frontend (axios interceptor de petición):
  ¿token usuarioStore presente? → Authorization: Bearer {token_usuario}
  ¿token adminStore presente? → Authorization: Bearer {token_admin}

Backend (dependencia get_actor_benchmark):
  Decodifica JWT → claim "tipo"
  tipo == "usuario_app" → devuelve UsuarioApp (con cuota)
  tipo == "admin" → devuelve None (sin restricción de cuota)

Frontend (axios interceptor de respuesta):
  Si status == 401:
    usuarioStore.logout() — limpia localStorage
    adminStore.clearToken() — limpia sessionStorage
    → React re-render → RutaProtegida → redirect a /
```

Estos diagramas se pueden representar como **diagramas de secuencia PlantUML** o como
**diagramas de flujo** según el estilo que prefiera el tribunal. Se recomienda incluir
al menos el Diagrama 3 (flujo JWT) en el capítulo de seguridad (Sección 5.x)
junto con la tabla de vulnerabilidades del S4-46.

---

### Detalle de S4-70 — Scroll horizontal en TablaUsuarios y AutoStats (continuación de S4-67)

S4-67 corrigió el desbordamiento de la tabla `TablaAdmin` cambiando
`overflow-hidden` por `overflow-x-auto` y añadiendo `min-w-[860px]`. Las
pruebas en móvil revelaron que el mismo patrón faltaba en otros dos
puntos:

- **`frontend/src/components/historial/TablaUsuarios.tsx`** — la tabla
  de gestión de usuarios del admin truncaba las columnas de la derecha
  (Estado, Consultas, Intentos, Guía, Registro, Acciones) sin permitir
  desplazamiento. Aplicado el mismo patrón: `overflow-x-auto` en el
  contenedor `card` y `min-w-[860px]` en `<table>`.
- **`frontend/src/pages/BenchmarkPage.tsx`** — `AutoStats` (tabla
  comparativa de métricas automáticas mostrada bajo los resultados)
  ya tenía `overflow-x-auto` en el wrapper, pero la tabla con
  `w-full` se comprimía hasta hacer ilegible cada celda. Añadido
  `min-w-[640px]` (4 LLMs × ~110 px + columna de métrica de 7 rem).

Tras este cambio, todas las tablas del proyecto siguen el mismo
contrato: contenedor `overflow-x-auto`, tabla con `min-w-[<px>]`.

### Detalle de S4-71 — Exportación CSV de evaluaciones para análisis estadístico

Por requisito del responsable del TFG (reunión del 09/05/2026), se
reactiva la exportación CSV (S4-10 había quedado descartada en su
momento) con un alcance distinto y más estricto: **solo administrador**
y **solo a través del panel `TablaAdmin`** (no del dashboard público).

**Endpoint backend.** Nuevo handler en
`backend/app/routers/admin.py`:

```python
GET /api/v1/admin/evaluaciones/exportar-csv
```

Acepta los mismos parámetros de filtro que el listado paginado
(`nick`, `categoria`, `prompt`, `estado`, `valoracion`, `fecha_desde`,
`fecha_hasta`) para que la descarga refleje exactamente lo que el
admin ve filtrado en pantalla. Requiere JWT de administrador
(`Depends(get_current_user)`).

**Repositorio.** `BenchmarkEvaluacionRepository.listar_para_export()`
realiza una query sin paginación con eager-load de respuestas y
valoraciones humanas (`selectinload`) para evitar el problema N+1
al iterar al construir el CSV.

**Servicio CSV.** `backend/app/services/admin_export_service.py` usa
el módulo `csv` estándar de Python y `StreamingResponse` de FastAPI:

- Codificación **UTF-8 con BOM** (`﻿`) al inicio para que Excel
  en Windows interprete correctamente acentos sin pasos manuales.
- **Granularidad tidy/largo**: una fila por respuesta LLM. Los datos
  de la `BenchmarkEvaluacion` padre se denormalizan en cada fila para
  que el CSV sea autocontenido y se pueda cargar directamente en
  pandas, R o Excel sin necesidad de joins posteriores.
- **Sin textos largos**: ni el `prompt` original ni el `response_text`
  de la respuesta LLM se exportan. Distorsionan la lectura en Excel
  (saltos de línea internos, miles de caracteres) y el análisis
  estadístico no los necesita.
- **`tipo_imagen` derivado**: para `categoria=imagen` se calcula una
  columna `tipo_imagen` (`generar` / `describir`) a partir del flag
  `es_generacion_imagen`.
- Nombre del fichero: `benchmark-export-YYYYMMDD-HHMMSS.csv`
  (`Content-Disposition: attachment; filename="..."`).

**Frontend.** `frontend/src/services/adminApi.ts` añade
`exportarEvaluacionesCsvAdmin(token, filtros)` que descarga como
`Blob` (axios `responseType: 'blob'`) y extrae el filename del
`Content-Disposition`. `TablaAdmin.tsx` añade un botón
"📥 Exportar CSV" en la cabecera junto al botón de reset, que dispara
la descarga con los `filtrosActivos` y muestra un toast con el número
de evaluaciones exportadas. El botón se desactiva si no hay resultados.

**Documentación.** ADR-009 actualizada con la sección
"Revisión 09/05/2026 — reactivación post-reunión" que recoge el
alcance final, el endpoint y la lista canónica de columnas.

### Detalle de S4-72 — Sanitización de credenciales en mensajes de error

Durante la primera prueba real del CSV se detectó que **3 evaluaciones
de generación de imagen** con Gemini Imagen 4 contenían en el campo
`error_message` la URL completa de la API de Google con la API key
expuesta como query parameter:

```
Client error '400 Bad Request' for url
'https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-generate-001:predict?key=AIzaSy…'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/400
```

El origen del leak está en
`backend/app/llm_engine/clients/gemini_client.py:284`:

```python
except httpx.HTTPError as exc:
    return ResultadoLLM(
        ...
        mensaje_error=str(exc),  # ← URL completa con ?key=… del header
        ...
    )
```

`str(exc)` para `httpx.HTTPStatusError` siempre incluye la URL
completa de la petición fallida. Como Google AI exige la API key
como query parameter (no en `Authorization`), la clave acaba
persistida en `llm_responses.error_message` y se exporta en el CSV.

**Solución estructural — defensa centralizada.** En lugar de
parchear cada `mensaje_error=str(exc)` en los cuatro clientes
LLM (con riesgo de olvidar alguno), se aplica la sanitización
en el `__post_init__` del dataclass `ResultadoLLM`:

```python
# backend/app/llm_engine/resultado.py
from app.llm_engine.sanitizar_error import sanitizar_mensaje_error

@dataclass
class ResultadoLLM:
    ...
    mensaje_error: str | None = None
    ...
    def __post_init__(self) -> None:
        self.mensaje_error = sanitizar_mensaje_error(self.mensaje_error)
```

Cualquier `ResultadoLLM` creado en cualquier punto del código
(clientes existentes, runner, futuras extensiones) pasa por aquí.
Es imposible olvidar la sanitización al añadir un cliente nuevo.

**Helper `sanitizar_mensaje_error`** (`backend/app/llm_engine/sanitizar_error.py`)
aplica una lista de patrones regex al texto y los sustituye por
`***REDACTED***`:

| Patrón | Cubre |
|---|---|
| `[?&]key=[A-Za-z0-9_\-]{20,}` | Google AI URL key (`?key=AIza...`) |
| `Authorization:\s*Bearer\s+\S+` | Header `Authorization` completo |
| `Bearer\s+[A-Za-z0-9._\-]{20,}` | Bearer suelto |
| `sk-(proj-|ant-)?[A-Za-z0-9_\-]{20,}` | OpenAI / Anthropic |
| `xai-[A-Za-z0-9_\-]{20,}` | xAI / Grok |
| `AIza[A-Za-z0-9_\-]{35}` | Google API key suelta (39 chars) |

**Limpieza de los registros existentes.** Las 3 filas
contaminadas (evaluaciones #57, #58, #60 de imagen) se eliminaron
con `DELETE FROM benchmark_evaluaciones WHERE id IN (57, 58, 60)`.
El cascade arrastra las `llm_responses` y `user_evaluations`
asociadas. Estamos en periodo de pruebas, así que la pérdida de
estas evaluaciones no afecta al estudio.

### Detalle de S4-73 — Subcategoría persistida para CSV (revisión parcial de ADR-014)

Por requisito del responsable del TFG (misma reunión del 09/05/2026),
el CSV debe distinguir qué prompt o variante exacta se ejecutó dentro
de cada categoría: «Efecto Doppler» en lugar de simplemente
«concretas», o «Resumen en 20 palabras» en lugar de simplemente
«resumen».

ADR-014 había decidido **no persistir la subcategoría en BD**
(solo en la UI) por dos motivos: (1) flexibilidad para reordenar
prompts sin migraciones; (2) evitar agrupaciones difusas en el
dashboard con 8 categorías × 10 subcategorías = 80 combinaciones.

**Reversión parcial.** Se persiste la subcategoría **únicamente para
el CSV**, sin afectar al dashboard, al runner ni a las métricas. Los
motivos originales de ADR-014 se mantienen porque el campo no
participa en ningún agregado.

**Cambios aplicados.**

1. **Migración Alembic `e4f5a6b7c8d9_add_subcategoria_csv`**:
   `ALTER TABLE benchmark_evaluaciones ADD COLUMN subcategoria_csv VARCHAR(150) NULL`.
   Nullable porque las evaluaciones existentes (anteriores a esta
   migración) no tendrán valor; estamos en periodo de pruebas y se
   acepta dejarlas vacías sin backfill.
2. **Modelo ORM** (`backend/app/models/benchmark_evaluacion.py`):
   campo `subcategoria_csv: Mapped[str | None]`.
3. **Schema** (`backend/app/schemas/benchmark.py`):
   `PeticionBenchmark.subcategoria_csv: str | None = Field(None, max_length=150)`.
4. **Servicio y repositorio**: `BenchmarkService.ejecutar()` y
   `BenchmarkEvaluacionRepository.crear()` propagan el campo
   sin tocar la lógica existente.
5. **Frontend `SubcatPanel.tsx`**: nueva prop opcional
   `onSubcategoriaCsvChange` y un `useEffect` que, según la
   categoría, calcula el valor a emitir:
   - `razonamiento` / `codigo` / `creativa` / `concretas` →
     `"N. Etiqueta"` (índice 1-based + etiqueta del prompt
     seleccionado, ej. `"2. Efecto Doppler"`).
   - `traduccion` → idioma sin emoji (ej. `"Inglés"`).
   - `resumen` → etiqueta de la opción seleccionada
     (ej. `"Resumen en 20 palabras"`).
   - `imagen` → id de la opción
     (`"generar"`/`"describir"`/`"logotipo"`/`"modificar"`).
   - `libre` → siempre `"Texto Libre"`.
6. **Frontend `BenchmarkPage.tsx`**: estado local
   `subcategoriaCsv` que se incluye en el body de la petición
   `POST /api/v1/benchmarks/run`.
7. **Servicio CSV** (`admin_export_service.py`): nueva columna
   `subcategoria` en posición 6 (entre `categoria` y `tipo_imagen`).

**Documentación**: ADR-009 actualizada con la columna nueva;
ADR-014 incluye una nota explícita de "Nota 09/05/2026 — reversión
parcial para CSV de admin" indicando que las decisiones originales
del ADR se mantienen intactas.

### Detalle de S4-74 — Columna `valoracion_estado` para filtrado explícito

Durante la revisión del CSV se detectó que distinguir las respuestas
no valoradas de las valoradas o de las que tuvieron error obligaba a
cruzar dos columnas (`tuvo_error` + comprobar si `rating` está vacío),
lo que es propenso a errores en Excel. Se añade una columna
explícita `valoracion_estado` con tres valores discretos:

| Valor | Cuándo |
|---|---|
| `no_aplica` | `tuvo_error=true` — el LLM falló, nada que valorar |
| `pendiente` | LLM respondió OK pero falta valoración humana |
| `valorada` | existe `UserEvaluation` enlazada a la respuesta |

La columna se inserta justo antes de `evaluador_nickname` (posición
23) para abrir el bloque de "Evaluación humana" del CSV. No requiere
nuevo campo en BD: el valor se deriva en
`admin_export_service.py:generar_csv()` a partir de
`respuesta.tuvo_error` y de la existencia de `respuesta.evaluacion`
(relación 1:1).

El total del CSV pasa de 27 a **28 columnas**. ADR-009 actualizada
con la columna y la lógica de derivación.

### Detalle de S4-75 — Filtros de fecha con precisión de hora y minuto

Los filtros "Desde" y "Hasta" del panel admin usaban `<input type="date">`
con granularidad de día. Esto bastaba para localizar evaluaciones por
fecha aproximada pero no permitía aislar una franja horaria concreta
(p. ej. para reproducir un fallo intermitente o auditar un periodo
estrecho de pruebas).

**Frontend.**

- `components/historial/TablaAdmin.tsx`: dos inputs cambiados a
  `type="datetime-local"`. Etiquetas actualizadas a
  "Desde (fecha y hora)" y "Hasta (fecha y hora)".
- `services/adminApi.ts`: nuevo helper `aIsoUtc(valorLocal)` que
  convierte el valor del input (formato `"YYYY-MM-DDTHH:MM"`,
  interpretado como hora local del navegador) a ISO 8601 UTC con
  `new Date(valorLocal).toISOString()`. El usuario en CEST (+02:00)
  selecciona "10:30" y al backend llega `"2026-05-09T08:30:00.000Z"`.
  Aplicado en `listarEvaluacionesAdmin` y
  `exportarEvaluacionesCsvAdmin` (mismo formato en listado paginado y
  en export CSV).

**Backend.**

- `routers/admin.py`: `Query` de `fecha_desde` y `fecha_hasta`
  cambiada de `date | None` a `datetime | None` en los dos endpoints
  afectados (listado paginado y export CSV). Pydantic acepta de forma
  nativa cadenas ISO 8601 con offset.
- `repositories/benchmark_evaluacion_repository.py`: la lógica
  anterior calculaba inicio del día (`datetime(y,m,d, tzinfo=UTC)`) e
  inicio del día siguiente para hacer rangos inclusivos sobre `date`.
  Sustituida por comparación directa `>=` / `<=` contra el datetime
  recibido. Si llega naive (sin tzinfo), se asume UTC para mantener
  coherencia con cómo se persiste `created_at`.
- Importes simplificados: eliminado `date` y `timedelta` que dejaron
  de usarse.

**Smoke test contra BD real:**

| Ventana UTC | Total filtrado |
|---|---|
| 2026-05-07 07:00–08:00 | 6 evaluaciones |
| 2026-05-07 07:20–07:25 | 1 evaluación |
| 2026-05-07 20:00–23:00 | 0 evaluaciones |

Confirma que el filtro respeta minutos y que la conversión local→UTC
no introduce desplazamientos.

### Detalle de S4-76 — DateTimePicker custom para garantizar el formato DD/MM/YYYY

Tras aplicar los `<input type="datetime-local">` (S4-75) se observó
que el formato visible (DD/MM o MM/DD) lo impone el **locale del
sistema operativo**, no el atributo HTML `lang`. En Windows con
formato regional inglés, el input mostraba `MM/DD/YYYY` aunque la
página declarase `lang="es"` y el input `lang="es-ES"`. Forzar el
orden DD/MM con HTML/CSS sobre el input nativo es inviable de forma
fiable cross-browser.

**Solución adoptada — picker controlado.** Se sustituye el input
nativo por un componente propio
`frontend/src/components/shared/DateTimePicker.tsx` que envuelve
[`react-day-picker`](https://daypicker.dev) (v10) con locale `es`
de [`date-fns`](https://date-fns.org). Esto da control total sobre
la presentación, manteniendo el contrato de valor
`"YYYY-MM-DDTHH:MM"` que ya consumía `aIsoUtc()` en el frontend.

**Dependencias añadidas en `frontend/package.json`:**

- `react-day-picker@^10.0.0` (~12 KB gz, MIT)
- `date-fns@^4.1.0` (módulo de formato/parseo + locales, MIT)

**Apariencia.** El componente tiene dos partes:

1. **Trigger.** Botón con la misma forma que `input-base`:
   fondo `#0F0F1C`, borde morado al 35 % (al 100 % cuando el
   popover está abierto), `border-radius: 10px`. Muestra la fecha
   formateada `dd/MM/yyyy HH:mm` o un placeholder atenuado si
   no hay valor. Icono 📅 a la derecha en color primario.
2. **Popover** (`absolute`, `z-40`, `min-width: 320px`,
   `shadow-card-lg`). Contiene:
   - Almanaque `react-day-picker` con locale `es` (lunes como
     primer día de la semana, días en español). Estilizado vía
     CSS con la clase `rdp-tfg`: día seleccionado con gradiente
     `#9D4EDD → #6D28D9`, día actual con borde y texto morado en
     negrita, hover día normal con fondo morado al 22 %, días
     fuera del mes atenuados al 32 %.
   - Dos **tiles** grandes `HH` y `MM` (font-mono 24 px, fondo
     morado al 12 %, borde 1.5 px) separados por un `:` morado.
     Pulsar un tile lo activa (gradiente + glow morado) y
     despliega bajo el almanaque una rejilla con todas las
     opciones: 24 botones (0–23) en grid de 6×4 para horas o
     60 botones (0–59) en grid de 10×6 para minutos. La opción
     seleccionada destaca con gradiente y sombra morada.
     Pulsar el otro tile cambia, pulsar el mismo tile colapsa.
     Los tiles son a la vez **inputs editables**: el usuario puede
     **teclear directamente** la hora o el minuto (`inputMode="numeric"`,
     `maxLength=2`) además de elegir desde la rejilla. Al recibir foco
     se selecciona el contenido para sobrescribir rápido. Los valores
     se filtran a dígitos y se acotan a `0-23` y `0-59`
     respectivamente.
   - Botones inferiores **✕ Limpiar** (rojo, deshabilitado si
     no hay valor) y **Aceptar** (botón primario morado).

**Cierre.** Click fuera cierra todo. `Escape` colapsa primero la
rejilla expandida; segunda pulsación cierra el popover entero.

**CSS.** Los overrides de `react-day-picker` se ubican fuera de
`@layer components` en `index.css` para asegurar que tengan
prioridad sobre el CSS por defecto de la librería sin necesidad
de `!important`. Bloque etiquetado como `.rdp-tfg`.

**Archivos tocados:**

- `frontend/package.json` y `package-lock.json` — dependencias.
- `frontend/src/components/shared/DateTimePicker.tsx` — nuevo.
- `frontend/src/index.css` — bloque `.rdp-tfg` con personalización
  de `react-day-picker`. Eliminado el bloque `.input-datetime`
  (con sus pseudo-elementos `-webkit-*`) que quedaba sin uso al
  retirar el input nativo.
- `frontend/src/components/historial/TablaAdmin.tsx` — los dos
  `<input type="datetime-local">` se sustituyen por
  `<DateTimePicker>`. La lógica del estado (`filtroFechaDesde`,
  `filtroFechaHasta`) y de envío al backend (`aIsoUtc()`) **no
  cambia** — el contrato de cadena `"YYYY-MM-DDTHH:MM"` se
  conserva.

**Beneficios.** Formato visible `DD/MM/YYYY HH:mm` garantizado
en cualquier navegador y SO; selector de hora/minuto visualmente
amplio que evita teclear; alineación completa con la paleta del
proyecto (esquinas redondeadas, gradientes morados, sombras
suaves). Sin tocar backend ni el contrato de filtros.

---

### Detalle de S4-77 — Unificación de las tablas de usuarios

Hasta este sprint el sistema mantenía dos tablas paralelas (`users`
para el admin y `usuarios_app` para los usuarios web evaluadores) por
contexto histórico (Sprint 1 vs Sprint 4). En la reunión del
10/05/2026 el responsable del TFG pidió poder **promover un usuario
regular a administrador** desde el panel admin sin cambiar su
contraseña, y degradarlo de vuelta cuando convenga. Mantener dos
tablas paralelas obligaba a mover registros entre ellas, perdiendo
trazabilidad. Se decidió unificar.

**Esquema final.** Una única tabla `usuarios_app` con un nuevo flag
`is_admin BOOLEAN NOT NULL DEFAULT FALSE` y una columna `email
VARCHAR(255) UNIQUE NULL`. Check constraint
`ck_admin_requires_email`: si `is_admin=True`, el email es
obligatorio. La tabla `users` se elimina. El login del admin pasa a
ser por **nick + password** (igual que cualquier usuario), y el
campo email queda como dato de contacto/recuperación obligatorio
sólo para admins.

**Comportamiento de cuota tras promote/demote.** Por requisito
explícito del responsable: degradar un admin no toca su cuota ni
sus consultas; los contadores reanudan su control con los valores
que tenían en BD. El admin que degrada usa los botones existentes
"± Ajustar cuota" o "↺ Reset evaluaciones" para asignar cuota nueva.
Promover no resetea nada: la cuota simplemente se ignora mientras
`is_admin=True` (`get_actor_benchmark()` devuelve `None`).

**Guard "no degradar al último admin".** Antes de quitar `is_admin`,
el servicio cuenta los admins activos. Si el usuario en cuestión es
el único admin, devuelve `HTTP 400` con un mensaje claro. El sistema
nunca queda sin acceso administrativo.

**Migración Alembic `f5a6b7c8d9e0`.**
1. `ADD COLUMN email`, `ADD COLUMN is_admin` en `usuarios_app`.
2. `INSERT` del admin existente desde `users` (nick = username,
   conservando el `created_at` original y el hash bcrypt).
3. Check constraint `ck_admin_requires_email`.
4. `DROP TABLE users`.

El downgrade recrea `users` y restaura los admins, así que es
reversible sin pérdida de datos.

**Frontend.** El formulario `LoginAdmin.tsx` cambia el campo "Email"
a "Nick". `TablaUsuarios.tsx` añade una columna "Rol" con badge
"👑 Admin" o "Usuario", muestra el email bajo el nick cuando existe,
y dos botones nuevos:
- "👑 Promover" (sólo sobre `is_admin=False` y `estado='habilitado'`):
  abre `PromoteModal` con un campo email (validación regex en cliente,
  EmailStr en backend, comprobación de unicidad en el servicio).
- "↩ Quitar admin" (sólo sobre `is_admin=True`): abre `ConfirmModal`
  destructivo. La degradación falla con 400 si el guard del último
  admin se dispara.

**Limpieza.** Se borran los archivos legacy:
`backend/app/models/user.py`, `backend/app/repositories/user_repository.py`,
y los tests `test_user_repository.py`, `test_router_admin.py`,
`test_dependencies.py`, `test_auth_service.py` (todos basados en el
flujo viejo). El docstring de `UsuarioApp` decía erróneamente que el
hash era Argon2 cuando la implementación real era bcrypt; se corrige.

**Documentación.** ADR-024 marcado como **superseded** por ADR-027
(en lo que respecta a la separación de tablas; las decisiones
operativas de ADR-024 sobre estados, cuota y bloqueo se mantienen
intactas).

---

### Detalle de S4-78 — Rol root vs admin promovido

Tras desplegar S4-77 surgió la pregunta natural: si cualquier admin
puede promover, un admin promovido podría a su vez convertir a otros
en admins, diluyendo el control del estudio. Por requerimiento del
responsable del TFG (10/05/2026), se introduce un **segundo flag**
`es_root` que separa al admin canónico del despliegue del resto:

- **Root** (`es_root=True`): el admin creado por `seed_admin.py`. Es
  el único que puede invocar `POST /admin/usuarios/{id}/promover-admin`
  y `POST /admin/usuarios/{id}/quitar-admin`.
- **Admin promovido** (`is_admin=True`, `es_root=False`): hereda
  todos los privilegios del panel admin EXCEPTO la gestión de roles.

**Backend:**

- Migración `g6b7c8d9e0f1_add_es_root_admin`: añade
  `es_root BOOLEAN NOT NULL DEFAULT FALSE` a `usuarios_app` y marca
  como root al admin existente con `nick='admin'` (idempotente para
  despliegues nuevos).
- `seed_admin.py`: inserta con `es_root=True`.
- `UsuarioAppAdminService.promover_admin()` y `degradar_admin()`
  ahora aceptan `caller` y devuelven 403 si `caller.es_root=False`.
  Promoción nunca pone `es_root=True`; degradación rechaza si
  `target.es_root=True`.
- `RespuestaToken` y `RespuestaTokenUsuarioApp`: incluyen el flag
  `es_root` para que el frontend lo reciba en el login sin
  consulta adicional.

**Frontend:**

- `adminStore` extendido con `esRoot: boolean` y
  `setSession(token, esRoot)`.
- `NickPage.tsx` y `LoginAdmin.tsx`: ambos puntos de login admin
  pasan `respuesta.es_root` al store.
- `TablaUsuarios.tsx`: los botones "Promover" y "Quitar admin"
  solo se renderizan si `esRoot`. Badge de rol diferenciado:
  "⭐ Root" en rojo (único, único con permiso de gestionar roles)
  vs "👑 Admin" en amarillo (promovidos).

**Despliegue (Cloud Run / docs/guides/04_despliegue_cloud_run.md):**

- Nueva FASE 6.1 antes del seed: `db-migrate` ejecuta
  `alembic upgrade head` en un Cloud Run Job propio. Es idempotente
  y se relanza en cada despliegue posterior.
- `ADMIN_PASSWORD` movida a Secret Manager (era pasada en claro
  como `--set-env-vars`, visible en `gcloud run jobs describe` y
  logs de auditoría). El Job `seed-admin` la inyecta vía
  `--update-secrets=ADMIN_PASSWORD=ADMIN_PASSWORD:latest`.
- Subsección 6.4 documenta el caso de despliegues que ya estaban
  con esquema antiguo: las dos migraciones (`f5a6b7c8d9e0` y
  `g6b7c8d9e0f1`) se aplican automáticamente y migran el admin
  existente como root.

---

### Detalle de S4-77 / S4-78 — fixes y refinamientos posteriores al despliegue

Tras desplegar las dos features grandes (unificación + rol root) se
detectaron varios bugs de UX y un ajuste funcional en la valoración.
Todos commiteados como follow-ups individuales:

**Login admin (NickPage):** la vista `login_admin` pedía email aunque
ya habíamos unificado a nick+password. Sustituido por entrada de
contraseña con el nick mostrado read-only ("@admin"), eliminada toda
referencia a email en el flujo (commit `5a3f1bf`).

**Promoción y redirección automática:** un usuario web promovido a
admin (defkorn) entraba por `/usuarios/login` con éxito pero el
frontend lo guardaba en `usuarioStore` y mostraba el UI de usuario
regular. `RespuestaTokenUsuarioApp` incluye ahora `is_admin`; si es
true, NickPage activa la sesión administrativa con el mismo JWT y
redirige al `/historial` admin (commit `dddbb32`).

**Subpestañas admin para promovidos:** `nickStore.esAdmin()`
comprobaba `nick.toLowerCase() === 'admin'` literal, así que defkorn
veía el nav admin pero la página renderizaba la vista de usuario.
Cambiado para consultar `adminStore.token`; HistorialPage suscrito
directamente al token para re-renderizar al login/logout (commit
`2d0c0d0`).

**Protección del root:** un admin promovido podía pulsar el botón
✕ y eliminar al admin root del sistema. Guard backend en
`eliminar_usuario` que devuelve 400 si `target.es_root=True`, y
ocultamiento del botón en TablaUsuarios para filas root (commit
`b5b82a8`).

**Cuota y admins:** botón "± Cuota" oculto para administradores
(no aplica mientras `is_admin=True`). El "↺ Reset" se mantiene
visible porque borra evaluaciones del usuario, lo cual sí es útil
para preparar al admin promovido para una eventual degradación.
El modal de reset, cuando target es admin, muestra una nota
amarilla aclarando que la cuota asignada queda en suspenso hasta
que se quite el rol (commits `8f289fa` y `13ecbca`).

**Compactación TablaUsuarios:** los 5 botones que ve el root sobre
una fila de usuario regular caían en 3 filas con flex-wrap.
Estrechadas las columnas Estado/Consultas/Intentos/Guía y reducido
padding de los botones; labels acortados ("Conceder acceso" →
"Conceder", "Ajustar cuota" → "Cuota", "Quitar admin" → "Quitar")
con tooltips conservando la descripción completa. min-w bajado
de 1080 a 960 px para que entre sin scroll en portátiles
estándar (commits `40d5626`, `f51aab8`).

**Nick del actor admin promovido en evaluaciones:** las
evaluaciones que creaba defkorn (admin promovido) se persistían
con `nickname='admin'` literal. `BenchmarkPage` derivaba el nick
con un fallback hardcodeado a 'admin' cuando había `tokenAdmin`,
sin tener en cuenta que el actor es ahora `defkorn`. Cambiado
para leer de `nickStore` que sí guarda el nick real del actor
actual (commit `ee0b223`).

**Restricción de valoración por propietario:** sólo el nick que
ejecutó la evaluación puede valorarla. El backend ya enforcea
esta regla en `EvaluacionService.crear()` con un `403` si
`respuesta.benchmark.nickname != peticion.nickname`. En frontend
`TablaAdmin` ahora oculta el botón "Evaluar" cuando
`s.nickname !== nickActual` y muestra un texto atenuado
"sin valorar" para que el admin sepa que la evaluación está
pendiente pero no la puede tocar él. Aplicable también al admin
root: solo puede valorar las evaluaciones que él mismo ejecutó.

---

---

### Detalle de S4-79 / S4-80 / S4-81 — Refactorización de diagramas UML y memoria TFG V2 (11-12/05/2026)

#### S4-79 — Reorganización del catálogo de diagramas

El directorio `docs/diagramas/plantuml/` tenía nombres técnicos poco descriptivos
(`01_casos_uso_usuario.puml`, etc.) que no explicaban el contenido sin abrirlos.
Se reorganizó el catálogo a nombres semánticamente claros:
`act_benchmark_completo.puml`, `seq_autenticacion_usuario.puml`, etc.
Se creó adicionalmente un catálogo en Mermaid editable directamente en GitHub
(`docs/diagramas/mermaid/`) con los diagramas más relevantes para la memoria,
y el script `tools/diagramas/render_puml.py` para regenerar todos los PNGs
de PlantUML sin tocar el `.docx` de la memoria.

#### S4-80 — Estética uniforme PlantUML

Todos los diagramas PlantUML tenían estilos mezclados (algunos con fondo negro,
otros con fondo blanco, diferentes fuentes y grosor de líneas), lo que producía
inconsistencia visual dentro del mismo documento.

Se aplicó estética común a todos: fondo `#FFFFFF`, fuente y líneas `#000000`,
rellenos pastel suaves para diferenciar actores/sistemas. Los diagramas de
secuencia de gran tamaño (benchmark completo, autenticación) se trocearon en
sub-diagramas que caben en una página A4 en vertical. Se separó el flujo de
administración del flujo de usuario en diagramas independientes para mayor
legibilidad.

**Regla de estilo documentada en memory** (`feedback_diagramas_estilo_claro.md`):
fondo blanco, fuente y líneas negras, rellenos pastel suaves; nunca modo nocturno.

#### S4-81 — Memoria TFG V2 y docx con 24 UMLs embebidos

La primera versión de la memoria (V1) tenía una estructura que el tribunal
evaluó como mejorable: algunos capítulos mezclaban análisis con implementación,
y los diagramas UML estaban referenciados pero no embebidos en el documento Word.

Se redactó **Memoria TFG V2** siguiendo la estructura recomendada por el tribunal
(`docs/memoria/`), con 24 diagramas UML embebidos directamente en el `.docx`.
El inventario de Requisitos Funcionales se amplió a 31 RFs organizados por actor
(usuario anónimo, administrador, sistema) con trazabilidad directa a los
diagramas de casos de uso.

---

### Detalle de S4-82 — Ranking anti-sesgo: slots vacíos (ADR-028) (12/05/2026)

El diseño anterior del ranking de preferencia inicializaba las posiciones con los
cuatro modelos ya colocados en orden de llegada de las respuestas. El evaluador
tenía que reordenar activamente, pero si no lo hacía, el orden por defecto
(determinado por `asyncio.gather`) quedaba registrado como su preferencia.

Este sesgo sistemático podía inflar artificialmente las posiciones de los modelos
que responden más rápido (típicamente GPT-4o), sesgando los resultados de la
comparativa humana sin que el evaluador lo percibiera.

**Solución adoptada:**

- El ranking parte de **4 slots vacíos** (null) y un **pool con los chips de los
  modelos** mezclados en orden aleatorio por respuesta en la sesión.
- El evaluador debe arrastrar activamente cada chip a un slot para registrar su
  preferencia. El botón "Guardar evaluación" permanece deshabilitado hasta que
  todos los slots están ocupados (`rankingCompleto = orden.every(s => s !== null)`).
- El borrador se guarda en `localStorage` para no perder el trabajo si el usuario
  cierra el navegador accidentalmente.

**ADR-028** documenta la decisión, el sesgo detectado y el análisis de alternativas
(orden fijo, orden aleatorio, slots vacíos). La opción de slots vacíos es la única
que garantiza que cada posición en el ranking es una elección activa del evaluador.

---

### Detalle de S4-83 / S4-84 / S4-85 — UX flujo guiado y mejoras de evaluación (12/05/2026)

#### S4-83 — Nick case-insensitive

El sistema diferenciaba "Emilio" de "emilio" como usuarios distintos, lo que
producía duplicados accidentales cuando los evaluadores no recordaban la
capitalización exacta de su alias. El login, el registro y la verificación de
cuota se normalizan a minúsculas en todas las capas (backend `.lower()` +
constraint `LOWER(nickname)` en BD).

#### S4-84 — Flujo guiado por pasos con bloqueo y parpadeos

El formulario de benchmark exponía simultáneamente todos los controles (categoría,
prompt, modelos), lo que desorientaba a usuarios nuevos que no sabían qué paso
completar primero. Se rediseñó como flujo de 4 pasos secuenciales:

1. Elegir categoría
2. Escribir prompt (se desbloquea al seleccionar categoría)
3. Ajustar modelos (se desbloquea al tener prompt ≥ 10 caracteres)
4. Evaluar respuestas (aparece tras ejecutar el benchmark)

Cada paso usa `animate-pulse-strong` en su control principal mientras está activo
y sin completar, para guiar visualmente la atención. Los pasos posteriores están
visualmente atenuados hasta que se desbloquean.

#### S4-85 — Cuarto paso unificado + botón cerrar EvalViewModal

La evaluación (estrellas + ranking DnD) se integró directamente en la página de
resultados del benchmark como cuarto paso, eliminando la navegación a una ruta
separada. Tras guardar, aparecen dos acciones: "Nueva Comparativa" (limpia el
estado y hace scroll al inicio) y "Ver historial →". El modal `EvalViewModal`
recibió un botón de cierre explícito (✕) para mejorar la accesibilidad en móvil.

---

### Detalle de S4-86 — Tarifas LLM versionadas con caché (ADR-009 rev.) (13/05/2026)

Los precios de los LLMs cambian con frecuencia. El diseño anterior tenía los
precios hardcodeados en el cliente de cada proveedor, lo que implicaba modificar
código fuente cada vez que un proveedor actualizaba su tarifa.

**Nuevo modelo de tarifas:**

- Tabla `llm_tarifas` en BD con columnas: `proveedor`, `modelo`, `precio_entrada_usd_por_mtoken`,
  `precio_salida_usd_por_mtoken`, `precio_entrada_cacheado_usd_por_mtoken`,
  `vigente_desde`, `vigente_hasta`.
- `TarifaRepository.obtener_vigente(proveedor, modelo, fecha)` devuelve la tarifa
  activa para una fecha concreta, permitiendo auditar costes históricos aunque
  los precios hayan cambiado después.
- Las tarifas se cargan en caché en memoria al arrancar el backend (TTL 1h),
  evitando consultas repetidas por cada respuesta LLM.
- Se realizó **auditoría oficial de precios** contrastando con las páginas de
  pricing de Anthropic, OpenAI, Google y xAI (fuente citada en el ADR).
- El coste se calcula con `Decimal` (no `float`) para evitar pérdida de precisión
  en llamadas de bajo coste. El campo `cost_usd` en BD usa `Numeric(12,8)`.

---

### Detalle de S4-87 — Edición imagen nativa Gemini/Grok (13/05/2026)

La subcategoría "modificar imagen" (enviar una imagen base para que el modelo la
edite) requiere una API diferente a la de generación desde cero. Gemini y Grok
soportan edición nativa mediante endpoints distintos que requieren subir primero
el fichero a su servicio de almacenamiento temporal (API Files).

**Implementación:**

- `GeminiClient`: usa la API Files de Google AI para subir la imagen, obtener un
  `file_uri` y pasarlo como parte del mensaje multimodal a `imagen-3.0-generate`.
- `GrokClient`: sube la imagen como Base64 en el body de la petición a Aurora.
- `ClaudeClient` y `OpenAIClient`: no soportan edición nativa en sus APIs actuales;
  se les pasa el prompt de modificación como texto con descripción de la imagen.

Se añadió la **gráfica de coste por modo de imagen** al dashboard (`DashboardPage`)
para mostrar las diferencias de precio entre generar desde cero, describir una
imagen existente y editar/modificar.

---

### Detalle de S4-88 — Sub-experimento bilingüe ES vs EN (ADR-029) (14/05/2026)

Una hipótesis frecuente en el benchmarking de LLMs es que los modelos rinden
mejor cuando se les formula la pregunta en inglés (su idioma de entrenamiento
mayoritario). El TFG añade un sub-experimento controlado para medir esto.

**Diseño metodológico:**

Para categorías participantes (`razonamiento`, `creativa`, `concretas` con opción
predefinida), el frontend ofrece un selector lateral con el prompt traducido al
inglés. Si el evaluador activa la opción, el backend ejecuta **dos rondas de
llamadas independientes**:

1. `ejecutar_benchmark(clientes, prompt_es, idioma_prompt='es')` — corpus principal
2. `ejecutar_benchmark(clientes, prompt_en, idioma_prompt='en')` — sub-experimento

Cada ronda es una inferencia fresca sin contexto compartido, lo que garantiza que
se mide el rendimiento lingüístico aislado (no continuación de conversación).
La cuota del usuario descuenta una sola consulta porque la experiencia humana es
una pregunta única.

**Dashboard:**

Nueva sección "Métricas automáticas — Comparativa prompt Español(ES) vs Inglés(EN)"
con barras agrupadas por proveedor e idioma para latencia, tok/s, coste y palabras.
La consulta `medias_comparativa_es_en()` trae únicamente evaluaciones bilingües
(las que tienen al menos una respuesta EN), sin contaminar las medias globales que
siguen usando solo ES.

**Similitud Jaccard:**

Se calcula exclusivamente entre respuestas ES (no entre ES y EN) porque el
vocabulario de los dos idiomas es incomparable léxicamente.

---

### Detalle de S4-89 / S4-90 / S4-91 — Pulido final y corrección de sesgo (14/05/2026)

#### S4-89 — Pulido UX bilingüe y CSV europeo

El acordeón "Ver respuesta en inglés" de `BenchmarkCard`, `EvalViewModal` y el
modal admin (`TablaAdmin`) recibió el nuevo componente `BotonVerEn`: borde y fondo
tintados con el color del LLM, efecto hover/glow y estado visual distinto cuando
está abierto. Los textos largos (> 60 palabras) implementan toggle ampliar/contraer
con gradiente de fade y soporte de doble clic.

El CSV de exportación admin cambió de formato anglosajón (`,` decimal) a
**CSV europeo** (`;` delimitador, `,` decimal) para que Excel en locales
españoles, franceses y alemanes lo importe directamente como tabla numérica
sin requerir el asistente "Obtener datos externos".

#### S4-90 — UX: renombrar pestaña y botón de reinicio

La pestaña de navegación principal se renombraba "Nueva Comparativa", lo que
creaba confusión con el botón homónimo dentro de la página de resultados.
Se renombró a **"Benchmark"**. El botón "+ Nueva Comparativa" en el paso 4
(tras guardar la evaluación) llama a `lanzarNuevo()` (resetea categoría, prompt,
modelos e imagen) y hace `window.scrollTo({ top: 0, behavior: 'smooth' })`.

#### S4-91 — Auditoría de métricas y corrección de sesgo en ratings

Se realizó una auditoría completa de todas las fórmulas de métricas automáticas
y humanas. Las métricas automáticas (`cost_usd`, `tokens_por_segundo`, Jaccard,
medias del dashboard) resultaron **correctas**. Se detectó un **sesgo crítico**
en las métricas humanas:

Las tres consultas SQL de media de rating (`ratings_por_proveedor`,
`ratings_por_proveedor_y_categoria`, `ratings_generacion_imagen_por_proveedor`)
no filtraban `tuvo_error=True`. El frontend asigna automáticamente `rating=1`
a respuestas fallidas, de modo que un proveedor con más fallos aparecía
artificialmente peor en las gráficas de valoración humana.

**Corrección:** `LLMResponse.tuvo_error.is_(False)` añadido a los tres `.where()`.
El ranking de preferencia (`rango_preferencia`) ya estaba correcto porque
`rango_preferencia=NULL` para errores y la consulta filtra `IS NOT NULL`.

**Impacto cuantitativo del sesgo corregido** (ejemplo ilustrativo):
- Proveedor con 50 respuestas exitosas (rating medio 4.0) y 10 errores con rating=1
- Antes: `(50×4.0 + 10×1) / 60 = 3.5` (−12.5% de distorsión)
- Después: `50×4.0 / 50 = 4.0` (valor real)

---

_Última actualización: 14/05/2026 (v9)_

---

## Cierre de sprint — 14/05/2026

**Estado: DESARROLLO FUNCIONAL COMPLETADO.**

El día 14/05/2026 se da por cerrada la evolución funcional de la aplicación.
Todos los requisitos funcionales (RF-01 a RF-35) están implementados, integrados
y verificados en producción (Cloud Run). No se realizarán más cambios funcionales
durante el período de estudio con usuarios.

### Lo que permanece abierto

| Tipo | Descripción |
|------|-------------|
| Estética | Ajustes visuales menores (colores, tipografía, espaciado) detectados durante el uso real |
| Bugs de estudio | Errores de comportamiento detectados durante el período de evaluación con usuarios — se priorizarán por impacto en la experiencia, no en la funcionalidad |
| Diagramas y memoria | Revisión y ajuste de los diagramas PlantUML y redacción de la memoria TFG |

### Lo que queda cerrado

- Motor LLM y clientes (Claude, OpenAI, Gemini, Grok)
- Sub-experimento bilingüe ES/EN (ADR-029)
- Sistema de tarifas versionadas (ADR-028)
- Flujo de evaluación humana: 4 pasos, ranking DnD, estrellas
- Panel de administración: gestión de usuarios, exportación CSV europeo
- Dashboard: todas las gráficas automáticas y humanas, comparativa ES/EN
- Autenticación: usuarios web por nick + JWT admin
- Despliegue Cloud Run (backend + frontend)
- Tests: 389 tests, 96% cobertura

### Período de estudio con usuarios

14/05/2026 – ~01/06/2026. Durante este período:
- La aplicación está accesible en producción para los participantes del estudio.
- Solo se aplicarán correcciones urgentes que impidan completar una evaluación.
- Cualquier cambio estético o corrección menor se registrará aquí con prefijo **BUG-EST** o **EST**.

---

_Sprint cerrado — v10_

---

### Detalle de S4-92 — UX traducción: sin idioma por defecto, parpadeo y mínimo 10 palabras

La categoría de traducción tenía "🇬🇧 Inglés" como idioma de destino predeterminado, lo
que permitía enviar sin haber seleccionado conscientemente el idioma ni haber introducido
el texto. El sistema no bloqueaba el envío con textos cortos o vacíos.

**Cambios implementados en `SubcatPanel.tsx`:**

- El estado inicial del selector de idioma pasó de `'🇬🇧 Inglés'` a `''` (cadena vacía),
  añadiendo una primera opción `<option value="">— Selecciona idioma —</option>` como
  marcador de posición no seleccionable.
- El selector parpadea con `animate-pulse-strong placeholder-glow` mientras
  `idioma === ''`; deja de parpadear en cuanto el usuario elige un idioma.
- El textarea parpadea con las mismas clases mientras el número de palabras sea menor
  que 10; el contador muestra `X / 10 palabras mínimas` en ámbar.
- La función `actualizarTraduccion()` emite `onPromptChange('', false)` si
  `!lang || palabras < 10`, bloqueando el botón "Comparar modelos" en el paso 3 del
  flujo guiado hasta que ambas condiciones se cumplan.

---

### Detalle de S4-93 — UX resumen: contador 300 palabras, parpadeo y botón "Generar texto"

La categoría resumen requería que el usuario aportara el texto a resumir manualmente
o mediante la carga de un fichero (S4-15). Para documentos cortos o cuando no se
disponía de texto propio, el flujo resultaba poco fluido.

**Contador mínimo (subfeature A):**

- El textarea parpadea con `animate-pulse-strong` mientras tenga menos de 300 palabras.
- El contador debajo del textarea muestra `X / 300 palabras mínimas` en ámbar y pasa a
  verde cuando se alcanza el umbral.
- `actualizarResumen()` emite `onPromptChange('', false)` mientras `palabras < 300`,
  impidiendo el envío al igual que la lógica de traducción.

**Botón "✨ Generar texto" con selector LLM (subfeature B):**

Combo seleccionable con cinco opciones (orden de más barato a más caro):

| Opción  | Alias frontend | Proveedor real |
|---------|---------------|----------------|
| Auto    | `auto`         | Primer disponible por coste |
| Gemini  | `gemini`       | Google Gemini 2.5 Flash |
| Grok    | `grok`         | xAI Grok 4.3 |
| GPT-4o  | `openai`       | OpenAI GPT-4o |
| Claude  | `claude`       | Anthropic Claude Sonnet 4.6 |

El selector tiene valor inicial `auto` y puede cambiarse antes de pulsar el botón.
Mientras la llamada está en curso, el botón muestra un spinner y queda deshabilitado.
Tras la respuesta del backend, el texto generado rellena el textarea y se activa el
flag `textoAutogenerado=true` para que BenchmarkPage lo incluya en la petición.
Si el usuario edita manualmente el textarea después de la generación, el flag vuelve
a `false` (el texto deja de considerarse autogenerado).

---

### Detalle de S4-94 — Backend: endpoint GET /benchmarks/texto-ejemplo

**Endpoint `GET /api/v1/benchmarks/texto-ejemplo`** (router `benchmark.py`):

- Parámetro opcional `proveedor: str | None = Query(None)`: alias de proveedor frontend
  (`claude`, `openai`, `gemini`, `grok`).
- Rate limit `@limitador.limit("10/minute")` independiente del endpoint `/run`.
- No persiste nada en la base de datos ni descuenta cuota al usuario.
- Requiere JWT de usuario web habilitado o de administrador.

**DTO de respuesta `RespuestaTextoEjemplo`** (schema `benchmark.py`):

```python
class RespuestaTextoEjemplo(BaseModel):
    texto: str
    palabras: int
    proveedor: str
```

**Lógica del servicio `BenchmarkService.generar_texto_ejemplo()`:**

Se construyen los cuatro clientes LLM con `construir_clientes()`, que los devuelve
en el orden interno (Claude primero). Para el modo **Auto**, los candidatos se
reordenan por el diccionario `_orden_coste`:

```python
_orden_coste = {"google": 0, "xai": 1, "openai": 2, "anthropic": 3}
```

Gemini se intenta primero (más barato), luego Grok, GPT-4o y Claude como último
recurso. Para un proveedor concreto, el mapa `_ALIAS_PROVEEDOR` traduce el alias
del frontend al valor interno del proveedor:

```python
_ALIAS_PROVEEDOR = {
    "claude": "anthropic",
    "openai": "openai",
    "gemini": "google",
    "grok": "xai",
}
```

El servicio itera por los candidatos llamando a
`cliente.completar(prompt_generacion, max_tokens=600)` hasta que uno responde sin
error. Si ninguno responde, devuelve HTTP 503. El `prompt_generacion` instruye al
modelo a generar un texto en castellano de entre 300 y 400 palabras sobre un tema
aleatorio de actualidad, sin título ni encabezados.

**Bug corregido:** `settings.anthropic_api_key` es un `SecretStr` de Pydantic; la
versión inicial del servicio lo pasaba directamente al constructor del SDK de
Anthropic, que espera una cadena normal y lanzaba
`'SecretStr' object has no attribute 'encode'`. La corrección fue aplicar
`.get_secret_value()` en todos los clientes dentro de `generar_texto_ejemplo()`,
igual que ya se hacía en `ejecutar()`.

---

### Detalle de S4-95 — RF-17: persistir texto_entrada autogenerado + acordeón en historial

**Motivación:** hasta este item, el texto generado con el botón "✨ Generar texto"
solo existía en memoria del navegador. Si el usuario evaluaba la comparativa en el
momento, el texto era visible en las tarjetas de resultados. Pero si cerraba la
pestaña, navegaba al historial más tarde o la sesión caducaba, el texto desaparecía
para siempre: el historial mostraba las métricas y la valoración, pero no había
forma de saber sobre qué texto se había pedido el resumen.

**Nuevo requisito funcional RF-17:** "El sistema debe persistir el texto de entrada
proporcionado por el usuario en la categoría Resumen cuando dicho texto haya sido
generado automáticamente por el LLM, de modo que sea recuperable desde el historial
de evaluaciones."

**Implementación — backend:**

- Migración Alembic `q6f7a8b9c0d1_texto_entrada_autogenerado.py`:
  - `ALTER TABLE benchmark_evaluaciones ADD COLUMN texto_entrada TEXT NULL`
  - `ALTER TABLE benchmark_evaluaciones ADD COLUMN texto_entrada_autogenerado BOOLEAN NOT NULL DEFAULT FALSE`
  - `down_revision = 'p5e6f7a8b9c0'`
- Modelo ORM `BenchmarkEvaluacion`: dos nuevos `mapped_column`.
- Repositorio `BenchmarkEvaluacionRepository.crear()`: acepta y pasa los dos nuevos campos.
- Schema `PeticionBenchmark`: campos `texto_entrada` y `texto_entrada_autogenerado`.
- Schema `RespuestaBenchmark`: los mismos campos en la respuesta.
- Servicio `BenchmarkService.ejecutar()`: recibe y propaga ambos campos.
- Router `POST /benchmarks/run`: propaga los campos desde la petición hasta el servicio.

**Implementación — frontend:**

- Tipos `SesionBenchmark` y `PeticionBenchmark` en `benchmark.ts`: nuevos campos opcionales.
- `SubcatPanel.tsx`:
  - Nueva prop `onTextoEntradaChange?(texto, autogenerado)`.
  - Flag de estado `textoAutogenerado` (false inicial; true al completar la generación;
    vuelve a false si el usuario edita el textarea manualmente).
  - Función `actualizarResumen(texto, autogenerado=false)` centraliza la actualización
    del textarea, el flag y la emisión de la prop `onTextoEntradaChange`.
- `BenchmarkPage.tsx`: estados `textoEntrada` y `textoEntradaAutoGen`; la mutación
  incluye `texto_entrada` y `texto_entrada_autogenerado` solo cuando el flag es true.
- `EvalViewModal.tsx`: acordeón "✨ Ver texto original generado automáticamente"
  con estados `verTextoOriginal` y `ampliadoTextoOriginal`. Se renderiza
  condicionalmente si `sesion?.texto_entrada_autogenerado && sesion.texto_entrada`.
  Está presente en ambas ramas del modal: la vista de formulario de evaluación y la
  vista de solo lectura para evaluaciones ya valoradas. El usuario puede expandir
  y colapsar el texto con un botón y hacer doble clic en el párrafo para ampliarlo,
  replicando el patrón del acordeón de respuestas EN del sub-experimento bilingüe.

**Decisión de diseño:** solo se persiste el texto cuando `texto_entrada_autogenerado=true`.
Los textos introducidos manualmente o cargados desde fichero no se persisten porque
son propiedad del usuario (pueden ser documentos confidenciales). El texto generado
por la plataforma no tiene esa restricción de privacidad y sí aporta valor
reproducible al corpus del estudio. Esta decisión se registra en ADR-030.

---

### Detalle de S4-96 — Dashboard: "Generación de código" en el sub-experimento bilingüe

El texto descriptivo del bloque "Comparativa ES vs EN" en `DashboardPage.tsx` listaba
las categorías del sub-experimento bilingüe como "Razonamiento lógico, Escritura
creativa y Preguntas concretas". Se añadió "Generación de código" a la lista para
reflejar que esta categoría también forma parte del experimento comparativo y sus
resultados aparecen en las gráficas de barras agrupadas ES/EN del dashboard.

El cambio fue puramente en el texto de la UI, sin modificación de lógica de backend
ni de las constantes `CATEGORIAS_BILINGUES`.

---

### Detalle de S4-97 — BatLoader: modal de carga al pulsar "✨ Generar texto"

**Motivación:** al pulsar el botón "✨ Generar texto" en la categoría Resumen, la
llamada al endpoint `GET /benchmarks/texto-ejemplo` podía tardar varios segundos
sin ninguna retroalimentación visual. El usuario no sabía si el sistema estaba
trabajando o había fallado.

**Implementación en `SubcatPanel.tsx`:**

- Nuevas constantes de módulo `LLM_NOMBRES_DISPLAY` y `LLM_COLORES` (fuera del
  componente) que mapean cada alias de proveedor (`auto`, `gemini`, `grok`,
  `openai`, `claude`) a su nombre de display y color de marca.
- Nuevo estado `showLoaderTexto: boolean` (false por defecto).
- `handleGenerarTexto` modificado:
  - Al inicio: `setShowLoaderTexto(true)` + `setGenerandoTexto(true)` simultáneos.
  - En éxito: `setGenerandoTexto(false)` deja que BatLoader ejecute la animación
    de completado antes de que `onComplete` cierre el overlay.
  - En error: `setShowLoaderTexto(false)` + `setGenerandoTexto(false)` ocultan el
    overlay de inmediato y muestran el mensaje de error bajo el textarea.
- Overlay `position: fixed inset-0 z-50` con fondo semiopaco (`rgba(0,0,0,0.72)`)
  y `backdropFilter: blur(4px)`, que contiene:
  - Un párrafo "Generando texto aleatorio con el agente **[LLM]**" donde el nombre
    del agente se colorea con `LLM_COLORES[llmEjemplo]`.
  - Un `<BatLoader>` con un único modelo (`modelos.length = 1`) y `isLoading` ligado
    a `generandoTexto`. `onComplete` llama a `setShowLoaderTexto(false)`.

**Comportamiento con BatLoader de un solo modelo:** la secuencia de completado dura
≈ 1.3 s (1 100 ms de spin + 200 ms de buffer), igual que si solo un LLM ha
terminado en el loader habitual de cuatro modelos.

---

### Detalle de S4-98 — BatLoader: gotas sangre → iconos LLM + balanceo

**Motivación:** la metáfora del proyecto es "vampiros de información": los LLMs
consumen tokens de texto y producen conocimiento. Se reforzó visualmente esta idea
haciendo que las gotas de sangre de los colmillos del murciélago se transformen a
mitad de trayecto en el icono del LLM que está procesando.

**Iconos LLM en miniatura (`LLM_MINI`):**

Cada LLM tiene asignado un círculo SVG con una letra y su color de marca:

| LLM       | Letra | Color    |
|-----------|-------|----------|
| Gemini    | G     | #EF4444  |
| Grok      | X     | #4DB8FF  |
| GPT-4o    | G     | #10D9A0  |
| Claude    | C     | #E8956D  |

**Gotas que se transforman (`TODAS_GOTAS`, 6 posiciones):**

Cada posición de gota renderiza dos elementos SVG superpuestos con el mismo
`animationDelay`:

- `bat-drop-blood` (`<ellipse>`): visible entre el 12 % y el 68 % del ciclo de 2.6 s.
  Incluye **balanceo decreciente** con `translateX` oscilando −5 px / +4 px /
  −3 px / +2 px / −1 px a lo largo de la caída, simulando la tensión superficial
  al desprenderse del colmillo.
- `bat-drop-icon` (`<g>` con `<circle>` + `<text>`): invisible hasta el 68 %, luego
  aparece en la misma posición y continúa cayendo hasta el 83 % antes de
  desvanecerse.

El cruce ocurre exactamente en `translateY(48px)` / `translateX(-1px)` — ambas
fases coinciden en ese punto, lo que hace que la transformación se vea fluida.

Los iconos de las 6 gotas se sortean aleatoriamente al montar el componente con
`useState(() => Array.from({ length: 6 }, aleatorioLLM))` y se rotan cada 5.2 s
(dos ciclos completos) mediante `setInterval`.

**Salpicaduras con iconos LLM (`SPLATTER_POS`, 12 posiciones):**

En cada llamada a `triggerSpin()` (que ocurre al completarse cada modelo), se sortea
si cada una de las 12 posiciones de salpicadura muestra sangre o un icono LLM
(probabilidad 55 % de icono). Las posiciones asignadas a icono renderizan un
`<g>` con `<circle r={9}>` + `<text>` en lugar de la `<ellipse>` o `<circle>` de
sangre habitual. Los delays de animación se aplican vía `style={{ animationDelay }}`
inline, eliminando los selectores `:nth-child` que había en el CSS original.

---

### Detalle de S4-99 — UX resumen: readonly autogenerado + mínimo 305 palabras + "Limpiar Texto" + acordeón en resultados

Este item agrupa cuatro mejoras relacionadas con la usabilidad de la categoría Resumen
detectadas durante las pruebas.

**1. Garantía de mínimo 305 palabras (backend)**

El prompt original pedía "exactamente unas 300 palabras", lo que hacía que algunos
modelos generaran 290–298 palabras, insuficientes para superar el umbral de 300 del
frontend. Cambios en `BenchmarkService.generar_texto_ejemplo()`:

- Prompt actualizado a "mínimo 310 palabras, máximo 390 palabras".
- `max_tokens` aumentado de 600 a 700.
- Constante `_MIN_PALABRAS = 305` (margen de 5 sobre el umbral del frontend).
- Si el texto generado tiene menos de 305 palabras, se lanza un segundo intento con
  un prompt de ampliación: "El siguiente texto tiene N palabras. Amplíalo hasta
  alcanzar al menos 310 palabras…". El segundo intento usa `max_tokens=800`.
- Se registra un log `INFO` cuando se activa el reintento para facilitar el análisis
  de calidad de cada proveedor.

**2. Textarea readonly cuando el texto es autogenerado (frontend)**

Cuando `textoAutogenerado === true`, el textarea de la categoría Resumen pasa a
solo lectura (`readOnly={archivoReadonly || textoAutogenerado}`) con el mismo
estilo visual que el modo fichero: opacidad 0.85, cursor `default`, fondo `#060610`.
El `onChange` también comprueba `!textoAutogenerado`. El bloqueo preserva el flag
`texto_entrada_autogenerado=true` en la petición al backend; si el usuario editara
el texto manualmente, ese flag se perdería y el texto no se persistiría.

**3. Botón "Limpiar Texto"**

Aparece junto al aviso "🔒 Texto autogenerado — solo lectura…" cuando
`textoAutogenerado === true`. Al pulsarlo llama a
`actualizarResumen('', false)` + `setOpResumen(null)`, lo que:

- Vacía el textarea y desbloquea la edición manual.
- Deselecciona la opción activa de "¿Qué quieres hacer con el texto?".
- Ambas secciones vuelven al estado inicial con el pulso animado.

El botón tiene borde y texto en `#F5F5F0` (blanco roto), fondo transparente y halo
blanco `rgba(245,245,240,0.75)` al pasar el ratón.

**4. Acordeón "Ver texto original" en la vista de resultados de benchmark**

Replica el patrón del acordeón de `EvalViewModal` pero en `BenchmarkPage.tsx`,
situado **justo debajo del título "Respuestas de los modelos"** y antes del grid de
tarjetas. Solo se renderiza cuando `evaluacion?.texto_entrada_autogenerado &&
evaluacion.texto_entrada`. Estados nuevos en el componente:
`verTextoOriginalResultados` y `ampliadoTextoOriginalResultados`. El texto se
expande/contrae con botón de texto y también con doble clic sobre el párrafo
(mismo patrón que el historial).

---

### Detalle de S4-100 — Cohesión visual botones sección resumen

Todos los botones interactivos de la sección Resumen (y los acordeones "Ver texto
original" en todos sus puntos de aparición) se homogeneizaron con el mismo
vocabulario visual:

**Borde:** `#F5F5F0` (blanco roto) en los botones "Generar texto", "Subir fichero"
y "Limpiar Texto"; `rgba(245,245,240,0.35)` en reposo y `#F5F5F0` en hover/selected
para los botones de opción de "¿Qué quieres hacer con el texto?".

**Sombra en hover:** `box-shadow: 0 0 22px 6px rgba(245,245,240,0.75)` en todos los
botones anteriores. En "Generar texto" y "Subir fichero" se aplica mediante la clase
Tailwind `hover:shadow-[0_0_22px_6px_rgba(245,245,240,0.75)]` (sustituye el antiguo
`boxShadow` permanente con el color del tema). En los botones de opción, mediante
`boxShadow` inline condicional en el objeto `style` cuando `sel || hov`.

**Pulso con sombra blanca:** nueva clase CSS `animate-pulse-strong-white` en
`index.css` (variante de `animate-pulse-strong` con `rgba(245,245,240,0.75)` en
lugar del morado). Se aplica a "Generar texto", "Subir fichero" y a las opciones de
resumen cuando aún no se ha seleccionado ninguna. El resto de elementos que usan
`animate-pulse-strong` (textarea, otros paneles) conservan el pulso morado original.

**Acordeones "Ver texto original":** el contenedor `<div>` de los tres puntos de
aparición (`EvalViewModal` × 2 y `BenchmarkPage` × 1) tiene
`hover:border-[#F5F5F0]/60` + `hover:shadow-[0_0_22px_6px_rgba(245,245,240,0.75)]`
para que el acordeón brille al pasar el ratón, indicando que es interactivo.

---

### Detalle de S4-101 a S4-104 — Flujo de solicitud de borrado de evaluaciones (ADR-031)

**Contexto:** los evaluadores no tenían ninguna forma de retirar una evaluación
errónea (categoría equivocada, prompt incorrecto). Dar borrado directo al usuario
habría comprometido la integridad del corpus del estudio; se diseñó en su lugar
un flujo intermediado por el administrador (ADR-031, RF-32 y RF-33).

---

#### S4-101 — Backend: estado `solicitud_borrado` y migración

**Enum `SessionStatus` (`backend/app/models/enums.py`):**
```python
solicitud_borrado = "solicitud_borrado"
```

**Migración `r7a8b9c0d1e2_solicitud_borrado_estado.py`:**
```sql
ALTER TYPE sessionstatus ADD VALUE IF NOT EXISTS 'solicitud_borrado';
```
El `downgrade` es no-operativo: PostgreSQL no permite eliminar valores de enums
en uso. La cláusula `IF NOT EXISTS` hace la migración idempotente.

**`BenchmarkEvaluacionRepository.marcar_solicitud_borrado(evaluacion_id, nickname)`:**
Nuevo método con tres guards:
- `evaluacion is None` → `ValueError("no_encontrada")` → HTTP 404.
- `evaluacion.nickname != nickname` → `ValueError("sin_permiso")` → HTTP 403.
- `evaluacion.status == solicitud_borrado` → `ValueError("ya_solicitada")` → HTTP 409.

---

#### S4-102 — Backend: endpoints solicitar y rechazar borrado

**Endpoint usuario `POST /api/v1/usuarios/evaluaciones/{id}/solicitar-borrado`:**
```
Requiere: JWT de usuario web (get_current_usuario_app)
Lógica: delega en marcar_solicitud_borrado + commit
Respuesta: {"ok": True, "evaluacion_id": id}
```

**Endpoint admin `POST /api/v1/admin/evaluaciones/{id}/rechazar-borrado`:**
```
Requiere: JWT de administrador
Guard: status != solicitud_borrado → 409
Lógica: status → completada + commit
Respuesta: {"ok": True, "evaluacion_id": id, "nuevo_estado": "completada"}
```

El endpoint de eliminación definitiva ya existía como `DELETE /admin/evaluaciones/{id}`
(RF-20, S4-41) y no requirió cambios: acepta cualquier evaluación en cualquier estado,
por lo que cubre la aprobación de solicitudes de borrado sin modificación.

---

#### S4-103 — Frontend historial usuario

**Cambios en `HistorialPage.tsx`:**

- Nuevo estado `confirmandoId: number | null` para el modal de confirmación.
- Importaciones añadidas: `useMutation`, `ConfirmModal`, `solicitarBorradoEvaluacion`,
  `obtenerEvaluacion`, `useUsuarioStore`, `useToastStore`.
- **Botón "Solicitar borrado"** (visible solo para sesiones `completada` con JWT activo):
  borde rojo `rgba(248,113,113,0.55)` en reposo; al hover añade fondo
  `rgba(248,113,113,0.12)` y `box-shadow: 0 0 10px 2px rgba(248,113,113,0.45)`.
- Al pulsar el botón se abre `ConfirmModal`; al confirmar se dispara la mutación.
- **`useMutation` `mutSolicitudBorrado`:**
  - `onSuccess`: `marcarSolicitudBorrado(nick, id)` + toast éxito + cierra modal.
  - `onError` con HTTP 404: la evaluación no existe en BD → `eliminarSesion(nick, id)` +
    toast informativo (la entrada huérfana desaparece del historial).
  - `onError` otros: toast de error genérico.
- **Badge naranja** "⏳ Borrado solicitado" para entradas en estado `solicitud_borrado`
  (sustituye al botón de acción mientras el admin no actúa).
- **`useEffect` de resincronización** (se ejecuta al montar y al cambiar de nick):
  para cada entrada `solicitud_borrado` en el store local, consulta `obtenerEvaluacion(id)`;
  si la BD devuelve un estado distinto, llama a `actualizarEstado`; si devuelve 404,
  llama a `eliminarSesion`. Cubre el caso en que el admin rechazó la solicitud pero el
  usuario no ha recargado desde entonces.

**`historialStore.ts`:** tres acciones nuevas: `marcarSolicitudBorrado`,
`actualizarEstado`, `eliminarSesion`.

**`benchmarkApi.ts`:** función `solicitarBorradoEvaluacion(evaluacionId: number)`.

**`EvalViewModal.tsx`:** captura `isError` y `retry: false` de `useQuery`; cuando
la evaluación no existe en BD muestra panel de error con botón "Eliminar del historial"
que llama a `eliminarSesion(nick, sesionId)` y cierra el modal.

---

#### S4-104 — Frontend panel admin: badge y gestión de solicitudes

**`adminApi.ts`:** función `rechazarBorradoEvaluacion(token, id)`.

**`TablaAdmin.tsx`:**

- **Query independiente de conteo:**
  ```typescript
  const { data: dataSolicitudes } = useQuery({
    queryKey: ['admin-solicitudes-borrado'],
    queryFn: () => listarEvaluacionesAdmin(token, 1, 1, { estado: 'solicitud_borrado' }),
    refetchInterval: 60_000,
  })
  ```
  El campo `total` de la respuesta da el número de solicitudes pendientes.

- **Badge naranja clickable** junto al título del panel: al pulsar activa el filtro
  `estado: solicitud_borrado` en la tabla directamente.

- **Resaltado de filas:** las evaluaciones en `solicitud_borrado` reciben clase
  `bg-orange-400/10 hover:bg-orange-400/20` para destacarse visualmente.

- **Botón "Rechazar"** (color naranja) en la columna de acciones de filas
  `solicitud_borrado`: usa `ConfirmModal` interno antes de llamar a `mutRechazar`.
  `mutRechazar` invalida `admin-comparativas` y `admin-solicitudes-borrado` para
  refrescar tanto la tabla como el badge.

- Estado `solicitud_borrado` añadido a `ESTADO_COLOR` (`text-orange-400`),
  `ESTADO_LABEL` (`'Borrado solicitado'`) y al selector de filtro `ESTADO_OPC`.

---

**Diagrama de estados actualizado:** `est_evaluacion.puml` refleja el nuevo ciclo
de vida completo con las transiciones `completada → solicitud_borrado → completada`
(admin rechaza) y `solicitud_borrado → [*]` (admin elimina).

**Casos de uso actualizados:**
- `cu_usuario_04_historial.puml`: CU-20 (RF-32).
- `cu_admin_02_evaluaciones.puml`: CU-A19 (RF-33), CU-A05 con badge.

---

### Detalle de S4-105 — Refactor SOLID frontend: llmProviders.ts + tokens.ts (ADR-032)

**Problema detectado:** Los metadatos de proveedores LLM estaban dispersos en seis o más
componentes: colores hardcodeados como strings hex en estilos inline, arrays locales con los
cuatro nombres, condicionales `proveedor === 'claude'` para activar/desactivar funcionalidades.
Los tokens de diseño (hex de colores del sistema) se repetían en decenas de componentes sin
relación declarada con `tailwind.config.ts`. Añadir un quinto proveedor habría requerido
modificar al menos ocho ficheros con alto riesgo de inconsistencia.

**Solución — Principio Open/Closed aplicado:**

Se crean dos módulos nuevos como fuente única de verdad:

- **`frontend/src/config/llmProviders.ts`** — define la interfaz `ProveedorConfig` y el objeto
  `LLM_PROVIDERS_CONFIG` indexado por `LLMProvider`. Expone constantes derivadas
  (`PROVEEDORES_LIST`, `PROVEEDORES_SIN_IMAGEN`) y helpers (`proveedorColor`, `proveedorIcono`,
  `proveedorNombre`). El union type `LLMProvider` en `types/benchmark.ts` actúa como fuente de
  verdad para los identificadores válidos. TypeScript garantiza en compilación que
  `LLM_PROVIDERS_CONFIG` tiene exactamente una entrada por cada valor del union.

- **`frontend/src/utils/tokens.ts`** — objeto `TOKENS` con 28 tokens de diseño para uso
  programático (canvas, Recharts, Mermaid). Para CSS declarativo se siguen usando las clases
  Tailwind directamente.

**Patrón de extensión resultante (Open/Closed):**

Para añadir un quinto proveedor solo se modifican tres ficheros:

| Paso | Fichero | Cambio |
|------|---------|--------|
| 1 | `types/benchmark.ts` | Añadir `\| 'nuevo'` al union `LLMProvider` |
| 2 | `utils/llmIcons.ts` | Importar SVG y añadir entrada en el record de iconos |
| 3 | `config/llmProviders.ts` | Añadir objeto `ProveedorConfig` con color, nombre y flags |

Ningún componente de la UI requiere modificación.

**Auditoría post-refactor** (Explore agent):
- 0 strings hex hardcodeados en componentes de UI.
- 7 componentes consumen `llmProviders.ts` directamente.
- 12 componentes consumen `tokens.ts` directamente.

**Diagrama generado:** `arq_extension_nuevo_llm_frontend.puml` + PNG en
`docs/diagramas/plantuml/png/`.

---

### Detalle de S4-106 — Fix cuota obsoleta al recargar: GET /usuarios/me (ADR-033)

**Problema detectado:** El store `usuarioStore` de Zustand persiste `consultasUsadas` y
`cuotaAsignada` en `localStorage` (clave `'tfg-usuario'`). Al recargar la página, Zustand
rehidrata el store desde `localStorage` sin contactar el backend. Si el administrador modifica
la cuota de un usuario mientras este tiene la sesión abierta, el usuario sigue viendo el valor
antiguo hasta que vuelva a hacer login manualmente.

Caso reproducido en pruebas: admin asignó 62 consultas a una cuenta que tenía 52; al recargar
la página del usuario el contador seguía mostrando 52.

**Causa raíz:** `partialize` de Zustand incluye `consultasUsadas` y `cuotaAsignada` en la
serialización a `localStorage`. No existía ningún mecanismo de refresco al montar la aplicación.

**Solución implementada:**

1. **Backend** — nuevo endpoint `GET /api/v1/usuarios/me` en `routers/usuarios.py`:

```python
@router.get(
    "/me",
    response_model=RespuestaUsuarioApp,
    summary="Perfil del usuario autenticado",
)
async def obtener_perfil_usuario(
    usuario_actual: UsuarioApp = Depends(get_current_usuario_app),
) -> RespuestaUsuarioApp:
    return RespuestaUsuarioApp.model_validate(usuario_actual)
```

   Usa la dependencia existente `get_current_usuario_app` (Bearer JWT de usuario web, distinta de
   la dependencia de admin). Devuelve `consultas_usadas`, `cuota_asignada` y `estado` frescos
   desde la base de datos.

2. **Frontend** — `obtenerPerfilUsuario(token)` en `services/usuarioApi.ts`:

```typescript
export async function obtenerPerfilUsuario(
  token: string,
): Promise<RespuestaUsuarioApp> {
  const { data } = await api.get<RespuestaUsuarioApp>(
    '/usuarios/me',
    { headers: { Authorization: `Bearer ${token}` } },
  )
  return data
}
```

3. **Layout.tsx** — `useEffect` con array de dependencias vacío (solo al montar):

```typescript
useEffect(() => {
  if (!tokenUsuario) return
  obtenerPerfilUsuario(tokenUsuario)
    .then((perfil) => {
      actualizarCuota(perfil.consultas_usadas, perfil.cuota_asignada)
      actualizarEstado(perfil.estado)
    })
    .catch(() => {
      // El interceptor de axios gestiona el 401 (logout automatico)
    })
// eslint-disable-next-line react-hooks/exhaustive-deps
}, [])
```

**Trade-off asumido:** Una petición HTTP extra al cargar cada página. El impacto es despreciable
(< 50 ms en red local, < 200 ms en Cloud Run). El valor de `localStorage` se muestra durante
los milisegundos que tarda la respuesta, evitando parpadeo.

**Comportamiento en caso de fallo de red:** el `catch` no hace nada; el usuario ve el valor
cacheado. El interceptor de axios gestiona automáticamente el 401 (token caducado) llamando a
`logout()`.

---

### Detalle de S4-107 — Documentación alineada con el código (ADR-032/033)

**Alcance de la auditoría:** tras implementar S4-105 y S4-106 se auditaron todos los artefactos
de documentación para alinearlos con el estado real del código.

**Cambios en `docs/memoria/chapters/04_analisis_diseno.md`:**

- **RNF-07** (extensibilidad) actualizado: "Añadir un quinto proveedor LLM requiere únicamente:
  (1) implementar `BaseLLMClient` en el backend, y (2) añadir una entrada en `llmProviders.ts`
  en el frontend."
- **Tabla de endpoints de la API** ampliada con tres nuevas filas:
  `POST /usuarios/login`, `GET /usuarios/me`, `POST /usuarios/solicitar-mas-tokens`.
- **Sección 4.5 — Diseño del frontend** expandida con tres subsecciones nuevas:
  - 4.5.1: Principio Open/Closed en el frontend (`llmProviders.ts` + `tokens.ts`).
  - 4.5.2: Estado global con Zustand (tabla de stores con columna Persistencia + descripción
    del `useEffect` de refresco en Layout).
  - 4.5.3: Comunicación con el backend (renumerada, antes era 4.5.2).

**Cambios en `docs/memoria/chapters/05_implementacion.md`:**

- Nueva sección **5.5 — Frontend: componentes y sistema de diseño** insertada antes del antiguo
  5.5 Despliegue:
  - 5.5.1: Estructura del frontend (árbol de directorios).
  - 5.5.2: Principio Open/Closed (código de `llmProviders.ts` + tabla de extensión en 3 pasos).
  - 5.5.3: Sincronización de cuota (snippet del `useEffect` en `Layout.tsx`).
- Antiguo 5.5 Despliegue renumerado a 5.6.
- Antiguo 5.6 Tests renumerado a 5.7.

**ADRs creados:**

| ADR | Título | Decisión |
|-----|--------|----------|
| ADR-032 | SOLID en el frontend — llmProviders.ts como fuente única de verdad | Centralizar metadatos de proveedores en `llmProviders.ts` + tokens en `tokens.ts` |
| ADR-033 | Refresco de cuota al recargar — GET /usuarios/me | Llamar `GET /usuarios/me` en `useEffect` del Layout al montar |

**Diagrama actualizado:** `arq_componentes_frontend_p1.puml` — añadido paquete
`PKG_CONFIG #DDEEFF` con los dos módulos de configuración, flechas desde `BPage` y `DPage`
hacia `PROV`/`TOK`, flecha `Layout → US` con `actualizarCuota()`, y notas con referencias
a ADR-032 y ADR-033. PNG regenerado.
