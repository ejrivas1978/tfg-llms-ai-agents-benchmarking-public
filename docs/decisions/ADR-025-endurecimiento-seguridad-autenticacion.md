# ADR-025 — Auditoría y endurecimiento de seguridad del sistema de autenticación

**Fecha:** 05/05/2026
**Estado:** Aceptado
**Sprint:** Sprint 4 (S4-46)

---

## Contexto

Una vez completado el sistema de control de acceso para usuarios evaluadores (ADR-024),
se realizó una auditoría de seguridad exhaustiva del sistema de autenticación completo,
cubriendo los dos niveles de acceso:

- Administrador: JWT con email + contraseña, almacenado en `adminStore` (Zustand).
- Evaluadores: JWT con nick + contraseña, almacenado en `usuarioStore` (Zustand).

La auditoría examinó el backend (FastAPI, slowapi, bcrypt, JWT HS256) y el frontend
(React, Zustand, localStorage) identificando vulnerabilidades en cuatro categorías:
crítico, medio, bajo y aceptable para el alcance del TFG.

---

## Vulnerabilidades identificadas y decisiones adoptadas

### Crítico — C1: `secret_key` con valor por defecto inseguro

**Hallazgo:** `config.py` define `secret_key: SecretStr = SecretStr("change_me_in_production")`.
Si el `.env` de producción no sobreescribe `SECRET_KEY`, todos los JWT del sistema se
firman con una cadena pública conocida, permitiendo a cualquier atacante fabricar tokens
de administrador válidos.

**Decisión:** No se cambia el código (el valor por defecto es solo un fallback). Se añade
un comentario prominent en `config.py` indicando el comando para generar un valor seguro
(`openssl rand -hex 32`) y se documenta como requisito previo obligatorio en el manual
de despliegue. La verificación en CI/CD (Sprint 4, tarea S4-11) debe incluir un check
que rechace el valor por defecto.

**Archivos:** `backend/app/core/config.py`

---

### Crítico — C2: `/verificar/{nick}` sin límite de peticiones

**Hallazgo:** El endpoint `GET /usuarios/verificar/{nick}` devuelve `{"existe": bool}`
sin ningún decorador `@limitador.limit`. Un atacante podía recorrer un diccionario de
nicks en segundos y mapear todos los usuarios del estudio.

**Decisión:** Se añade `@limitador.limit("20/minute")` al endpoint. Este límite permite
el flujo normal de la UI (una petición por intento de login) pero bloquea la enumeración
automatizada. Se añade también el parámetro `request: Request` requerido por slowapi.

**Archivos:** `backend/app/routers/usuarios.py`

---

### Medio — M1: HTTP 404 vs 401 en login revela si un nick existe

**Hallazgo:** El método `login()` del servicio devolvía HTTP 404 cuando el nick no existía
y HTTP 401 cuando la contraseña era incorrecta. Dos códigos diferentes permiten determinar
si un nick está registrado simplemente observando el código de respuesta, sin pasar por
`/verificar/{nick}`.

**Decisión:** Se unifica: nick inexistente → HTTP 401 con mensaje genérico
`"Credenciales incorrectas."`. El mensaje es idéntico al de contraseña incorrecta, haciendo
indistinguibles ambos casos desde fuera del sistema.

**Archivos:** `backend/app/services/usuario_app_auth_service.py`

---

### Medio — M2: Mensaje de login revela intentos restantes

**Hallazgo:** El detalle del 401 por contraseña incorrecta era:
`"Contraseña incorrecta. Intentos restantes: X."` Este contador funciona como asistente
para un atacante de fuerza bruta, indicándole cuántos intentos le quedan antes del bloqueo.

**Decisión:** El mensaje se sustituye por `"Credenciales incorrectas."` sin ningún
contador. El bloqueo sigue produciéndose a los 5 intentos y devuelve HTTP 423 con
instrucciones para recuperar el acceso, sin revelar el estado interno del contador.

**Archivos:** `backend/app/services/usuario_app_auth_service.py`

---

### Medio — M3: `regenerar-contrasena` sin autenticación — riesgo de DoS selectivo

**Hallazgo:** `POST /usuarios/regenerar-contrasena` solo recibe `nick` + nueva contraseña.
Cualquier persona que conozca el nick de un evaluador puede forzar su cuenta a
`pendiente_acceso`, impidiéndole el acceso hasta que el administrador la reapruebe.

**Análisis:** Añadir autenticación completa al endpoint es incompatible con el caso de
uso legítimo: el usuario que olvidó su contraseña no tiene token. Otras alternativas
(código temporal enviado por email, challenge-response) quedan fuera del alcance del TFG.

