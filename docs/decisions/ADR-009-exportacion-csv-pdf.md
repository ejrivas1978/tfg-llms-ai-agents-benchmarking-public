# ADR-009: Exportación de resultados en CSV (backend) y PDF (frontend)

Estado: Aceptado y reactivado tras reunión 09/05/2026
Fecha: 01/02/2026 (revisión 09/05/2026)
Sprint: Sprint 2 (revisión Sprint 4)

## Contexto

Los resultados del estudio deben poder exportarse para dos usos distintos:

- **Análisis estadístico**: el alumno necesita abrir los datos en Excel
  o Google Sheets para calcular medias, desviaciones típicas y construir
  tablas para la memoria del TFG.
- **Ilustración de la memoria**: las gráficas del dashboard deben poder
  incluirse en el documento LaTeX como imágenes de alta calidad.

Estos dos casos de uso tienen requisitos técnicos opuestos: el análisis
estadístico necesita datos estructurados (CSV), y la ilustración necesita
capturar la visualización tal como aparece en pantalla (PDF o PNG).

## Opciones consideradas

### 1. Todo en el backend (CSV + PDF server-side)

Ventajas: control total del formato, sin dependencias JavaScript.

Desventajas: generar el PDF en el servidor requiere reimplementar el
renderizado de las gráficas Chart.js en Python (con matplotlib u otra
librería), lo que duplica la lógica de visualización y produce gráficas
con estilos distintos a los del dashboard. La coherencia visual entre
el dashboard y las figuras de la memoria quedaría comprometida.

### 2. Todo en el frontend (CSV + PDF client-side)

Ventajas: sin endpoints adicionales en el backend.

Desventajas: generar el CSV en JavaScript con columnas correctamente
escapadas, encoding UTF-8 con BOM para Excel, y números decimales con
coma (notación española) requiere código no trivial. El módulo `csv`
de Python hace todo esto de forma nativa y fiable.

### 3. CSV en backend, PDF en frontend (elegida)

CSV en el backend con el módulo estándar `csv` de Python:
- Sin dependencias adicionales.
- Encoding UTF-8 con BOM (necesario para Excel en Windows).
- Separador configurable (coma o punto y coma según la configuración
  regional del sistema del alumno).
- Formato decimal consistente independientemente del navegador.

PDF en el frontend con `jspdf` + `html2canvas`:
- `html2canvas` captura el DOM del dashboard tal como lo renderiza
  el navegador, incluyendo las gráficas Chart.js con sus colores,
  animaciones ya resueltas y tipografía.
- `jspdf` inserta el canvas como imagen en el PDF con márgenes y
  metadatos configurables.
- El resultado es idéntico a lo que el tribunal verá en la demo,
  garantizando coherencia entre la figura de la memoria y la
  aplicación en vivo.

## Decisión tomada

Se elige la estrategia híbrida: CSV desde el backend vía endpoint
`GET /api/v1/export/csv`, PDF generado en el frontend desde el
botón "Exportar PDF" del dashboard.

## Consecuencias

Positivas:
- El CSV puede generarse con todas las columnas de métricas sin
  depender de lo que el navegador pueda calcular; el backend tiene
  acceso directo a la base de datos.
- El PDF captura exactamente el estado visual del dashboard en el
  momento de exportar: incluye filtros activos, tooltips visibles
  y el tema oscuro del prototipo.
- Cada mecanismo usa la herramienta más adecuada para su caso:
  Python para datos estructurados, JavaScript para captura de UI.

Trade-offs asumidos:
- `html2canvas` tiene limitaciones conocidas con fuentes personalizadas
  cargadas via CDN: puede renderizarlas como fallback de sistema. Se
  mitiga especificando explícitamente las fuentes en el CSS del canvas
  con `font-display: block` y pre-cargando la fuente Inter antes de
  la captura.
- El PDF generado en el navegador no es vectorial: es una imagen
  rasterizada. Para LaTeX se recomienda exportar las gráficas
  individuales como PNG desde el menú contextual nativo del canvas
  de Chart.js (clic derecho → "Guardar imagen"), que sí produce
  imágenes de mayor resolución que html2canvas.
