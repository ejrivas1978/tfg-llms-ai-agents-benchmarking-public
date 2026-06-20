# Sprint 5 — Evaluación humana y análisis de resultados
Periodo: 14/05/2026 – 15/06/2026
Estado: EN CURSO

---

## Objetivo del sprint

Obtener un corpus de evaluaciones humanas representativo por categoría de
tarea, ejecutar el análisis estadístico completo de los resultados y
documentar los hallazgos en la memoria del TFG. Al cierre del sprint
la memoria debe incluir un capítulo de análisis de resultados con conclusiones
respaldadas por los datos recogidos en la plataforma.

---

## Bugs corregidos durante el estudio (BUG-EST)

| ID | Descripción | Fecha | Estado |
|----|-------------|-------|--------|
| BUG-EST-01 | Historial de usuario vacío al acceder desde otro navegador o dispositivo | 19/05/2026 | ✅ Corregido |
| BUG-EST-02 | Navegador sirve index.html antiguo tras despliegue (sin hard refresh) | 19/05/2026 | ✅ Corregido |

### Detalle BUG-EST-01 — Historial siempre desde BD

**Síntoma:** un usuario que había ejecutado evaluaciones veía el historial vacío
al entrar desde un navegador diferente, o cuando su JWT había caducado. El
administrador sí podía ver sus evaluaciones en el panel. La vista de usuario
leía exclusivamente de `localStorage` (historialStore Zustand), que no existe
en el nuevo contexto, o el efecto de sincronización se cortocircuitaba cuando
el token ya no estaba presente.

**Causa raíz (JWT expirado):** el JWT de usuario dura 1 hora. Cuando caduca,
el interceptor de axios en `usuarioApi.ts` llama a `logout()` y deja
`usuarioStore.token = null`. El `useEffect` de sincronización del historial
comprobaba `usuarioToken` antes de lanzar la petición y retornaba antes de
hacer nada. El historial quedaba congelado en los datos antiguos del
`localStorage`.

**Causa secundaria (nuevo dispositivo / navegador):** el `localStorage` no
existe en un dispositivo distinto, de modo que `sesiones[nick]` era un array
vacío y nunca se rellenaba porque el efecto tampoco se ejecutaba.

**Solución:**

- **Backend — nuevo método `listar_historial_usuario`** en
  `BenchmarkEvaluacionRepository`: devuelve las últimas 50 evaluaciones del
  nick indicado con el flag `evaluada` calculado mediante subconsulta
  correlacionada. La consulta usa `func.lower()` para ser insensible a
  mayúsculas (defensivo; en producción todos los nicks son minúsculas).

- **Backend — nuevo endpoint público `GET /api/v1/benchmarks/historial/{nick}`**
  en `routers/benchmark.py` (sin autenticación requerida). El nick es el
  identificador persistido en `nickStore` (localStorage), que sobrevive a la
  expiración del JWT. Registrado **antes** que `GET /benchmarks/{evaluacion_id}`
  para evitar que FastAPI intente parsear `"historial"` como entero.

- **Backend — nuevo schema `ResumenEvaluacionUsuario`** en
  `schemas/benchmark.py` (DTO ligero con `id`, `prompt`, `categoria`, `estado`,
  `created_at`, `evaluada`).

- **Frontend — acción `hidratar` en `historialStore`**: reemplaza completamente
  el array local con los datos de BD. El servidor es la fuente de verdad.

- **Frontend — `HistorialPage.tsx`**: `useEffect` con dependencia `[nick]`
  que llama a `obtenerHistorialPorNick(nick)` e invoca `hidratar`. Sin
  dependencia de `usuarioToken`: funciona aunque el JWT haya caducado o no
  exista. Si la petición falla (sin red), el historial local sigue visible.

- **Frontend — `benchmarkApi.ts`**: nueva función pública
  `obtenerHistorialPorNick(nick)` que llama a
  `GET /api/v1/benchmarks/historial/{encodeURIComponent(nick)}` usando la
  instancia `api` compartida (el interceptor inyecta JWT si existe, pero el
  endpoint no lo exige).

**Archivos modificados:**
- `backend/app/repositories/benchmark_evaluacion_repository.py`
- `backend/app/schemas/benchmark.py`
- `backend/app/routers/benchmark.py`
- `frontend/src/services/benchmarkApi.ts`
- `frontend/src/pages/HistorialPage.tsx`

**Diagrama de secuencia:** `docs/diagramas/editables/puml/sec_historial_sync_bd.puml`

---

### Detalle BUG-EST-02 — Cache del navegador en index.html tras despliegue

**Síntoma:** tras un nuevo despliegue en Cloud Run, el navegador seguía
sirviendo el `index.html` antiguo (con hashes de bundles JS/CSS ya obsoletos)
hasta que el usuario hacía un *hard refresh* manual (Ctrl+Shift+R). Esto
provocaba que la corrección de BUG-EST-01 no tuviera efecto hasta ese gesto.

**Causa raíz:** nginx no enviaba cabecera `Cache-Control` para `index.html`,
de modo que el navegador lo cacheaba con la política por defecto del servidor
(heurística basada en `Last-Modified`). Al desplegar una versión nueva, el
navegador no la descargaba de nuevo.

**Solución:** añadir `add_header Cache-Control "no-cache"` al bloque
`location /` de `nginx.conf.template`. Esto obliga al navegador a revalidar
`index.html` en cada visita. Los bundles JS/CSS de Vite conservan
`Cache-Control: public, immutable` porque llevan hash en el nombre de fichero
y son inmutables por naturaleza.

