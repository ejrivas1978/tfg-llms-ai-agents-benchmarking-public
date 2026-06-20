# ADR-033: Refresco de cuota al recargar — GET /usuarios/me

Estado: Aceptado
Fecha: 17/05/2026
Sprint: Sprint 4

## Contexto

El store `usuarioStore` de Zustand persiste `consultasUsadas` y `cuotaAsignada` en `localStorage` (clave `tfg-usuario`). Al recargar la página, Zustand rehidrata el store desde `localStorage` sin contactar el backend. Si el administrador cambia la cuota de un usuario mientras este tiene la sesión abierta, el usuario sigue viendo el valor antiguo hasta que vuelva a hacer login manualmente.

Esta inconsistencia se detectó en pruebas de usuario: el admin asignó 62 consultas a una cuenta que tenía 52, pero al recargar la página del usuario el contador seguía mostrando 52.

## Opciones consideradas

1. **No persistir `consultasUsadas`/`cuotaAsignada` en localStorage** — eliminar esos campos del `partialize` de Zustand. El store comenzaría en 0 en cada recarga hasta que se contactara el backend. Requiere una llamada de refresh en cualquier caso.
2. **Añadir `GET /usuarios/me` y llamarlo en el montaje de Layout** — el valor de localStorage se muestra momentáneamente (evita parpadeo) y se corrige en cuanto llega la respuesta del backend. La experiencia percibida es de dato instantáneo y corrección silenciosa.
3. **Polling periódico** — innecesario para este caso de uso (la cuota solo cambia cuando el admin actúa) y consume peticiones sin valor.
4. **WebSocket de notificación push** — excede el alcance del TFG y añade complejidad de infraestructura.

## Decisión tomada

Se elige la opción 2. Se añade:

- **Backend**: `GET /api/v1/usuarios/me` en `routers/usuarios.py`. Usa la dependencia existente `get_current_usuario_app` (Bearer JWT) y devuelve `RespuestaUsuarioApp` con `consultas_usadas`, `cuota_asignada` y `estado` frescos desde la BD.

- **Frontend**: `obtenerPerfilUsuario(token)` en `services/usuarioApi.ts`. `Layout.tsx` lo llama en un `useEffect` con array de dependencias vacío (solo al montar), actualiza el store con `actualizarCuota()` y `actualizarEstado()`.

## Consecuencias

Positivas:
- El usuario siempre ve la cuota correcta tras cualquier recarga, independientemente de cuándo el admin la haya modificado.
- La solución es transparente: no hay parpadeo ni spinner adicional. El valor de localStorage se muestra durante los milisegundos que tarda la petición.
- El endpoint es reutilizable para otros escenarios futuros (p. ej. verificar el estado tras un período de inactividad).

Trade-offs asumidos:
- Añade una petición HTTP extra al cargar cada página. El impacto es despreciable (< 50 ms en red local, < 200 ms en Cloud Run).
- Si el backend no está disponible al cargar, el `catch` del `useEffect` no hace nada: el usuario ve el valor cacheado. El interceptor de axios gestiona el 401 (token caducado) llamando a `logout()`.

Riesgos:
- Ninguno identificado. La petición es idempotente y de solo lectura.
