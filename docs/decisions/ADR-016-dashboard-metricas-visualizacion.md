# ADR-016: Diseño del dashboard de métricas y visualizaciones

Estado: Aceptado
Fecha: 02/05/2026 — Revisado: 03/05/2026
Sprint: Sprint 3
DEF relacionada: DEF-002-dashboard.md

## Contexto

Con las sesiones de benchmark almacenadas, el sistema necesita una pantalla de
análisis agregado que permita extraer conclusiones comparativas entre los cuatro
LLMs. Las decisiones afectan a tres planos: qué almacenar por respuesta, cómo
agregar los datos, y qué visualizaciones exponer y con qué criterios.

El contexto académico impone dos restricciones adicionales que una herramienta
comercial no tendría: los resultados deben ser honestos (sin destacar un modelo
sobre otro de forma arbitraria) y comprensibles para un tribunal evaluador sin
conocimientos técnicos profundos de LLMs.

## Decisiones tomadas

### 1. Métricas almacenadas por respuesta LLM

Se almacenan las once métricas calculadas en el motor de benchmarking, separadas
en dos grupos según si provienen de la API o del texto de respuesta:

Desde la API (todos los proveedores la devuelven):
- tokens_entrada, tokens_salida (campos distintos por proveedor, normalizados)
- tuvo_error (derivado del status de la llamada)

Calculadas en el backend a partir de tokens + tiempo de llamada:
- latencia_ms, tokens_por_segundo, ratio_sal_ent, coste_usd, coste_por_100_palabras

Calculadas a partir del texto de la respuesta:
- palabras, diversidad_lexica, parrafos

Más a nivel de sesión: similitud_jaccard_media entre todas las respuestas.
Y desde la evaluación del usuario: rating (1-5).

Caso especial imagen generativa: tokens_salida, palabras, diversidad_lexica,
parrafos no aplican. El coste se calcula por imagen (precio fijo),
no por tokens.

### 2. Estrategia de agregación: vistas materializadas en PostgreSQL

Se elige PostgreSQL materialized views (ya justificado en ADR-002) con refresco
síncrono al guardar cada sesión. Dos vistas:

- mv_metricas_modelo_categoria: media de las once métricas agrupadas por
  (modelo, categoria). Tamaño máximo: 4 modelos × 8 categorías = 32 filas.
- mv_sesiones_semana: conteo de sesiones por semana ISO, para la gráfica de
  progreso del estudio.

No se usa job periódico ni Redis. El volumen esperado (centenares de sesiones)
no lo justifica. El refresco síncrono añade latencia negligible al endpoint de
guardado de sesión.

### 3. Librería de gráficos: Chart.js 4.x

Opciones consideradas:
- D3.js: máximo control, excesiva complejidad para el prototipo y la memoria.
- Chart.js 4.x: API declarativa, soporte nativo de scatter, radar, line, bar y
  doughnut; integración en una sola línea CDN; animaciones de entrada incluidas.
  Soporta gráficos mixtos (bar + line en el mismo canvas) y ejes secundarios
  independientes, lo que permite superponer métricas con escalas distintas.
- Recharts/ECharts: sólo si el frontend fuera React ya construido; añade
  dependencia de framework al prototipo HTML standalone.

Se elige Chart.js 4.x. Cubre todos los tipos de gráfica necesarios sin
dependencias adicionales y es la librería más documentada para prototipos
académicos con datos tabulares. Los gráficos sin soporte nativo en Chart.js
(heatmap, matriz Jaccard) se implementan como grids CSS, que resultan más
ligeros y no requieren dependencias adicionales.

### 4. Visualizaciones seleccionadas y su justificación académica

Cada gráfica responde a una pregunta concreta del estudio. Se excluye todo lo
que no responda una pregunta o que pueda sesgar la lectura.

El dashboard se organiza en dos bloques con separador visual explícito:

**Bloque A — Evaluación humana** (métricas que dependen del juicio del evaluador):

