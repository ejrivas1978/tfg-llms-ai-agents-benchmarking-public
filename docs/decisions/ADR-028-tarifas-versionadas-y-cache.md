# ADR-028 — Tarifas versionadas, descuento de caché y modelo de precios LLM

**Fecha:** 13/05/2026
**Estado:** Aceptado
**Sprint:** Sprint 4
**Revisión 13/05/2026 (tarde):** auditoría contra webs oficiales — Gemini corregido, precio imagen movido a la tabla versionada (ver § Auditoría al final).
**Revisión 13/05/2026 (final):** precisión de columnas elevada a `NUMERIC(12, 8)` para precios y costes (ver § Precisión numérica al final).
**Revisión 13/05/2026 (post-final):** el marcador de autor de las filas sembradas en `tarifas_llm.actualizado_por` se renombra de `'seed'` a `'root'` (migración `m2b3c4d5e6f7`) por coherencia con el rol root canónico del estudio (ADR-027).
**Revisión 13/05/2026 (edición imagen nativa):** se separa el precio por imagen en dos columnas (`generar` / `editar`) y se implementa edición nativa para Gemini (`gemini-2.5-flash-image`) y Grok (`grok-imagine-image-quality`); migración `n3c4d5e6f7a8` (ver § Edición nativa al final).
**Revisión 13/05/2026 (DALL-E 3 retirada):** OpenAI retira `dall-e-3` del API (HTTP 400 *"model does not exist"*); migración a `gpt-image-1` con `quality="medium"` ($0.07/img) tras análisis comparativo de calidad (ver § DALL-E 3 retirada al final); migración `o4d5e6f7a8b9`.

---

## Contexto

Casi todas las métricas automáticas del estudio dependen del coste por llamada
LLM. Hasta esta revisión, los precios estaban **hardcoded** en un diccionario
en `backend/app/llm_engine/metricas.py` (`_PRECIOS_POR_MTOKEN`) con dos valores
por proveedor: entrada y salida en USD por millón de tokens. La fórmula del
coste se calculaba al momento de cada llamada y se persistía en
`llm_responses.cost_usd`.

Esa simplificación era suficiente mientras los precios se consideraban estables
y idénticos por todos los caminos (texto, imagen, llamada repetida). Tres
problemas la hacen insostenible para el TFG:

1. **No es editable en operación**: si un proveedor sube tarifas durante el
   estudio, hay que tocar código, redesplegar y "perder" la coherencia
   histórica de los costes ya calculados.
2. **No hay trazabilidad histórica**: dos respuestas LLM del mismo proveedor
   pueden haber sido cobradas con tarifas diferentes si entre medias hubo un
   cambio. Sin un registro explícito de qué tarifa se usó en cada llamada,
   el coste `cost_usd` queda como un número opaco no reproducible.
3. **La realidad del pricing es multidimensional**: cada proveedor tiene varias
   tarifas según el camino de la llamada (caché, batch, long-context,
   imagen, vision tokens). No modelar nada de esto introduce un error potencial
   en `cost_usd` que conviene cuantificar y, en lo posible, reducir.

Esta ADR justifica las dos decisiones combinadas:

- **Versionado de tarifas + trazabilidad por respuesta**: cada llamada LLM
  queda enlazada a la fila exacta de tarifa que se cobró.
- **Detección de cache hits y aplicación de descuento**: capturar los tokens
  cacheados que las APIs ya exponen y aplicar un tercer precio editable
  (`precio_entrada_cacheado`), opcional por proveedor.

## Realidad del pricing por proveedor (mayo 2026)

Lo que cobra **realmente** cada API según el camino de la llamada:

| Dimensión               | Claude Sonnet 4.6                    | GPT-4o                                  | Gemini 2.5 Flash                              | Grok 3                          |
|-------------------------|--------------------------------------|-----------------------------------------|------------------------------------------------|---------------------------------|
| Texto in/out estándar   | 3.00 / 15.00                         | 2.50 / 10.00                            | 0.075 / 0.30                                   | 1.25 / 2.50                     |
| Caché — write           | **3.75** (1.25× base)                | —                                       | —                                              | —                               |
| Caché — read (hit)      | **0.30** (0.1× base)                 | **1.25** (0.5× base)                    | **~0.019** (0.25× base)                        | **~0.625** (0.5× base, est.)    |
| Tier "long context" (>200k) | —                                | —                                       | **2×** las tarifas base                        | —                               |
| Batch API (–50 %)       | sí                                   | sí                                      | sí                                             | no documentado                  |
| Imagen generación       | — (no soporta, ADR-011)              | DALL·E 3: $0.040/img · gpt-image-1: var. | Imagen 4: ~$0.04/img                           | grok-imagine: ~$0.04/img        |
| Vision in (tokens img)  | ~1600 tok/img                        | 85 – 1100 tok según `detail`            | tokens internos                                | tokens internos                 |

Precios en USD por millón de tokens salvo donde se indique "/img".