- La exportación CSV no incluye los textos completos de las respuestas
  LLM por defecto (limitaría la legibilidad del fichero). Se exportan
  las métricas numéricas y los primeros 200 caracteres de cada
  respuesta. El acceso a respuestas completas es via historial.

## Revisión 09/05/2026 — reactivación post-reunión

S4-10 (export CSV) se había marcado como descartado. En la reunión del
09/05/2026 con el responsable del TFG se reactiva con un alcance
distinto y más estricto:

### Alcance final

- **Solo administrador**: el botón aparece en `TablaAdmin` (no en el
  dashboard público) y el endpoint exige JWT de admin. Los usuarios
  web nunca pueden exportar.
- **Endpoint final**: `GET /api/v1/admin/evaluaciones/exportar-csv`
  (no `/api/v1/export/csv` como contemplaba la versión original;
  se reubica bajo `/admin` para coherencia con el resto de
  endpoints administrativos).
- **Respeta los filtros de la tabla**: el botón pasa los mismos
  parámetros `nick`, `categoria`, `prompt`, `estado`, `valoracion`,
  `fecha_desde` y `fecha_hasta` que el listado paginado, de modo que
  el admin descarga exactamente lo que ve filtrado.
- **Sin textos largos**: por requisito explícito del responsable, ni
  el prompt ni el `response_text` aparecen en el CSV. Distorsionan
  la lectura en Excel y el análisis estadístico no los necesita.
  Esto sustituye el "primeros 200 caracteres" de la decisión original.
- **Granularidad tidy/largo**: una fila por LLMResponse (estándar
  académico para pandas/R); los datos de la BenchmarkEvaluacion
  padre se denormalizan en cada fila para que el CSV sea
  autocontenido.
- **Subcategoría**: como la BD no la persiste (ADR-014), se incluye
  una columna derivada `tipo_imagen` (`generar` / `describir`) solo
  para `categoria=imagen`. El resto de categorías llevan ese campo
  vacío.

### Columnas finales del CSV (en orden)

1. `evaluacion_id`
2. `nickname` — usuario que ejecutó la evaluación
3. `fecha_creacion` (ISO 8601 UTC)
4. `fecha_completado` (ISO 8601 UTC, vacío si no completada)
5. `categoria` — enum TestCategory (razonamiento, codigo, ...)
6. `subcategoria` — etiqueta human-readable del prompt seleccionado
   (ver migración `e4f5a6b7c8d9` y nota a ADR-014). Para predefinidos
   "N. Etiqueta" (ej. `2. Efecto Doppler`); para traducción el idioma
   sin emoji (`Inglés`); para resumen la opción (`Resumen en 20 palabras`);
   para imagen la opción (`generar`/`describir`/`logotipo`/`modificar`);
   para texto libre siempre `Texto Libre`. Nullable para evaluaciones
   anteriores a la migración.
7. `tipo_imagen` — `generar` / `describir` / vacío
8. `estado` — completada / pendiente / en_curso / fallida
8. `similitud_jaccard_media` — `0.000000` o vacío
9. `proveedor` — claude / openai / gemini / grok
10. `modelo`
11. `tuvo_error` — `true` / `false`
12. `error_message`
13. `input_tokens`
14. `output_tokens`
15. `latencia_ms`
16. `tokens_por_segundo`
17. `ratio_sal_ent`
18. `coste_usd`
19. `coste_por_100_palabras`
20. `palabras`
21. `diversidad_lexica`
22. `parrafos`
23. `valoracion_estado` — `valorada` / `pendiente` / `no_aplica`.
    `no_aplica` cuando `tuvo_error=true` (no hay nada que valorar);
    `pendiente` cuando el LLM respondió pero el humano no la valoró aún;
    `valorada` cuando existe una `UserEvaluation` enlazada.
24. `evaluador_nickname` — quien valoró (puede coincidir o no con `nickname`)
25. `rating` — 0–5 o vacío
26. `rango_preferencia` — 1–N o vacío
27. `fecha_evaluacion` — ISO 8601 UTC o vacío

Codificación UTF-8 con BOM (`\\ufeff`) al inicio para que Excel en
Windows interprete correctamente los acentos sin pasos manuales.
`StreamingResponse` de FastAPI con `csv.writer` estándar para evitar
materializar todo el fichero en memoria antes de enviarlo.
