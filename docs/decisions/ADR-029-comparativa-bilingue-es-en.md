# ADR-029 — Sub-experimento bilingüe ES vs EN sobre tres categorías controladas

**Fecha:** 14/05/2026
**Estado:** Aceptado
**Sprint:** Sprint 4

---

## Contexto

Toda la plataforma —y por tanto todo el corpus de evaluaciones humanas
recogido a lo largo del estudio— está en castellano. Los cuatro LLMs
comparados (Claude Sonnet 4.6, GPT-4o, Gemini 2.5 Flash y Grok 4.3) están
entrenados con corpus mayoritariamente en inglés. Esto plantea una
limitación metodológica clara: las diferencias observadas en latencia,
tokens, coste o longitud podrían deberse en parte a que los modelos rinden
mejor en su lengua dominante, y no necesariamente a las propiedades
intrínsecas de cada modelo.

Se descartó previamente la opción de internacionalizar la web completa
(`react-i18next`, traducción de KPIs, prompts, dashboard) por desbordar el
alcance del TFG: requería traducir todos los textos de UI, todos los
tooltips, los exportadores y los modales. La conclusión fue que el coste
era muy alto y el beneficio metodológico no estaba alineado con el objetivo
del estudio (que es comparar modelos, no localizar una aplicación).

A cambio, queda viva una pregunta científica relevante: **¿cómo cambian las
métricas técnicas de los cuatro LLMs cuando el mismo prompt se les envía
en castellano y en inglés?** Esta pregunta es:

- **Acotada** — afecta solo a métricas técnicas (latencia, tok/s, coste,
  palabras, diversidad léxica), no a valoración humana.
- **Útil** — convierte una limitación reconocida del estudio en una variable
  explícita que puede analizarse.
- **Reproducible** — bastan prompts predefinidos traducidos profesionalmente
  para que cualquier persona repita el experimento.

## Decisión

Se implementa un sub-experimento controlado dentro del flujo normal de
evaluación, restringido a tres categorías y a sus prompts predefinidos:

- **Razonamiento lógico** (10 acertijos)
- **Escritura creativa** (10 retos de redacción con restricciones)
- **Preguntas concretas** (10 preguntas de conocimiento general)

Cada uno de los 30 prompts predefinidos lleva asociada su traducción al
inglés, validada manualmente, en `OPCIONES_LISTA` del componente
`SubcatPanel`. Cuando el usuario elige una de estas tres categorías y
selecciona un prompt predefinido, la petición POST `/api/v1/benchmarks/run`
incluye ambos textos (`prompt` y `prompt_en`). El backend, al detectar el
campo `prompt_en` y que la categoría está en `CATEGORIAS_BILINGUES`,
lanza **dos rondas paralelas** consecutivas con `asyncio.gather`:

1. Una primera ronda con el prompt en castellano sobre los 4 LLMs.
2. Una segunda ronda con el prompt en inglés sobre los mismos 4 LLMs.

Las 8 respuestas resultantes (4 ES + 4 EN) se persisten en
`llm_responses` con la nueva columna `idioma_prompt` (`'es'` o `'en'`),
todas asociadas a la misma `BenchmarkEvaluacion`. La cuota del usuario se
descuenta una sola vez: el sub-experimento bilingüe no penaliza el límite
diario, porque su coste extra es de Anthropic/OpenAI/Google/xAI y no del
usuario.

### El humano solo valora castellano

El humano solo puntúa y rankea las 4 respuestas en castellano. Las 4
respuestas en inglés se presentan bajo un acordeón colapsable
"Ver respuesta en inglés" dentro de cada tarjeta ES, accesible tanto en
el resultado inmediato como en el `EvalViewModal` del historial. No
participan en el sistema de puntuación con estrellas ni en el drag-and-drop
del ranking de preferencia.

Esta asimetría es deliberada: el objetivo del sub-experimento no es duplicar
la potencia estadística del juicio humano (lo cual implicaría reclutar
evaluadores nativos de inglés), sino aislar el efecto del idioma sobre las
métricas técnicas manteniendo la categoría y el prompt como variables fijas.

### Donde se muestran los datos bilingües

- **Vista de resultados de la evaluación** (`BenchmarkPage`): grid 4 tarjetas
  con la respuesta ES; cada tarjeta tiene un acordeón "Ver respuesta en
  inglés" con la EN.
- **Modal del historial** (`EvalViewModal`): mismo patrón. La vista de
  solo lectura para evaluaciones ya valoradas también incluye el acordeón.
