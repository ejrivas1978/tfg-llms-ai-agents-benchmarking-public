# Sprint 2 — Reporte de cierre
Periodo planificado: 01/02/2026 — 28/02/2026
Cierre real: 02/05/2026

---

## Objetivo del sprint

Implementar el motor de llamadas paralelas a los cuatro LLMs y construir el núcleo de la API REST, de modo que `POST /api/v1/benchmarks/run` devuelva cuatro respuestas simultáneas con métricas de latencia, tokens y coste.

---

## Ítems completados

| ID    | Tarea                                              | Puntos | Estado      |
|-------|----------------------------------------------------|--------|-------------|
| S2-01 | BaseLLMClient abstracta con interfaz común          | 3      | Completado  |
| S2-02 | ClaudeClient (Anthropic SDK)                        | 3      | Completado  |
| S2-03 | OpenAIClient (GPT-4o + DALL-E 3)                   | 3      | Completado  |
| S2-04 | GeminiClient (Google AI — texto + Imagen 4)        | 3      | Completado  |
| S2-05 | GrokClient (xAI — texto + grok-imagine-image)      | 2      | Completado  |
| S2-06 | ClientFactory con registro dinámico                 | 2      | Completado  |
| S2-07 | LLMRunner con asyncio.gather paralelo               | 5      | Completado  |
| S2-08 | Métricas: latencia, tokens, coste                   | 3      | Completado  |
| S2-09 | BenchmarkRepository (CRUD sesiones)                 | 3      | Completado  |
| S2-10 | BenchmarkService con lógica de negocio              | 4      | Completado  |
| S2-11 | Endpoint POST /benchmarks/run                       | 3      | Completado  |
| S2-12 | Endpoint GET /benchmarks/{id}                       | 2      | Completado  |
| S2-13 | Rate limiting en /benchmarks/run                    | 2      | Completado  |
| S2-14 | Tests unitarios del LLMRunner (mocks)               | 3      | Completado  |
| S2-15 | Cap. 3 Metodología borrador + UML                   | 3      | No completado |

---

## Velocidad

Comprometidos: **43 pt** | Completados: **40 pt** | Completitud: **93 %**

S2-15 es un ítem *Should* (no *Must*) que se traslada como deuda técnica al Sprint 3 junto con los capítulos de diseño e implementación.

---

## Impedimentos y resoluciones

### 1. Configuración de licencias de pago para los cuatro LLMs
**Problema:** Las comparaciones de modelos exigen el mismo nivel de acceso en los cuatro proveedores. Las cuentas gratuitas de Google AI y xAI presentan límites de rate y cuotas diarias que invalidarían los resultados al introducir sesgos de muestreo.

**Resolución:**
- Se activó una cuenta de facturación en Google Cloud Platform para obtener acceso al tier de pago de Gemini 2.5 Flash.
- Se creó una cuenta nueva en xAI Console (`@ejrivas1978`) con API key de producción.
- Las cuatro keys de pago (Anthropic, OpenAI, Google, xAI) quedan en `backend/.env` y documentadas en `docs/guides/02_configuracion_api_keys_llm.md` con justificación metodológica completa (principio *ceteris paribus*).

**Coste estimado del proyecto:** ~5,28 USD para 200 sesiones de benchmark (tabla detallada en la guía).

---

### 2. Desajuste entre nombres de campos ORM y esquemas Pydantic
**Problema:** Los modelos SQLAlchemy usan nombres en inglés (`category`, `status`, `responses`) mientras que los esquemas Pydantic del proyecto siguen la convención en castellano (`categoria`, `estado`, `respuestas`). El mapeo automático `from_attributes=True` de Pydantic no funciona cuando los nombres difieren.

**Resolución:** Se construyeron los DTOs manualmente en `BenchmarkService._construir_dto()`, mapeando campo a campo entre ORM y schema. Esto garantiza que los cambios futuros en cualquier lado sean explícitos y no silenciosos.

---

### 3. Similitud de Jaccard sin función SQL disponible
**Problema:** No existe una función nativa de Jaccard en PostgreSQL. Calcularla en SQL requeriría extensiones adicionales no previstas.

**Resolución:** Se implementó `jaccard_bigramas()` en Python dentro de `app/llm_engine/metrics.py`. `StatsService._calcular_pares_jaccard()` carga los textos desde la base de datos y calcula todos los pares de proveedores en memoria. Para el volumen esperado de la plataforma (< 1000 sesiones) el rendimiento es adecuado.

---