**Archivos modificados:**
- `frontend/nginx.conf.template`

---

## Ítems planificados

| ID    | Tarea                                                                 | Puntos | Estado      |
|-------|-----------------------------------------------------------------------|--------|-------------|
| S5-01 | Diseño del protocolo de evaluación humana                             | 3      | Planificado |
| S5-02 | Preparación del entorno Cloud Run con datos de prueba iniciales       | 2      | Planificado |
| S5-03 | Reclutamiento de evaluadores externos (mínimo 3)                      | 2      | Planificado |
| S5-04 | Sesiones de evaluación piloto (validar coherencia del protocolo)      | 3      | Planificado |
| S5-05 | Corpus de evaluaciones: ≥ 10 evaluaciones por categoría × 8 categorías| 8      | Planificado |
| S5-06 | Sub-experimento ES vs EN: corpus paralelo en 4 categorías controladas | 5      | Planificado |
| S5-07 | Análisis estadístico: medias por categoría, rankings, dispersión      | 5      | Planificado |
| S5-08 | Análisis comparativo ES vs EN sobre métricas técnicas                 | 3      | Planificado |
| S5-09 | Gráficas de resultados exportadas del dashboard para la memoria       | 2      | Planificado |
| S5-10 | Redacción del capítulo de análisis de resultados en la memoria        | 8      | Planificado |
| S5-11 | Revisión de coherencia integral de la memoria (caps. 1–6)             | 3      | Planificado |
| S5-12 | Correcciones finales y preparación del documento de entrega           | 2      | Planificado |

**Total planificado: 46 puntos**

---

## Protocolo de evaluación humana

### Criterios de evaluación

Cada evaluador valorará las cuatro respuestas obtenidas para el mismo prompt
con los siguientes criterios, siguiendo la escala de la plataforma:

- **Relevancia (0–5 estrellas):** la respuesta aborda directamente lo que
  pide el prompt, sin desviarse ni añadir contenido irrelevante.
- **Calidad técnica o lingüística (0–5 estrellas):** corrección factual para
  preguntas concretas, corrección de código para la categoría código,
  riqueza expresiva para escritura creativa.
- **Preferencia global (ranking 1–4):** ordenación de las cuatro respuestas
  de mayor a menor preferencia, incluyendo criterios propios del evaluador.

El valor 0 estrellas se reserva exclusivamente para respuestas rechazadas por
política de contenido del modelo (sin contenido evaluable).

### Escenarios de evaluación por categoría

| Categoría             | Nº de prompts distintos | Subcategorías a cubrir         |
|-----------------------|-------------------------|--------------------------------|
| Razonamiento lógico   | ≥ 5                     | Series, silogismos, acertijos  |
| Generación de código  | ≥ 5                     | Python, SQL, algoritmos        |
| Escritura creativa    | ≥ 5                     | Relato, descripción, diálogo   |
| Preguntas concretas   | ≥ 5                     | Ciencia, historia, definición  |
| Traducción            | ≥ 3                     | ES→EN, EN→ES, técnico          |
| Resumen               | ≥ 3                     | Texto largo, artículo, fichero |
| Imagen generativa     | ≥ 5                     | Logotipo, ilustración, retrato |
| Prompt libre          | ≥ 4                     | Sin restricción de evaluador   |

### Número de evaluadores

El estudio no aspira a una muestra estadísticamente representativa de la
población general —el protocolo de reclutamiento de un TFG no lo permite—
sino a una muestra de conveniencia que cubra al menos tres perfiles:
un evaluador con perfil técnico (desarrollador o ingeniero), uno con perfil
no técnico (sin conocimientos de programación) y uno bilingüe (para el
sub-experimento ES/EN). La ausencia de acuerdo formal entre anotadores
(*inter-rater reliability*) es una limitación reconocida del estudio y se
documenta como tal en la memoria.

---

## Criterios de cierre del sprint

1. El corpus de evaluaciones contiene al menos 80 evaluaciones completas
   distribuidas entre las 8 categorías.
2. El sub-experimento ES vs EN tiene datos en las cuatro categorías controladas
   (razonamiento lógico, escritura creativa, preguntas concretas).
3. El capítulo de análisis de resultados está redactado e integrado en
   `MEMORIA_V3.md`.
4. La memoria completa ha sido revisada para coherencia interna.

---

## Impedimentos identificados

**Disponibilidad de evaluadores externos.** El reclutamiento de evaluadores
fuera del círculo inmediato del autor depende de la disponibilidad ajena.
Se establece como plan de contingencia que el autor complete las evaluaciones
necesarias para cubrir el corpus mínimo si no hay suficientes evaluadores
externos antes del 01/06/2026.

**Variabilidad de las APIs en producción.** Las APIs de los proveedores LLM
pueden modificar sus modelos o precios durante el sprint. El sistema de
tarifas versionadas mitiga el impacto sobre la reproducibilidad histórica
(ADR-028), pero cualquier cambio de modelo requeriría actualizar el análisis
de resultados si altera sustancialmente el perfil de respuestas.

---

## Artefactos a entregar

- `docs/sprints/sprint-05-report.md` — este documento (actualizado al cierre)
- Capturas de las gráficas del dashboard en formato PNG para la memoria
- `docs/memoria/chapters/05b_analisis_resultados.md` — nuevo capítulo
- `docs/memoria/MEMORIA_V3.md` — regenerada con el capítulo de resultados
- `docs/memoria/Version_final_Memoria_TFG_V3.docx` — versión de entrega