- **Dashboard** (`DashboardPage`): nueva sección
  "Comparativa ES vs EN — métricas técnicas" con cuatro mini-gráficos de
  barras agrupadas (latencia, tok/s, coste, palabras) que renderizan ES y
  EN lado a lado para los cuatro proveedores. Solo aparece cuando la BD
  ya tiene al menos una respuesta `idioma_prompt='en'` persistida.
- **CSV de admin**: nueva columna `idioma_prompt` por fila. Permite que un
  análisis externo en pandas reconstruya el experimento sin joins
  adicionales.

### Aislamiento de las agregaciones existentes

Las medias globales del dashboard (latencia media, tok/s medio, etc.) y el
cálculo de similitud Jaccard agregada se filtran a `idioma_prompt='es'`.
La nueva tarjeta bilingüe es la única que cruza ES y EN, lo cual evita que
las medias del estudio principal se desplacen al introducir el
sub-experimento. En código:

- `LLMResponseRepository.medias_por_proveedor()` añade
  `WHERE idioma_prompt='es'`.
- `LLMResponseRepository.textos_por_evaluacion_y_proveedor()` añade
  `WHERE idioma_prompt='es'`.
- `LLMResponseRepository.medias_comparativa_es_en()` es el método
  específico de la tarjeta bilingüe: devuelve medias por
  `(proveedor, idioma_prompt)` restringido a evaluaciones que tienen al
  menos una respuesta EN (sub-experimento puro).

El Jaccard de cada evaluación individual (`similitud_jaccard_media`
guardado en `benchmark_evaluaciones`) también se calcula solo sobre los
textos ES en `BenchmarkService.ejecutar()` para que el indicador conserve
su significado original.

### Texto libre desactivado

En las tres categorías bilingües, el `<textarea>` del tercer paso queda
forzosamente de solo lectura. El usuario no puede escribir un prompt libre
porque, sin par EN validado, el sub-experimento perdería su control. Esto
está implícito en el contrato de `SubcatPanel`: el `<textarea>` se rellena
exclusivamente desde `elegirSubcat()`, que emite siempre con
`readonly=true`.

## Alternativas consideradas

### Alternativa A — Internacionalización completa de la web

`react-i18next` con traducción de UI, mensajes, exportadores, dashboard,
prompts predefinidos y subcategorías. La aplicación se podría usar en
ambos idiomas y los evaluadores nativos de cada idioma podrían valorar
las respuestas en su lengua materna.

**Descartada** por desproporción coste/alcance. Para el objetivo del TFG
—comparar la calidad técnica y humana de cuatro LLMs— una localización
completa de la herramienta es ortogonal y dispara el tiempo de
implementación.

### Alternativa B — Categoría nueva "Bilingüe"

Crear una octava categoría `bilingue` con su propio panel y prompts. Las
estadísticas del estudio principal quedarían intactas porque la categoría
nueva no tocaría las existentes.

**Descartada** porque introducir una categoría duplicaría la lógica de
flujo y rompería la simetría con las demás (el usuario no tendría una
intuición clara de qué significa "bilingüe" como categoría). La opción
elegida mantiene los nombres familiares y añade un badge dentro de la
caja del panel que avisa visualmente del sub-experimento.

### Alternativa C — Reutilizar la categoría de Traducción

Aprovechar la categoría `traduccion` existente para que los modelos
traduzcan el mismo texto a inglés. Tendría dos ventajas: ya existe el
flujo y la traducción es exactamente el caso de uso de la categoría.

**Descartada** porque el objetivo no es medir calidad de traducción
(eso es categórico de la categoría `traduccion` y ya tiene sus métricas),
sino medir el efecto del idioma del *prompt* sobre las métricas técnicas
de un modelo realizando una tarea no relacionada con traducir.

## Ventaja arquitectónica principal

El sub-experimento bilingüe transforma una limitación metodológica
(corpus en castellano, modelos entrenados en inglés) en una **variable
controlada explícita**. Al mantener la categoría y el prompt constantes
y variar únicamente el idioma, el diseño permite atribución causal directa:
cualquier diferencia en latencia, tok/s, coste o diversidad léxica entre
la ronda ES y la ronda EN es atribuible al idioma del prompt, no a la
tarea. Sin este aislamiento, el efecto del idioma quedaría confundido con
el efecto de la tarea o del proveedor en el análisis de resultados.
Arquitectónicamente, el aislamiento se consigue con un único campo
`idioma_prompt` en `llm_responses` y un filtro `WHERE idioma_prompt='es'`
en todas las agregaciones del estudio principal, garantizando que el
sub-experimento no desplaza ninguna media ni Jaccard existente.

