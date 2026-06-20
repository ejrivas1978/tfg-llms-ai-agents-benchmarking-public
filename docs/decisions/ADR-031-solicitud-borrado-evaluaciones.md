# ADR-031 — Flujo de solicitud de borrado de evaluaciones por el usuario

**Fecha:** 16/05/2026
**Estado:** Aceptado
**Sprint:** Sprint 4

---

## Contexto

Los evaluadores del estudio ejecutan comparativas de forma progresiva a lo largo de
varias sesiones. En algunos casos pueden haberse equivocado en la categoría elegida,
haber enviado un prompt incorrecto o simplemente querer retirar una evaluación que
consideran no representativa.

El diseño original del sistema no contemplaba ningún mecanismo de borrado para los
usuarios ordinarios. Solo el administrador podía eliminar evaluaciones desde el panel
`TablaAdmin`. Los usuarios no tenían forma de señalar que una evaluación era errónea
ni de solicitar su retirada.

Surgen dos alternativas: (a) permitir que el usuario borre directamente sus
evaluaciones, o (b) implementar un flujo de solicitud que pase por el administrador,
de modo que el corpus del estudio no pueda modificarse unilateralmente por los
evaluadores.

---

## Opciones consideradas

### Opción A — Borrado directo por el usuario

El usuario puede eliminar sus propias evaluaciones completadas desde su historial
sin intervención del administrador.

**Ventajas:**
- Flujo de UX más sencillo: una acción, efecto inmediato.
- No genera carga de trabajo en el administrador.

**Inconvenientes:**
- Rompe la integridad del corpus del estudio: un evaluador podría eliminar evaluaciones
  con valoraciones bajas para mejorar artificialmente el perfil de uso registrado.
- No hay trazabilidad de qué se eliminó ni por qué.
- Inconsistente con el propósito del TFG, donde los datos recogidos deben ser
  representativos e inalterables por los participantes.

### Opción B — Solicitud de borrado intermediada por el administrador

El usuario puede solicitar el borrado de una evaluación completada. La solicitud
cambia el estado de la evaluación a `solicitud_borrado` y el administrador recibe
una alerta. El administrador decide si aprueba (elimina) o rechaza (restaura a
`completada`).

**Ventajas:**
- El corpus no puede modificarse unilateralmente; el admin actúa como guardián.
- Trazabilidad completa: el estado `solicitud_borrado` queda registrado en la BD.
- El admin puede evaluar si el motivo es legítimo (error de prompt, categoría
  equivocada) antes de actuar.
- Si el admin rechaza, la evaluación vuelve a `completada` sin pérdida de datos.

**Inconvenientes:**
- Añade un estado intermedio al ciclo de vida del enum `SessionStatus`.
- Requiere migración Alembic para añadir el nuevo valor al tipo PostgreSQL.
- La sincronización entre el estado en BD y el `localStorage` de Zustand requiere
  una lógica de resincronización explícita al cargar el historial.

---

## Decisión tomada

Se elige la **Opción B** porque preserva la integridad del corpus del estudio.
El TFG necesita datos fiables: permitir que los evaluadores borren evaluaciones
a voluntad introduciría un sesgo de selección inaceptable. El flujo intermediado
por el admin mantiene la trazabilidad y la coherencia del conjunto de datos,
al coste de una complejidad técnica moderada y asumible.

---

## Consecuencias

### Positivas

- El corpus del estudio es inmune a modificaciones unilaterales por parte de los
  evaluadores.
- El administrador puede distinguir entre errores legítimos (que merece borrar) y
  solicitudes injustificadas (que puede rechazar).
- La trazabilidad completa es útil para el capítulo de análisis de la memoria: se
  puede documentar cuántas evaluaciones fueron solicitadas para borrar, cuántas se
  aprobaron y cuántas se rechazaron.
- El estado `solicitud_borrado` actúa como señal de calidad de datos: las
  evaluaciones en ese estado no computan en las métricas mientras están pendientes,
  lo que evita contaminar el dashboard.

### Negativas y trade-offs asumidos

- El estado `solicitud_borrado` introduce una nueva transición en el ciclo de vida:
  `completada → solicitud_borrado → completada | [borrado]`. El estado `completada`
  deja de ser puramente terminal.
- La desincronización entre `localStorage` (Zustand persist) y la BD es un problema
  estructural: si el admin rechaza la solicitud, el `localStorage` del usuario sigue
  mostrando `solicitud_borrado` hasta que se produzca una resincronización. Solución
  implementada: `useEffect` al montar `HistorialPage` que consulta la BD por cada
  entrada `solicitud_borrado` del store local y actualiza el estado si difiere.
