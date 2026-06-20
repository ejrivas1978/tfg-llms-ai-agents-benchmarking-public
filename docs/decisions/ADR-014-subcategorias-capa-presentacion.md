# ADR-014: Subcategorias de prompt como capa de presentacion, categoria en base de datos

Estado: Aceptado
Fecha: 02/02/2026
Sprint: Sprint 2

## Contexto

El sistema organiza los benchmarks en categorias (razonamiento, codigo,
escritura creativa, preguntas concretas, traduccion, resumen, imagen,
texto libre). Dentro de cada categoria existen 10 subcategorias con
prompts especificos. Se planteo si la subcategoria elegida debia
almacenarse en la base de datos junto a cada sesion de benchmark.

## Opciones consideradas

1. **Almacenar categoria y subcategoria en la BD** — cada BenchmarkSession
   guarda tanto la categoria (ej: "razonamiento") como la subcategoria
   (ej: "cajas_mal_etiquetadas"). Permite filtrar el dashboard por
   subcategoria exacta y ver cuantas veces se ha ejecutado cada prompt.
   El coste es un campo adicional en la tabla y mayor granularidad en
   las graficas, que pueden volverse difusas con 10 x 8 = 80 combinaciones.

2. **Almacenar solo la categoria en la BD, subcategoria solo en UI** —
   la subcategoria determina que prompt predefinido se carga en pantalla,
   pero el registro en BD solo guarda la categoria padre. Las graficas
   del dashboard agregan por categoria (8 barras maximo), lo que es
   manejable visualmente. La subcategoria es un mecanismo de ayuda
   al usuario para no tener que recordar ni escribir los prompts, no
   una dimension de analisis en si misma.

3. **Sin subcategorias, prompt libre siempre** — el usuario escribe el
   prompt directamente. Se pierde la guia estructurada y la reproducibilidad
   de los benchmarks entre evaluadores.

## Decision tomada

Se elige la opcion 2: **la subcategoria es una capa de presentacion**,
solo la categoria se almacena en la base de datos.

La razon principal es la escala de visualizacion. Con 8 categorias, el
dashboard puede mostrar graficas de barras comparativas claras (latencia
media por categoria, coste medio por categoria, puntuacion media por
categoria). Con 80 subcategorias, las mismas graficas serian ilegibles
y el valor analitico marginal no justifica la complejidad.

Las subcategorias cumplen su funcion como herramienta de guia: el usuario
ve opciones concretas, hace clic y el prompt correcto se carga sin
necesidad de memorizarlo ni escribirlo. Esto asegura la reproducibilidad
del prompt (todos los evaluadores usan el mismo texto) sin necesidad de
que la BD tenga ese nivel de detalle.

Para el caso de texto libre, la subcategoria almacenada es "libre",
independientemente de lo que escriba el usuario. Todas las ejecuciones
libres se agrupan bajo esa categoria en las estadisticas.

## Ventaja arquitectonica principal

Separar la subcategoria (capa UI) de la categoria (BD) desacopla dos
ciclos de cambio con velocidades distintas: los prompts de subcategoria
pueden redactarse, reordenarse o sustituirse sin ninguna migracion Alembic
ni riesgo de inconsistencia en datos historicos. El schema queda estable
en su dimension de analisis (8 categorias fijas) mientras la capa de
presentacion evoluciona libremente. Ademas, las agregaciones del dashboard
trabajan siempre sobre un conjunto controlado de 8 dimensiones, lo que
garantiza que cada grafica sea estadisticamente representativa: con 80
subcategorias, muchas celdas tendrian n=1 o n=2, haciendo las medias
no interpretables.

## Consecuencias

Positivas:
- Las medias del dashboard son robustas: minimo ~10 evaluaciones por
  categoria frente a ~1 por subcategoria en 80 combinaciones posibles.
- Schema de BD simple: un campo categoria en BenchmarkSession, sin
  campo subcategoria ni tabla adicional de subcategorias.
- Cambiar o anadir prompts de subcategoria no requiere migracion de BD
  ni produce inconsistencias en el historico de evaluaciones.

Trade-offs asumidos:
- No es posible saber desde el dashboard cuantas veces se ha ejecutado
  el prompt "Cajas mal etiquetadas" especificamente. Esta informacion
  solo es accesible si se exportan los datos brutos.
- Si dos subcategorias de la misma categoria tienen comportamientos muy
  distintos entre modelos, la media de categoria puede enmascarar
  diferencias relevantes. Se asume como limitacion conocida del diseno.

## Nota 09/05/2026 — reversion parcial para CSV de admin

Por requisito del responsable del TFG (reunion 09/05/2026), se anade
una columna `subcategoria_csv` (nullable) a `benchmark_evaluaciones` —
ver migracion `e4f5a6b7c8d9_add_subcategoria_csv` y ADR-009. Se persiste
el nombre human-readable de la subcategoria seleccionada en la UI para
que el CSV de admin sirva al analisis estadistico del estudio.

El campo es **estrictamente informativo**: no se usa en el dashboard,
runner, metricas ni en ningun otro endpoint. Las decisiones originales
de este ADR (no agrupar metricas por subcategoria, mantener flexibilidad
para reordenar prompts sin migraciones, etc.) se mantienen intactas.