| Gráfica | Pregunta respondida | Decisión de diseño |
|---|---|---|
| KPI cards (4) | ¿Cuántos datos hay? ¿Son suficientes? | Siempre visibles; incluye n para contexto |
| Scatter latencia vs coste | ¿Cuál ofrece mejor eficiencia técnica? | Ejes sin truncar en 0; sin ordenar modelos |
| Barras valoración media | ¿Cuál prefieren los evaluadores globalmente? | Eje Y desde 3.0, no desde 0 (evita engaño visual) |
| Heatmap modelo × categoría | ¿En qué tareas destaca cada uno? | Color proporcional; escala desde 3.5 (mínimo realista) |
| Radar perfil técnico | ¿Cómo es el perfil completo de cada modelo? | Todos los ejes normalizados "mayor = mejor"; etiquetas explícitas |
| Línea sesiones/semana | ¿Cómo progresa la recogida de datos? | Útil para defender el volumen de datos en la memoria |
| Donut distribución categorías | ¿Hay sesgo en las categorías evaluadas? | Expone el sesgo en lugar de ocultarlo |
| Barras latencia por categoría | ¿Influye la tarea en la velocidad? | Muestra el caso especial imagen generativa |

**Bloque B — Métricas automáticas** (calculadas sin intervención del evaluador;
añadidas en la revisión del prototipo tras detectar cobertura insuficiente de
métricas objetivas en la primera versión del dashboard):

| Gráfica | Pregunta respondida | Decisión de diseño |
|---|---|---|
| Barras agrupadas tokens entrada/salida | ¿Cuánto genera cada modelo y es proporcional al prompt? | Opacidad diferenciada: prompt semitransparente, respuesta sólida |
| Barras velocidad (tok/s) | ¿Qué modelo procesa texto más rápido intrínsecamente? | Métrica independiente de latencia de red o tamaño de respuesta |
| Barras coste por 100 palabras | ¿Cuál ofrece mejor relación precio/utilidad? | Normaliza el coste bruto por la utilidad generada |
| Combo barras + línea (doble eje) | ¿Los modelos más extensos son también más ricos léxicamente? | Doble eje Y: palabras (izq.) y TTR diversidad léxica (der., línea punteada amarilla) |
| Matriz Jaccard 4×4 (CSS grid) | ¿Los modelos convergen en contenido o aportan perspectivas distintas? | Simétrica; diagonal = 1; color proporcional al solapamiento de bigramas |

### 5. Principios anti-sesgo aplicados

- Los cuatro modelos aparecen siempre en todas las gráficas, en orden consistente
  (Claude, GPT-4o, Gemini, Grok) sin reordenar por rendimiento.
- Todos los gráficos muestran el tamaño muestral (n=X) en una nota al pie o
  en el tooltip para que el lector evalúe la significancia estadística.
- El dashboard incluye una advertencia permanente: "Resultados propios del
  estudio. No extrapolables como benchmark general."
- El radar convierte métricas "menor es mejor" (latencia, coste) a su inverso
  antes de normalizar, con etiqueta "Rapidez" y "Economía" en lugar de
  "Latencia" y "Coste", evitando que el lector inexperto invierta la lectura.
- El heatmap usa una escala de color continua (no discreta) con punto de
  partida en 3.5 (mínimo realista), no en 1.0, para que las diferencias
  entre modelos sean visualmente perceptibles.
- La separación explícita en dos bloques (evaluación humana / métricas
  automáticas) impide que el lector interprete las métricas objetivas con el
  mismo peso epistemológico que las subjetivas, o viceversa.
- La matriz Jaccard muestra la similitud léxica (bigramas), no semántica. Esta
  limitación se documenta explícitamente en la nota al pie del gráfico para
  evitar que se sobreinterprete como "los modelos piensan igual".

## Consecuencias

Positivas:
- El dashboard cubre las dos dimensiones del estudio con 13 visualizaciones
  en dos bloques temáticos diferenciados: 8 de evaluación humana y 5 de
  métricas automáticas objetivas.
- El bloque de métricas automáticas permite defender ante el tribunal la
  rigurosidad técnica del estudio más allá de las valoraciones subjetivas:
  tokens, velocidad de generación, coste normalizado, riqueza léxica y
  similitud entre modelos son métricas reproducibles e independientes del
  evaluador.
- La separación explícita en dos bloques con cabecera de sección evita la
  confusión epistemológica entre métricas objetivas y subjetivas.
