# ADR-002: PostgreSQL sobre MySQL

Estado: Aceptado
Fecha: 01/01/2026
Sprint: Sprint 1

## Contexto

El proyecto almacena sesiones de benchmark con evaluaciones que incluyen
arrays de etiquetas (tags) y estadisticas agregadas para el dashboard.
Se evaluaron PostgreSQL 15 y MySQL 8 como motores relacionales.

## Opciones consideradas

1. **MySQL 8** — ampliamente conocido en entornos academicos y hosting
   compartido. Soporte para JSON desde la version 5.7. Arrays nativos
   no disponibles; se simulan con JSON o tablas auxiliares.

2. **PostgreSQL 15** — motor de base de datos relacional avanzado con
   tipos nativos ARRAY y JSONB, vistas materializadas, y soporte completo
   en Cloud SQL de GCP. Mayor presencia en arquitecturas modernas.

## Decision tomada

Se elige **PostgreSQL 15**.

Tres caracteristicas nativas que MySQL implementa con limitaciones:

El tipo `ARRAY` de PostgreSQL almacena las etiquetas de evaluacion
(campo `tags` en `user_evaluations`) directamente, consultable con
operadores `&&` (overlaps) y `@>` (contains) sin tabla auxiliar.

Las vistas materializadas precalculan las estadisticas del dashboard
(latencia media por modelo, distribucion de ratings) sin ejecutar
agregaciones pesadas en cada carga de pagina.

SQLAlchemy tiene soporte mas completo para tipos propios de PostgreSQL
(ARRAY, JSONB, UUID nativo) que para sus equivalentes en MySQL.

## Consecuencias

Positivas:
- Tipo ARRAY nativo elimina la tabla `evaluation_tags` del schema
- Consultas del dashboard mas simples y eficientes con agregaciones nativas
- Cloud SQL en GCP soporta PostgreSQL de primera clase en Cloud Run

Trade-offs asumidos:
- MySQL tiene mayor presencia en hosting compartido economico y mayor
  familiaridad en el ambito academico espanol.
- Setup inicial de PostgreSQL en Windows es ligeramente mas complejo que
  MySQL; se mitiga con el docker-compose del proyecto.

Riesgos:
- Si el proyecto migrara a hosting compartido basico, PostgreSQL podria
  no estar disponible. Cloud Run + Cloud SQL elimina este riesgo en prod.
