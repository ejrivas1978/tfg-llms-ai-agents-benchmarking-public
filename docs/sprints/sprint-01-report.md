# Sprint 1 — Reporte de cierre
Periodo: 01/01/2026 - 31/01/2026
Cierre real: 02/05/2026

---

## Objetivo del sprint

El entorno de desarrollo esta operativo y la estructura base del proyecto existe
en GitHub con los modelos de base de datos implementados y la primera migracion aplicada.

---

## Items completados

| ID    | Tarea                                         | Puntos | Estado      |
|-------|-----------------------------------------------|--------|-------------|
| S1-01 | Instalar VS Code con extensiones              | 1      | Completado  |
| S1-02 | Instalar Python 3.11, Node 20, Git            | 1      | Completado  |
| S1-03 | Configurar PostgreSQL 15 via Docker           | 2      | Completado  |
| S1-04 | Crear repositorio GitHub con estructura base  | 2      | Completado  |
| S1-06 | Disenar schema inicial de base de datos       | 3      | Completado  |
| S1-07 | Implementar modelos SQLAlchemy (4 entidades)  | 3      | Completado  |
| S1-08 | Configurar Alembic y primera migracion        | 2      | Completado  |
| S1-10 | Endpoint GET /api/v1/health funcionando       | 1      | Completado  |
| S1-11 | docker-compose.yml para dev (PostgreSQL)      | 2      | Completado  |

## Items no completados (arrastre a Sprint 2)

| ID    | Tarea                                         | Puntos | Motivo                        |
|-------|-----------------------------------------------|--------|-------------------------------|
| S1-05 | Configurar pre-commit hooks (Black, ESLint)   | 1      | Pospuesto, bajo impacto       |
| S1-09 | Implementar autenticacion JWT                 | 5      | Arrastrado a Sprint 2         |
| S1-12 | Borrador capitulo 1 Introduccion              | 3      | Arrastrado a documentacion    |
| S1-13 | ADR-001 a ADR-004 documentados               | 2      | Arrastrado, decisiones claras |

---

## Velocidad

Comprometidos: 28 pt | Completados: 17 pt | Completitud: 61%

Items Must completados: 8 de 10 (80%)
Items Should completados: 1 de 3 (S1-05, S1-12, S1-13 pendientes)

---

## Impedimentos y resoluciones

**PostgreSQL nativo vs Docker**
Se decidio usar PostgreSQL 15 instalado de forma nativa en Windows en lugar de
dockerizado para los sprints 1 a 3. Docker introduce una capa de red que
complica la depuracion de migraciones en Windows. La contenedorizacion completa
se aplaza al Sprint 4.

**Retraso de inicio**
El sprint arranco con demora respecto a las fechas planificadas. El desarrollo
efectivo comenzo en mayo de 2026. Los sprints restantes (2, 3, 4) se comprimiran
o solaparan para respetar la fecha de entrega.

---

## Retrospectiva

**Que fue bien**
- La separacion en capas (models / schemas / repositories / services / routers)
  quedo clara desde el inicio y no requirio refactorizacion posterior.
- Alembic autogenerate detecto los cuatro modelos sin ajustes manuales.
- La eleccion de asyncpg + SQLAlchemy 2.0 async es correcta para FastAPI;
  no hay deuda tecnica aqui.

**Que mejorar**
- Definir las ADRs antes de escribir codigo, no despues. En este sprint se
  tomaron decisiones (PostgreSQL, Alembic, asyncpg) sin dejarlas por escrito.
- La autenticacion JWT deberia haberse incluido en Sprint 1 ya que desbloquea
  todos los endpoints protegidos de Sprint 2.

**Accion concreta para Sprint 2**
Implementar JWT completo (registro, login, token refresh) en los primeros tres
dias del sprint, antes de tocar el motor LLM, para no bloquear los endpoints.

---

## Estado del producto al cierre

Con lo entregado en este sprint el sistema puede:

- Levantar PostgreSQL y la aplicacion FastAPI con un solo comando
- Confirmar que el servicio esta vivo via `GET /api/v1/health`
- Persistir usuarios, sesiones de benchmark, respuestas LLM y evaluaciones
  humanas gracias al schema ya aplicado en base de datos
- Generar y aplicar migraciones incrementales con Alembic

Lo que aun no puede hacer: autenticar usuarios, ejecutar llamadas a LLMs,
ni mostrar nada en el frontend. Eso es el objetivo de los sprints 2 y 3.

---

## Artefactos entregados

- `backend/app/models/` — cuatro modelos ORM con relaciones y enums
- `backend/alembic/versions/1eca8e05e17b_initial_schema.py` — migracion inicial
- `backend/app/main.py` — app FastAPI con health check y CORS
- `backend/app/core/config.py` — Settings Pydantic con todas las variables
- `backend/app/core/database.py` — motor asyncpg async
- `docker-compose.yml` — PostgreSQL 15 + pgAdmin para dev
- `.env.example` — plantilla con todas las variables documentadas
- `docs/guides/01_setup_entorno_local.md` — guia de instalacion en Windows
