# ADR-024 — Sistema de control de acceso para usuarios evaluadores

**Fecha:** 05/05/2026
**Estado:** Superseded por ADR-027 (10/05/2026) — esquema de tabla unificado
**Sprint:** Sprint 4 (S4-38 a S4-44)

---

## Contexto

El TFG requiere que varios evaluadores externos (compañeros, profesores) utilicen
la aplicación de forma controlada durante el periodo de recogida de datos. Sin
ningún mecanismo de control:

- Cualquier persona con acceso a la URL podría ejecutar comparaciones, consumiendo
  créditos de las APIs de LLM (Claude, OpenAI, Gemini, xAI) sin límite.
- No existía forma de identificar de qué evaluador provenía cada comparación
  cuando múltiples personas usaban el sistema simultáneamente.
- El sistema anterior usaba un campo libre de nickname sin autenticación, lo que
  permitía suplantar cualquier evaluador con solo conocer su nick.

El sistema de autenticación existente (JWT con email+contraseña) solo cubría al
administrador. Los evaluadores eran completamente anónimos.

---

## Ventaja arquitectónica principal

El sistema de dos niveles desacopla dos problemas que en otras soluciones
van acoplados: la **identidad del evaluador** (¿quién eres?) y el **control
del gasto** (¿cuánto puedes consumir?). Manejarlos por separado permite
gestionar cada dimensión de forma independiente: el investigador puede
ampliar la cuota de un evaluador sin tocar su identidad, o revocar el
acceso sin afectar a otros evaluadores. La alternativa de lista blanca
simple o contraseña compartida solo resuelve la identidad, no el gasto.
La alternativa OAuth resuelve la identidad pero requiere infraestructura
externa y no tiene semántica de cuota. El claim `"tipo": "usuario_app"`
en el JWT permite que la dependencia `get_actor_benchmark` tome la
decisión de cuota en memoria, sin consulta adicional a la BD en cada
petición de benchmark.

## Decisión

Se diseñó un sistema de control de acceso de dos niveles:

### Nivel 1 — Identidad verificada con contraseña

Cada evaluador se registra con un nick único y una contraseña. El nick es su
identidad pública en el estudio; la contraseña impide suplantación.

El registro no es instantáneo: genera una solicitud en estado
`pendiente_acceso` que el administrador debe aprobar antes de que el
evaluador pueda ejecutar comparaciones. Este flujo garantiza que solo
participan en el estudio las personas seleccionadas por el investigador.

### Nivel 2 — Cuota de consultas gestionada por el administrador

Cada cuenta aprobada tiene una cuota de comparaciones asignada por el
administrador. Cuando la cuota se agota, el evaluador puede solicitar
una ampliación; el administrador la concede manualmente.

Esta cuota sirve dos propósitos:
1. Limitar el gasto en APIs LLM a lo estrictamente necesario para el estudio.
2. Incentivar que cada evaluador dedique atención real a cada comparación en
   lugar de ejecutarlas masivamente.

### Ciclo de vida de una cuenta de evaluador

```
Registro → pendiente_acceso → [admin aprueba] → habilitado
                                                     ↓
                                             [cuota agotada]
                                                     ↓
                                    [usuario solicita ampliación]
                                                     ↓
                                        pendiente_ampliar_tokens
                                                     ↓
                                        [admin amplía cuota]
                                                     ↓
                                               habilitado
```

Adicionalmente:
- 5 intentos de login fallidos consecutivos bloquean la cuenta (HTTP 423).
- El usuario puede regenerar su contraseña; la cuenta vuelve a
  `pendiente_acceso` para que el administrador la reapruebe.
- Si el administrador elimina una cuenta, todas sus evaluaciones se
  eliminan en cascada para mantener la integridad del estudio.

### Tokens JWT diferenciados

Los JWT de los evaluadores incluyen el claim `"tipo": "usuario_app"` para
distinguirlos de los JWT de administrador (que no incluyen ese claim).
La dependencia `get_actor_benchmark` inspecciona este claim para:
- JWT con `tipo = "usuario_app"` → devuelve `UsuarioApp`, aplica cuota.
- JWT sin `tipo` (admin) → devuelve `None`, cuota ilimitada.

---

## Alternativas consideradas

### A. Registro abierto sin aprobación previa

Los evaluadores se registran y acceden directamente sin intervención
del administrador.

**Descartado:** sin aprobación, cualquier persona que encuentre la URL
podría participar en el estudio, contaminando los datos con evaluaciones
no controladas.