## Decisión

### 1. Versionado de tarifas

Se sustituye el diccionario hardcoded por una **tabla versionada**
`tarifas_llm`:

| Columna                                       | Tipo            | Notas                                                  |
|-----------------------------------------------|-----------------|--------------------------------------------------------|
| `id`                                          | INTEGER PK      | autoincremental — única por versión                    |
| `proveedor`                                   | ENUM            | claude / openai / gemini / grok (no `UNIQUE`)          |
| `precio_entrada_usd_por_mtoken`               | NUMERIC(10,4)   | NOT NULL — tarifa estándar de entrada                  |
| `precio_salida_usd_por_mtoken`                | NUMERIC(10,4)   | NOT NULL — tarifa estándar de salida                   |
| `precio_entrada_cacheado_usd_por_mtoken`      | NUMERIC(10,4)   | NULL = sin descuento configurado                       |
| `vigente`                                     | BOOLEAN         | NOT NULL DEFAULT TRUE                                  |
| `actualizado_en`                              | TIMESTAMPTZ     | NOT NULL                                               |
| `actualizado_por`                             | VARCHAR(64)     | nick del admin o `'root'` (sembrado en despliegue inicial)  |

Índices:

```sql
UNIQUE (proveedor) WHERE vigente = TRUE     -- una sola vigente por proveedor
INDEX  (proveedor, actualizado_en)          -- consultas de historial
```

Cada **PUT** desde el panel admin crea una fila nueva con `vigente=TRUE` y
marca la anterior del mismo proveedor con `vigente=FALSE`. Las filas
históricas se conservan indefinidamente para auditoría.

`llm_responses` gana **`tarifa_id INTEGER FK -> tarifas_llm.id ON DELETE
RESTRICT`** (nullable, indexado). Cada respuesta queda ligada a la versión
exacta de tarifa con la que se cobró su `cost_usd`. `ON DELETE RESTRICT`
impide borrar una tarifa que tenga respuestas asociadas, preservando la
trazabilidad histórica.

### 2. Cache de precios en memoria + refresh atómico

`metricas._PRECIOS_POR_MTOKEN` deja de ser fuente de verdad y pasa a ser
**cache mutable** del dato persistido:

```python
{
  LLMProvider.claude: {"id": 1, "entrada": 3.00, "salida": 15.00, "entrada_cacheado": 0.30},
  ...
}
```

- Se hidrata al arrancar la app (`lifespan` en `main.py`) leyendo las filas
  `vigente=TRUE`. Si la BD no responde, se mantienen los defaults hardcoded
  como fallback (operación degradada pero funcional).
- Tras cada PUT del admin, `TarifaService.actualizar_tarifa()` hace
  `commit()` **antes** de `refrescar_cache_precios()`. Orden crítico: si
  refrescásemos antes del commit, un fallo de commit dejaría el cache con
  un precio que nunca llegó a persistirse; las siguientes llamadas LLM
  cobrarían con un valor "fantasma".
- La mutación se hace **in-place** con `dict.clear() + dict.update()` para
  que cualquier módulo que haya importado la referencia (`from metricas
  import _PRECIOS_POR_MTOKEN`) siga viendo los valores actualizados.

### 3. Detección de cache hits y fórmula

Cada cliente LLM captura defensivamente el campo `cached_tokens` que la API
devuelve:

| Proveedor   | Campo en `usage`                                      |
|-------------|-------------------------------------------------------|
| Claude      | `usage.cache_read_input_tokens`                       |
| OpenAI/Grok | `usage.prompt_tokens_details.cached_tokens`           |
| Gemini compat | `usage.prompt_tokens_details.cached_tokens` (si lo expone) |

Si el SDK no lo expone, se queda en 0. Se guarda en
`llm_responses.input_tokens_cached` y se propaga a `ResultadoLLM.tokens_entrada_cacheados`.

`calcular_coste_usd()` aplica la fórmula:

```
tokens_no_cached = max(0, tokens_entrada - tokens_entrada_cacheados)
si precio_cacheado IS NOT NULL y tokens_entrada_cacheados > 0:
    coste_in = tokens_no_cached × precio_in + tokens_entrada_cacheados × precio_cacheado
si no:
    coste_in = tokens_entrada × precio_in   (sin descuento, caso por defecto)

coste = (coste_in + tokens_salida × precio_out) / 1_000_000
```

Compatibilidad hacia atrás: si nadie configura `precio_cacheado` (queda
NULL) o la API no reporta hits (= 0), la fórmula colapsa al cálculo
estándar previo y `cost_usd` no cambia.

### 4. Valores vigentes tras auditoría (13/05/2026)