### 4. Bug en agrupación del heatmap de evaluaciones
**Problema:** `UserEvaluationRepository.ratings_por_proveedor_y_categoria()` agrupaba por `LLMResponse.session_id` en lugar de `BenchmarkSession.category`, lo que devolvía una fila por sesión en vez de una por categoría.

**Resolución:** Se añadió un JOIN a `BenchmarkSession` y se cambió el `group_by` a `BenchmarkSession.category`.

---

### 5. Import `Float` ausente en el modelo ORM
**Problema:** `benchmark_session.py` declaraba el campo `similitud_jaccard_media: Mapped[float | None] = mapped_column(Float, nullable=True)` pero el import de SQLAlchemy solo incluía `DateTime, Enum, String, Text`.

**Resolución:** Detectado y corregido al cerrar el sprint. Se añadió `Float` a la línea de imports.

---

### 6. Auditoría de documentación: eliminación de proveedores descartados
**Problema:** Ocho ficheros del proyecto todavía referenciaban DeepSeek, Azure OpenAI y GitHub Copilot, que fueron descartados antes del Sprint 2 (ver ADR-010).

**Resolución:** Revisión completa de todos los `.md` del proyecto. Los ficheros actualizados fueron:
`README.md`, `docs/memoria/chapters/01_introduccion.md`, `docs/memoria/cap01_introduccion_guia.md`, `docs/guides/01_setup_entorno_local.md`, `docs/decisions/ADR-004-asyncio-gather-llms-paralelo.md`, `skills/agile-sprints.md`, `skills/code-quality.md`, `skills/documentation-tfg.md`.
ADR-010 conserva las menciones a los proveedores descartados como registro histórico de la decisión.

---

## Burndown del Sprint 2

| Semana | Puntos restantes (real) | Puntos restantes (ideal) |
|--------|------------------------|--------------------------|
| Inicio | 43                     | 43                       |
| Sem 1  | 38                     | 32                       |
| Sem 2  | 28                     | 22                       |
| Sem 3  | 16                     | 11                       |
| Sem 4  | 10                     | 0                        |
| Cierre | 3 (S2-15 trasladado)   | 0                        |

El retraso en las semanas 3-4 se explica principalmente por el tiempo invertido en la configuración de las cuatro cuentas de proveedor LLM y la auditoría de documentación, tareas no estimadas en el backlog inicial.

---

## Retrospectiva

**Qué fue bien:**
- El patrón `asyncio.gather(return_exceptions=True)` cumple exactamente la especificación de ADR-004: el benchmark completo no se cancela por el fallo de un proveedor individual.
- La separación Service / Repository permite testear el `LLMRunner` de forma completamente aislada (tests con `AsyncMock`), sin necesidad de base de datos ni credenciales reales.
- El módulo de métricas (`metrics.py`) contiene únicamente funciones puras, lo que facilita los tests unitarios y la reutilización.

**Qué mejorar:**
- La convención de nombres ORM en inglés vs. schemas en castellano generó trabajo extra al construir los DTOs. En el Sprint 3 se definirán los nombres de campos en los schemas *antes* de implementar los servicios para evitar el mismo problema.
- La estimación del backlog no contabilizó el tiempo de obtención de credenciales de los proveedores. En sprints futuros, las tareas de aprovisionamiento de infraestructura externa tendrán ítems dedicados.

**Acción concreta para el Sprint 3:**
Antes de comenzar cualquier servicio del frontend, crear un documento `docs/decisions/schema-field-names.md` con la tabla de equivalencias ORM↔Schema para todos los modelos, de modo que el mapeo sea explícito y consultable.

---

## Estado del producto al cierre del Sprint 2

El alumno puede ejecutar en local la siguiente secuencia completa:

1. `docker-compose up -d postgres` — base de datos operativa
2. `alembic upgrade head` — todas las tablas creadas
3. `POST /api/v1/auth/login` — devuelve token JWT válido para el administrador
4. `POST /api/v1/benchmarks/run` con un prompt y los cuatro modelos seleccionados — devuelve cuatro respuestas en paralelo con latencia, tokens consumidos, coste estimado en USD y similitud de Jaccard entre pares de respuestas
5. `GET /api/v1/benchmarks/{id}` — recupera la sesión completa con todas las respuestas
6. `GET /api/v1/stats` — devuelve el resumen agregado del dashboard
7. `GET /api/v1/admin/sesiones` — lista paginada de sesiones (requiere JWT)

La suite de tests unitarios cubre el módulo de métricas y el runner con cobertura del 100 % de esas dos unidades. No existe todavía ninguna interfaz de usuario.
