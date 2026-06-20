# ADR-008: JWT stateless para autenticación del administrador

Estado: Aceptado
Fecha: 01/02/2026
Sprint: Sprint 2

## Contexto

El sistema tiene dos tipos de actores con requisitos de autenticación
muy distintos:

- **Evaluadores anónimos**: se identifican con un nickname libre
  almacenado en localStorage. No tienen cuenta, contraseña ni sesión
  en el servidor. Esta decisión está documentada en ADR-012.
- **Administrador**: único usuario con acceso a operaciones destructivas
  (borrado de sesiones, reset del estudio) y a la vista completa del
  historial. Necesita autenticación real.

El sistema se desplegará en Cloud Run con potencial de múltiples instancias
activas simultáneamente durante picos de uso.

## Opciones consideradas

### 1. Sesiones en base de datos (session-based auth)

Ventajas: revocación inmediata al eliminar el registro de sesión,
modelo mental sencillo.

Desventajas: requiere consultar la base de datos en cada petición
autenticada para validar la sesión. En Cloud Run con múltiples
instancias, todas las instancias deben acceder a la misma BD para
verificar la sesión, lo que añade latencia y acoplamiento. Además,
la base de datos PostgreSQL ya tiene suficiente carga con las sesiones
de benchmark.

### 2. Sesiones en Redis

Ventajas: validación rápida sin tocar PostgreSQL, compartible entre
instancias.

Desventajas: añade un servicio de infraestructura adicional (Cloud
Memorystore en GCP, ~10 €/mes mínimo). Para un único usuario
administrador en un TFG, el coste y la complejidad son
completamente desproporcionados.

### 3. JWT stateless (elegida)

Ventajas: el token se valida en cada instancia sin contactar ningún
servicio externo (solo se verifica la firma con la clave secreta
almacenada en Secret Manager). Sin estado en servidor, compatible
con Cloud Run multi-instancia de forma nativa. La biblioteca
`python-jose` implementa la verificación en microsegundos.

Desventajas: los tokens no se pueden revocar antes de su expiración.
Con un token de vida de 60 minutos y un único usuario administrador,
el riesgo es aceptable: en el peor caso, si el administrador cierra
sesión manualmente, el token robado tiene una ventana de 60 minutos.

### 4. OAuth 2.0 con proveedor externo (Google, GitHub)

Ventajas: sin gestión de contraseñas, autenticación robusta.

Desventajas: introduce dependencia de un servicio externo para una
aplicación académica con un único usuario administrador. Si el
proveedor tiene una interrupción durante la defensa del TFG, el
administrador no puede autenticarse. La complejidad de implementar
el flujo OAuth está desproporcionada para el alcance del proyecto.

## Decisión tomada

Se elige JWT stateless con `python-jose` y `passlib` para el hash de
contraseñas (bcrypt). Tokens de acceso con expiración de 60 minutos.

El secreto de firma se almacena en GCP Secret Manager en producción y
en el fichero `.env` en desarrollo local (nunca en el repositorio).

El endpoint `POST /api/v1/auth/login` verifica las credenciales del
administrador contra la tabla `users` de PostgreSQL (único registro
con `role = "admin"`) y devuelve el JWT. Los endpoints protegidos
verifican el token con un `Depends(get_current_admin_user)` de FastAPI.

## Consecuencias

Positivas:
- Sin consultas a la base de datos en la validación de cada petición
  autenticada: toda la verificación ocurre en memoria.
- Compatible con Cloud Run multi-instancia sin ninguna configuración
  adicional.
- La implementación ocupa menos de 50 líneas en `core/security.py`.
- Patrón estándar en el ecosistema FastAPI; ampliamente documentado.

Trade-offs asumidos:
- Los tokens no se pueden revocar antes de expirar. Aceptable porque:
  (a) solo hay un usuario administrador, (b) los tokens duran 60 min,
  (c) el TFG no maneja datos sensibles de terceros.
- Ausencia de refresh tokens en v1. Al expirar el token, el administrador
  debe volver a iniciar sesión. Con sesiones de uso de 1-2 horas como
  máximo, el impacto es mínimo.
- La contraseña del administrador se crea manualmente mediante un
  script `seed_admin.py` que hashea la contraseña con bcrypt y la
  inserta en la BD. No hay registro por formulario.