| Proveedor | Modelo exacto         | `precio_entrada` | `precio_salida` | `precio_entrada_cacheado` | `precio_imagen` |
|-----------|------------------------|------------------|------------------|---------------------------|------------------|
| Claude    | `claude-sonnet-4-6`    | 3.0000           | 15.0000          | 0.3000 (=10 % base, oficial) | — (no soporta)   |
| OpenAI    | `gpt-4o` + `dall-e-3`  | 2.5000           | 10.0000          | 1.2500 (=50 % base, oficial) | 0.0400/img       |
| Gemini    | `gemini-2.5-flash` + `imagen-4.0-generate-001` | 0.3000 | 2.5000 | 0.0300 (oficial)        | 0.0400/img       |
| Grok      | `grok-4.3` + `grok-imagine-image` | 1.2500 | 2.5000           | 0.6250 (=50 % base, **estimación** documentada) | 0.0200/img       |

> El precio cacheado de Grok es la única estimación no oficial: xAI no publica
> tarifa de caché. Se ha alineado con OpenAI (50 % base) como aproximación
> razonable y se mantiene editable para corregirlo cuando xAI lo publique.

## Dimensiones de pricing **NO** modeladas

Se descartan modelar los siguientes caminos por análisis de impacto en
**este** estudio. Cada uno se documenta junto con el motivo concreto de
descarte:

| Dimensión no modelada                | Cuándo aplicaría                                              | Impacto en TFG (justificación del descarte) |
|--------------------------------------|---------------------------------------------------------------|---------------------------------------------|
| Caché — write (Claude)               | Reusar el mismo prompt en otra llamada en < 5 min             | Improbable: cada evaluación se lanza una vez con un prompt distinto; el caché no se inicializa explícitamente |
| Tier "long context" Gemini (> 200k)  | Prompts que excedan el umbral                                 | No aplica: prompts del estudio < 2 k tokens típicamente |
| Batch API (–50 %)                    | Cuando se enviase como job asíncrono                          | No aplica: el sistema es síncrono paralelo (`asyncio.gather`, ADR-004) |
| Vision tokens (`detail high`)        | Categoría visión multimodal con imagen alta resolución        | Ya contabilizados: el SDK suma los tokens de imagen a `input_tokens` automáticamente |
| `gpt-image-1` por tier de calidad    | Si se cambiase de `standard` a `hd`                           | Hoy se usa tarifa fija $0.04/img (ADR sobre tarifa imagen) |
| Conversión de moneda                 | Si se quisiera mostrar en EUR                                  | El estudio reporta en USD; conversión la haría el lector con tipo de cambio del día |

## Consecuencias

### Positivas

- **Trazabilidad completa**: cada `llm_responses.cost_usd` se puede reproducir
  haciendo JOIN con la versión exacta de tarifa, incluso años después.
- **Auditoría reactiva**: `input_tokens_cached > 0` queda registrado por
  llamada. Si un escenario futuro disparase cache, lo detectaríamos.
- **Editable sin redesplegar**: el admin actualiza precios desde la pestaña
  Tarifas; el cache se refresca al instante para las siguientes llamadas.
- **Histórico inmutable**: una llamada antigua nunca cambia de coste cuando se
  actualizan tarifas; el FK la fija a la versión con la que se cobró.

### Negativas

- **Mantenimiento manual**: las tarifas no se actualizan automáticamente desde
  las páginas de pricing de los proveedores (las APIs públicas de pricing no
  existen). Hay que revisar y editar a mano periódicamente.
- **Backfill aproximado**: las respuestas LLM anteriores al despliegue de esta
  migración (377 filas en la BD del entorno de desarrollo a 13/05/2026) se
  asocian al seed inicial; no necesariamente coincide con el precio real que
  estaba en código en el momento exacto de la llamada, pero es la mejor
  aproximación disponible sin información histórica.
- **Cobertura parcial del pricing real**: las 5 dimensiones no modeladas
  (tabla anterior) podrían introducir desviaciones puntuales si la realidad
  cambia. En el escenario actual del estudio el impacto es despreciable.

## Implementación

- **Modelos**: `app/models/tarifa_llm.py` (con `vigente`, `precio_cacheado`),
  `LLMResponse` (con `tarifa_id`, `input_tokens_cached`,
  `relationship(tarifa, lazy='raise')`).
- **Cache + helper**: `metricas._PRECIOS_POR_MTOKEN`,
  `refrescar_cache_precios(db)`, `obtener_id_tarifa_vigente(prov)`.
- **Fórmula**: `calcular_coste_usd(prov, in, out, cached=0)` con descuento
  condicional.
- **Clientes LLM**: claude/openai/gemini/grok extraen `cached_tokens` con
  `getattr` defensivo y propagan `tokens_entrada_cacheados` +
  `tarifa_id` en `ResultadoLLM`.
- **Repositorio + servicio**: `TarifaRepository.crear_nueva_version()`,
  `TarifaService.actualizar_tarifa()` con `commit()` antes del refresh.
- **Router**: `GET /admin/tarifas`, `PUT /admin/tarifas/{proveedor}`,
  `GET /admin/tarifas/{proveedor}/historial`.
