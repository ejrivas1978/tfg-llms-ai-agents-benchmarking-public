# ADR-030 — Persistencia del texto de entrada autogenerado en la categoría Resumen

**Fecha:** 15/05/2026
**Estado:** Aceptado
**Sprint:** Sprint 4

---

## Contexto

La categoría Resumen exige que el usuario aporte un texto de al menos 300 palabras
sobre el que los cuatro LLMs generarán sus resúmenes. Para facilitar este paso se
añadió en S4-93 y S4-94 un botón "✨ Generar texto" que llama al endpoint
`GET /api/v1/benchmarks/texto-ejemplo` y rellena automáticamente el textarea con
un texto en castellano generado por el LLM más barato disponible.

El problema detectado a posteriori fue que este texto existía solo en memoria del
navegador. Si el usuario evaluaba la comparativa de inmediato, los resultados eran
coherentes. Pero si cerraba la pestaña, retomaba la sesión más tarde o consultaba
el historial días después, el texto había desaparecido. El historial mostraba métricas
y valoraciones, pero era imposible saber sobre qué texto concreto se había pedido
el resumen, lo que dificultaba la reproducibilidad del experimento.

Esta limitación resulta especialmente problemática en el contexto del TFG porque
el análisis empírico del capítulo de resultados requiere que cada evaluación sea
trazable: se deben poder relacionar las métricas de los modelos con el texto que
procesaron.

---

## Opciones consideradas

### Opción A — No persistir; mostrar el texto solo en la vista de resultados inmediata

El texto permanece en el estado de React de `BenchmarkPage` mientras el usuario
no navega. La vista de resultados lo muestra directamente en el textarea (que queda
bloqueado). Una vez que el usuario navega o cierra la pestaña, el texto se pierde.

**Ventajas:**
- Cero cambios en el modelo de datos y en las migraciones.
- Sin riesgo de almacenar contenido generado de forma no intencional.

**Inconvenientes:**
- El corpus del estudio queda incompleto: las evaluaciones de resumen no son
  reproducibles desde el historial.
- El administrador no puede revisar a posteriori sobre qué texto se realizó
  el resumen al inspeccionar una evaluación desde el panel admin.

### Opción B — Persistir el texto en `benchmark_evaluaciones` con flag discriminador

Añadir dos columnas:
- `texto_entrada TEXT NULL`: almacena el texto de entrada.
- `texto_entrada_autogenerado BOOLEAN NOT NULL DEFAULT FALSE`: indica que el texto
  fue producido por la plataforma y no introducido directamente por el usuario.

El texto **solo se persiste cuando `texto_entrada_autogenerado=true`**, es decir,
cuando la plataforma lo generó. Los textos introducidos manualmente o cargados desde
fichero no se persisten, por considerarse potencialmente confidenciales (documentos
del usuario).

La vista de historial (`EvalViewModal`) muestra un acordeón "✨ Ver texto original
generado automáticamente" exclusivamente en evaluaciones con `texto_entrada_autogenerado=true`,
replicando el patrón del acordeón de respuestas EN ya implementado en ADR-029.

**Ventajas:**
- Corpus completo: cada evaluación de resumen con texto autogenerado es 100 % trazable
  y reproducible desde el historial.
- El administrador puede revisar el contexto completo de cualquier evaluación.
- El flag discriminador garantiza que solo se almacena contenido generado por la
  plataforma, sin exponer datos del usuario.
- Implementación limpia: la lógica de persistencia existe en una única capa
  (BenchmarkService) y los demás componentes simplemente propagan los campos.

**Inconvenientes:**
- Requiere una migración Alembic adicional (`q6f7a8b9c0d1`).
- Aumenta el tamaño de la tabla `benchmark_evaluaciones` para las evaluaciones de
  resumen con texto autogenerado (~300–400 palabras por registro).

---

## Decision tomada

Se elige la **Opción B** por razones de reproducibilidad científica del estudio.
El texto de entrada es parte esencial del contexto de una evaluación de resumen:
sin él, las métricas (latencia, coste, relación salida/entrada) carecen de
interpretación. El coste en almacenamiento es insignificante (~2 KB por evaluación)
frente al valor que aporta tener el corpus completo y trazable.