**Decisión:** Se reduce el límite de peticiones de `5/minute` a `2/minute` por IP, lo que
dificulta la ejecución de este ataque a escala. La ventana de riesgo residual es aceptable
para el TFG: el administrador gestiona directamente la reaprobación, que es inmediata.
Se documenta como deuda técnica conocida.

**Archivos:** `backend/app/routers/usuarios.py`

---

### Medio — M4: Token de administrador con expiración de 8 horas

**Hallazgo:** `access_token_expire_minutes = 480` (8 horas) aplica al JWT del administrador.
Un token expuesto en un equipo compartido o en un log permanece válido durante 8 horas,
dando una ventana amplia para su explotación.

**Decisión:** Se reduce a `120` minutos (2 horas). Los tokens de evaluadores ya estaban
hardcodeados a 1 hora en el servicio y no se modifican. Se añade comentario en `config.py`
documentando el razonamiento.

**Archivos:** `backend/app/core/config.py`

---

### Bajo — B1: CORS demasiado permisivo (`allow_methods=["*"]`, `allow_headers=["*"]`)

**Hallazgo:** La configuración CORS permitía cualquier método HTTP y cualquier cabecera,
exponiendo métodos no usados (OPTIONS, TRACE, CONNECT) que pueden ser vectores de ataque
en infraestructuras intermedias.

**Decisión:** Se restringe a los métodos que usa el frontend:
`["GET", "POST", "PUT", "DELETE", "PATCH"]` y a las cabeceras:
`["Authorization", "Content-Type"]`.

**Archivos:** `backend/app/main.py`

---

### Bajo — B2: Swagger/OpenAPI accesible en producción

**Hallazgo:** Los endpoints `/api/v1/docs`, `/api/v1/redoc` y `/api/v1/openapi.json`
estaban activos incondicionalmente, exponiendo en producción la documentación completa
de todos los endpoints, parámetros y esquemas.

**Decisión:** Se hace condicional a `environment != "production"`. En desarrollo y
staging el Swagger sigue accesible. En producción (`ENVIRONMENT=production` en Cloud Run)
FastAPI recibe `docs_url=None`, `redoc_url=None` y `openapi_url=None`.

**Archivos:** `backend/app/main.py`

---

## Vulnerabilidades aceptadas para el alcance del TFG

### JWT en `localStorage` (riesgo XSS)

Los tokens de evaluadores y administrador se almacenan en `localStorage` mediante Zustand
persist. Esto los expone a scripts maliciosos inyectados (XSS). La alternativa segura son
cookies `HttpOnly + SameSite=Strict`, que requieren cambios en backend (emisión de cookies)
y eliminan la necesidad del header `Authorization`. Para el TFG en un entorno controlado
y sin contenido generado por usuarios sin sanitizar, el riesgo es aceptable.

### Sin invalidación de tokens en logout

Al hacer logout solo se elimina el token del store del cliente; el JWT sigue siendo válido
en el servidor hasta su expiración. La solución estándar (lista negra en Redis) está fuera
del alcance del TFG. Mitigado parcialmente por la reducción de expiración a 2 horas (M4).

### Sin política de complejidad de contraseñas

Las contraseñas solo requieren un mínimo de 8 caracteres. No hay reglas de complejidad
(mayúsculas, números, símbolos). Para un estudio académico con evaluadores conocidos, este
nivel es suficiente. Se delega la responsabilidad al evaluador mediante instrucciones.

---

## Resumen de cambios implementados

| ID  | Severidad | Cambio | Archivo |
|-----|-----------|--------|---------|
| C1  | Crítico   | Comentario de advertencia + instrucciones para SECRET_KEY | `config.py` |
| C2  | Crítico   | Rate limit 20/min a `/verificar/{nick}` | `routers/usuarios.py` |
| M1  | Medio     | Login: 404 → 401 para nick inexistente | `usuario_app_auth_service.py` |
| M2  | Medio     | Login: eliminar contador "Intentos restantes: X" | `usuario_app_auth_service.py` |
| M3  | Medio     | `regenerar-contrasena`: reducir límite 5→2/min | `routers/usuarios.py` |
| M4  | Medio     | Token admin: reducir expiración 8h → 2h | `config.py` |
| B1  | Bajo      | CORS: restringir métodos y cabeceras | `main.py` |
| B2  | Bajo      | Swagger deshabilitado en `environment=production` | `main.py` |

---

## Archivos afectados

**Backend:**
- `backend/app/core/config.py` — M4, C1
- `backend/app/main.py` — B1, B2
- `backend/app/routers/usuarios.py` — C2, M3
- `backend/app/services/usuario_app_auth_service.py` — M1, M2

**Documentación:**
- `docs/decisions/ADR-025-endurecimiento-seguridad-autenticacion.md` — este documento
- `docs/guides/seguridad-autenticacion.md` — guía operacional derivada de esta auditoría