- **CSV admin**: 5 columnas nuevas — `input_tokens_cached`, `tarifa_id`,
  `tarifa_precio_entrada_usd_por_mtoken`, `tarifa_precio_salida_usd_por_mtoken`,
  `tarifa_precio_entrada_cacheado_usd_por_mtoken`.
- **Frontend admin**: pestaña "Tarifas" con tabla editable (3 precios) + modal
  "Ver historial" con columnas de cada versión.
- **Migraciones Alembic**: `h7c8d9e0f1a2` (tabla seed), `i8d9e0f1a2b3`
  (versionado + tarifa_id + backfill), `j9e0f1a2b3c4` (cached + precio
  cacheado + backfill).

## Verificación funcional

Las 4 invariantes críticas se han comprobado con un script end-to-end:

1. Sin hits y sin tarifa cacheada: `cost_usd` idéntico al cálculo anterior.
2. Con hits y tarifa cacheada presente: descuento aplicado correctamente
   (e.g. OpenAI 1 M in + 1 M out con 500 k hits = $11.875 en vez de $12.50).
3. Con hits pero `precio_cacheado` = NULL en BD: descuento ignorado, se cobra
   todo al precio estándar.
4. Tras un PUT desde admin: cache refrescado, llamadas siguientes aplican el
   precio nuevo, llamadas previas conservan su `tarifa_id` original.

## Auditoría contra fuentes oficiales (13/05/2026)

A petición del responsable del TFG, se contrastaron los precios sembrados
con las páginas oficiales de cada proveedor. Se documentan a continuación
las tablas **literales** obtenidas y las dos correcciones que la auditoría
forzó a aplicar.

### Modelos exactos invocados por los clientes LLM

| Proveedor | Cliente | Modelo texto | Modelo imagen | Modelo edición imagen |
|-----------|---------|--------------|---------------|------------------------|
| Anthropic | `ClaudeClient` | `claude-sonnet-4-6` | — (ADR-011) | — |
| OpenAI    | `OpenAIClient` | `gpt-4o` | `dall-e-3` (deprecado por OpenAI pero accesible) | `gpt-image-1` |
| Google    | `GeminiClient` | `gemini-2.5-flash` | `imagen-4.0-generate-001` | — |
| xAI       | `GrokClient`   | `grok-4.3` | `grok-imagine-image` | — |

### Tabla A — Anthropic ([docs.claude.com/en/docs/about-claude/pricing](https://docs.claude.com/en/docs/about-claude/pricing))

Tabla completa del modelo `Claude Sonnet 4.6` y su familia, fuente oficial:

| Modelo            | Base Input Tokens | 5m Cache Writes | 1h Cache Writes | Cache Hits & Refreshes | Output Tokens |
|-------------------|-------------------|-----------------|-----------------|-----------------------|---------------|
| Claude Sonnet 4.6 | **$3 / MTok**     | $3.75 / MTok    | $6 / MTok       | **$0.30 / MTok**      | **$15 / MTok**|
| Claude Sonnet 4.5 | $3 / MTok         | $3.75 / MTok    | $6 / MTok       | $0.30 / MTok          | $15 / MTok    |
| Claude Sonnet 4   | $3 / MTok         | $3.75 / MTok    | $6 / MTok       | $0.30 / MTok          | $15 / MTok    |
| Claude Opus 4.7   | $5 / MTok         | $6.25 / MTok    | $10 / MTok      | $0.50 / MTok          | $25 / MTok    |
| Claude Haiku 4.5  | $1 / MTok         | $1.25 / MTok    | $2 / MTok       | $0.10 / MTok          | $5 / MTok     |

