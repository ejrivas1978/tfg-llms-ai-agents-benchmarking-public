# ADR-027 — Unificación de las tablas `users` y `usuarios_app`

**Fecha:** 10/05/2026
**Estado:** Aceptado
**Sprint:** Sprint 4 (S4-77)
**Supersedes:** ADR-024 (en lo que respecta a la separación de tablas; el resto
de decisiones operativas de ADR-024 se mantienen)

---

## Contexto

La aplicación arrastraba dos tablas paralelas para representar a los actores
con sesión:

- `users` — único registro: el administrador. Login con `email + password`.
  Hash bcrypt (passlib). Sin estados ni cuota.
- `usuarios_app` — registros de los usuarios web evaluadores. Login con
  `nick + password`. Mismo hash bcrypt. Estados de ciclo de vida
  (`pendiente_acceso` / `habilitado` / `pendiente_ampliar_tokens`),
  contador de cuota (`cuota_asignada` + `consultas_usadas`), bloqueo
  tras 5 `intentos_fallidos`, y flag `guia_vista`.

Ambas existían por contexto histórico:

- En **Sprint 1** solo había administración; `users` era la tabla de auth.
- En **Sprint 4** aparecieron los usuarios web (ADR-024) en una tabla
  separada por respeto al alcance ya construido para `users` y para no
  arrastrar campos administrativos a un dominio anónimo.

A medida que el sistema maduró, esta separación dejó de aportar valor:

- Los dos tipos de actor comparten todo lo importante (login, JWT,
  hash de contraseña, identidad por nombre).
- El responsable del TFG pidió en la **reunión del 10/05/2026** que
  cualquier usuario web pudiera ser **promovido a administrador** sin
  cambiar su contraseña, y degradado de vuelta cuando convenga. Con
  dos tablas separadas eso obliga a mover registros entre tablas, lo
  que es propenso a errores y rompe el rastro de auditoría
  (`created_at` original, etc.).

## Decisión

Se unifica el esquema en una **única tabla** `usuarios_app` con un flag
**`is_admin`** que distingue los dos roles. La tabla `users` se elimina.

### Esquema final

| Columna             | Tipo            | Notas                                                                |
|---------------------|-----------------|----------------------------------------------------------------------|
| `id`                | INTEGER PK      | autoincrementado                                                     |
| `nick`              | VARCHAR(100)    | UNIQUE NOT NULL — identidad de login para todos                      |
| `password_hash`     | VARCHAR(255)    | bcrypt (passlib) — mismo formato para admin y usuario regular        |
| `email`             | VARCHAR(255)    | UNIQUE NULL — obligatorio si `is_admin=True` (check)                 |
| `is_admin`          | BOOLEAN         | NOT NULL DEFAULT FALSE — distingue el rol                            |
| `estado`            | ENUM            | NOT NULL — válido sólo para `is_admin=False`                         |
| `cuota_asignada`    | INTEGER         | NOT NULL DEFAULT 0 — ignorada mientras `is_admin=True`               |
| `consultas_usadas`  | INTEGER         | NOT NULL DEFAULT 0 — no se incrementa si el actor es admin           |
| `intentos_fallidos` | INTEGER         | NOT NULL DEFAULT 0                                                   |
| `guia_vista`        | BOOLEAN         | NOT NULL DEFAULT FALSE                                               |
| `created_at`        | TIMESTAMPTZ     | NOT NULL                                                             |
| `updated_at`        | TIMESTAMPTZ     | NOT NULL ON UPDATE                                                   |

### Constraint de integridad

```sql
CHECK ((NOT is_admin) OR (email IS NOT NULL))   -- ck_admin_requires_email
```

Garantiza a nivel de BD que un admin sin email es imposible. La capa
de aplicación lo refuerza con `EmailStr` en Pydantic + lookup de
unicidad antes de hacer la promoción.

### Login unificado

- **Endpoint admin** `POST /api/v1/auth/login` recibe `{nick, password}`
  (antes `{email, password}`). El servicio busca por `nick`, verifica
  el hash, y solo emite token si `is_admin=True`. Un usuario regular
  con credenciales válidas obtiene `401` para no filtrar la existencia
  del nick.
- **Endpoint usuario** `POST /api/v1/usuarios/login` sigue usando
  `nick + password`. Rechaza tokens cuyo registro tenga `is_admin=True`
  (un admin no debe acceder como usuario para no romper la cuota).

### Hash de contraseña

Bcrypt para todos los registros (`passlib CryptContext(schemes=["bcrypt"])`).
El docstring previo de `UsuarioApp` mencionaba Argon2 pero la
implementación real era bcrypt; se elimina la divergencia documental
para que el modelo refleje la realidad. La unificación se hace **sin
rotación de hash**: el `password_hash` del admin se copia tal cual.

### Cuota tras promote/demote

- **Promote**: `is_admin=False → True`. La cuota y `consultas_usadas`
  permanecen como estaban en BD. Mientras `is_admin=True` se ignoran:
  `get_actor_benchmark()` devuelve `None` para admins, lo que indica
  al `BenchmarkService` que debe ejecutar sin descontar cuota.
