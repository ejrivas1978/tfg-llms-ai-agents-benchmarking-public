# ADR-012: Modelo de usuarios anonimos con nickname

Estado: Aceptado
Fecha: 02/02/2026
Sprint: Sprint 2

## Contexto

La aplicacion tiene dos tipos de actores: el administrador (el propio
alumno, que gestiona la plataforma) y los evaluadores web (personas que
acceden a comparar y valorar respuestas LLM durante demostraciones o de
forma voluntaria). Se planteo si los evaluadores deben crear una cuenta
con email y contrasena o si basta con un identificador informal.

## Opciones consideradas

1. **Registro completo con email y contrasena** — cada evaluador crea una
   cuenta. Permite historial personal, login en multiples dispositivos
   y control de acceso. Requiere implementar registro, verificacion de
   email, recuperacion de contrasena y GDPR. Sobredimensionado para el
   alcance del TFG; los evaluadores no tienen una relacion de largo plazo
   con la plataforma.

2. **Nickname libre en localStorage** — el usuario introduce un alias la
   primera vez. Se persiste en localStorage del navegador para no pedirlo
   en cada visita. Se puede modificar desde la barra superior. El nickname
   se almacena junto a cada evaluacion para identificar al evaluador en
   los datos, sin necesidad de cuenta.

3. **Completamente anonimo, sin identificador** — las evaluaciones no
   llevan ningun identificador de usuario. Imposible detectar si un mismo
   evaluador ha valorado varias veces la misma sesion, lo que permite
   manipulacion de las estadisticas.

## Decision tomada

Se elige el modelo de **nickname libre en localStorage** (opcion 2).

El proposito de identificar al evaluador en el TFG es exclusivamente
analitico: saber si un mismo usuario ha evaluado multiples sesiones, y
mostrar en el dashboard quienes han participado. No requiere autenticacion
real. El nickname en localStorage consigue este objetivo sin infraestructura
adicional y sin friccion para el usuario.

La persistencia entre visitas es deliberada: si el evaluador cierra el
navegador y vuelve, no tiene que reintroducir su alias. La posibilidad
de editar el nick desde la barra superior cubre el caso de uso de quien
quiere cambiar su identificador.

El JWT con autenticacion completa se reserva exclusivamente para el
administrador (endpoint /admin), que es el unico que necesita acceso
seguro a funciones de gestion.

## Consecuencias

Positivas:
- Friccion minima para el evaluador: un solo campo la primera vez.
- Sin infraestructura de autenticacion ni GDPR para usuarios web.
- Suficiente para el analisis estadistico del TFG.

Trade-offs asumidos:
- Un usuario puede cambiar su nickname y aparecer como una persona
  diferente en los datos. Para el alcance del TFG esto es aceptable;
  no es una plataforma de produccion con integridad de datos critica.
- El nickname no es unico globalmente: dos evaluadores pueden usar el
  mismo alias. Se asume que en el contexto del TFG (grupo reducido de
  evaluadores conocidos) esto no es un problema practico.