Multiplicadores de prompt caching (Anthropic los publica como reglas, no como
columnas separadas por modelo): 5 m cache write = 1.25× base · 1 h cache write
= 2× base · cache hit = **0.1× base** ("A cache hit costs 10 % of the standard
input price").

Batch API: 50 % de descuento sobre input y output (no se modela; el sistema es
síncrono).

**Resultado auditoría Claude**: ✅ Coincide al 100 % con el seed.

### Tabla B — OpenAI ([developers.openai.com/api/docs/pricing](https://developers.openai.com/api/docs/pricing))

| Modelo           | Input USD/MTok | Cached input USD/MTok | Output USD/MTok | Imagen $/img (1024×1024) | Notas oficiales |
|------------------|----------------|------------------------|------------------|--------------------------|------------------|
| `gpt-4o`         | **$2.50**      | **$1.25**              | **$10.00**       | —                        | "Default", versátil, flagship; no deprecado |
| `dall-e-3`       | —              | —                      | —                | **$0.04** standard / $0.08 HD | Listado como **"Deprecated"** ("Previous generation image generation model") pero sigue accesible |
| `gpt-image-1`    | —              | —                      | —                | ~$0.02 low / ~$0.07 medium / ~$0.19 high | Precio variable según calidad; en el código se usa con calidad por defecto |

**Resultado auditoría OpenAI**: ✅ Coincide al 100 % con el seed para
`gpt-4o` y `dall-e-3` (que es el modelo realmente facturado por el cliente
`generar_imagen()`). El uso eventual de `gpt-image-1` para `editar_imagen()`
en calidad media o alta podría desviarse del precio plano $0.04; se documenta
como limitación (ver tabla de dimensiones no modeladas).

### Tabla C — Google ([ai.google.dev/gemini-api/docs/pricing](https://ai.google.dev/gemini-api/docs/pricing))

Tarifa del modelo `gemini-2.5-flash` por tier de servicio, en USD/MTok:

| Tier      | Input (text/image/video) | Output | Context caching |
|-----------|--------------------------|--------|------------------|
| **Standard (Paid)** | **$0.30**          | **$2.50** | **$0.03**     |
| Batch     | $0.15                    | $1.25  | $0.03            |
| Flex      | $0.15                    | $1.25  | $0.03            |
| Priority  | $0.54                    | $4.50  | $0.054           |

El cliente `GeminiClient` invoca el endpoint compat-OpenAI estándar (síncrono),
así que aplica el **Standard tier**.

Imagen 4 (`imagen-4.0-generate-001`):

| Variante  | $/img    |
|-----------|----------|
| Fast      | $0.02    |
| **Standard** | **$0.04** |
| Ultra     | $0.06    |

**Resultado auditoría Gemini**: ❌ El seed original tenía $0.075 input /
$0.30 output / $0.0188 cached, valores que correspondían a un tier histórico
(probablemente Gemini Flash-Lite o una tarifa anterior). El **factor de
error** era 4×–8× por debajo del Standard tier oficial. Aplicada la
corrección con una nueva versión vigente (`actualizado_por='audit-2026-05-13'`)
con valores $0.30 / $2.50 / $0.03 / $0.04 imagen.

### Tabla D — xAI ([docs.x.ai/docs/models](https://docs.x.ai/docs/models))

Modelos texto vigentes mayo 2026:

| Modelo                          | Input USD/MTok | Output USD/MTok | Cached input |
|---------------------------------|----------------|------------------|--------------|
| **`grok-4.3`**                  | **$1.25**      | **$2.50**        | No especificado |
| `grok-4.20-0309-reasoning`      | $1.25          | $2.50            | No especificado |
| `grok-4.20-0309-non-reasoning`  | $1.25          | $2.50            | No especificado |
| `grok-4-1-fast-reasoning`       | $0.20          | $0.50            | No especificado |
| `grok-4-1-fast-non-reasoning`   | $0.20          | $0.50            | No especificado |
| `grok-4.20-multi-agent-0309`    | $1.25          | $2.50            | No especificado |

Imagen:

| Modelo                      | $/img    |
|-----------------------------|----------|
| **`grok-imagine-image`**    | **$0.02** |
| `grok-imagine-image-quality`| $0.05    |
| `grok-imagine-image-pro`    | $0.07 (a retirar 15/05/2026) |

**Resultado auditoría xAI**:
- ✅ Texto `grok-4.3`: $1.25 / $2.50 coincide con el seed.
- ⚠️ Cached input: xAI no documenta tarifa. Mantenida la estimación interna
  $0.625 (= 50 % base, alineada con OpenAI) como aproximación documentada.
- ❌ Imagen `grok-imagine-image`: el seed tenía $0.04 hardcoded;
  el precio oficial es **$0.02**. Aplicada corrección.

### Cambios aplicados por la auditoría

| Cambio                                              | Migración        | Implementación |
|------------------------------------------------------|------------------|---------------|
| Nueva columna `tarifas_llm.precio_imagen_usd_por_imagen` (NUMERIC NULL) | `k0f1a2b3c4d5` | Eliminado el dict hardcoded `_PRECIO_IMAGEN_USD`; `calcular_coste_imagen_usd()` lee del cache |
| Backfill imagen: Claude NULL, OpenAI $0.04, Gemini $0.04, **Grok $0.02** | `k0f1a2b3c4d5` | UPDATE in-place en todas las filas (dev data) |
| Nueva versión vigente Gemini con precios audit ($0.30/$2.50/$0.03/$0.04) | `k0f1a2b3c4d5` | Versión seed antigua queda con `vigente=FALSE`; nueva `actualizado_por='audit-2026-05-13'` |
| Cache `_PRECIOS_POR_MTOKEN` gana clave `imagen` | — | `refrescar_cache_precios()` la rellena al hidratar |
| Schemas/Repo/Service/Router aceptan `precio_imagen_usd_por_imagen` | — | Editable desde la pestaña Tarifas |
| CSV admin gana columna `tarifa_precio_imagen_usd_por_imagen` | — | Persistencia histórica intacta |
| Frontend `TablaTarifas` gana 4ª columna "Imagen $/img" editable | — | Validación: positivo o vacío |
| Frontend modal historial gana columna "Imagen $/img" por versión | — | "—" si NULL |

### Validez post-auditoría

Tras estos cambios, el modelo de coste cubre con precios oficiales **todos
los caminos reales** del benchmark:

- Texto estándar (entrada/salida sin caché) — 100 % oficial para los 4 proveedores.
- Texto con cache hit — 100 % oficial para Claude/OpenAI/Gemini; estimación
  documentada para Grok.
- Imagen — 100 % oficial para los 3 modelos invocados (DALL·E 3 standard,
  Imagen 4 standard, grok-imagine-image).

Las dimensiones que siguen no modeladas (long-context Gemini, batch API,
gpt-image-1 high quality) están documentadas en la tabla de § Decisión §
"Dimensiones no modeladas" con su justificación de descarte para este TFG.

## Precisión numérica (revisión 13/05/2026 final)

Tras la auditoría se detectó que el almacenamiento de precios y costes
tenía menos precisión decimal que el cálculo en Python:

| Columna                                       | Tipo previo     | Tipo nuevo        |
|-----------------------------------------------|-----------------|-------------------|
| `tarifas_llm.precio_entrada_usd_por_mtoken`   | `NUMERIC(10, 4)`| `NUMERIC(12, 8)`  |
| `tarifas_llm.precio_salida_usd_por_mtoken`    | `NUMERIC(10, 4)`| `NUMERIC(12, 8)`  |
| `tarifas_llm.precio_entrada_cacheado_usd_por_mtoken` | `NUMERIC(10, 4)` | `NUMERIC(12, 8)` |
| `tarifas_llm.precio_imagen_usd_por_imagen`    | `NUMERIC(10, 4)`| `NUMERIC(12, 8)`  |
| `llm_responses.cost_usd`                      | `NUMERIC(10, 6)`| `NUMERIC(12, 8)`  |
| `llm_responses.coste_por_100_palabras`        | `NUMERIC(10, 6)`| `NUMERIC(12, 8)`  |

**Motivación**:

1. **Coherencia input/output**: `calcular_coste_usd()` redondea internamente
   a 8 decimales (`round(coste, 8)`), pero la BD truncaba a 4 / 6 decimales
   al persistir. La precisión que se calculaba se perdía al guardarla.

2. **Llamadas pequeñas con caché**: para una llamada de 50 tokens cacheados
   a Gemini (precio cacheado $0.03/Mtok), el coste real es 50 × 0.03 / 1 M
   = **$0.0000015**. Con `NUMERIC(10, 6)` se redondea a $0.000002 (33 % de
   error en ese registro individual); este error se acumula en los
   agregados `AVG(cost_usd)` del dashboard.

3. **Coste futuro de modelos baratos**: pricing futuro sub-centésima de
   Mtok no se representa exactamente con 4 decimales en el precio (ej.
   $0.018750 truncado a $0.0188 = 0.27 % de desviación al multiplicar).

Capacidad de `NUMERIC(12, 8)`: 4 dígitos enteros + 8 decimales →
máximo `9999.99999999`. Cubre cualquier precio razonable (el más alto hoy
documentado es Claude Opus 4.7 Fast Mode output a $150/MTok).

Cambios complementarios:
- Migración Alembic `l1a2b3c4d5e6` con `ALTER COLUMN TYPE` no destructivo.
- Modelos ORM SQLAlchemy: `Numeric(10, 4)` y `Numeric(10, 6)` → `Numeric(12, 8)`.
- Schema Pydantic `PeticionActualizarTarifa`: `le=Decimal("999999.9999")`
  → `le=Decimal("9999.99999999")`.
- Frontend `TablaTarifas`: `step="0.0001"` → `step="0.00000001"`,
  `max="999999.9999"` → `max="9999.99999999"`.
- Frontend: nuevo helper `utils/formatPrecio.ts` que muestra hasta 8
  decimales pero recorta ceros sobrantes tras el cuarto (legibilidad).
- CSV exporter: formato de precios y costes `:.4f`/`:.6f` → `:.8f`.

## Edición de imagen nativa (revisión 13/05/2026, tarde-noche)

Tras la auditoría se detectó que la suposición inicial — "solo OpenAI tiene
modelo de edición de imagen, Gemini y Grok ignoran la imagen de referencia y
generan desde texto" — era **incorrecta** a fecha mayo 2026. Ambos
proveedores ya publican modelos dedicados a edición img2img:

| Proveedor | Modelo edición (img2img) | Endpoint API | Precio oficial |
|-----------|---------------------------|--------------|----------------|
| OpenAI    | `gpt-image-1` | `/v1/images/edits` | ~$0.04/img |
| **Google** | **`gemini-2.5-flash-image`** (alias "Nano Banana") | `models/gemini-2.5-flash-image:generateContent` | **$0.039/img** (1290 tok × $30/MTok) |
| **xAI**   | **`grok-imagine-image-quality`** | `/v1/images/edits` | **$0.05/img** |
| Anthropic | — | (no soporta imagen, ADR-011) | — |

### Cambios aplicados

1. **`tarifas_llm`** se reestructura para separar precio de **generación**
   (txt2img) y precio de **edición** (img2img). Hasta esta revisión existía
   una sola columna `precio_imagen_usd_por_imagen`; ahora hay dos:
   - `precio_imagen_generar_usd_por_imagen` (renombrada desde la anterior)
   - `precio_imagen_editar_usd_por_imagen` (nueva, `NUMERIC(12, 8) NULL`)

2. **Backfill** en la migración `n3c4d5e6f7a8` para TODAS las filas
   existentes según los precios oficiales auditados arriba.

3. **`GeminiClient.editar_imagen()`** se implementa nativamente vía httpx
   al endpoint `models/gemini-2.5-flash-image:generateContent`, pasando
   `inline_data` con la imagen base64 y solicitando
   `responseModalities: ["TEXT", "IMAGE"]`. Antes este método delegaba en
   `generar_imagen()` ignorando la imagen de referencia.

4. **`GrokClient.editar_imagen()`** se implementa nativamente vía httpx al
   endpoint `POST /v1/images/edits` con `model="grok-imagine-image-quality"`
   y la imagen en formato `data-URI` (`image_url` según convención xAI).
   El SDK de OpenAI `images.edit()` no es compatible con el formato xAI
   según su documentación oficial, por eso se usa httpx puro.

5. **Cache `_PRECIOS_POR_MTOKEN`** gana dos claves: `imagen_generar` e
   `imagen_editar`. La función `calcular_coste_imagen_usd()` acepta un
   nuevo parámetro `editar: bool = False` para elegir la tarifa correcta.

6. **CSV admin** gana una columna adicional: a partir de ahora se exportan
   `tarifa_precio_imagen_generar_usd_por_imagen` y
   `tarifa_precio_imagen_editar_usd_por_imagen` (antes había solo una columna
   genérica `tarifa_precio_imagen_usd_por_imagen`).

7. **Frontend `TablaTarifas`** muestra ahora **5 columnas editables** por
   proveedor (entrada / salida / cacheado / img gen / img edit) en vez de 4.
   Cada `<input>` lleva tooltip indicando los modelos exactos a los que
   aplica el precio.

### Validez del estudio tras este cambio

A partir de esta revisión, la **categoría "editar imagen"** del benchmark
pasa a ser comparable manzana-con-manzana entre los 3 proveedores que
soportan imagen:

- OpenAI: edita realmente con `gpt-image-1` (ya lo hacía).
- Gemini: edita realmente con `gemini-2.5-flash-image` (antes ignoraba la
  imagen y generaba desde cero).
- Grok: edita realmente con `grok-imagine-image-quality` (antes ignoraba
  la imagen y generaba desde cero).
- Claude: no participa (ADR-011).

### Limpieza dev

La misma migración `n3c4d5e6f7a8` elimina filas residuales con
`actualizado_por='verify-script'` que habían quedado de scripts de pruebas
en entorno de desarrollo. No están referenciadas por respuestas LLM, por lo
que el `ON DELETE RESTRICT` permite el borrado. En el entorno de estudio
final no quedará constancia de esos experimentos.

## DALL-E 3 retirada — migración a gpt-image-1 medium (13/05/2026, tarde)

Durante pruebas de generación de imagen tras la auditoría, OpenAI devolvió:

```
Error code: 400 — {'error': {'message': "The model 'dall-e-3' does not exist.",
                              'type': 'image_generation_user_error',
                              'param': 'model', 'code': 'invalid_value'}}
```

Verificación contra el pricing oficial confirma que `dall-e-3` ya no aparece
en `developers.openai.com/api/docs/pricing`: ha sido **retirado del API**
sustituido por la familia `gpt-image-1` / `gpt-image-1.5` / `gpt-image-2`.

### Modelo elegido y por qué: `gpt-image-1` quality `medium`

| Quality `gpt-image-1` | Tokens out (1024×1024) | Precio oficial | Posicionamiento |
|---|---|---|---|
| `low` | 272 | $0.02/img | Drafts rápidos, alta volumen |
| **`medium`** ← elegido | **1056** | **$0.07/img** | Default razonable, calidad profesional |
| `high` | 4160 | $0.19/img | Máxima fidelidad |

#### Análisis comparativo de calidad

Para que la categoría "generación de imagen" del benchmark mantenga
comparabilidad **manzana-con-manzana** entre los 3 proveedores con soporte
de imagen, se evaluó cuál quality de `gpt-image-1` se aproxima más a los
modelos ya usados:

| Modelo (proveedor) | Posicionamiento | Comparable con… |
|---|---|---|
| `imagen-4.0-generate-001` standard (Gemini) | "Calidad profesional, texturas/tipografía mejoradas" | **`gpt-image-1` medium** |
| `grok-imagine-image` (Grok) | "Production-quality básica, estilos narrow", $0.02/img | `gpt-image-1` low |
| `gpt-image-1` low | "Drafts rápidos" | Grok Imagine |
| `gpt-image-1` medium | "Default razonable, profesional" | **Imagen 4 standard** |
| `gpt-image-1` high | "SOTA fotorrealismo" | Sin equivalente en este estudio |

**Fuentes consultadas**: Artificial Analysis (`artificialanalysis.ai/image/models`),
Notes by Lex (*"Imagen 4 is faster, but GPT is still the GOAT"*),
OpenAI dev community thread "GPT-Image-1 quality parameter".

**Conclusión**: No existe un único `quality` de `gpt-image-1` que se
aproxime a los DOS otros simultáneamente. Cualquier elección genera una
ligera asimetría:

- Elegir `low` ($0.02) alinearía precios con Grok pero dejaría a OpenAI
  en su tier mínimo. Imagen 4 standard quedaría POR ENCIMA en calidad y
  sesgaría el rating humano a favor de Gemini sin reflejar la capacidad
  real de OpenAI.
- Elegir **`medium`** ($0.07) alinea calidad con Imagen 4 standard
  (ambos "profesionales"). Grok queda por debajo en calidad pero a
  un tercio del precio — eso **es la conclusión del estudio**, no ruido:
  cada proveedor tiene su sweet spot real en el mercado.

Se elige `medium` porque el estudio mide **calidad percibida** (rating
humano) y **coste-por-llamada**. Dejar a OpenAI en `low` daría imágenes
visiblemente peores que las de Gemini sin reflejar la capacidad del modelo;
sería un sesgo de configuración del benchmark, no del modelo en sí.

### Cambios aplicados

| Cambio | Migración | Implementación |
|---|---|---|
| `OpenAIClient._MODELO_IMAGEN`: `dall-e-3` → `gpt-image-1` | — | `clients/openai_client.py:57` |
| `OpenAIClient._CALIDAD_IMAGEN = "medium"` | — | nueva constante de clase |
| `generar_imagen()`: response handling de `data[0].url` → `data[0].b64_json` (gpt-image-1 devuelve base64, no URL) | — | igual que `editar_imagen()` |
| Tarifa OpenAI: `precio_imagen_generar`: $0.04 → **$0.07**; `precio_imagen_editar`: $0.04 → **$0.07** (mismo modelo gpt-image-1 en ambas rutas) | `o4d5e6f7a8b9` | nueva versión vigente con autor `audit-2026-05-13b` |
| Frontend `MODELOS_POR_PROVEEDOR.openai`: `dall-e-3` / `gpt-image-1` → `gpt-image-1 (medium)` en ambas columnas | — | `pages/DashboardPage.tsx` |

### Justificación de aceptar la divergencia de precio resultante

Tras este cambio, los precios oficiales por imagen quedan:

| Modo | OpenAI | Gemini | Grok | Spread |
|---|---|---|---|---|
| Generar | **$0.07** | $0.04 | $0.02 | 3.5× entre el más caro y el más barato |
| Editar | **$0.07** | $0.039 | $0.05 | 1.8× spread |

El spread más amplio en "Generar" **es información válida del mercado**:
OpenAI cobra premium por mejor calidad (`gpt-image-1 medium`), Gemini se
sitúa en el medio (`imagen-4 standard`) y Grok ofrece la opción más
económica (`grok-imagine-image`). Esto se refleja directamente en la tabla
de tarifas del dashboard y permite al lector del TFG comparar cost/quality
trade-offs entre proveedores con datos reales.

## Referencias

- **Anthropic pricing & caching**: https://www.anthropic.com/pricing,
  https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching
- **OpenAI pricing & cached input**: https://openai.com/api/pricing,
  https://platform.openai.com/docs/guides/prompt-caching
- **Google Gemini pricing & context caching**:
  https://ai.google.dev/pricing, https://ai.google.dev/gemini-api/docs/caching
- **xAI Grok API**: https://x.ai/api (precios estimados; xAI no publica
  caché público oficialmente a la fecha de esta ADR).
- **Gemini 2.5 Flash Image (Nano Banana)**: https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash-image
- **xAI Grok Image Editing**: https://docs.x.ai/developers/model-capabilities/images/editing
- **xAI Grok Imagine Quality Mode**: https://x.ai/news/grok-imagine-quality-mode
- **OpenAI gpt-image-1 quality parameter (community)**: https://community.openai.com/t/gpt-image-1-quality-parameter/1246424
- **Artificial Analysis · Image Models comparison**: https://artificialanalysis.ai/image/models
- **Notes by Lex · "Imagen 4 is faster, but GPT is still the GOAT"**: https://notesbylex.com/imagen-4-is-faster-but-gpt-is-still-the-goat
- ADR-004 — `asyncio.gather` paralelo (motivo por el que batch no aplica).
- ADR-009 — Exportación CSV (ahora ampliado con 5 columnas tarifa).
- ADR-011 — Selección de modelos por tarea (Claude excluido de imagen).
- ADR-016 — Dashboard métricas (consume `cost_usd` agregado, ajeno al detalle).