- **Demote**: `is_admin=True → False`. Los contadores reanudan su
  función con los **valores que tenían**. El admin que degrada usa
  los botones existentes "± Ajustar cuota" o "↺ Reset evaluaciones"
  para asignar una cuota nueva. **Diseño explícito**: la degradación
  no toca cuota ni `consultas_usadas`; ese trabajo lo hace el admin
  posterior con las herramientas ya existentes.

### Guard "no degradar al último admin"

Antes de poner `is_admin=False`, el servicio cuenta los admins
restantes. Si solo queda uno (el que se está degradando), devuelve
`HTTP 400` con mensaje "No se puede degradar al ultimo administrador
del sistema". Garantiza que el sistema nunca queda sin acceso
administrativo.

### Rol root vs admin promovido (revisión 10/05/2026)

A petición del responsable del TFG (misma reunión), se introduce un
**segundo flag** booleano `es_root` en `usuarios_app` que distingue
dos clases de administrador:

- **`es_root = True` (root)**: el admin creado por `seed_admin.py`
  durante el despliegue. Tiene **todos los privilegios** del panel
  administrativo, incluyendo el único que solo a él se le permite:
  **promover** un usuario regular a admin y **quitar admin** a otro
  administrador. Es la cuenta canónica del estudio.
- **`es_root = False` (admin promovido)**: cualquier usuario al que
  el root haya promovido. Tiene **todos los demás** privilegios
  administrativos (ver evaluaciones, gestionar usuarios, ajustar
  cuotas, exportar CSV, eliminar evaluaciones, etc.) **excepto**
  los dos endpoints de gestión de roles. No puede crear ni
  destruir admins.

Esta separación impide que un admin promovido pueda crear más admins
o degradar al root, manteniendo el control centralizado de roles en
manos de la cuenta provisionada en el despliegue.

#### Implementación

- Migración Alembic `g6b7c8d9e0f1_add_es_root_admin`: añade columna
  `es_root BOOLEAN NOT NULL DEFAULT FALSE` y marca como root al
  registro existente con `nick='admin'` (idempotente para nuevos
  despliegues).
- `seed_admin.py`: inserta el admin con `es_root=True`.
- `UsuarioAppAdminService.promover_admin()` y
  `degradar_admin()`: aceptan un parámetro `caller: UsuarioApp` y
  devuelven `HTTP 403` si `caller.es_root=False`. La promoción
  nunca propaga `es_root` (los nuevos admins son siempre no-root);
  la degradación rechaza al objetivo si `target.es_root=True`
  (no se puede degradar al root).
- Login: `RespuestaToken` (admin) y `RespuestaTokenUsuarioApp`
  (usuario regular promovido) incluyen un campo `es_root` para que
  el frontend conozca el flag tras el login sin un round-trip
  adicional a `/auth/me`.
- Frontend `adminStore`: extendido con `esRoot: boolean` y
  `setSession(token, esRoot)`. `TablaUsuarios.tsx` oculta los
  botones "Promover" y "Quitar admin" cuando `!esRoot`. El badge
  de rol distingue visualmente "⭐ Root" (rojo, único) de "👑 Admin"
  (amarillo, promovidos).

#### Restricciones complementarias

- **Eliminar al root está prohibido**: el guard de
  `UsuarioAppAdminService.eliminar_usuario()` rechaza con `400`
  cualquier intento de borrar un usuario con `es_root=True`,
  incluyendo el caso del propio root borrándose a sí mismo. La
  única forma de remover al root es manualmente en BD por un
  operador con acceso al servidor.
- **Solo el propietario puede valorar evaluaciones**: aunque un
  administrador (root o promovido) puede ver todas las evaluaciones
  del estudio, solo puede valorar (asignar rating + ranking) las
  que él mismo ejecutó. El servicio `EvaluacionService.crear()`
  ya validaba esto con un `403` si el nickname no coincidía; en
  esta revisión se complementa en frontend ocultando el botón
  "Evaluar" sobre evaluaciones de otros usuarios y mostrando un
  texto neutro "sin valorar".
- **Admins no consumen cuota ni la "ajustan" desde la UI**: los
  botones "± Cuota" y los contadores asociados se ocultan para
  filas con `is_admin=True`. El "↺ Reset" se conserva porque su
  utilidad (borrar evaluaciones del usuario y dejar
  `consultas_usadas=0` para una eventual degradación) sigue
  vigente; el modal explica que la cuota asignada en ese reset
  solo se aplicará si se le quita el rol admin.

## Migración

Migración Alembic `f5a6b7c8d9e0_unificar_users_usuarios_app`:

1. `ALTER TABLE usuarios_app ADD COLUMN email VARCHAR(255) UNIQUE NULL`
2. `ALTER TABLE usuarios_app ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE`
3. `INSERT INTO usuarios_app (nick, password_hash, email, is_admin, estado, ...)
   SELECT username, password_hash, email, true, 'habilitado', ... FROM users`
   — el admin se copia conservando su `created_at` original.
