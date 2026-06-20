# ADR-010: Stack de LLMs comparados en el benchmark

Estado: Aceptado
Fecha: 02/02/2026
Sprint: Sprint 2

## Contexto

El objetivo del TFG es comparar los modelos de lenguaje de mayor relevancia
comercial y academica en 2025-2026. La seleccion inicial contemplaba seis
proveedores: Claude (Anthropic), GPT-4o (OpenAI), Azure OpenAI, DeepSeek,
Gemini (Google) y Grok (xAI). Durante el diseno del prototipo se revisaron
las capacidades reales de cada modelo frente a los requisitos funcionales,
en particular el soporte de generacion de imagen.

## Opciones consideradas

1. **Los seis proveedores originales** — maxima cobertura. Azure OpenAI es
   en realidad un punto de acceso a los mismos modelos de OpenAI (GPT-4o,
   GPT-4 Turbo) con una capa de infraestructura Microsoft. Compararlo junto
   a GPT-4o nativo duplica el modelo sin aportar diferencia semantica en
   las respuestas. DeepSeek, aunque competitivo en texto, no expone API de
   generacion de imagen, lo que lo excluye de una categoria completa.

2. **Claude + GPT-4o + Gemini 2.5 Flash + Grok 3** — cuatro proveedores
   distintos, cada uno con arquitectura propia y empresa diferente.
   Los cuatro cubren la generacion de texto. Para imagen, GPT-4o (DALL-E 3),
   Gemini (Imagen 4) y Grok (grok-imagine-image) tienen capacidad generativa nativa.

3. **Solo modelos open-source** — descartado porque el TFG compara APIs
   comerciales de produccion, que son las herramientas reales en el mercado.

## Decision tomada

Se selecciona el stack de **cuatro proveedores**: Claude Sonnet 4.6,
GPT-4o, Gemini 2.5 Flash y Grok 3.

Motivos determinantes:
- Los cuatro representan empresas distintas (Anthropic, OpenAI, Google, xAI)
  con arquitecturas y objetivos diferentes, maximizando la diversidad de
  resultados sin redundancias.
- Azure OpenAI se descarta porque ejecuta modelos OpenAI identicos a GPT-4o;
  compararlo aporta datos de latencia de infraestructura Microsoft, no de
  capacidad del modelo, que es el objeto del TFG.
- DeepSeek se descarta por ausencia de generacion de imagen, lo que crearia
  una asimetria en la evaluacion de esa categoria.
- Grok 3 se incorpora como el unico modelo de xAI, empresa con enfoque
  diferenciado y acceso a datos de X (Twitter), relevante para tareas
  de conocimiento factual reciente.

## Consecuencias

Positivas:
- Comparativa homogenea: cuatro modelos participan en todas las categorias
  de texto y tres en imagen, sin huecos asimetricos injustificados.
- Cobertura de las cuatro grandes empresas del sector en 2025.
- Simplificacion de la UI: sin casos especiales por modelo en texto.

Trade-offs asumidos:
- Se pierde la comparativa con DeepSeek, que en benchmarks academicos de
  razonamiento obtiene resultados competitivos con GPT-4o.
- Grok 3 tiene menos documentacion publica que los otros tres proveedores,
  lo que puede dificultar la implementacion del cliente en Sprint 2.
