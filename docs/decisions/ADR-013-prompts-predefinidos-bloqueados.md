# ADR-013: Prompts predefinidos bloqueados para garantizar comparabilidad

Estado: Aceptado
Fecha: 02/02/2026
Sprint: Sprint 2

## Contexto

Cada categoria del benchmark tiene subcategorias con prompts disenados
especificamente para evaluar una capacidad concreta de los LLMs. En el
diseno inicial del prototipo, el prompt cargado en el area de texto era
editable: el usuario podia modificarlo antes de enviar. Se detecto que
esta libertad pone en riesgo la validez de la comparativa acumulada.

## Opciones consideradas

1. **Prompt editable siempre** — el usuario puede ajustar cualquier prompt
   antes de enviar. Maxima flexibilidad. El problema es que si dos ejecuciones
   de "Cajas mal etiquetadas" (razonamiento) tienen prompts diferentes,
   no se pueden comparar de forma objetiva en el dashboard. La ejecucion A
   puede haber simplificado el enunciado y la B anadido contexto, haciendo
   que las diferencias de rendimiento sean artefactos del prompt, no del modelo.

2. **Prompts predefinidos bloqueados (readonly), texto libre editable** —
   cuando el usuario elige una subcategoria predefinida, el prompt se muestra
   en modo solo lectura: visible pero no modificable. La categoria "Texto libre"
   es la excepcion deliberada: su proposito es precisamente que el usuario
   escriba lo que quiera. Para traduccion y resumen, el prompt se genera
   automaticamente a partir de las entradas del usuario (texto a traducir,
   opcion de resumen) y tambien se bloquea.

3. **Sin textarea visible, solo mostrar el titulo de la subcategoria** —
   el usuario no ve el prompt que se envia. Reduce transparencia; el evaluador
   no sabe exactamente que pregunta estan respondiendo los modelos.

## Decision tomada

Se elige la opcion 2: **prompts predefinidos en modo readonly, editable
solo en texto libre**.

La transparencia es necesaria: el evaluador debe poder leer el prompt para
juzgar la calidad de las respuestas. El bloqueo garantiza que todas las
ejecuciones de una subcategoria usan exactamente el mismo enunciado,
haciendo las comparativas entre sesiones y entre evaluadores validas.

La categoria "Texto libre" tiene un tratamiento diferenciado porque su
proposito es explorar comportamientos no cubiertos por los prompts
predefinidos. Los datos de texto libre se almacenan bajo la misma
subcategoria "libre" y se comparan con otras ejecuciones libres, lo que
tiene valor relativo aunque los prompts sean distintos.

## Consecuencias

Positivas:
- Integridad de los datos: cada subcategoria predefinida tiene un prompts
  identico en todas las ejecuciones del sistema, haciendo valida la
  agregacion estadistica en el dashboard.
- Claridad para el evaluador: ve exactamente el enunciado enviado.
- La separacion predefinido/libre es conceptualmente clara para el usuario.

Trade-offs asumidos:
- Un evaluador no puede ajustar un prompt predefinido que considere
  suboptimo. Si el prompt tiene un defecto, hay que corregirlo en el
  codigo fuente y volver a ejecutar las comparativas.
- Para las subcategorias de imagen con parte variable (Modificar imagen),
  el prompt incluye la instruccion del usuario, por lo que dos ejecuciones
  de "Modificar imagen" tendran prompts distintos. Se acepta esta variabilidad
  porque el valor comparativo (como cada LLM interpreta la instruccion)
  se mantiene entre ejecuciones del mismo tipo de tarea.
