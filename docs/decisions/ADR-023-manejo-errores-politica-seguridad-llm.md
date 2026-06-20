# ADR-023 — Manejo de errores de política de seguridad en clientes LLM

**Estado:** Aceptado
**Fecha:** 2026-05-04
**Autor:** Emilio Javier Rivas Fernández

---

## Contexto

Durante las pruebas del sistema con prompts de contenido explícito o violento, se
detectó que los cuatro modelos LLM rechazaban las solicitudes a través de sus
respectivos mecanismos de moderación de contenido. Cada proveedor expone este rechazo
de forma diferente:

- **OpenAI (GPT-4o / DALL-E 3):** HTTP 400 con `"code": "content_policy_violation"` en el body JSON. El SDK lanza `APIStatusError`.
- **Anthropic (Claude):** HTTP 400 con `"type": "invalid_request_error"` y mensaje que menciona "content filtering" o "safety classifiers". El SDK lanza `APIStatusError`.
- **Google (Gemini / Imagen 4):**
  - Texto: HTTP 200 con `finish_reason == "content_filter"` (respuesta vacía sin excepción) **o** HTTP 400 con `APIStatusError`.
  - Imagen: HTTP 200 con campo `predictions` ausente o vacío (sin excepción ni error HTTP).
- **xAI (Grok / grok-imagine-image):** HTTP 400 con `"error": "Generated image rejected by content moderation."`. El SDK lanza `APIStatusError`.

El comportamiento anterior de todos los clientes era capturar estas excepciones con
`except (APIConnectionError, APIStatusError) as exc: str(exc)`, que volcaba el
mensaje crudo de la API en el campo `mensaje_error`. Esto producía salidas como:

```
Error code: 400 - {'code': 'Client specified an invalid argument', 'error':
'Generated image rejected by content moderation.', 'usage':
{'cost_in_usd_ticks': 200000000}}
```

Ese texto es incomprensible para un usuario no técnico y rompe el tratamiento
visual homogéneo que el frontend necesita para identificar rechazos de contenido.

---

## Decisión

Se implementa un **sistema de normalización de errores de política de seguridad**
en la capa de clientes LLM del backend, con detección basada en patrones de texto
y producción de mensajes estandarizados que el frontend puede reconocer de forma
uniforme.

### Principio de diseño

El campo `mensaje_error` de `ResultadoLLM` debe contener siempre un texto legible
por el usuario final. La complejidad del protocolo HTTP de cada proveedor queda
encapsulada en su cliente correspondiente y no se expone a capas superiores.

### Patrón backend (clientes LLM)

Cada método `completar()` y `generar_imagen()` separa `APIStatusError` de
`APIConnectionError` y aplica detección de vocabulario específico:

```python
except APIStatusError as exc:
    raw = str(exc)
    if <patron_censura> in raw.lower():
        mensaje = "Contenido rechazado por las politicas de seguridad de <Proveedor>."
    else:
        body = exc.body
        mensaje = (<campo_message_del_body>) or raw
    return ResultadoLLM(tuvo_error=True, mensaje_error=mensaje, ...)
except APIConnectionError as exc:
    return ResultadoLLM(tuvo_error=True, mensaje_error=str(exc), ...)
```

**Patrones por proveedor:**

| Proveedor | Método | Patrón de detección | Mensaje normalizado |
|-----------|--------|--------------------|--------------------|
| Claude | `completar` | `content filtering`, `safety classifier`, `output blocked`, `filtered`, `safety system`, `content_policy` | `"Contenido rechazado por las politicas de seguridad de Anthropic."` |
| OpenAI | `completar` + `generar_imagen` | `content_policy_violation`, `safety system` | `"Contenido rechazado por las politicas de seguridad de OpenAI (content_policy_violation)."` |
| Gemini | `completar` | `finish_reason == "content_filter"` (sin excepción) + `safety`, `content_policy`, `unsafe`, `violat`, `filtered` | `"Contenido bloqueado por los filtros de seguridad de Google."` |
| Gemini | `generar_imagen` | `predictions` ausente o vacío en HTTP 200 | `"Contenido bloqueado por los filtros de seguridad de Imagen 4."` |
| Grok | `completar` + `generar_imagen` | `content moderation`, `content_policy` | `"Contenido rechazado por las politicas de seguridad de xAI (content moderation)."` |

