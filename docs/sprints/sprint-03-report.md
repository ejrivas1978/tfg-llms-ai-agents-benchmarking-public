# Sprint 3 — Reporte de cierre
Periodo: 01/03/2026 - 30/04/2026
Cierre real: 04/05/2026

---

## Objetivo del sprint

El prototipo funcional del frontend está terminado y validado, con las
pantallas de Historial y Dashboard completamente especificadas. Las
decisiones de diseño de interfaz están documentadas con sus justificaciones
y vinculadas a los requisitos funcionales del TFG.

---

## Items completados

| ID    | Tarea                                                      | Puntos | Estado     |
|-------|------------------------------------------------------------|--------|------------|
| S3-01 | Prototipo HTML standalone con tema gótico oscuro           | 5      | Completado |
| S3-02 | Pantalla Benchmark: categorías, subcategorías, prompt      | 5      | Completado |
| S3-03 | Pantalla Evaluación: tarjetas LLM, ranking, rating         | 5      | Completado |
| S3-04 | Pantalla Historial: tabla filtrada, vista usuario          | 5      | Completado |
| S3-05 | Vista administrador: CRUD, paginación, borrado por lotes   | 5      | Completado |
| S3-06 | Filtros tipo Excel: fecha, usuario, categoría, modelos     | 5      | Completado |
| S3-07 | Datepicker personalizado con selector de hora              | 3      | Completado |
| S3-08 | Sticky scroll: fila filtros encima de la cabecera          | 2      | Completado |
| S3-09 | Pantalla Dashboard: KPI cards + 8 gráficos evaluación      | 8      | Completado |
| S3-10 | Bloque métricas automáticas: 5 gráficos objetivos          | 8      | Completado |
| S3-11 | Matriz de similitud Jaccard entre modelos (CSS grid)       | 3      | Completado |
| S3-12 | ADR-015 (Historial por rol) documentado                    | 1      | Completado |
| S3-13 | ADR-016 (Dashboard métricas) documentado                   | 2      | Completado |
| S3-14 | DEF-001 (Historial) con 6 acuerdos y 3 iteraciones         | 2      | Completado |
| S3-15 | DEF-002 (Dashboard) con 7 acuerdos funcionales             | 2      | Completado |
| S3-22 | Subcategoría "Mapa mental" con render Mermaid en tarjeta                | 3 | Completado |
| S3-23 | Sustitución "Imagen similar" → "Logotipo" en categoría imagen           | 1 | Completado |
| S3-24 | Iconos SVG de cada LLM en ranking, evaluación y chips de modelos        | 2 | Completado |
| S3-25 | Eliminar gráfico "Progreso: evaluaciones por semana" del Dashboard      | 1 | Completado |
| S3-26 | Tratamiento visual de censura en BenchmarkCard y EvalCard               | 3 | Completado |
| S3-27 | Estado "todos los modelos censurados": flujo sin puntuación             | 5 | Completado |
| S3-28 | Bug: ocultar fila "Coste" en tabla de métricas de imagen generativa    | 1 | Completado |
| S3-29 | UX: botón "Intentar con otro prompt" tras censura en imagen generativa | 2 | Completado |
| S3-30 | Bug: restaurar subcategoría imagen al volver del resultado             | 3 | Completado |
| S3-31 | Fix: botón "Limpiar" reinicia categoría y subcategoría seleccionadas   | 1 | Completado |
| S3-32 | UI: carga de imagen de referencia en subcategoría "Modificar imagen"   | 3 | Completado |
| S3-33 | Fix TablaAdmin: truncado de prompt + botón ✕ siempre visible            | 1 | Completado |
| S3-34 | Fix TablaAdmin: columna Acciones alineada a la izquierda                | 1 | Completado |
| S3-35 | TablaAdmin: badge de categoría con color por tipo (igual historial)     | 2 | Completado |
| S3-36 | Alineación colores de categoría entre BenchmarkPage, Historial y Admin (imagen → #F87171) | 1 | Completado |
| S3-37 | EvalViewModal: lightbox de imagen con zoom igual que BenchmarkCard      | 3 | Completado |
| S3-38 | DetalleComparativaModal: render mapa mental + lightbox imagen           | 3 | Completado |
| S3-39 | Refactor: extracción de componentes compartidos y utilidades comunes    | 5 | Completado |
| S3-40 | Rename: MermaidDiagram.tsx → MapaMentalDiagram.tsx                     | 1 | Completado |
| S3-41 | Rename: referencias "Mermaid" → "MapaMental" en todo el codebase       | 1 | Completado |
| S3-42 | Fix: fallback a imagen_miniatura cuando url_imagen de DALL-E/Grok caduca | 2 | Completado |
| S3-43 | Aumentar resolución miniatura de imagen 200 → 512 px                   | 1 | Completado |
| S3-44 | Fix: zoom en VisorImagen funciona correctamente con imagen en fallback  | 2 | Completado |

### Detalle de S3-22 — Subcategoría "Mapa mental" con render Mermaid

La subcategoría "Diagrama ASCII" de la categoría resumen se reemplazó por "Mapa mental"
porque su output era visualmente indistinguible del "Esquema jerárquico" existente.

**Implementación:**

- El prompt instruye al LLM a responder **únicamente** con un bloque ` ```mermaid ` de
  tipo `mindmap`, con el tema central como nodo raíz y ramas/subramas anidadas.
- `BenchmarkCard` detecta si `texto_respuesta` contiene ` ```mermaid ` mediante regex.
  Si lo detecta, renderiza `MermaidDiagram` en lugar del bloque de texto plano.
- `MermaidDiagram.tsx` usa la API asíncrona `mermaid.render()` de Mermaid v11 con tema
  `dark` para integrarse con el estilo visual del benchmark. Si la sintaxis que genera
  el modelo es incorrecta, muestra un mensaje de error explicativo en lugar de fallar.
- La dependencia `mermaid@^11.14.0` se añadió a `package.json` (frontend). No hay
  cambios en el backend: el diagrama se construye íntegramente en el cliente.

**Dependencia añadida:**

```
frontend/package.json  →  "mermaid": "^11.14.0"
```

### Detalle de S3-23 — Sustitución "Imagen similar" → "Logotipo"

La subcategoría "Imagen similar" de la categoría imagen se reemplazó por "Logotipo"
porque su comportamiento era funcionalmente idéntico al de "Generar imagen": ambas
reciben una descripción textual y activan la misma ruta `generar_imagen()` en el
backend. El único diferenciador era un prefijo de prompt que los modelos ignoraban en
favor de la descripción literal del usuario, por lo que la opción no aportaba ninguna
dimensión diferencial al benchmark.

"Logotipo" activa un modo de generación cualitativamente distinto — composición gráfica
minimalista, equilibrio figura-fondo, coherencia con el brief — que produce resultados
claramente comparables entre modelos y evaluables con criterios concretos. Además
corresponde a uno de los casos de uso reales más frecuentes de la IA generativa, lo que
refuerza la relevancia del benchmark ante el tribunal.

**Implementación:** cambio exclusivamente de presentación y prompt; el backend trata
`subcat_imagen = 'logotipo'` exactamente igual que trataba `'similar'` (ruta de
generación estándar). El argumentario completo está en ADR-022, sección "Revisión
posterior".

### Detalle de S3-24 — Iconos SVG de cada LLM en ranking, evaluación y chips

Todos los puntos de la interfaz que identifican un proveedor LLM (chips de
modelos, tarjetas de evaluación, ranking de preferencia, vista de solo lectura)
mostraban únicamente el nombre en texto coloreado.

Se añadieron cuatro ficheros SVG en `frontend/src/utils/` (uno por proveedor)
y un módulo `llmIcons.ts` que los exporta indexados por `LLMProvider`:

```typescript
// frontend/src/utils/llmIcons.ts
export const LLM_ICONS: Record<string, string> = { claude, openai, gemini, grok }
```

Los iconos se integraron en:
- `BenchmarkPage` — chips de "Modelos que participan" y fichas del ranking DnD (`RankingChip`)
- `EvalCard` — cabecera de cada tarjeta de evaluación
- `EvaluationPage` — vista de formulario y vista de solo lectura

Vite importa los SVG como URL string; la declaración de tipos la cubre
`vite/client` sin necesidad de módulos adicionales.

---

### Detalle de S3-25 — Eliminar gráfico "Progreso: evaluaciones por semana"

El gráfico `GraficoTimeline` del Dashboard mostraba el número de evaluaciones
agrupadas por semana. Tras el análisis funcional se descartó porque:

- El volumen de datos del estudio (≈ 50–100 sesiones) es demasiado reducido
  para que una distribución temporal tenga valor analítico.
- La información queda cubierta por los KPI cards (total evaluaciones,
  evaluaciones con puntuación).

**Cambio en `DashboardPage.tsx`:** se eliminó la función `GraficoTimeline` y su
bloque `<TarjetaGrafico>`. El grid pasó de `lg:grid-cols-3` a `lg:grid-cols-2`.
Se eliminó la importación de `LineChart` (no se usa en ningún otro lugar), pero
se conservó `Line` que sigue siendo necesario en `GraficoLongitudDiversidad`
(dentro de un `ComposedChart`).

---

### Detalle de S3-26 — Tratamiento visual de censura en BenchmarkCard y EvalCard

Cuando un modelo rechaza un prompt por política de seguridad la API devuelve
un error con `tuvo_error=true` y un `mensaje_error` que incluye vocabulario
específico del proveedor (`content_policy_violation`, `politicas de seguridad`,
`filtros de seguridad`, `safety system`, `content moderation`).

El comportamiento anterior mostraba ese texto crudo en pantalla. Se introdujo
la función `esCensura()` en todos los componentes de evaluación para detectar
el patrón y renderizar un bloque visual unificado:

- **`BenchmarkCard`**: bloque centrado con 🚫 grande, título "Política de
  seguridad" en rojo y texto explicativo neutro.
- **`EvalCard`**: en la sección de puntuación, en lugar de `StarRating` muestra
  un badge `"🚫 Rechazado por política de seguridad — 0 estrellas asignadas
  automáticamente"`.
- **`EvaluationPage`** y **`BenchmarkPage`**: cajitas de valoración inline
  muestran el mismo badge; se añade un banner informativo en rojo cuando al
  menos un modelo fue censurado.

La función `esCensura()` es idéntica en los cuatro componentes:

```typescript
function esCensura(msg: string | null | undefined): boolean {
  if (!msg) return false
  const m = msg.toLowerCase()
  return m.includes('content_policy') || m.includes('politicas de seguridad') ||
         m.includes('filtros de seguridad') || m.includes('safety system') ||
         m.includes('content moderation')
}
```

El schema backend `rating: int = Field(..., ge=0, le=5)` se amplió de `ge=1`
a `ge=0` para permitir guardar 0 estrellas en modelos censurados.

Decisión de diseño y argumentario académico: **ADR-023**.

---

### Detalle de S3-28 — Bug: ocultar fila "Coste" en evaluaciones de imagen generativa

En la tabla de comparación automática de métricas de `BenchmarkPage`, la fila "Coste"
mostraba `$0.04000` para todos los proveedores de imagen generativa, ya que el coste
es una tarifa fija igual para los tres (OpenAI, Gemini, Grok). Una métrica igual para
todos los participantes no tiene ningún poder discriminativo y confunde al usuario.

**Solución:** se añadió el flag `soloTexto: true` a la entrada de "Coste" en el array
`METRICAS_AUTO` de `BenchmarkPage.tsx`. El render de la tabla filtra las filas con ese
flag cuando `es_imagen=true`:

```typescript
{ label: 'Coste', fn: (r) => r.cost_usd, fmt: (v) => `${v.toFixed(5)}`, mejor: 'min', soloTexto: true },
```

El filtro `METRICAS_AUTO.filter(m => !m.soloTexto || !esImagen)` elimina la fila para
evaluaciones de imagen y la mantiene para texto, donde sí discrimina entre proveedores.

---

### Detalle de S3-29 — UX: botón de reintento tras censura en imagen generativa

Cuando una evaluación de imagen generativa termina en estado `fallida` (censura de
política de seguridad), el botón inferior mostraba siempre "Cerrar y volver al menú →"
que navegaba al historial. Para subcategorías de imagen generativa, el uso habitual
es reformular el prompt y reintentar, no abandonar el flujo.

**Solución:** el botón adapta su comportamiento según la subcategoría activa:

- **`generar`, `logotipo`, `modificar`** → label "Intentar con otro prompt →"; al pulsar,
  en lugar de navegar llama a `setEvaluacion(null)`, `setPrompt('')` y `setVista('formulario')`,
  volviendo al formulario sin salir de `/benchmark`.
- **Resto de subcategorías** → label "Cerrar y volver al menú →"; al pulsar navega a `/historial`.

Se usó `setVista('formulario')` en lugar de `navigate('/benchmark')` porque React Router
ignora la navegación cuando la ruta destino es la ruta activa.

---

### Detalle de S3-30 — Bug: subcategoría imagen no se restauraba al volver del resultado

Cuando el usuario pulsaba "Intentar con otro prompt →" y `SubcatPanel` volvía a montarse
(porque `vista === 'formulario'` reactiva el panel), el estado interno `opImagen` se
inicializaba a `null` en lugar de la subcategoría que tenía al ejecutar el benchmark.

**Primera iteración (descartada):** se usó un ref booleano `esRestauracion` para evitar
el reset del efecto de categoría. Fallaba con React StrictMode: el efecto se ejecuta dos
veces en montaje; en la segunda ejecución el ref ya era `false` y el reset borraba la
subcategoría restaurada.

**Solución definitiva — patrón `prevCategoria`:**

```typescript
const prevCategoria = useRef<TestCategory>(categoria)

useEffect(() => {
  const cambio = prevCategoria.current !== categoria
  prevCategoria.current = categoria
  if (!cambio) return  // montaje inicial (y doble-montaje StrictMode): no resetear
  setSubcatIdx(null)
  setOpImagen(null)
  // ... resto del reset
}, [categoria])
```

El efecto compara el valor anterior con el actual. En el montaje y en el doble-montaje de
StrictMode ambos son iguales, por lo que `cambio = false` y el reset no se ejecuta.
Solo cuando la categoría cambia de verdad (diferente valor) el reset se dispara.

La prop `opImagenInicial` pasa el valor de `subcatImagen` al remontarse `SubcatPanel`,
que lo usa como valor inicial de `useState`:

```typescript
const [opImagen, setOpImagen] = useState<string | null>(opImagenInicial ?? null)
```

Y un efecto de montaje sincroniza los callbacks del padre:

```typescript
useEffect(() => {
  if (!opImagenInicial) return
  onInactivar?.(opImagenInicial === 'describir' ? [] : ['claude'])
  onSubcatImagenChange?.(opImagenInicial)
}, [])
```

---

### Detalle de S3-31 — Botón "Limpiar" reinicia categoría y subcategoría

El botón "Limpiar" del formulario de benchmark solo llamaba a `setPrompt('')`, limpiando
únicamente el texto del prompt. La categoría y subcategoría seleccionadas permanecían
activas, lo que resultaba confuso si el usuario quería empezar un benchmark diferente.

**Solución:** `onClick` pasa a llamar a `cambiarCategoria('libre')`, que ya centraliza el
reset completo: `categoria → 'libre'`, `prompt → ''`, `imagenBase64 → null`, `subcatImagen → null`,
`modelosInactivos → []` y `modelosSinSoporte → []`. El `key={categoria}` del `SubcatPanel`
fuerza su remontaje, limpiando también los estados internos del panel.

---

### Detalle de S3-32 — UI: carga de imagen de referencia en "Modificar imagen"

La subcategoría "Modificar imagen" de `SubcatPanel` solo mostraba un textarea para la
instrucción de modificación, sin ningún mecanismo para subir la imagen a modificar.

**Solución:** se añadió al subpanel de `modificar` el mismo flujo de carga de imagen
de referencia que ya tenía "Describir imagen":

- Botón "Subir imagen a modificar" que activa un `<input type="file" accept=".jpg,.jpeg,.png">` oculto.
- Nuevo handler `manejarImagenModificar()`: valida formato (JPG/PNG) y límite (5 MB),
  lee el fichero con `FileReader`, guarda base64 y MIME type en el estado compartido
  `imagenDescribirNombre` / `imagenDescribirPreview` y llama a `onImagenChange(b64, mimeType)`.
  A diferencia de `manejarImagenDescribir()`, no auto-asigna el prompt —el usuario escribe
  la instrucción de modificación manualmente en el textarea inferior.
- Preview thumbnail 56×56 px con nombre del fichero y etiqueta "Lista para modificar".
- Mensajes de error en rojo para formato o tamaño inválidos.

El `input` reutiliza `imagenDescribirRef` —al ser bloques mutuamente excluyentes
(solo uno de los dos subpaneles está en el DOM), no existe conflicto de referencia.

---

### Detalle de S3-27 — Estado "todos los modelos censurados": flujo sin puntuación

Cuando el prompt contiene contenido vetado por las políticas de todos los modelos
participantes (caso frecuente en la categoría imagen con prompts de contenido
explícito), no existe ninguna respuesta evaluable. El flujo normal —puntuar con
estrellas + ordenar ranking— queda sin sentido.

**Detección:** `todasCensuradas` es `true` cuando todas las respuestas activas
tienen `tuvo_error === true`.

**Cambios en `BenchmarkPage.tsx`:**

- El banner informativo pasa de "Valora los que sí respondieron" a "Todos los
  modelos rechazaron el prompt. No es posible evaluación humana."
- La sección de ranking DnD se oculta completamente (no hay fichas que ordenar).
- Los avisos de validación (estrellas pendientes, ranking sin ordenar) no
  aparecen.
- El botón cambia de `"Guardar evaluación"` a `"Cerrar — sin puntuación"` y
  queda **habilitado** sin requisito de estrellas ni ranking.
- Tras guardar, el mensaje de confirmación es `"🚫 Registrada sin puntuación —
  todos los modelos bloqueados por política de seguridad"`.

**Cambios en `EvaluationPage.tsx`:**

- Misma lógica de detección `todasCensuradas`.
- Mensaje informativo en el pie: "Se registrará sin puntuación".
- Botón `"Cerrar — sin puntuación"` habilitado.
- Vista de solo lectura (sesión ya evaluada): si todas las evaluaciones tienen
  `rating=0` y `rango_preferencia=null`, muestra banner rojo en lugar del
  verde habitual y lista los modelos con su icono sin numeración de ranking.

La evaluación se guarda correctamente en la base de datos (`rating=0`,
`rango_preferencia=null` para todos), lo que permite incluirla en métricas
de rechazo de contenido del análisis cuantitativo.

---

### Detalle de S3-33 / S3-34 — Fix columna Prompt y alineación Acciones en TablaAdmin

Al añadir horas a la fecha (formato `DD-MM-YYYY HH:MM:SS`) la columna Fecha ganó anchura
y en pantallas estrechas el botón ✕ de borrado quedaba fuera del viewport.

**S3-33 — Truncado de la columna Prompt:**
El patrón habitual `max-w-xs` en `<td>` no funciona en tablas porque las celdas no
calculan su ancho desde el elemento sino desde el `<col>`. Solución: `w-48` en `<th>`
para fijar anchura + `max-w-0 truncate` en `<td>` para activar truncado con ellipsis.

```tsx
<th className="px-3 py-3 text-left w-48">Prompt</th>
<td className="px-3 py-3 text-xs text-muted max-w-0 truncate">{s.prompt}</td>
```

**S3-34 — Alineación izquierda en Acciones:**
La columna Acciones usaba `justify-center`. Se cambió a `justify-start` para alinear
el contenido a la izquierda igual que el resto de columnas de texto.

---

### Detalle de S3-35 / S3-36 — Badges de categoría con colores alineados

**S3-35:** La tabla de admin mostraba la categoría como texto plano. Se añadió el mismo
badge con borde coloreado que ya existía en el historial de usuario:

```tsx
<span style={{
  color:      COLOR_CAT[s.categoria],
  background: `${COLOR_CAT[s.categoria]}20`,
  border:     `1px solid ${COLOR_CAT[s.categoria]}40`,
}}>
  {s.categoria}
</span>
```

**S3-36:** Los colores no eran consistentes entre los tres puntos de la UI que muestran
categorías (BenchmarkPage, HistorialPage, TablaAdmin). Se unificó el mapa `COLOR_CAT`
en los tres ficheros con los mismos valores hexadecimales. La categoría `imagen` se
cambió de naranja (`#FF8C42`) a rojo suave (`#F87171`) para diferenciarse visualmente
de `resumen` (`#818CF8`), que era demasiado similar en tono al anterior naranja.

---

### Detalle de S3-37 — Lightbox de imagen con zoom en EvalViewModal

La vista de evaluaciones pendientes (`EvalViewModal`) mostraba las imágenes generativas
en miniatura fija sin posibilidad de ampliarlas. `BenchmarkCard` ya tenía un lightbox
completo con zoom y descarga.

Se igualó el comportamiento:
- Un clic en la miniatura o en el botón `BtnAmpliar` abre `VisorImagen` (portal).
- Dentro del visor: un clic hace zoom ×2, segundo clic vuelve a escala natural,
  doble clic cierra, clic fuera cierra.
- La fuente de imagen es `url_imagen` (full resolution); la miniatura del thumbnail
  usa `imagen_miniatura` (base64). Antes ambas usaban `imagen_miniatura`.

---

### Detalle de S3-38 — DetalleComparativaModal: render mapa mental + lightbox imagen

La opción "Ver" del admin abría un modal que mostraba los mapas mentales como texto
crudo (el bloque ````mermaid...```) y las imágenes sin posibilidad de ampliar.

Se añadió el mismo comportamiento que existe en `BenchmarkCard` y `EvalViewModal`:
- Las respuestas con diagrama detectan el bloque con `extraerMapaMental()` y renderizan
  `MapaMentalDiagram`. Doble clic o `BtnAmpliar` abren `VisorMapaMental` con zoom/drag.
- Las imágenes muestran miniatura + `BtnAmpliar` que abre `VisorImagen`.
- Estados locales `visorSrc`, `svgMap` y `mapaMentalSvg` gestionan los lightbox.

---

### Detalle de S3-39 — Refactor: componentes compartidos y utilidades comunes

`BenchmarkCard`, `EvalViewModal` y `DetalleComparativaModal` contenían ~210 líneas de
código duplicado para lightbox de imagen, lightbox de mapa mental y utilidades de
análisis de contenido. Se extrajo a cuatro artefactos reutilizables:

**`frontend/src/components/shared/BtnAmpliar.tsx`**
Botón "⤢ Ampliar" con borde blanco brillante y sombra púrpura al hacer hover.
Props: `children: React.ReactNode`, `onClick: () => void`.

**`frontend/src/components/shared/VisorImagen.tsx`**
Lightbox para imágenes generativas. Estado interno `zoom: boolean`.
- Un clic: activa zoom ×2.
- Doble clic: cierra.
- Clic fuera del área de imagen: cierra.
- Prop `onDescargar` opcional (solo visible en BenchmarkCard).

**`frontend/src/components/shared/VisorMapaMental.tsx`**
Lightbox para diagramas de mapa mental. Gestiona internamente zoom continuo (rueda
del ratón o botones ⊕/⊖/Reset) y arrastre con `useRef` + eventos `onMouseDown/Move/Up`.
Preprocesa el SVG recibido eliminando `width`/`height` fijos para que escale al 100%
del contenedor. Prop `onDescargar` opcional.

**`frontend/src/utils/contenidoLLM.ts`**
Funciones de análisis de texto de respuestas LLM:

```typescript
export function esCensura(msg: string | null | undefined): boolean
export function extraerMapaMental(texto: string | null | undefined): string | null
```

`extraerMapaMental` detecta bloques ````mermaid` en el texto de la respuesta y devuelve
el contenido del bloque o `null` si no hay diagrama.

---

### Detalle de S3-40 / S3-41 — Rename Mermaid → MapaMental

**S3-40:** El fichero `MermaidDiagram.tsx` se renombró a `MapaMentalDiagram.tsx` y la
función exportada de `MermaidDiagram` a `MapaMentalDiagram`. El nombre anterior exponía
un detalle de implementación (la librería subyacente) que no es relevante para los
consumidores del componente.

**S3-41:** Se actualizaron sistemáticamente todas las referencias del codebase:

| Antes | Después |
|---|---|
| `MentalMapaDiagram` (nombre intermedio) | `MapaMentalDiagram` |
| `VisorMentalMapa` | `VisorMapaMental` |
| `extraerMentalMapa()` | `extraerMapaMental()` |
| Variables: `svgMentalMapa`, `modalMentalMapa`, etc. | `svgMapaMental`, `modalMapaMental`, etc. |
| Tipo literal `'mentalMapa'` | `'mapaMental'` |

Se conservan con el nombre `mermaid` únicamente: el import del paquete npm, las llamadas
internas `mermaid.initialize/render`, la clase CSS `.mermaid-thumbnail` (par css/tsx) y
el regex `` /```\s*mermaid\s*\n/ `` y el prompt de SubcatPanel (nombre del formato
que el LLM debe generar).

---

### Detalle de S3-42 / S3-43 / S3-44 — Imágenes en historial: fallback base64 y zoom

**Contexto:**
Las URLs de imagen de OpenAI (DALL-E 3) y Grok expiran en ~1 hora. El backend ya
guardaba una miniatura en base64 (`imagen_miniatura`) precisamente para este caso,
pero el frontend no la usaba como fallback.

**S3-42 — Fallback a `imagen_miniatura` cuando la URL caduca:**

El operador `??` no sirve para este caso: `url_imagen` existe como cadena aunque la URL
esté caducada, así que `??` nunca activa el base64. Se añadió `onError` en todos los
`<img>` de historial y admin, y se amplió `VisorImagen` con una prop `fallbackSrc`:

```tsx
// Thumbnail
<img
  src={r.url_imagen ?? `data:image/jpeg;base64,${r.imagen_miniatura}`}
  onError={(e) => {
    if (r.imagen_miniatura)
      (e.target as HTMLImageElement).src = `data:image/jpeg;base64,${r.imagen_miniatura}`
  }}
/>

// Lightbox — VisorImagen recibe fallbackSrc
<VisorImagen
  src={lightbox.src}
  fallbackSrc={lightbox.fallbackSrc}
  onClose={...}
/>
```

Afecta a: `EvalViewModal`, `DetalleComparativaModal` (TablaAdmin), `VisorImagen`.

**S3-43 — Resolución de miniatura 200 → 512 px:**

Con 200×200 la miniatura quedaba muy pixelada al mostrarse como fallback en el lightbox.
Se subió el tamaño por defecto en `generar_miniatura()` de 200 a 512 px. El tamaño en
base64 pasa de ~10-20 KB a ~60-100 KB por imagen. Para el volumen del estudio (~50-100
sesiones, 3-4 imágenes cada una) el impacto en la base de datos es menor de 40 MB.

```python
# backend/app/llm_engine/metricas.py
def generar_miniatura(imagen_bytes: bytes, tamano: int = 512) -> str | None:
```

**S3-44 — Zoom en VisorImagen con imagen en fallback:**

Al hacer clic para hacer zoom, React re-renderiza `VisorImagen` y resetea el atributo
`src` a su valor original (la URL caducada), deshaciendo la mutación DOM del `onError`
anterior. Resultado: la imagen parpadeaba o desaparecía al activar el zoom.

Solución: trackear el src activo en estado React (`useState`) en lugar de mutar el DOM:

```tsx
const [imgSrc, setImgSrc] = useState(src)
useEffect(() => { setImgSrc(src) }, [src])

<img
  src={imgSrc}
  onError={() => { if (fallbackSrc) setImgSrc(fallbackSrc) }}
/>
```

El estado `imgSrc` sobrevive a los re-renders por cambio de `zoom`, por lo que una vez
activado el fallback el zoom funciona con normalidad sobre el base64.

---

## Items no completados (arrastre a Sprint 4)

| ID    | Tarea                                                      | Puntos | Motivo                                         |
|-------|------------------------------------------------------------|--------|------------------------------------------------|
| S3-16 | React frontend conectado al backend (axios + interceptores)| 8      | Pendiente backend completamente operativo      |
| S3-17 | Estado global Zustand sin prop drilling                    | 3      | Bloqueado por S3-16                            |
| S3-18 | Dashboard con datos reales del endpoint /stats             | 5      | Bloqueado por S3-16                            |
| S3-19 | Exportación CSV funcionando end-to-end                     | 3      | Bloqueado por S3-16                            |
| S3-20 | Detalle de sesión (expandir fila en historial)             | 3      | Pospuesto a Sprint 4 por prioridad             |
| S3-21 | Relanzar benchmark desde historial                         | 3      | Pospuesto a Sprint 4 por prioridad             |

---

## Velocidad

Comprometidos: 76 pt | Completados: 97 pt | Completitud: 100% (+ 23 pt de refinamiento)

Items de diseño y documentación: 15 de 15 (100%)
Items de integración frontend-backend: 0 de 4 (pendientes Sprint 4)
Items de refinamiento UX/bug post-cierre (S3-28 a S3-32): 5 de 5 (10 pt adicionales)
Items de refinamiento UI/refactor (S3-33 a S3-41): 9 de 9 (18 pt adicionales)
Items de corrección imagen fallback (S3-42 a S3-44): 3 de 3 (5 pt adicionales)

---

## Impedimentos y resoluciones

**Compresión de sprints**
El calendario del proyecto se comprimió porque el inicio real del desarrollo
fue en mayo de 2026, cuatro meses después de la fecha planificada. Los
sprints 1 a 3 se solaparon en el tiempo real de trabajo. El prototipo cubre
el trabajo de diseño del Sprint 3 completo; la integración real frontend-
backend pasa al Sprint 4 como primera prioridad.

**Iteraciones en el sticky scroll del historial**
La combinación de dos filas sticky en el `<thead>` de la tabla del historial
requirió tres iteraciones antes de encontrar la posición correcta (filtros
sobre cabecera con padding extra). Este proceso iterativo queda documentado
en DEF-001, sección 6, como ejemplo de decisión de diseño por descarte.

**Cobertura insuficiente de métricas automáticas en la primera versión**
El primer diseño del dashboard priorizaba las métricas de evaluación humana.
Tras la revisión del prototipo se detectó que las métricas objetivas
(tokens, velocidad, coste normalizado, diversidad léxica, similitud Jaccard)
apenas aparecían. Se tomó la decisión de añadir el bloque completo de cinco
gráficos adicionales. Este proceso está documentado en DEF-002, sección 6,
y en ADR-016 como consecuencia positiva de la revisión iterativa.

---

## Retrospectiva

**Qué fue bien**
- El prototipo standalone (HTML/CSS/JS) permitió iterar sobre el diseño de
  interfaz con velocidad máxima: cualquier cambio era visible sin tiempo de
  compilación. La elección de no arrancar el frontend React hasta tener el
  diseño validado fue correcta.
- La separación entre métricas humanas y métricas automáticas en el dashboard
  surgió de la revisión del prototipo, no del diseño inicial. El proceso de
  revisión iterativa generó una decisión arquitectónica mejor que la original.
- Los documentos DEF-001 y DEF-002 capturan las iteraciones y descensos, no
  solo el resultado final. Esto es el material más valioso para el Capítulo 4
  de la memoria (Análisis y Diseño).

**Qué mejorar**
- La integración frontend-backend debería haberse prototipado al menos con
  datos reales de un endpoint en el Sprint 3. El dashboard funciona con datos
  simulados y no se ha validado la estructura del JSON real que devolverá
  el backend.
- Los formularios de los gráficos de métricas automáticas deberían validarse
  con n > 30 sesiones reales para confirmar que los rangos de los ejes son
  correctos y que los datos de Jaccard tienen sentido estadístico.

**Acción concreta para Sprint 4**
Prioridad 1: conectar el frontend React al endpoint `/api/v1/stats` con datos
reales antes de añadir ninguna funcionalidad nueva. El prototipo v1.html sirve
como especificación exacta del contrato visual que debe cumplir la implementación
React.

---

## Estado del producto al cierre

Con lo entregado en este sprint el equipo puede:

- Recorrer el flujo completo de la aplicación en el prototipo: nick de entrada,
  selección de categoría y prompt, visualización de cuatro respuestas LLM,
  evaluación con rating y ranking, consulta del historial con filtros, y análisis
  en el dashboard con 13 gráficos interactivos.
- Defender ante el tribunal el diseño de interfaz con documentación exhaustiva:
  cada decisión de diseño tiene su justificación escrita en DEF-001 o DEF-002.
- Mostrar en vivo la separación entre métricas objetivas y subjetivas, el
  principio anti-sesgo, y el argumento cuantitativo de la matriz Jaccard para
  justificar el uso de cuatro modelos distintos.

Lo que aún no puede hacer: ejecutar benchmarks reales contra las APIs de LLM,
guardar sesiones en PostgreSQL, ni mostrar datos reales en el dashboard.
Eso es el objetivo prioritario del Sprint 4.

**Refinamientos post-cierre (S3-28 a S3-32):** se corrigieron cinco defectos de UX
detectados durante las primeras pruebas reales con las APIs: coste fijo no discriminativo
en imagen ocultado, flujo de reintento tras censura rediseñado, subcategoría imagen
restaurada correctamente al reintentar (patrón `prevCategoria` ref, compatible con React
StrictMode), botón "Limpiar" reiniciando categoría completa, y carga de imagen de
referencia en la subcategoría "Modificar imagen". El frontend queda completamente
funcional para el estudio con datos reales del Sprint 4.

---

## Artefactos entregados

- `docs/prototipos/prototipo_v1.html` — prototipo funcional completo (141 KB)
- `docs/funcional/DEF-001-historial-sesiones.md` — especificación funcional historial
- `docs/funcional/DEF-002-dashboard.md` — especificación funcional dashboard
- `docs/decisions/ADR-015-historial-sesiones-roles.md` — decisión arquitectónica historial
- `docs/decisions/ADR-016-dashboard-metricas-visualizacion.md` — decisión dashboard
- `frontend/src/components/shared/MapaMentalDiagram.tsx` — componente render de diagrama mapa mental (SVG via librería mermaid)
- `frontend/src/components/shared/VisorImagen.tsx` — lightbox reutilizable para imágenes con zoom
- `frontend/src/components/shared/VisorMapaMental.tsx` — lightbox reutilizable para mapas mentales con zoom/drag/pan
- `frontend/src/components/shared/BtnAmpliar.tsx` — botón de ampliación compartido con estilo unificado
- `frontend/src/utils/contenidoLLM.ts` — utilidades `esCensura()` y `extraerMapaMental()`
- `frontend/package.json` — dependencia `mermaid@^11.14.0` añadida
- `frontend/src/pages/BenchmarkPage.tsx` — fix coste imagen, botón reintento censura, limpiar completo, rename sesion→evaluacion, color imagen #F87171
- `frontend/src/pages/HistorialPage.tsx` — colores de categoría alineados con BenchmarkPage
- `frontend/src/components/benchmark/SubcatPanel.tsx` — carga imagen "Modificar imagen", patrón prevCategoria ref, prop opImagenInicial
- `frontend/src/components/benchmark/BenchmarkCard.tsx` — refactor: usa VisorImagen/VisorMapaMental/BtnAmpliar compartidos
- `frontend/src/components/historial/EvalViewModal.tsx` — lightbox imagen con zoom, render mapa mental, refactor compartidos
- `frontend/src/components/historial/TablaAdmin.tsx` — badge categoría coloreado, truncado prompt, acciones izquierda, render mapa mental + lightbox
