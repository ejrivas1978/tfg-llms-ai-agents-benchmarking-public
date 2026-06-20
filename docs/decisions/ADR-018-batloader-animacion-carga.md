# ADR-018: BatLoader — componente de carga animada con murciélago SVG

Estado: Aceptado
Fecha: 03/05/2026
Sprint: Sprint 4

---

## Contexto

Las llamadas a las APIs de los cuatro modelos LLM tienen una latencia
típica de entre 8 y 25 segundos. El prototipo del Sprint 3 no incluía
ningún estado de carga visible: al pulsar "Comparar modelos" la
interfaz permanecía congelada hasta recibir respuesta, lo que generaba
confusión sobre si la acción se había registrado.

Se necesitaba un indicador de carga que cumpliese tres requisitos:

1. Aparecer de forma inmediata al lanzar la petición.
2. Comunicar que se están esperando respuestas de varios modelos en
   paralelo, no solo una operación genérica.
3. Mantenerse coherente con la identidad visual gótica oscura de la
   aplicación.

---

## Opciones consideradas

### Opción A — Spinner o barra de progreso estándar

Un componente de carga genérico (círculo giratorio o barra indeterminada)
sobre la pantalla.

Ventajas: implementación trivial (5 minutos), sin mantenimiento.
Desventajas: no comunica el estado por modelo; rompe la coherencia
visual del tema gótico; experiencia de usuario pobre para esperas largas.

### Opción B — Skeleton cards (cuatro tarjetas en estado de carga)

Mostrar las cuatro tarjetas de modelo con contenido en esqueleto
(líneas grises pulsantes) mientras se espera.

Ventajas: indica exactamente qué se está cargando; patrón conocido por
los usuarios de interfaces modernas.
Desventajas: implica que los modelos responden en paralelo y no permite
indicar cuál ha completado primero; no encaja con el diseño visual.

### Opción C — BatLoader: animación personalizada con tema gótico

Un murciélago SVG articulado dentro de una esfera oscura, con una lista
de modelos y su estado (respondiendo / completado). Cuando la API
responde, cada modelo pasa a "completado" de forma secuencial con una
animación de giro, un toast emergente y un indicador verde.

Ventajas: refuerza la identidad visual; comunica el estado por modelo;
hace la espera percibida más corta al dar feedback de progreso;
diferenciador memorable para la presentación ante el tribunal.
Desventajas: coste de desarrollo mayor (≈ 2 horas); el SVG del
murciélago requiere mantenimiento si se quiere modificar.

---

## Decisión tomada

Se elige la **Opción C**.

La aplicación es un TFG de demostración, no un producto de producción
con miles de usuarios. El coste de implementar la animación es
asumible y el retorno en términos de experiencia de usuario y
diferenciación visual es alto. La animación por modelo también tiene
valor didáctico: comunica con precisión que las cuatro llamadas LLM
son independientes y que el backend las gestiona en paralelo.

---

## Decisiones técnicas internas al componente

### Arquitectura de estados

El componente recibe tres props: `modelos`, `isLoading` y `onComplete`.

- Mientras `isLoading=true` el murciélago flota (`bat-hover`) y las
  alas aletean (`bat-flap-l/r`). La lista muestra todos los modelos
  como "respondiendo...".
- Cuando `isLoading` pasa a `false` se inicia la secuencia de
  completado: giro CSS (`bat-spin-once`), toast, y transición
  del punto de estado a verde, a intervalos de 1.100 ms por modelo.
- Al finalizar la secuencia se llama a `onComplete`, que en el padre
  (`BenchmarkPage`) oculta el overlay y muestra la vista de resultados.

### Renderizado como overlay, no como página separada

El BatLoader se renderiza en un `div` con `position: fixed; inset: 0`
sobre el formulario de benchmark. El formulario permanece visible y
atenuado detrás del overlay (`backdrop-filter: blur`). Esta decisión
refuerza el contexto: el usuario sabe en todo momento que está
esperando el resultado de la petición que acaba de lanzar.

En la primera implementación el loader se renderizaba como una página
separada (sustituyendo todo el contenido). Se descartó porque perdía
el contexto del formulario y creaba un salto visual abrupto.

### Problema de timers cancelados por cleanup de useEffect

El `useEffect` que gestiona la secuencia de completado necesita acceder
a `modelos` y `onComplete`. Si se incluyen en el array de dependencias,
cualquier re-render del padre (que recrea el array y la función inline)
provoca que React ejecute la función de cleanup (que cancela los timers)
antes de ejecutar el nuevo efecto, el cual ve `terminadoRef.current=true`
y no los restablece. Los timers quedan cancelados y la animación se
congela con todos los modelos en "respondiendo...".

Solución: `modelos` y `onComplete` se almacenan en refs
(`modelosRef`, `onCompleteRef`) actualizadas mediante efectos auxiliares
sin dependencias. El efecto de completado solo depende de
`[isLoading, triggerSpin]`. Como `triggerSpin` está memoizado con
`useCallback([])` y `isLoading` es un booleano primitivo, el efecto
solo se re-ejecuta cuando `isLoading` cambia, no en cada re-render.

---

## Ventaja arquitectónica principal

El BatLoader hace visible al usuario la arquitectura paralela del backend
sin texto explicativo: cada indicador de estado (respondiendo → completado)
corresponde directamente a una de las cuatro llamadas independientes de
`asyncio.gather`. Esto convierte un detalle de implementación —que los LLMs
se consultan en paralelo, no en secuencia— en algo perceptible e intuitivo.
Ningún spinner genérico puede comunicar esto; el componente existe
precisamente para hacer ese vínculo explícito.

## Consecuencias

Positivas:
- Feedback de progreso por modelo que comunica con precisión la arquitectura
  paralela del backend (`asyncio.gather` con cuatro llamadas independientes).
- La espera percibida se acorta: el usuario ve avance por modelo en lugar
  de una pantalla congelada durante los 8-25 segundos típicos de latencia.
- Coherencia visual con el tema de la aplicación sin requerir texto
  explicativo sobre la arquitectura subyacente.

Trade-offs asumidos:
- La secuencia de completado es siempre secuencial (modelo 0, 1, 2, 3
  en orden fijo) independientemente del orden real de respuesta de las
  APIs. Esto es una simplificación visual: el backend procesa en
  paralelo pero no existe un canal de streaming que informe al
  frontend del orden real de completado.
- El SVG del murciélago está hardcodeado en el componente. Si se
  quisiera cambiar el personaje habría que reescribir el JSX.

Riesgos:
- En conexiones muy lentas, si la API tarda más de 30 segundos el
  usuario verá el murciélago flotando durante un tiempo prolongado sin
  progreso visible. Mitigación futura: añadir un texto de "tiempo
  estimado" o un contador de segundos.
