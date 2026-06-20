# ADR-019: Evaluación de primera impresión — sin modificaciones permitidas

Estado: Aceptado
Fecha: 03/05/2026
Sprint: Sprint 4

---

## Contexto

La pantalla de evaluación (`EvaluationPage`) permitía al usuario
modificar su evaluación anterior navegando a `/evaluar/{sesionId}`.
Durante las pruebas se detectaron dos problemas:

1. **Problema funcional**: al pulsar el botón de evaluación en el
   historial, la aplicación navegaba fuera de la pantalla de historial,
   lo que obligaba al usuario a pulsar "volver" para retomar la vista
   anterior. El flujo era disruptivo.

2. **Problema de validez del estudio**: el TFG compara la percepción
   humana de los cuatro modelos LLM. Permitir que el usuario corrija
   su evaluación después de haber visto las métricas automáticas
   (latencia, coste, tokens) invalida la naturaleza de "primera
   impresión" del experimento. La evaluación dejaría de medir la
   percepción espontánea del usuario para medir su opinión revisada.

---

## Opciones consideradas

### Opción A — Permitir modificaciones (upsert)

La evaluación existente se actualiza con los nuevos valores. El botón
en el historial dice "Modificar evaluación".

Ventajas: flexible para el usuario; implementación directa con un
endpoint `PUT /evaluaciones/{id}`.
Desventajas: compromete la validez del estudio académico; las
modificaciones pueden estar sesgadas por las métricas automáticas
que el usuario acaba de consultar; complica el análisis estadístico
(¿qué valor es el "real"?).

### Opción B — Bloquear modificaciones (primera impresión)

Una vez guardada la evaluación, no se puede modificar. El botón en
el historial dice "Ver Evaluación" y abre una vista de solo lectura.
Las sesiones no evaluadas muestran el botón "Finalizar Evaluación"
con énfasis visual (rojo parpadeante).

Ventajas: garantiza la integridad de los datos del estudio; coherente
con el diseño académico del TFG; simplifica el backend (no necesita
endpoint de modificación); el énfasis visual motiva al usuario a
completar la evaluación sin distracciones.
Desventajas: el usuario no puede corregir un error en la valoración;
requiere explicar la restricción en la interfaz.

---

## Decisión tomada

Se elige la **Opción B**.

La razón determinante es académica: los datos de evaluación son el
núcleo del estudio comparativo del TFG. Permitir modificaciones
introduciría un sesgo de confirmación (el usuario ajusta su valoración
subjetiva después de ver las métricas objetivas) que invalidaría las
conclusiones del Capítulo 6. Un diseño experimental riguroso requiere
que las evaluaciones subjetivas sean independientes de las métricas
automáticas.

---

## Implementación

### Modal emergente en lugar de navegación

La evaluación se gestiona en `EvalViewModal`, una ventana emergente
que se abre sobre la pantalla de historial. El usuario no pierde el
contexto: el historial permanece visible detrás del modal. El cierre
se puede hacer con el botón ✕, la tecla Escape o clic en el fondo.

Esta decisión de presentación (modal vs. navegación) es independiente
de la decisión de solo lectura, pero ambas mejoran la coherencia del
flujo de uso.

### Sincronización del flag `evaluada` en localStorage

El store Zustand (`historialStore`) mantiene un flag `evaluada` por
sesión en localStorage. Para sesiones que existían antes de implementar
el flag (o que se evaluaron sin actualizar el store), `EvalViewModal`
consulta siempre el servidor al abrirse. Si el servidor devuelve
evaluaciones existentes, el modal llama a `marcarEvaluada` para
sincronizar el estado local. Esto evita que sesiones ya evaluadas
muestren el botón "Finalizar Evaluación" de forma incorrecta.

### Distinción visual entre estados

| Estado de la sesión          | Botón en historial           | Estilo                                    |
|------------------------------|------------------------------|-------------------------------------------|
| Benchmark completado, sin evaluar | Finalizar Evaluación    | Rojo brillante (`#FF0000`), `animate-pulse` |
| Benchmark completado, evaluado    | Ver Evaluación           | Gris neutro (`btn-ghost`)                 |

El estado "completada" del benchmark se muestra como "Ejecutada" en
la interfaz para evitar confusión con el estado "completada" de la
evaluación, que son entidades distintas en el modelo de datos.

---

## Consecuencias

Positivas:
- Los datos del estudio reflejan la percepción de primera impresión,
  que es el indicador de interés académico.
- El análisis estadístico del Capítulo 6 puede asumir que cada
  evaluación es independiente y no está contaminada por revisiones.
- El flujo de historial es más limpio: el usuario no sale de la página.

Trade-offs asumidos:
- Si un usuario comete un error en la valoración (por ejemplo, un clic
  accidental en las estrellas) no tiene forma de corregirlo. Este
  riesgo es bajo dado el diseño del formulario (confirmación explícita
  con botón "Guardar") y aceptable en el contexto de un estudio con
  usuarios voluntarios informados.

Riesgos:
- Si el usuario cierra el modal a mitad de evaluación sin pulsar
  "Guardar", pierde el trabajo parcial. No se considera un riesgo
  grave porque el formulario es corto (cuatro estrellas y un ranking
  de cuatro elementos).
