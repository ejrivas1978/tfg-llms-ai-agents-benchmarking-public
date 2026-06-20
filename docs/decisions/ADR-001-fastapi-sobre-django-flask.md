# ADR-001: FastAPI sobre Django REST Framework y Flask

Estado: Aceptado
Fecha: 01/01/2026
Sprint: Sprint 1

## Contexto

El proyecto requiere un backend Python para una API REST que:
- Ejecuta llamadas concurrentes a cuatro APIs de LLMs en paralelo
- Genera documentacion OpenAPI consumida directamente por el frontend
- Necesita validacion de tipos en todos los parametros de entrada y salida

Las alternativas evaluadas fueron Django REST Framework, Flask con extensiones,
y FastAPI.

## Opciones consideradas

1. **Django REST Framework** — framework maduro, ORM integrado, panel admin
   incluido, ecosistema de plugins amplio. Anade peso de Django para una API
   sin necesidad de renderizado de plantillas ni panel de administracion.

2. **Flask + extensiones** — minimalista, flexible, bien conocido.
   Async nativo requiere quart o adaptaciones; validacion via marshmallow
   o wtforms, sin integracion nativa con type hints.

3. **FastAPI** — disenado especificamente para APIs asincronas modernas.
   Documentacion OpenAPI automatica desde type hints Pydantic.
   Rendimiento en el top-3 de frameworks Python (TechEmpower benchmarks).

## Decision tomada

Se elige **FastAPI**.

Tres razones tecnicas determinantes para este proyecto en concreto:
Primero, el motor de LLMs necesita asyncio nativo para lanzar llamadas
a cuatro APIs en paralelo sin bloquear el event loop; Django y Flask
requieren adaptadores para esto, FastAPI lo hace de forma nativa.
Segundo, FastAPI genera documentacion OpenAPI automatica desde los
type hints y schemas Pydantic, simplificando la integracion con el
frontend y la documentacion de la API para la memoria del TFG.
Tercero, Pydantic v2 esta integrado de forma nativa, garantizando
validacion y serializacion consistentes en todos los endpoints.

## Consecuencias

Positivas:
- asyncio nativo desbloquea el paralelismo de LLMs sin deuda tecnica
- Swagger UI disponible en /api/v1/docs desde el primer endpoint
- Type hints obligan a un contrato claro entre capa de router y service

Trade-offs asumidos:
- Django tiene ecosistema mas maduro: admin, ORM integrado, auth completa.
  FastAPI requiere ensamblar estas piezas manualmente, lo que aumenta el
  setup inicial pero mejora la comprension del alumno de cada componente.
- Menor numero de ejemplos academicos en espanol comparado con Django.

Riesgos:
- FastAPI 0.115 es estable pero versiones menores pueden cambiar la API;
  se mitiga fijando la version exacta en requirements.txt.