- Evaluaciones en `localStorage` que ya no existen en la BD (borradas externamente)
  pueden producir errores 404 al intentar solicitar borrado. Se maneja con `onError`
  en la mutación TanStack Query: si HTTP 404, la entrada se elimina del store local
  y se muestra un toast informativo.

---

## Implementación

### Backend

**Enum `SessionStatus` (`backend/app/models/enums.py`):**
```python
solicitud_borrado = "solicitud_borrado"
```

**Migración Alembic `r7a8b9c0d1e2_solicitud_borrado_estado.py`:**
```sql
ALTER TYPE sessionstatus ADD VALUE IF NOT EXISTS 'solicitud_borrado';
```
El `downgrade` es no-operativo: PostgreSQL no permite eliminar valores de enums
en uso. La migración es segura de reaplicar (cláusula `IF NOT EXISTS`).

**`BenchmarkEvaluacionRepository.marcar_solicitud_borrado(evaluacion_id, nickname)`:**
- Verifica existencia (404 si no existe).
- Verifica propiedad (`evaluacion.nickname == nickname`; 403 si no).
- Guard idempotencia (409 si ya está en `solicitud_borrado`).
- Cambia `status` y hace `flush`.

**Endpoint usuario `POST /api/v1/usuarios/evaluaciones/{id}/solicitar-borrado`:**
- Requiere JWT de usuario web (`get_current_usuario_app`).
- Delega en el repositorio y hace `commit`.
- Devuelve `{"ok": True, "evaluacion_id": id}`.

**Endpoint admin `POST /api/v1/admin/evaluaciones/{id}/rechazar-borrado`:**
- Requiere JWT de administrador.
- Guard: `status != solicitud_borrado` → 409.
- Cambia `status → completada` y hace `commit`.
- Devuelve `{"ok": True, "evaluacion_id": id, "nuevo_estado": "completada"}`.

### Frontend

**`frontend/src/types/benchmark.ts`:**
```typescript
export type SessionStatus = 'pendiente' | 'en_curso' | 'completada' | 'fallida' | 'solicitud_borrado'
```

**`historialStore.ts`:** tres nuevas acciones:
- `marcarSolicitudBorrado(nick, sesionId)`: cambia `estado → solicitud_borrado`.
- `actualizarEstado(nick, sesionId, estado)`: actualización genérica de estado.
- `eliminarSesion(nick, sesionId)`: elimina la entrada del store local.

**`benchmarkApi.ts`:** función `solicitarBorradoEvaluacion(evaluacionId)`.

**`adminApi.ts`:** función `rechazarBorradoEvaluacion(token, id)`.

**`HistorialPage.tsx` (vista usuario):**
- Botón "Solicitar borrado" con borde rojo y glow en hover (solo evaluaciones
  `completada` con sesión JWT activa).
- Flujo de confirmación via `ConfirmModal` antes de llamar a la API.
- `useMutation` con manejo de 404 (elimina del store local) y error genérico (toast).
- Badge naranja "Borrado solicitado" para entradas en estado `solicitud_borrado`.
- `useEffect` de resincronización al montar: consulta la BD por cada `solicitud_borrado`
  del store y actualiza si el admin ya actuó.

**`TablaAdmin.tsx` (vista admin):**
- Badge naranja clickable con el conteo de `solicitud_borrado` (query separada
  con `refetchInterval: 60_000`).
- Click en el badge filtra la tabla directamente al estado `solicitud_borrado`.
- Resaltado de filas: `solicitud_borrado` recibe fondo `bg-orange-400/10`.
- Botón "Rechazar" (naranja) en la columna de acciones de filas `solicitud_borrado`.
- El botón "Eliminar" preexistente cubre la aprobación de la solicitud (mismo endpoint).

**`EvalViewModal.tsx`:**
- Cuando la evaluación no existe en BD (404), muestra UI de error con botón
  "Eliminar del historial" que llama a `eliminarSesion` del store.

---

## Referencias

- RF-32: El usuario puede solicitar el borrado de una evaluación completada propia.
- RF-33: El administrador puede rechazar una solicitud de borrado.
- RF-20: El administrador puede eliminar una evaluación (preexistente; ahora también
  cubre la aprobación de solicitudes de borrado).
- CU-20: Solicitar borrado de evaluación propia (cu_usuario_04_historial.puml).
- CU-A19: Rechazar solicitud de borrado (cu_admin_02_evaluaciones.puml).
- est_evaluacion.puml: ciclo de vida actualizado con el estado `solicitud_borrado`.
- ADR-015: Historial de sesiones por roles (decisión sobre el historial como localStorage).
- S4-101: Implementación completa del flujo solicitud de borrado.
