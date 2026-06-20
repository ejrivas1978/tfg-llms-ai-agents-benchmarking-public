# ADR-017: Stack de librerías frontend — Tailwind, TanStack Query, Recharts, dnd-kit

Estado: Aceptado
Fecha: 03/05/2026
Sprint: Sprint 3

## Contexto

El frontend es una SPA con cuatro pantallas (Nick, Benchmark, Evaluación, Historial,
Dashboard) construida en React 18 + Vite + TypeScript (ADR-005). Esta decisión cubre
las cuatro librerías de soporte que completan ese stack: estilos, datos del servidor,
visualizaciones y arrastrar-soltar. Se agrupan en un solo ADR porque son elecciones
de herramienta complementarias, no decisiones de arquitectura independientes.

---

## Decisiones tomadas

### 1. Tailwind CSS — estilos

**Elegido sobre:** CSS Modules, styled-components, vanilla CSS.

Tailwind genera clases de utilidad durante el build; el CSS final contiene solo
lo que se usa. En una SPA con tema oscuro fijo (colores y espaciados ya definidos
en el prototipo) esto es más directo que mantener ficheros `.module.css`
independientes por componente.

styled-components requiere un runtime en el navegador para interpolar props en
estilos. Para una aplicación sin theming dinámico eso es overhead injustificado.

El sistema de diseño del TFG (paleta fija, 8 colores de categoría, 4 colores de
proveedor) se mapea directamente a tokens en `tailwind.config.ts`, lo que hace que
los colores del prototipo queden versionados y accesibles en toda la app sin
variables CSS duplicadas.

**Trade-off asumido:** Las clases de Tailwind en JSX son verbosas. En componentes
complejos se extraen con `clsx` o constantes, no se repiten inline.

---

### 2. TanStack Query v5 (React Query) — datos del servidor

**Elegido sobre:** useState + useEffect manual, SWR, RTK Query.

El backend expone cinco endpoints que el frontend consume: `/benchmarks/run`,
`/benchmarks/:id`, `/evaluaciones`, `/stats` y `/admin/sesiones`. TanStack Query
gestiona el ciclo completo (loading, error, cache, refetch) de cada uno con
un hook declarativo. Sin él, cada pantalla necesita su propio useEffect con
gestión manual de estados de carga y error, lo que multiplica el código repetitivo.

SWR es una alternativa válida pero con menos funcionalidades para mutaciones
(el flujo `POST /benchmarks/run` → invalidar cache → refetch es más limpio
con `useMutation` + `invalidateQueries` de TanStack Query).

RTK Query viene con Redux Toolkit y añade boilerplate de slice/reducer innecesario
para una app de cuatro pantallas sin estado global complejo.

**Trade-off asumido:** TanStack Query v5 cambió la API respecto a v4 (callbacks
`onSuccess`/`onError` eliminados). Los ejemplos de internet son mayoritariamente v4.
Se trabaja con la documentación oficial de v5.

---

### 3. Recharts — visualizaciones del dashboard

**Elegido sobre:** Chart.js (usada en el prototipo HTML).

El prototipo usa Chart.js con la API imperativa de canvas. En React, Chart.js
requiere gestionar manualmente las instancias con `useRef` y llamar a
`chart.destroy()` antes de cada re-render para evitar fugas de memoria —
patrón documentado en DEF-002. Recharts es una librería diseñada específicamente
para React: cada gráfica es un componente declarativo que React monta y desmonta
de forma natural, sin gestión manual de instancias.

La decisión de cambiar de Chart.js (prototipo) a Recharts (producción) está
justificada precisamente por el cambio de contexto: el prototipo era HTML
vanilla donde Chart.js es la opción estándar; la implementación React se
beneficia de componentes declarativos.

Las gráficas no estándar del dashboard (heatmap modelo×categoría y matriz
Jaccard 4×4) se implementan como CSS Grid con cálculo de color en JavaScript,
igual que en el prototipo, porque ninguna librería de gráficas las cubre
de forma nativa sin un plugin externo.

**Trade-off asumido:** Recharts no expone acceso directo al canvas subyacente,
lo que dificulta la exportación a PNG/PDF (S3-18, marcado como Could). Si
se implementa la exportación, se usará `html2canvas` sobre el contenedor del
dashboard en lugar de la API de Chart.js.

---

### 4. dnd-kit — arrastrar y soltar en EvaluationPage

**Elegido sobre:** react-beautiful-dnd, @hello-pangea/dnd, HTML5 Drag and Drop API nativa.

Ya citado en ADR-005 como justificación de usar React frente a Vue. dnd-kit
es la librería de drag-and-drop más mantenida para React en 2026, accesible
por defecto (cumple WCAG 2.1 con teclado), y funciona sin depender del
event system nativo del navegador, lo que evita conflictos con el modelo
de eventos de React.

react-beautiful-dnd está en modo mantenimiento desde 2022 (Atlassian lo archivó).
@hello-pangea/dnd es su fork comunitario, válido pero sin soporte oficial.
La API nativa de HTML5 Drag and Drop no integra bien con el modelo de estado
de React y tiene comportamiento inconsistente entre navegadores.

El uso en la app es simple: ordenar cuatro tarjetas de modelos en la pantalla
de evaluación. dnd-kit no es sobredimensionado para este caso porque su
instalación es modular (solo se instala `@dnd-kit/core` y `@dnd-kit/sortable`).

**Trade-off asumido:** dnd-kit requiere más boilerplate que react-beautiful-dnd
para un caso de uso simple. Para cuatro elementos el overhead es aceptable.

---

## Consecuencias globales

El stack completo del frontend queda:

| Capa | Librería | Versión |
|------|----------|---------|
| Framework | React 18 | 18.x |
| Build | Vite | 5.x |
| Lenguaje | TypeScript | 5.x |
| Estilos | Tailwind CSS | 3.x |
| Estado servidor | TanStack Query | 5.x |
| Estado cliente | Zustand | 4.x |
| Router | React Router | 6.x |
| Visualizaciones | Recharts | 2.x |
| Drag-and-drop | dnd-kit | 6.x |
| HTTP | Axios | 1.x |
| Validación forms | Zod | 3.x |

Este stack no introduce ninguna dependencia que requiera runtime en producción
más allá del bundle estático servido desde Nginx en Cloud Run (ADR-006).
