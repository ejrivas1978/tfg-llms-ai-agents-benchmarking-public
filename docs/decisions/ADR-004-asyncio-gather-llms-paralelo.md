# ADR-004: asyncio.gather para ejecucion paralela de LLMs

Estado: Aceptado
Fecha: 01/01/2026
Sprint: Sprint 1

## Contexto

El flujo principal del benchmark envia el mismo prompt a cuatro LLMs
(Claude Sonnet 4.6, GPT-4o, Gemini 2.5 Flash, Grok 3) y espera todas las respuestas.
La latencia tipica de cada llamada es de 2-8 segundos. Ejecutarlos en
secuencia resulta en tiempos de espera inaceptables para el usuario.

## Opciones consideradas

1. **Ejecucion secuencial** — implementacion trivial. Si Claude tarda
   3s, GPT-4o tarda 4s y Grok 3 tarda 5s, el usuario espera 12+s.
   Inaceptable como experiencia de usuario.

2. **ThreadPoolExecutor** — paralelismo real con threads. Mezcla el
   modelo de threads con asyncio, lo que complica el manejo de errores
   y el acceso a la sesion de base de datos (que no es thread-safe).

3. **Celery con workers** — cola de tareas distribuida. Introduce Redis
   o RabbitMQ como broker, workers independientes y un mecanismo de
   polling de resultados. Sobredimensionado para 4 llamadas concurrentes.

4. **asyncio.gather con return_exceptions=True** — paralelismo cooperativo
   nativo de Python. Las cuatro corrutinas se ejecutan en el mismo
   event loop sin threads adicionales. Errores capturados como valores
   de retorno, no como excepciones que cancelen el gather.

## Decision tomada

Se elige **asyncio.gather con return_exceptions=True**.

Con gather, el usuario espera el tiempo del LLM mas lento (tipicamente
5-6s), no la suma de todos. Para cuatro LLMs esto representa un ahorro
de 6-10 segundos por benchmark.

`return_exceptions=True` garantiza que si un proveedor falla (timeout,
API key invalida, servicio caido), los otros tres continuan y el
fallo se registra como `LLMResult(had_error=True, error_message=...)`.
Este es un requisito de usabilidad fundamental: el benchmark no debe
romperse por un fallo parcial.

## Consecuencias

Positivas:
- Tiempo de respuesta igual al del LLM mas lento, no la suma
- Tolerancia a fallos parciales sin cancelar el benchmark completo
- Sin dependencias de infraestructura adicionales (Redis, workers)
- Nativo de Python, coherente con el modelo async de FastAPI

Trade-offs asumidos:
- asyncio.gather no ofrece prioridades ni reintentos automaticos.
  Si se necesita retry con backoff, cada cliente LLM debe implementarlo.
- El paralelismo es cooperativo: una llamada que bloquea el event loop
  (codigo sincrono dentro de una corrutina) afecta a las demas.
  Todos los clientes LLM deben usar httpx.AsyncClient o el SDK async.

Riesgos:
- Timeouts: si un LLM tarda mas de 60s, el endpoint bloquea.
  Se mitiga con timeout explicito en cada cliente LLM (configurable
  en Settings) y cancelacion individual de la tarea que supera el limite.