- El gráfico combo (barras + línea en doble eje) demuestra el uso avanzado
  de Chart.js 4 y sirve como ejemplo técnico concreto en el capítulo 5 de la
  memoria (implementación del frontend).
- La matriz Jaccard es el argumento cuantitativo para justificar la elección
  de cuatro modelos distintos: si los Jaccard fueran altos, comparar cuatro
  modelos aportaría poca información adicional respecto a usar solo uno.
- Chart.js facilita la exportación a PNG desde el botón nativo del contexto
  del canvas para incluir gráficas en la memoria.

Trade-offs asumidos:
- Las medias pueden ocultar alta varianza. Con n < 10 por celda del heatmap
  los resultados son orientativos. Se mitiga mostrando n en tooltips.
- El radar comprime cinco dimensiones en un polígono cuya área es sensible
  al orden de los ejes. Se acepta porque el objetivo es orientativo, no
  estadísticamente preciso.
- La diversidad léxica (TTR) es sensible a la longitud del texto: respuestas
  más largas tienden a tener TTR más bajo por la repetición estructural.
  Las comparaciones entre modelos son válidas si las longitudes de respuesta
  son similares; si difieren mucho, el TTR no es directamente comparable.
- La similitud Jaccard mide solapamiento de bigramas, no similitud semántica.
  Dos respuestas pueden ser semánticamente equivalentes con Jaccard bajo
  (vocabulario distinto, misma idea) o léxicamente similares con Jaccard
  alto pero semánticamente distintas. Esta limitación está documentada.
- Los datos simulados del prototipo usan valores representativos pero no
  reales. Los valores reales se cargarán cuando el backend esté operativo.

---

## Revisiones y refinamientos posteriores — 03/05/2026

Durante la fase de recogida de datos del estudio (Sprint 4) se realizó una
auditoría sistemática de los mecanismos de agregación tras detectar un sesgo
inicial. La auditoría y sus correcciones quedan documentadas en detalle en
`docs/memoria/chapters/refinamiento_metricas_sesgo.md`. Se resumen aquí las
decisiones de diseño que afectan directamente a este ADR:

### Sesgo inicial detectado: contaminación imagen→texto en métricas automáticas

La versión original del método `medias_por_proveedor()` (repositorio
`LLMResponseRepository`) calculaba promedios de métricas de texto incluyendo
las sesiones de categoría `imagen`. Dado que para sesiones de imagen los campos
`palabras`, `diversidad_lexica`, `tokens_por_segundo` y `parrafos`
se almacenan con valor 0 (no aplican), incluirlas en el promedio
arrastraba las medias hacia abajo de forma artificial. La corrección aplicada fue
añadir un filtro `JOIN BenchmarkEvaluacion WHERE category != 'imagen'` a dicha query
y a `textos_por_evaluacion_y_proveedor()` (usada en el cálculo Jaccard).

### Correcciones derivadas de la auditoría de seguimiento

Tras la corrección inicial se auditaron todos los métodos de agregación del
sistema, encontrando cuatro puntos adicionales que replicaban el mismo patrón
o introducían sesgos relacionados:

1. **`ratings_por_proveedor()`** y **`ranking_medio_por_proveedor()`**
   (repositorio `UserEvaluationRepository`): calculaban medias de valoración
   humana mezclando sesiones de texto e imagen. Dado que la valoración de una
   imagen generada tiene naturaleza distinta a la de una respuesta de texto
   (criterios estéticos vs. criterios de calidad argumentativa), mezclarlas
   distorsionaba el `rating_medio` que aparece en el bloque de métricas de texto
   del dashboard. Corrección: se añadió `JOIN BenchmarkEvaluacion WHERE category !=
   'imagen'` en ambos métodos. Los ratings de imagen permanecen visibles en el
   heatmap por categoría, donde sí tiene sentido mostrarlos de forma aislada.

2. **`evaluaciones_por_categoria()`** (repositorio `BenchmarkEvaluacionRepository`):
   contaba todas las sesiones independientemente de su estado, incluidas las
   fallidas. Si una categoría de prompt tiene mayor tasa de error de API
   (especialmente `imagen`, que depende de tres proveedores con APIs menos
   estables), el donut del dashboard inflaría artificialmente su volumen.
   Corrección: se añadió `WHERE status = 'completada'`.

