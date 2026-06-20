# ADR-005: React 18 + Vite + Zustand sobre Next.js y Vue

Estado: Aceptado
Fecha: 01/02/2026
Sprint: Sprint 2

## Contexto

El frontend es una SPA de uso interno para ejecutar benchmarks, evaluar
respuestas y consultar el dashboard. Las características del proyecto
condicionan la elección del stack:

- SPA sin necesidad de SEO ni renderizado en servidor (aplicación de
  evaluación académica, no un sitio público indexable).
- Despliegue en Google Cloud Run como contenedor Docker: el proceso de
  build genera estáticos que se sirven desde Nginx; no se necesita un
  runtime Node.js en producción.
- Estado compartido entre tres pantallas (configuración del benchmark,
  evaluación de respuestas, historial); sin contexto padre común que
  facilite prop-drilling.
- Arrastrar y soltar para el ranking de preferencia de respuestas en la
  pantalla de evaluación.

## Opciones consideradas

### 1. Next.js 14

Ventajas: SSR y SSG integrados, file-based routing, ecosistema maduro,
React Server Components.

Desventajas: SSR y RSC añaden complejidad innecesaria para una SPA de
uso interno. El file-based routing no aporta valor con solo cuatro
pantallas. La imagen Docker de producción requiere un proceso Node.js
activo en Cloud Run, aumentando coste y latencia de arranque respecto
a servir estáticos desde Nginx.

### 2. Vue 3 + Pinia

Ventajas: Composition API, Pinia más sencillo que Vuex, documentación
excelente en castellano.

Desventajas: React tiene mayor presencia en el mercado laboral español
y en las ofertas de prácticas que el alumno consultará al terminar el
TFG. El ecosistema de componentes de drag-and-drop para la pantalla de
evaluación (ranking de respuestas) es más maduro en React. Cambiar a
Vue implicaría reaprender un paradigma distinto cuando React ya es
conocido.

### 3. React 18 + Vite + Zustand (elegida)

Ventajas: HMR instantáneo con Vite frente a CRA o webpack. React 18
incluye Concurrent Mode y Suspense para manejar los cuatro streamings
de LLM en paralelo. Zustand ofrece un store global en menos de
30 líneas sin actions ni reducers, suficiente para el tamaño de esta
aplicación. El build de Vite genera estáticos servibles desde Nginx sin
proceso Node.js activo.

Desventajas: No incluye router de primera parte; se añade React Router v6
como dependencia separada. Zustand carece de las DevTools de Redux,
aunque sí se integra con Redux DevTools mediante middleware.

## Decisión tomada

Se elige React 18 + Vite + Zustand.

La combinación cubre todos los requisitos sin introducir complejidad
innecesaria. Vite resuelve la experiencia de desarrollo (arranque <1s),
React garantiza la disponibilidad de librerías de drag-and-drop, y
Zustand mantiene el estado global con el mínimo boilerplate justificable
para cuatro pantallas.

## Consecuencias

Positivas:
- Vite en desarrollo: HMR en milisegundos, sin configuración de webpack.
- React 18 Suspense facilita mostrar skeletons de carga mientras los
  cuatro LLMs responden en paralelo.
- Zustand: un único fichero de store cubre toda la lógica de estado
  sin prop-drilling entre BenchmarkPage, EvaluationPage y Dashboard.
- La librería dnd-kit (drag-and-drop accesible) tiene integración nativa
  con React y está mantenida activamente.

Trade-offs asumidos:
- React Router v6 se añade como dependencia explícita, a diferencia de
  Next.js donde el routing es implícito.
- TypeScript con React requiere tipado de props y hooks que Vue 3 maneja
  de forma más natural con la Composition API; se acepta porque el
  esfuerzo es comparable y el beneficio de mercado compensa.
- Zustand no tiene sincronización automática con el servidor (no es un
  cliente REST/GraphQL). Se complementa con React Query para el cache
  de peticiones al backend.
