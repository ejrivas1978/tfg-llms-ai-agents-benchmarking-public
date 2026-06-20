# ADR-007: Alembic como sistema de migraciones de base de datos

Estado: Aceptado  
Fecha: 02/01/2026  
Sprint: Sprint 1  

---

## Contexto

El proyecto necesita un mecanismo para gestionar la evolución del schema de PostgreSQL a lo largo de los cuatro sprints. El schema cambiará con frecuencia: se añadirán tablas, columnas, índices y restricciones a medida que avance la implementación. Sin un sistema de migraciones, sincronizar la base de datos entre el entorno local, el entorno de CI y el despliegue en Cloud Run requeriría scripts SQL manuales propensos a errores y difíciles de reproducir.

Los requisitos concretos son:

- Compatibilidad nativa con SQLAlchemy 2.x (ORM elegido para el proyecto)
- Capacidad de generar migraciones automáticamente comparando modelos Python con el schema real
- Soporte para `upgrade` y `downgrade` de versiones
- Integración con el ciclo de despliegue en Cloud Run (ejecutar migraciones en el arranque)
- Ecosistema Python sin dependencias externas a la JVM ni a otros runtimes

---

## Opciones consideradas

### 1. Alembic

Herramienta oficial de migraciones del ecosistema SQLAlchemy, mantenida por los mismos autores.

**Ventajas:**
- Integración nativa con los modelos SQLAlchemy: detecta cambios automáticamente con `--autogenerate`
- Migraciones versionadas en ficheros Python, controladas con git
- Soporte completo para `upgrade head` y `downgrade` a cualquier revisión
- Ampliamente adoptado en proyectos FastAPI en producción
- Sin dependencias adicionales fuera del ecosistema Python

**Desventajas:**
- Los ficheros autogenerados a veces requieren revisión manual (no detecta renombrados de columnas, solo borrado + creación)
- Curva de aprendizaje inicial para la configuración de `env.py`

### 2. SQLAlchemy `Base.metadata.create_all()`

Llamada directa que crea las tablas si no existen.

**Ventajas:**
- Sin configuración adicional, funciona con dos líneas de código

**Desventajas:**
- No gestiona cambios incrementales: si una tabla ya existe, no la modifica
- Imposible hacer `downgrade`
- No apto para producción ni para trabajo en equipo
- Descartado por no cubrir el ciclo de vida completo del schema

### 3. Scripts SQL manuales

Ficheros `.sql` versionados a mano en el repositorio.

**Ventajas:**
- Control total sobre el SQL generado

**Desventajas:**
- Trabajo manual propenso a errores y olvidados
- Sin integración con los modelos Python: cualquier cambio en el ORM requiere actualizar también el SQL a mano
- No hay protección contra aplicar el mismo script dos veces
- Descartado por coste de mantenimiento

### 4. Flyway / Liquibase

Herramientas de migraciones populares en el ecosistema Java/Spring.

**Ventajas:**
- Maduras y con soporte empresarial

**Desventajas:**
- Requieren JVM instalada, incompatible con el entorno Python puro del proyecto
- No hay integración con SQLAlchemy: los modelos Python y los scripts de migración vivirían desincronizados
- Descartadas por incompatibilidad de ecosistema

---

## Decision tomada

Se elige **Alembic** porque es la herramienta nativa del ecosistema SQLAlchemy, permite generar migraciones automáticamente desde los modelos Python, y su modelo de versiones encaja directamente con el flujo de despliegue en Cloud Run (`alembic upgrade head` en el arranque del contenedor).

El flujo de trabajo adoptado es:

```
Modificar modelo SQLAlchemy en backend/app/models/
    ↓
alembic revision --autogenerate -m "descripcion"
    ↓
Revisar el fichero generado en backend/alembic/versions/
    ↓
alembic upgrade head
    ↓
Commit del fichero de migración junto con el cambio del modelo
```

---

## Consecuencias

**Positivas:**
- El schema de la base de datos queda versionado en git al mismo nivel que el código
- Cualquier entorno (local, CI, Cloud Run) puede reproducir el schema exacto ejecutando `alembic upgrade head`
- El Sprint 4 puede añadir `alembic upgrade head` como paso previo al arranque del contenedor sin cambios adicionales
- Los ficheros de migración sirven como historial auditable de la evolución del schema

**Trade-offs asumidos:**
- Los ficheros autogenerados deben revisarse antes de aplicarse: Alembic no detecta renombrados de columnas (los trata como `DROP` + `ADD`) ni cambios en datos existentes
- Cada desarrollador debe ejecutar `alembic upgrade head` al actualizar la rama, lo que requiere disciplina en el equipo

**Riesgos:**
- Una migración mal revisada aplicada en producción puede causar pérdida de datos; se mitiga con revisión obligatoria del fichero generado y con el soporte de `downgrade` para revertir si es necesario
