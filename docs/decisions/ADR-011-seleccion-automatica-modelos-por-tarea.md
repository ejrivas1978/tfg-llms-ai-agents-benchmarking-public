# ADR-011: Seleccion automatica de modelos segun tipo de tarea

Estado: Aceptado
Fecha: 02/02/2026
Sprint: Sprint 2

## Contexto

Durante el diseno del prototipo de interfaz se incluyo inicialmente un
selector que permitia al usuario activar o desactivar individualmente cada
LLM antes de lanzar el benchmark. El objetivo era dar flexibilidad para
comparar, por ejemplo, solo Claude contra GPT-4o. Al analizar las
implicaciones para el dashboard de estadisticas, se identifico un conflicto
entre flexibilidad y coherencia de los datos acumulados.

## Opciones consideradas

1. **Selector manual libre** — el usuario activa los modelos que quiere
   comparar en cada ejecucion. Maxima flexibilidad. El problema es que
   los datos del dashboard quedan fragmentados: si unas ejecuciones
   incluyen Claude y otras no, las medias de latencia, coste y calidad
   por categoria no son comparables entre sesiones. Las graficas agregadas
   pierden validez estadistica.

2. **Seleccion automatica por tipo de tarea** — el sistema determina que
   modelos participan segun la categoria seleccionada:
   - Texto (todas las categorias): los cuatro modelos siempre.
   - Imagen — Describir (vision): los cuatro modelos.
   - Imagen — Generar / Logotipo / Modificar: los tres modelos con
     capacidad generativa (GPT-4o, Gemini 2.5 Flash, Grok 4.3).
   El usuario no toma esta decision; el sistema la aplica de forma
   transparente mostrando un indicador informativo.

3. **Sin posibilidad de comparacion parcial, siempre los cuatro** —
   ignorar completamente la limitacion de imagen y mostrar Claude
   con un panel de "no soportado". Simplifica la logica pero muestra
   cuatro paneles cuando uno siempre estara vacio en imagen generativa.

## Decision tomada

Se elige la **seleccion automatica por tipo de tarea** (opcion 2).

La razon principal es la integridad de los datos comparativos. Para que
el dashboard pueda mostrar estadisticas significativas (modelo mas rapido,
mas barato, mejor valorado por categoria), todas las ejecuciones de una
misma categoria deben incluir el mismo conjunto de modelos. Si el usuario
pudiera excluir modelos arbitrariamente, cada fila de la base de datos
tendria un subconjunto diferente y las agregaciones careceran de sentido.

Adicionalmente, simplifica la experiencia de usuario: el usuario se
concentra en elegir la tarea y el prompt, no en gestionar modelos.
La pantalla de benchmark pierde un elemento de UI (el selector) sin
perder ninguna funcionalidad real para el proposito del TFG.

## Consecuencias

Positivas:
- Datos del dashboard estadisticamente coherentes: cada categoria siempre
  tiene exactamente el mismo numero de modelos por ejecucion.
- Experiencia de usuario mas simple y enfocada en la tarea.
- Logica de imagen clara y sin paneles vacios injustificados.

Trade-offs asumidos:
- Se pierde la posibilidad de comparar solo dos modelos en una sesion
  especifica. Este caso de uso es secundario para el TFG y puede cubrirse
  en el futuro filtrando los resultados en el dashboard por modelo.
- Si en el futuro se incorpora un quinto modelo, la logica automatica
  debe actualizarse en el backend; no hay control desde la UI.