### B. Contraseña única compartida para todos los evaluadores

Una sola contraseña de acceso que el administrador comunica a los
participantes seleccionados.

**Descartado:** no permite distinguir evaluaciones por evaluador individual,
no permite revocar acceso a un evaluador concreto sin afectar a los demás,
y no da información sobre quién ejecutó qué comparación.

### C. Usar el mismo sistema JWT que el administrador (email + contraseña)

Crear cuentas de administrador adicionales para cada evaluador.

**Descartado:** confunde los roles del sistema; los evaluadores no necesitan
acceso a las funciones de administración. Además, el email como identificador
es innecesario en un estudio académico donde un nick es suficiente.

### D. Sistema OAuth con Google / GitHub

Autenticación delegada a un proveedor externo.

**Descartado:** introduce dependencia de un servicio externo, requiere
configuración de app OAuth por proveedor, añade fricción innecesaria para
los evaluadores del TFG, y no resuelve el problema de la cuota.

---

## Consecuencias

### Positivas

- El investigador controla exactamente quién participa en el estudio y
  cuántas comparaciones puede realizar cada participante.
- El gasto en APIs LLM queda acotado por la suma de cuotas asignadas.
- Cada comparación queda vinculada a un evaluador identificado, lo que
  permite análisis de consistencia inter-evaluador en el Capítulo 6.
- El sistema de bloqueo por intentos fallidos protege contra fuerza bruta
  en contraseñas.

### Negativas

- El flujo de registro requiere intervención del administrador, lo que
  introduce latencia entre el registro y el primer uso. Para el TFG esto
  es aceptable (el investigador gestiona directamente la aprobación).
- Los JWT de 1 hora de duración obligan a los evaluadores a reconectarse
  en sesiones largas. Se consideró aumentar la duración pero se mantuvo
  en 1h como práctica recomendada de seguridad.

### Deuda técnica conocida

- El historial del evaluador se almacena en `localStorage` (Zustand persist),
  no en el backend. Esto significa que al cambiar de dispositivo el
  evaluador no ve su historial anterior. Para los objetivos del TFG
  (evaluaciones en un único entorno controlado) esto es aceptable.
- La contraseña se verifica con bcrypt; no hay política de complejidad más
  allá del mínimo de 8 caracteres.

---

## Archivos afectados

**Backend:**
- `backend/app/models/usuario_app.py` — modelo ORM
- `backend/app/models/enums.py` — enum `EstadoUsuarioApp`
- `backend/app/repositories/usuario_app_repository.py` — repositorio
- `backend/app/services/usuario_app_auth_service.py` — lógica de autenticación
- `backend/app/services/usuario_app_admin_service.py` — lógica de gestión admin
- `backend/app/routers/usuarios.py` — endpoints evaluadores
- `backend/app/routers/admin.py` — endpoints admin (sección usuarios)
- `backend/app/core/dependencies.py` — `get_current_usuario_app`, `get_actor_benchmark`
- `backend/app/services/benchmark_service.py` — integración cuota
- `backend/alembic/versions/8515120b6649_add_usuarios_app_table.py` — migración

**Frontend:**
- `frontend/src/pages/NickPage.tsx` — flujo de autenticación
- `frontend/src/store/usuarioStore.ts` — estado de sesión del evaluador
- `frontend/src/services/usuarioApi.ts` — cliente API evaluadores
- `frontend/src/services/benchmarkApi.ts` — interceptor JWT
- `frontend/src/components/historial/TablaUsuarios.tsx` — panel gestión admin
- `frontend/src/pages/HistorialPage.tsx` — pestañas admin + pestana=usuarios
- `frontend/src/types/auth.ts` — tipos TypeScript

---

## Nota 10/05/2026 — superseded por ADR-027

A petición del responsable del TFG (reunión 10/05/2026), las dos tablas
`users` (admin) y `usuarios_app` (web) se unifican en una sola tabla
`usuarios_app` con un flag `is_admin`. Las decisiones operativas de
este ADR (estados, cuota, bloqueo por intentos, etc.) se mantienen
intactas; lo que cambia es la **forma del registro**: ahora el admin
también vive en `usuarios_app`, comparte hash y forma de login
(nick + password), y se pueden promover/degradar usuarios entre roles
sin migración de datos. Ver **ADR-027** para los detalles y la migración
Alembic `f5a6b7c8d9e0`.