### Patrón frontend (detección `esCensura`)

La función `esCensura()`, presente en `BenchmarkCard`, `EvalCard`, `BenchmarkPage`
y `EvaluationPage`, detecta los mensajes normalizados por el backend:

```typescript
function esCensura(msg: string | null | undefined): boolean {
  if (!msg) return false
  const m = msg.toLowerCase()
  return m.includes('content_policy') || m.includes('politicas de seguridad') ||
         m.includes('filtros de seguridad') || m.includes('safety system') ||
         m.includes('content moderation')
}
```

El contrato entre backend y frontend es simple: si `mensaje_error` contiene
cualquiera de esas cadenas, la UI trata la respuesta como rechazo por política
y aplica el tratamiento visual especial.

### Comportamiento por superficie UI

| Superficie | Respuesta censurada (parcial) | Todos censurados |
|-----------|-------------------------------|-----------------|
| `BenchmarkCard` | Bloque 🚫 centrado con "Política de seguridad" | Mismo |
| `EvalCard` | Badge 🚫 en lugar de `StarRating`; 0 estrellas auto | Mismo |
| `BenchmarkPage` evaluación inline | Banner rojo + cajita con badge; ranking oculta los censurados | Banner "no evaluación posible"; ranking **oculto**; botón "Cerrar — sin puntuación" |
| `EvaluationPage` | Misma lógica que inline; botón "Cerrar — sin puntuación" | Botón habilitado sin requisitos; vista solo lectura con banner rojo |

### Schema

`rating: int = Field(..., ge=0, le=5)` — se amplió de `ge=1` a `ge=0` para
permitir guardar 0 estrellas cuando el modelo fue censurado. La validación
"mínimo 1 estrella para respuestas no erróneas" se mantiene en el frontend.

---

## Alternativas consideradas

### A — Mostrar el error crudo tal como llega de la API

**Ventaja:** implementación trivial (comportamiento original).
**Desventaja:** incomprensible para el usuario; cada proveedor usa vocabulario
diferente; rompe cualquier lógica de detección en el frontend; no es aceptable
en un sistema destinado a demostración académica.

### B — Detectar censura solo en el frontend

Dejar `mensaje_error` con el texto crudo y parsear el JSON en el frontend para
detectar `content_policy_violation`.

**Ventaja:** no toca el backend.
**Desventaja:** el frontend tendría que conocer el formato exacto de error de
cada proveedor, acoplando la capa de presentación a la estructura interna de
cuatro APIs distintas. Frágil ante cambios de versión del SDK.

### C — Campo booleano dedicado `es_censura` en `ResultadoLLM`

Añadir `es_censura: bool = False` al modelo y activarlo en el backend.

**Ventaja:** semánticamente más explícito; no requiere parseo de cadenas.
**Desventaja:** cambio de schema + migración de base de datos. El patrón de texto
del campo `mensaje_error` ya existente es suficiente para distinguir el caso y no
justifica ese coste. Si en el futuro se necesita consultar estadísticas de rechazo
por proveedor en SQL, sería el momento de añadir este campo.

---

## Consecuencias

- Los mensajes de error de política de seguridad son legibles en cualquier perfil
  de usuario (técnico y no técnico).
- El frontend puede aplicar tratamiento visual homogéneo sin conocer la API de
  cada proveedor.
- Las evaluaciones con todos los modelos censurados se registran correctamente
  (`rating=0`, `rango_preferencia=null`) y son consultables para análisis de
  frecuencia de rechazo por proveedor, categoría y tipo de contenido.
- El sistema queda preparado para añadir un campo `es_censura` en una migración
  futura si el análisis estadístico de rechazos lo requiere (decisión pospuesta).

---

## Archivos afectados — Fase 1

**Backend:**
- `backend/app/llm_engine/clients/claude_client.py` — método `completar`
- `backend/app/llm_engine/clients/openai_client.py` — métodos `completar` y `generar_imagen`
- `backend/app/llm_engine/clients/gemini_client.py` — métodos `completar` y `generar_imagen`
- `backend/app/llm_engine/clients/grok_client.py` — métodos `completar` y `generar_imagen`
- `backend/app/schemas/evaluacion.py` — campo `rating ge=0`

