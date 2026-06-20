# ADR-034 — Generación de imagen de Gemini con gemini-2.5-flash-image (Nano Banana) en sustitución de Imagen 4

**Fecha:** 05/06/2026
**Estado:** Aceptado
**Sprint:** Sprint 4

---

## Contexto

Hasta ahora la generación de imagen (txt2img) del proveedor Gemini usaba el
modelo **Imagen 4** (`imagen-4.0-generate-001`) a través de su endpoint REST
nativo `:predict`. La edición de imagen (img2img) ya usaba un modelo distinto,
**`gemini-2.5-flash-image`** (alias "Nano Banana"), vía el endpoint
`generateContent`.

El 04/06/2026 la generación de imagen de Gemini empezó a fallar siempre. El
diagnóstico (reproducción directa contra la API) descartó todas las causas del
lado del proyecto:

- **Texto** (`gemini-2.5-flash`): responde HTTP 200 → la API key es válida y la
  cuenta no está bloqueada.
- **Modelo**: `imagen-4.0-generate-001` sigue existiendo y aceptando `predict`.
- **Facturación**: la key del `.env` pertenece al proyecto
  `tfg-llm-benchmarking`, en **Nivel 1 · Pospago** (de pago).
- **Cuota / rate limit**: el panel de Google muestra un uso de **2/10 RPM** y
  **15/70 RPD** para Imagen 4 Generate; muy por debajo del límite.

Sin embargo, las llamadas a `imagen-4.0-generate-001:predict` devolvían de forma
persistente **429 `RESOURCE_EXHAUSTED`** y **503 `UNAVAILABLE`** (5 intentos
espaciados → 0 imágenes generadas). En la API de Gemini, `RESOURCE_EXHAUSTED`
también se devuelve cuando se agota la **capacidad compartida de servidor** del
modelo, no solo la cuota del cliente. Conclusión: **incidencia de capacidad de
Google con Imagen 4 Generate**, fuera del control del proyecto, en plena recta
final del estudio (entrega 15/06/2026).

En la misma cuenta, `gemini-2.5-flash-image`:

- Genera imagen desde **solo texto** (verificado: HTTP 200 con PNG en base64).
- Tiene mucho **más margen de rate limit**: **500 RPM / 2K RPD** frente a los
  10 RPM / 70 RPD de Imagen 4.
- **Ya está integrado** en el cliente (se usaba para editar).

## Opciones consideradas

1. **Esperar a que Google estabilice Imagen 4.** Sin coste de desarrollo, pero
   no se controla el plazo y el estudio se entrega el 15/06. Riesgo alto.
2. **Activar/ampliar facturación.** Ya está en Tier 1 de pago; el problema no es
   de cuota sino de capacidad del modelo, así que pagar más no lo resuelve.
3. **Cambiar la generación a `gemini-2.5-flash-image` (Nano Banana).** Funciona
   ya, con más cuota y sin dependencia nueva. Cambia el modelo de generación de
   imagen de Gemini a mitad de estudio.

## Decisión

Se elige la **opción 3**: `generar_imagen()` del `GeminiClient` pasa a usar
`gemini-2.5-flash-image` vía `generateContent` (prompt de solo texto con
`responseModalities: ["TEXT", "IMAGE"]`), el mismo modelo y endpoint que ya
empleaba `editar_imagen()`. Se itera `candidates[0].content.parts[]` para quedarse
con la part que trae `inlineData` (la imagen) y descartar la part de texto.

Con esto, **generación y edición de imagen de Gemini usan el mismo modelo**, lo
que además simplifica el cliente.

Como un mismo modelo pasa a servir para generar y editar (también ocurría ya con
`gpt-image-1` en OpenAI), la detección del modo en
`LLMResponseRepository.costes_imagen_por_proveedor_y_modo` deja de basarse en el
`model_name` y pasa a derivarse de la **subcategoría** de la evaluación
(`subcategoria_csv == 'modificar'` → editar; `generar`/`logotipo` → generar). Esto
corrige además un error latente por el que las generaciones de OpenAI con
`gpt-image-1` se contabilizaban como ediciones.

Para mantener la coherencia del estudio se **homogeneíza el histórico**: las
evaluaciones de imagen de Gemini previas (que tenían `model_name =
imagen-4.0-generate-001`) se actualizan a `gemini-2.5-flash-image`, de modo que el
dashboard y el CSV muestran todo como si se hubiera generado con el modelo nuevo.

## Consecuencias

**Positivas:**
- La generación de imagen de Gemini vuelve a funcionar de inmediato.
- Mayor robustez frente a picos: 500 RPM en lugar de 10.
- El cliente queda más simple (un único modelo de imagen) y el modo generar/editar
  se calcula de forma fiable a partir de la subcategoría.

**Decisiones de datos asumidas:**
- **Tarifa:** se ajusta `precio_imagen_generar_usd_por_imagen` de Gemini de $0.04
  a **$0.039** (precio de Nano Banana) directamente sobre la fila vigente
  (`tarifas_llm` id 7), **sin** versionar una tarifa nueva, por ser una diferencia
  residual ($0.001/img). Queda igualada a `imagen_editar`.
- **Backfill:** las evaluaciones de imagen de Gemini existentes se actualizan a
  `model_name = gemini-2.5-flash-image` y `cost_usd` de $0.04 a $0.039. Como el
  coste del dashboard se lee del `cost_usd` persistido en cada `LLMResponse` (no
  se recalcula desde la tarifa), este backfill es necesario para que el histórico
  refleje el modelo y precio nuevos.
- Debe reflejarse como incidencia/limitación en la memoria (cap. 7 y 8).

**Riesgos:**
- Nano Banana es un modelo *preview*; su disponibilidad y precio pueden cambiar.
  El diseño de tarifas versionadas (ADR-028) permite ajustarlo sin tocar código.