3. **`evaluaciones_por_semana()`** (mismo repositorio): mismo patrón que el punto
   anterior aplicado al gráfico de evolución temporal. Corrección idéntica.

### Nuevo bloque de dashboard: generación de imagen

Como consecuencia de separar los dominios texto/imagen en la capa de datos, se
añadió al dashboard un tercer bloque "Generación de imágenes" que consolida
las métricas específicas de imagen (latencia y coste por imagen) para los tres
proveedores que soportan generación generativa (OpenAI, Gemini, Grok). Claude no
genera imágenes en este estudio. El bloque solo se renderiza si existen datos de
sesiones de imagen (`metricas_imagen_por_modelo.length > 0`).

El nuevo endpoint del backend expone `metricas_imagen_por_modelo: list[MetricasImagenModelo]`
dentro del mismo DTO `RespuestaStats`, manteniendo la filosofía de "una petición,
todos los datos del dashboard" establecida en este ADR.

### Eliminación de métricas de imagen no diferenciales — 03/05/2026

Durante la recogida de datos se detectó que tres columnas de la tabla
`llm_responses` (`imagen_size_bytes`, `imagen_ancho`, `imagen_alto`) no aportaban
información diferencial entre proveedores y sesgaban la legibilidad del dashboard.
Se eliminaron del modelo de datos, de los esquemas Pydantic y del frontend.

**Motivo de `imagen_size_bytes`:** OpenAI DALL-E 3 y Grok Aurora devuelven una URL
externa pública a la imagen generada; el backend nunca descarga el archivo, por lo
que el tamaño en bytes es 0 para ambos. Gemini Imagen 4 devuelve los bytes en
base64, por lo que sí tendría un valor real. Esta asimetría hace que la columna no
sea comparable entre proveedores: comparar 0 (URL) con ~200 KB (base64) no mide
nada relacionado con la calidad del proveedor; mide el formato de transporte de la
API. Incluir esta métrica en el dashboard introduciría un sesgo sistemático que
favorecería artificialmente a Gemini por tener mayor tamaño (consecuencia del
formato, no de la calidad de la imagen).

**Motivo de `imagen_ancho` e `imagen_alto`:** Los tres proveedores generan imágenes
con resolución 1024×1024 píxeles por defecto, que es la resolución estándar de la
API de generación de imágenes para el nivel de calidad HD. No hay variación
observable entre proveedores, por lo que la columna no discrimina nada y su
presencia en el dashboard crearía la falsa impresión de que las resoluciones
difieren.

**Decisión:** se mantienen únicamente `latencia_ms` y `cost_usd` como métricas
comparativas para el dominio imagen. El coste es uniforme (~0,040 USD por imagen
en todos los proveedores) pero se mantiene como referencia absoluta del gasto por
generación. La latencia sí muestra variación observable entre proveedores y es la
única métrica diferencial del bloque.

**Cambios aplicados en el stack:**
- Migración Alembic `f3a5b7c9d1e2`: `DROP COLUMN` de las tres columnas en PostgreSQL.
- `ResultadoLLM` (dataclass): eliminados los tres campos.
- Clientes LLM (`openai_client.py`, `grok_client.py`, `gemini_client.py`): eliminado
  el cálculo y asignación de estas métricas.
- `LLMResponseRepository.crear_desde_resultado()`: eliminados los parámetros.
- `MetricasImagenModelo` (schema Pydantic y tipo TypeScript): eliminados los campos.
- `DashboardPage.tsx`: bloque imagen reducido a dos columnas (latencia + coste);
  nota aclaratoria sobre por qué no se compara tamaño ni resolución.

### Limitación residual documentada: Jaccard con respuestas monograma

La función `jaccard_bigramas()` devuelve 0.0 cuando alguno de los textos
tiene menos de dos palabras (no es posible construir bigramas). Si una respuesta
de error contiene un único token (ej: "Error"), el índice Jaccard del par se
contabiliza como 0.0 en lugar de ser excluido del promedio. El impacto es mínimo
dado que el filtro `tuvo_error = False` ya excluye la mayoría de estos casos,
pero se documenta como limitación metodológica a mencionar en la memoria.