**Frontend:**
- `frontend/src/components/benchmark/BenchmarkCard.tsx` — función `esCensura` + bloque visual 🚫
- `frontend/src/components/evaluation/EvalCard.tsx` — función `esCensura` + badge en rating
- `frontend/src/pages/BenchmarkPage.tsx` — `todasCensuradas`, banner, ranking condicional, botón
- `frontend/src/pages/EvaluationPage.tsx` — `todasCensuradas`, botón, vista solo lectura

---

---

## Revisión: Fase 2 — Automatización del estado fallida y rediseño del flujo (2026-05-04)

### Problema detectado con el diseño de Fase 1

El diseño de Fase 1 presentaba dos problemas graves que solo se evidenciaron al
usar el sistema con datos reales:

**1. Inconsistencia persistente en la base de datos.**
El flujo anterior requería que el usuario pulsara el botón "Guardar como fallida"
para que el backend marcara la evaluación como `fallida`. Si el usuario cerraba el
navegador, navegaba hacia atrás o simplemente ignoraba el botón, la evaluación
permanecía indefinidamente en estado `completada` en la base de datos, a pesar de
no tener ninguna `UserEvaluation` asociada. Esto producía evaluaciones huérfanas
que no eran detectadas por los filtros de calidad del dashboard y podían contaminar
las métricas si en algún momento futuro se relajaban esos filtros.

**2. Contaminación silenciosa de las métricas del dashboard.**
Las evaluaciones con rechazo de contenido tenían estado `completada` y registros
`UserEvaluation` con `rating=0`. Los métodos de agregación del repositorio usaban
subqueries `NOT IN` para excluirlas, lo que:
- Acoplaba la lógica de exclusión a la representación física del rechazo (`rating=0`).
- Hacía los queries más complejos sin necesidad real.
- Era una fuente de sesgo potencial: si por cualquier razón se guardaba un
  `rating=0` legítimo, quedaría excluido de las métricas sin advertencia.

---

### Nueva decisión: el backend marca la evaluación como `fallida` automáticamente

**Principio:** el estado `fallida` es el marcador definitivo de "evaluación no
apta para métricas de calidad". Puede deberse a dos causas: (a) todos los modelos
fallaron con error técnico (comportamiento original), o (b) al menos un modelo fue
rechazado por política de contenido (causa nueva). En ambos casos, la exclusión
de métricas queda garantizada por `status != fallida`, sin necesidad de subqueries
adicionales.

La transición al estado `fallida` ocurre **en el backend**, al final del método
`BenchmarkService.ejecutar()`, antes de devolver la respuesta HTTP. El frontend
no necesita realizar ninguna acción para que la evaluación quede correctamente
clasificada.

### Detección de rechazo por política en el service layer

Se añadió en `BenchmarkService` el método privado `_es_rechazo_politica()` y la
constante de clase `_CENSURA_KW`:

```python
_CENSURA_KW = (
    "content moderation", "content_policy", "politicas de seguridad",
    "filtros de seguridad", "safety system", "contenido bloqueado",
    "contenido rechazado",
)

def _es_rechazo_politica(self, resultado: ResultadoLLM) -> bool:
    if not resultado.tuvo_error or not resultado.mensaje_error:
        return False
    msg = resultado.mensaje_error.lower()
    return any(kw in msg for kw in self._CENSURA_KW)
```

Los patrones coinciden exactamente con los mensajes normalizados que los clientes
LLM producen (Fase 1). No hay acoplamiento adicional: si un cliente normaliza su
mensaje correctamente, la detección en el service funciona sin cambios.

La lógica de transición de estado al final de `ejecutar()` es:

```python
hay_exito  = any(not r.tuvo_error for r in resultados)
hay_censura = any(self._es_rechazo_politica(r) for r in resultados)

if not hay_exito or hay_censura:
    estado_final = SessionStatus.fallida
else:
    estado_final = SessionStatus.completada
```

