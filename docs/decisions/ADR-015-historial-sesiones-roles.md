# ADR-015: Historial de sesiones diferenciado por rol

Estado: Aceptado
Fecha: 02/02/2026
Sprint: Sprint 3
DEF relacionada: DEF-001-historial-sesiones.md

## Contexto

La aplicacion tiene dos tipos de actores con necesidades distintas respecto
al historial de sesiones de benchmark: el evaluador anonimo (nick) que
quiere consultar sus propias comparativas pasadas, y el administrador que
necesita supervisar la actividad global de la plataforma y gestionar los
datos del estudio.

Se planteo si existir una unica vista de historial o dos vistas diferenciadas
segun el rol del usuario.

## Opciones consideradas

1. **Una sola vista para todos** — todos los usuarios ven todas las sesiones.
   Simple de implementar. El problema es que expone los prompts y resultados
   de otros evaluadores sin su consentimiento, y da capacidad de borrado a
   cualquiera, comprometiendo la integridad del estudio.

2. **Vista diferenciada por rol**:
   - Usuario con nick: ve solo sus propias sesiones en modo solo lectura.
     No puede borrar ni modificar nada. Puede expandir cada sesion para
     ver las respuestas completas y las metricas detalladas.
   - Administrador (autenticado con JWT): ve todas las sesiones de todos
     los usuarios con paginacion de 10 en 10. Puede borrar individualmente,
     por lotes (seleccion multiple con checkboxes) o resetear el estudio
     completo borrando todos los registros. Esta ultima opcion requiere
     confirmacion explicita para evitar borrados accidentales.

3. **Sin historial para el usuario, solo para el admin** — los evaluadores
   no ven sus sesiones pasadas. Reduce el valor percibido de la aplicacion
   para el evaluador y elimina la posibilidad de relanzar un benchmark previo.

## Decision tomada

Se elige la opcion 2: **vistas diferenciadas por rol**.

El historial para el usuario anonimo cumple dos funciones: permite revisar
resultados de sesiones anteriores sin tener que relanzarlas, y da transparencia
al evaluador sobre que datos suyos estan almacenados. El modo solo lectura
es la unica opcion coherente con un usuario sin cuenta permanente.

El historial para el administrador es una herramienta de gestion del estudio.
La paginacion de 10 en 10 es estandar y evita cargar todos los registros
en memoria. La capacidad de borrado por lotes y el reset completo permiten
al administrador reiniciar el estudio entre fases (por ejemplo, entre una
sesion de prueba y la recogida de datos real para el TFG).

La distincion de roles se implementa verificando el JWT del administrador
en el backend; en el frontend, la vista de historial adapta su contenido
y controles al tipo de usuario autenticado.

## Consecuencias

Positivas:
- Privacidad: cada evaluador solo ve sus propias sesiones.
- Integridad del estudio: solo el admin puede borrar datos.
- Herramienta de gestion completa para el TFG: el alumno puede limpiar
  datos de prueba antes de la recogida de datos definitiva.
- La opcion de relanzar un benchmark desde el historial permite comparar
  si los modelos mejoran entre versiones a lo largo del tiempo.

Trade-offs asumidos:
- El borrado masivo es irreversible. Se mitiga con dialogo de confirmacion
  explicito que describe cuantos registros se van a eliminar.
- La paginacion del admin no incluye busqueda ni filtros en v1; si el
  volumen de datos crece significativamente se anadiran en una iteracion
  posterior.
- Un usuario que cambia de nick pierde acceso visual a sus sesiones
  anteriores (aunque los datos siguen en BD con el nick antiguo).