4. `ALTER TABLE usuarios_app ADD CONSTRAINT ck_admin_requires_email
   CHECK ((NOT is_admin) OR (email IS NOT NULL))`
5. `DROP TABLE users`

El `downgrade` recrea `users` con el esquema original y mueve los
admins de vuelta antes de quitar las columnas, así que es reversible
sin pérdida del registro administrativo.

## Consecuencias

### Positivas

- **Modelo más simple.** Una tabla, un repositorio principal, un único
  flujo de hash y de JWT. Menos código duplicado.
- **Operación promote/demote** es trivial: un `UPDATE` en una sola
  fila. Sin migración de datos entre tablas, sin perder `created_at`,
  sin invalidar el contador de evaluaciones realizadas.
- **Guard del último admin** centralizado y explícito.
- **Eliminación de la divergencia documental** sobre el algoritmo de
  hash (Argon2 vs bcrypt) — todos los registros usan bcrypt.

### Trade-offs asumidos

- `email` y `username` (renombrado a `nick`) son ahora **nullable** a
  nivel de columna, con la integridad reforzada vía check constraint.
  Esto es ligeramente más débil que el `NOT NULL` de la tabla `users`
  original, pero el constraint impide tener admins sin email.
- Si en el futuro hace falta un sistema de roles más granular
  (`is_admin` es booleano, no enum), habría que añadir una columna
  `rol` o tabla `roles`. El esquema actual cubre el alcance del TFG
  (un solo rol elevado: admin) sin sobrediseñar.
- Los tests `test_user_repository.py` y `test_router_admin.py`
  (basados en la tabla legacy) se han eliminado en este sprint;
  los reemplazos que cubran la nueva forma quedan como deuda técnica
  para Sprint 4 final.

---

## Archivos afectados

**Backend:**
- `backend/app/models/user.py` — **eliminado**
- `backend/app/models/usuario_app.py` — añadidos `email`, `is_admin`
  y la check constraint
- `backend/app/models/__init__.py` — eliminada exportación de `User`
- `backend/app/repositories/user_repository.py` — **eliminado**
- `backend/app/repositories/usuario_app_repository.py` — añadidos
  `obtener_por_email()` y `contar_admins()`
- `backend/app/services/auth_service.py` — login por nick + guard
  `is_admin=True`
- `backend/app/services/usuario_app_admin_service.py` — métodos
  `promover_admin()` y `degradar_admin()`
- `backend/app/routers/auth.py` — referencias `User` → `UsuarioApp`
- `backend/app/routers/admin.py` — endpoints
  `POST /admin/usuarios/{id}/promover-admin` y
  `POST /admin/usuarios/{id}/quitar-admin`; type hints `User` → `UsuarioApp`
- `backend/app/core/dependencies.py` — `get_current_user` resuelve
  sobre `usuarios_app` con `is_admin=True`; `get_actor_benchmark`
  devuelve `None` para admin
- `backend/app/schemas/auth.py` — `PeticionLoginUsuario.email` →
  `nick`; `RespuestaUsuario` adaptado
- `backend/app/schemas/usuario_app.py` — añadido `PeticionPromoverAdmin`;
  `RespuestaUsuarioApp` incluye `email` e `is_admin`
- `backend/scripts/seed_admin.py` — crea el admin en `usuarios_app`
- `backend/alembic/versions/f5a6b7c8d9e0_unificar_users_usuarios_app.py`
  — migración nueva
- `backend/tests/conftest.py` — fixture `admin_credentials` adaptada
- `backend/tests/test_user_repository.py` — **eliminado**
- `backend/tests/test_router_admin.py` — **eliminado** (cubría flujo legacy)
- `backend/tests/test_dependencies.py` — **eliminado** (mockeaba `UserRepository`)
- `backend/tests/test_auth_service.py` — **eliminado** (login por email)

**Frontend:**
- `frontend/src/components/historial/LoginAdmin.tsx` — campo "Email" →
  "Nick"; mensaje de error actualizado
- `frontend/src/types/auth.ts` — `PeticionLogin` ahora con `nick`;
  `RespuestaUsuarioApp` incluye `email` e `is_admin`
- `frontend/src/services/adminApi.ts` — funciones `promoverAdminUsuario()`
  y `quitarAdminUsuario()`
- `frontend/src/components/historial/TablaUsuarios.tsx` — nueva
  columna "Rol" con badge admin; mostrar email bajo nick para admins;
  botones "👑 Promover" y "↩ Quitar admin"; `PromoteModal` con campo
  email validado; reutilización de `ConfirmModal` para degradar.

**Documentación:**
- `docs/decisions/ADR-024-sistema-control-acceso-usuarios.md` —
  marcado como `Superseded por ADR-027`
- `docs/decisions/ADR-027-tabla-unificada-usuarios.md` — este documento
- `docs/sprints/sprint-04-report.md` — entrada S4-77
- `docs/memoria/chapters/05_implementacion.md` — sección 5.17