La condición es **OR**: basta con que **cualquier** modelo haya sido rechazado por
política (aunque el resto hayan respondido correctamente) para que toda la evaluación
quede marcada como `fallida` y quede excluida de las métricas de calidad. El
razonamiento es que una evaluación parcialmente censurada no produce un juicio
comparativo equitativo: el evaluador no puede puntuar a los modelos rechazados y
cualquier ranking o rating resultante sería incompleto y potencialmente sesgado.

### Simplificación de los repositorios

Con el nuevo esquema, `status == completada` es condición **suficiente** para
garantizar que una evaluación:
- Tiene al menos una respuesta LLM válida.
- No tiene ningún modelo rechazado por política de contenido.
- Es apta para ser incluida en métricas de calidad y valoración humana.

Los tres métodos de agregación que antes usaban subqueries `NOT IN` para excluir
evaluaciones con `rating=0` se simplificaron al filtro `status == completada` ya
existente:

- `UserEvaluationRepository.ratings_por_proveedor()` — eliminado NOT IN
- `UserEvaluationRepository.ranking_medio_por_proveedor()` — eliminado NOT IN
- `UserEvaluationRepository.ratings_por_proveedor_y_categoria()` — eliminado NOT IN

### Nuevo método: `tasa_rechazo_por_proveedor()`

Para cuantificar la frecuencia de rechazo por política de cada proveedor, se
implementó el método de agregación:

```python
async def tasa_rechazo_por_proveedor(self) -> list[dict]:
    resultado = await self._db.execute(
        select(
            LLMResponse.provider,
            func.count(LLMResponse.id).label("total"),
            func.sum(
                case(
                    (and_(
                        BenchmarkEvaluacion.status == SessionStatus.fallida,
                        LLMResponse.tuvo_error.is_(True),
                    ), 1),
                    else_=0,
                )
            ).label("rechazos"),
        )
        .join(BenchmarkEvaluacion, BenchmarkEvaluacion.id == LLMResponse.evaluacion_id)
        .where(BenchmarkEvaluacion.status.in_(
            [SessionStatus.completada, SessionStatus.fallida]
        ))
        .group_by(LLMResponse.provider)
    )
    return [row._asdict() for row in resultado.all()]
```

**Denominador:** todas las participaciones de cada proveedor en evaluaciones
completadas o fallidas (excluye las `en_curso` y `pendiente`).
**Numerador:** participaciones con `tuvo_error=True` en evaluaciones con
`status=fallida`. Se usa `fallida` como proxy de rechazo de política porque
es la única causa que marca `fallida` cuando hay respuestas exitosas de otros
proveedores (el otro caso — todos los modelos en error técnico — también produce
`fallida`, pero en ese caso `rechazos/total` no es atribuible a política sino a
indisponibilidad de API, y las tasas de todos los proveedores serían similares).

### Migración Alembic: limpieza de datos históricos (`e1f2a3b4c5d6`)

La transición al nuevo diseño requirió limpiar los registros `rating=0` creados
por el mecanismo anterior. La migración realiza tres operaciones en orden:

1. Actualiza a `fallida` las evaluaciones `completada` que tenían `UserEvaluation`
   con `rating=0` (las creadas por el flujo anterior de censura).
2. Elimina todos los registros `UserEvaluation` con `rating=0`.
3. Restablece la restricción `CHECK (rating >= 1 AND rating <= 5)`.

La restricción de base de datos vuelve a garantizar que no puede almacenarse
un `rating=0` en ninguna circunstancia: la validación de `ge=1` que existía
antes de Fase 1 se restaura completamente.

### Nuevo comportamiento del frontend

Con el nuevo diseño, el frontend no necesita detectar censura ni gestionar el
flujo de "evaluación fallida":

- Cuando el backend devuelve una evaluación con `estado == 'fallida'`, tanto
  `BenchmarkPage` como `EvaluationPage` muestran una vista **informativa**:
  lista de modelos con el icono 🚫 para los que tuvieron error, y un único
  botón "Cerrar y volver al menú" que navega al historial.
- No hay botón de guardar, no hay StarRating, no hay ranking.
- El botón "Cerrar" es puramente navegacional: la evaluación ya está correctamente
  marcada en la base de datos desde que el endpoint `/benchmarks/run` devolvió
  la respuesta.
