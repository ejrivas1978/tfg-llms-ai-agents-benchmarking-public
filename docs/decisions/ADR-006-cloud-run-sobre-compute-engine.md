# ADR-006: Google Cloud Run sobre Compute Engine VM

Estado: Aceptado
Fecha: 01/02/2026
Sprint: Sprint 2

## Contexto

El sistema necesita un entorno de producción en Google Cloud Platform
accesible desde una URL pública para las demostraciones del TFG. Las
restricciones del contexto académico son distintas a las de un producto
comercial:

- Uso discontinuo: el sistema solo recibe tráfico durante sesiones de
  benchmark planificadas y durante la defensa del TFG. El resto del
  tiempo está completamente inactivo.
- Presupuesto cero: el proyecto no tiene financiación; cualquier coste
  idle debe ser mínimo o nulo.
- Operaciones mínimas: el alumno no puede dedicar tiempo a administrar
  un sistema operativo, aplicar parches de seguridad ni configurar
  un servidor web.
- Demo en directo: en la defensa del TFG se necesita una URL pública
  que funcione en segundos, sin preparación manual previa.

## Opciones consideradas

### 1. Compute Engine VM (e2-micro, always-on)

Ventajas: control total del entorno, sin cold starts, persistencia
de disco local.

Desventajas: coste continuo de ~6-8 €/mes aunque esté ociosa. Requiere
configurar Nginx, gestionar certificados TLS, aplicar actualizaciones
de seguridad del SO y administrar el servidor. Para un TFG con uso
discontinuo, el 95% del coste sería por tiempo idle.

### 2. App Engine Standard

Ventajas: escala a cero, despliegue con `gcloud app deploy`.

Desventajas: requiere adaptar el código FastAPI a las restricciones de
App Engine (handlers, configuración YAML específica). No acepta
imágenes Docker directamente; necesita un runtime específico de Python
de App Engine.

### 3. Google Cloud Run (elegida)

Ventajas: acepta cualquier imagen Docker sin modificaciones. Escala a
cero cuando no hay tráfico: el coste en inactividad es cero. Cada
solicitud levanta una instancia en 1-3 segundos (cold start); para un
TFG con demos planificadas esto es aceptable. HTTPS automático con
certificado gestionado por Google. URL pública permanente desde el
primer despliegue.

Desventajas: cold start de 1-3 segundos tras un período sin tráfico.
No hay estado en disco local (sin problema: el sistema es stateless
por diseño; todo el estado está en Cloud SQL PostgreSQL).

### 4. Firebase Hosting (solo frontend)

Ventajas: gratuito para sitios estáticos, CDN global, HTTPS automático.

Desventaja: solo sirve estáticos; el backend FastAPI necesita igualmente
un servicio de cómputo. Añade un servicio adicional a gestionar.

## Decisión tomada

Se elige Google Cloud Run para desplegar tanto el backend (FastAPI) como
el frontend (Nginx con los estáticos del build de Vite).

Dos contenedores Docker independientes en Cloud Run: uno para la API
(puerto 8000) y otro para el frontend (Nginx puerto 80). Cloud Run
gestiona el escalado, los certificados TLS y la alta disponibilidad
sin ninguna configuración de infraestructura manual.

## Consecuencias

Positivas:
- Coste operativo prácticamente cero fuera de las sesiones de evaluación
  y la defensa del TFG.
- La imagen Docker que funciona en local es exactamente la misma que se
  despliega en producción, sin adaptaciones.
- URL pública permanente disponible para compartir con el tribunal
  evaluador y los participantes del estudio.
- Sin gestión de SO, parches ni configuración de servidor web.

Trade-offs asumidos:
- Cold start de 1-3 segundos tras inactividad. Se mitiga enviando una
  petición de calentamiento manual (GET /api/v1/health) dos minutos
  antes de cualquier demo o sesión de evaluación planificada.
- Cloud Run no tiene disco persistente local; todos los datos van a
  Cloud SQL PostgreSQL. Si se necesitara persistencia local (p.ej.
  caché de respuestas) habría que añadir Cloud Storage o Memorystore.
- El tiempo de despliegue (build Docker + push a Artifact Registry)
  es de 3-5 minutos. No es un bloqueante para el flujo académico.