El flag `texto_entrada_autogenerado` resuelve la tensión entre reproducibilidad
y privacidad: solo el contenido que la plataforma misma genera queda registrado.
El contenido que el usuario introduce (textos propios, documentos cargados) no
se persiste en ningún caso.

---

## Consecuencias

### Positivas

- Cada evaluación de resumen con texto autogenerado es reproducible: el administrador
  puede reconstruir el experimento exacto desde el panel admin.
- El acordeón en `EvalViewModal` permite al usuario recuperar el texto si necesita
  revisarlo después de haber cerrado la vista de resultados.
- La columna `texto_entrada_autogenerado` puede usarse como filtro en análisis futuros
  para segmentar evaluaciones con contexto conocido de las que no lo tienen.

### Negativas y trade-offs asumidos

- La tabla `benchmark_evaluaciones` crece ~2–4 KB por evaluación de resumen con texto
  autogenerado. Con el volumen del estudio (~50–100 evaluaciones de resumen) el impacto
  es despreciable (< 400 KB).
- Las evaluaciones de resumen con texto manual o cargado desde fichero **no** tienen
  `texto_entrada` persistido. El corpus resultante es heterogéneo en cuanto a
  reproducibilidad. Esta heterogeneidad está documentada y puede ser argumento en el
  capítulo de amenazas a la validez del TFG.

### Riesgos

- El texto generado puede contener contenido inadecuado si el LLM lo produce de forma
  inesperada. Mitigación: los mismos filtros de política de contenido que ya protegen
  los otros endpoints aplican a `texto-ejemplo`; además, el texto nunca se procesa
  como instrucción, solo como contexto de resumen.

---

## Implementacion

### Backend

- Migración `q6f7a8b9c0d1_texto_entrada_autogenerado.py`:
  ```sql
  ALTER TABLE benchmark_evaluaciones ADD COLUMN texto_entrada TEXT NULL;
  ALTER TABLE benchmark_evaluaciones ADD COLUMN texto_entrada_autogenerado
      BOOLEAN NOT NULL DEFAULT FALSE;
  ```
- `BenchmarkEvaluacion` (modelo ORM): dos `mapped_column` nuevos.
- `BenchmarkEvaluacionRepository.crear()`: recibe `texto_entrada` y
  `texto_entrada_autogenerado` como parámetros con valores por defecto `None`/`False`.
- `PeticionBenchmark` y `RespuestaBenchmark` (schemas Pydantic): campos con `None`/`False`
  como valores por defecto para mantener retrocompatibilidad.
- `BenchmarkService.ejecutar()`: propaga ambos campos desde la petición al repositorio.
- Router `POST /benchmarks/run`: extrae los dos campos de `PeticionBenchmark` y los
  pasa al servicio.

### Frontend

- `SubcatPanel.tsx`:
  - Nueva prop `onTextoEntradaChange?(texto: string | null, autogenerado: boolean)`.
  - Estado `textoAutogenerado: boolean` (false por defecto; true al generar; false al editar).
  - Función `actualizarResumen(texto, autogenerado=false)` centraliza la propagación.
- `BenchmarkPage.tsx`:
  - Estados `textoEntrada: string | null` y `textoEntradaAutoGen: boolean`.
  - La mutación de benchmark incluye `texto_entrada` y `texto_entrada_autogenerado`
    únicamente cuando `textoEntradaAutoGen === true`.
- `EvalViewModal.tsx`:
  - Estados `verTextoOriginal` y `ampliadoTextoOriginal`.
  - Acordeón condicional: solo se renderiza si `sesion.texto_entrada_autogenerado && sesion.texto_entrada`.
  - Presente en ambas ramas del modal (formulario pendiente y vista de solo lectura).

---

## Referencias

- S4-93: UX categoría resumen con contador y botón "Generar texto".
- S4-94: Backend `GET /benchmarks/texto-ejemplo` con selector LLM y orden por coste.
- S4-95: Implementación completa de RF-17 con migración y acordeón en historial.
- ADR-021: Carga de ficheros para la categoría Resumen (decisión anterior sobre el mismo flujo).
- ADR-029: Acordeón de respuestas EN del sub-experimento bilingüe (patrón de UX reutilizado).