- La función `esCensura()` y la variable `todasCensuradas` se eliminaron de
  `EvaluationPage`. En `BenchmarkPage` se sustituyeron por la comprobación
  directa `esFallida = sesion?.estado === 'fallida'`.

### Nuevo gráfico en el dashboard: GraficoRestrictividad

El gráfico de rechazo se ubica **dentro de la sección de generación de imagen**
del dashboard, no como sección independiente, porque los rechazos por política
de contenido en este estudio se producen exclusivamente durante la generación de
imágenes (categorías generar, logotipo y modificar). Claude queda fuera de forma
natural al no participar en evaluaciones de imagen. Las evaluaciones de texto
no generan rechazos de contenido en el estudio y mezclarlas en el denominador
introduciría ruido estadístico sin valor analítico.

Características del componente:
- Tipo: `BarChart` de Recharts (barras verticales, colores por proveedor).
- Eje X: nombre del modelo (solo los tres con soporte de imagen).
- Eje Y: tasa de rechazo en porcentaje (0–100 %).
- Tooltip: muestra tasa, rechazos absolutos y total de participaciones.
- Solo se renderiza dentro del bloque imagen condicional; si no hay datos
  de imagen, el bloque completo está oculto.

El tipo `TasaRechazo` se añadió al schema de stats en backend y al tipo
TypeScript en frontend:

```python
# backend/app/schemas/stats.py
class TasaRechazo(BaseModel):
    proveedor: LLMProvider
    total_participaciones: int
    total_rechazos: int
    tasa: float
```

```typescript
// frontend/src/types/stats.ts
export interface TasaRechazo {
  proveedor: LLMProvider
  total_participaciones: number
  total_rechazos: number
  tasa: number
}
```

---

### Consecuencias de Fase 2

- La base de datos no puede quedar en estado inconsistente por abandono del
  usuario: el estado `fallida` se fija en el backend antes de devolver la respuesta.
- Las métricas de calidad del dashboard son correctas por construcción: el filtro
  `status == completada` excluye tanto errores técnicos como rechazos de contenido.
- La restricción `rating >= 1` en base de datos vuelve a ser un invariante fuerte.
- El frontend es más simple: no necesita lógica de detección de censura para
  decidir si mostrar el formulario de evaluación.
- La frecuencia de rechazo por proveedor es ahora una métrica de primer nivel
  del dashboard, no un dato derivado que había que inferir.

---

## Archivos afectados — Fase 2 (2026-05-04)

**Backend:**
- `backend/app/services/benchmark_service.py` — `_es_rechazo_politica()`, `_CENSURA_KW`, lógica de `estado_final`
- `backend/app/repositories/user_evaluation_repository.py` — eliminación NOT IN, nuevo `tasa_rechazo_por_proveedor()`
- `backend/app/repositories/llm_response_repository.py` — eliminación NOT IN
- `backend/app/repositories/benchmark_evaluacion_repository.py` — eliminación NOT IN
- `backend/app/services/evaluacion_service.py` — renombrado `obtener_por_evaluacion(evaluacion_id)`
- `backend/app/services/stats_service.py` — nuevo `_construir_tasa_rechazo()`
- `backend/app/schemas/stats.py` — nuevo `TasaRechazo`
- `backend/app/schemas/evaluacion.py` — revertido `rating ge=1`
- `backend/alembic/versions/e1f2a3b4c5d6_rating_min_uno_revert_censura.py` — migración de limpieza

**Frontend:**
- `frontend/src/types/stats.ts` — nuevo `TasaRechazo`, `tasa_rechazo` en `RespuestaStats`
- `frontend/src/pages/DashboardPage.tsx` — nueva sección `GraficoRestrictividad`
- `frontend/src/pages/BenchmarkPage.tsx` — `esFallida` sustituye a `todasCensuradas`
- `frontend/src/pages/EvaluationPage.tsx` — eliminada `esCensura()`, vista info-only para `fallida`
- `frontend/src/services/evaluacionApi.ts` — `obtenerEvaluacionesPorEvaluacion()`, URL `/evaluacion/{id}`
- `frontend/src/services/benchmarkApi.ts` — renombrado `obtenerEvaluacion()`
- `frontend/src/App.tsx` — param `:sesionId` → `:evaluacionId`
