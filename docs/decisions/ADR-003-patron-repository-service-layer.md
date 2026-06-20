# ADR-003: Patron Repository y Service Layer

Estado: Aceptado
Fecha: 01/01/2026
Sprint: Sprint 1

## Contexto

Con FastAPI, el codigo de acceso a base de datos puede escribirse
directamente en los endpoints (routers). Para un proyecto pequeno esto
es suficiente, pero genera tests que requieren base de datos real y
routers con logica de negocio mezclada con HTTP.

## Opciones consideradas

1. **Acceso directo en routers** — un solo archivo por recurso, menos
   capas, menos ficheros. Suficiente para proyectos de 3-5 endpoints.
   Los tests de integracion requieren base de datos activa. La logica
   de negocio queda acoplada al framework HTTP.

2. **Repository Pattern + Service Layer** — tres capas separadas:
   repositorio (queries SQL), servicio (logica de negocio), router (HTTP).
   Mas ficheros, pero cada capa es testeable de forma aislada.

## Decision tomada

Se elige **Repository Pattern con Service Layer**.

Sin Repository, los tests de servicios requieren base de datos real
o mocks complejos del ORM. Con Repository, los tests de servicios
usan mocks simples de la interfaz del repositorio, sin necesidad
de levantar PostgreSQL en CI.

El Service Layer concentra toda la logica de negocio en un lugar
testeable de forma aislada, sin dependencias de HTTP ni de BD.

Valor academico: demuestra conocimiento de SOLID, especificamente
Single Responsibility (cada capa tiene una unica razon de cambio) y
Dependency Inversion (los servicios dependen de la abstraccion del
repositorio, no de la implementacion SQLAlchemy).

## Consecuencias

Positivas:
- Tests de servicios con mocks del repositorio, sin base de datos
- Logica de negocio aislada y reutilizable desde CLI, tests o background tasks
- Estructura clara que facilita la explicacion en la defensa oral

Trade-offs asumidos:
- Para el tamano actual del proyecto (4 entidades), introduce abstracciones
  que pueden parecer sobredimensionadas. Se justifica por valor academico
  y por la posibilidad de que el proyecto crezca mas alla del TFG.
- Mas ficheros que gestionar: cada entidad tiene modelo, esquema,
  repositorio, servicio y router.

Riesgos:
- El alumno puede tender a poner logica en los routers por inercia.
  Regla: los routers llaman al servicio y devuelven el DTO; nada mas.