## Consecuencias

### Positivas

- **Atribución causal del efecto idioma**: con categoría y prompt fijos,
  cualquier diferencia de métricas ES vs EN es atribuible al idioma, no
  a la tarea ni al proveedor.
- **Estadísticas del estudio principal inmunes**: el filtro
  `idioma_prompt='es'` garantiza que ninguna media ni Jaccard existente
  se desplaza al añadir las rondas EN.
- **Cero impacto en cuota** de usuarios: una evaluación = una consulta,
  aunque la BD reciba 8 filas.
- **CSV admin autocontenido**: la columna `idioma_prompt` permite
  reproducir el sub-experimento desde pandas sin joins adicionales.

### Negativas

- **Duplicación de coste API** en las tres categorías bilingües: cada
  evaluación realiza 8 llamadas en lugar de 4. El gasto absoluto sigue
  siendo bajo (~0.10 USD por evaluación bilingüe) pero el presupuesto del
  TFG debe contemplarlo.
- **Cuello potencial en latencia**: las dos rondas se ejecutan
  secuencialmente para no saturar las cuotas por minuto de cada API. En
  el peor caso, una evaluación bilingüe tarda ~2× lo que tardaría una
  monolingüe del mismo prompt.
- **Asimetría de potencia estadística entre ES y EN**: las respuestas EN
  no tienen valoración humana, así que cualquier afirmación cualitativa
  ("el modelo X responde mejor en inglés") queda fuera del alcance.
  Solo se pueden afirmar diferencias de métricas técnicas.

## Implementación

### Backend

- Migración Alembic `p5e6f7a8b9c0` añade
  `llm_responses.idioma_prompt VARCHAR(2) NOT NULL DEFAULT 'es'` con
  `CHECK ('es', 'en')` e índice `ix_llm_responses_idioma_prompt`.
- `LLMResponse.idioma_prompt` en el modelo ORM.
- `ResultadoLLM.idioma_prompt` en el dataclass del motor LLM.
- `ejecutar_benchmark(..., idioma_prompt='es')` etiqueta cada resultado.
- `BenchmarkService.CATEGORIAS_BILINGUES = (razonamiento, creativa, concretas)`.
- `BenchmarkService.ejecutar(..., prompt_en=None)` detecta el sub-experimento
  y lanza dos rondas; el Jaccard de la evaluación se calcula solo sobre
  textos ES.
- `LLMResponseRepository.medias_comparativa_es_en()` y filtros ES en
  `medias_por_proveedor()` y `textos_por_evaluacion_y_proveedor()`.
- `StatsService` propaga la nueva lista al DTO `RespuestaStats`.
- `AdminExportService` añade `idioma_prompt` al CSV.

### Frontend

- `OPCIONES_LISTA` en `SubcatPanel` extendido con `label_en` y `prompt_en`
  opcionales; las tres categorías bilingües llevan los 30 pares
  validados. Se exporta el helper `esCategoriaBilingue`.
- Badge "🌐 Comparación ES / EN" en la cabecera de `SubcatPanel` para
  estas categorías.
- `BenchmarkPage` añade el estado `promptEn`, lo envía al backend en la
  mutación y muestra una doble caja de prompt antes de lanzar.
- `BenchmarkCard` acepta `respuestaEn` opcional y la renderiza bajo
  el acordeón "Ver respuesta en inglés".
- `EvalViewModal` aplica el mismo patrón en el formulario y la vista de
  solo lectura.
- `DashboardPage` añade la sección "Comparativa ES vs EN — métricas
  técnicas" con cuatro gráficos de barras agrupadas, oculta cuando no
  hay datos bilingües.

## Referencias

- Migración `p5e6f7a8b9c0_idioma_prompt_comparativa.py`.
- ADR-013 — Prompts predefinidos bloqueados (la lista de los 30 prompts
  ES se traduce 1-a-1 manteniendo la idea sin alterar la dificultad).
- ADR-016 — Dashboard métricas y visualización (la nueva tarjeta sigue el
  mismo patrón de barras agrupadas con etiqueta ★ por categoría).
- ADR-028 — Tarifas versionadas (el coste de las respuestas EN respeta la
  misma `tarifa_id` vigente: no hay tarifa especial por idioma).
