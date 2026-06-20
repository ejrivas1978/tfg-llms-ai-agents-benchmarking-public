"""
Modulo: middleware.rate_limit
Ruta:   backend/app/middleware/rate_limit.py

Descripcion:
    Configuracion del limitador de velocidad con slowapi.
    Protege el endpoint POST /benchmarks/run (costoso en tiempo y dinero)
    y POST /auth/login (proteccion contra fuerza bruta).

    El limitador usa la IP del cliente como clave de identificacion.
    En despliegues con proxy inverso (Cloud Run + Load Balancer) se usa
    la cabecera X-Forwarded-For cuando esta disponible.

    Limites configurados:
        POST /benchmarks/run              : 5 peticiones/minuto por IP
        GET  /benchmarks/texto-ejemplo    : 10 peticiones/minuto por IP
        GET  /benchmarks/{id}             : 30 peticiones/minuto por IP
        GET  /benchmarks/historial/{nick} : 20 peticiones/minuto por IP
        POST /auth/login                  : 10 peticiones/minuto por IP
        POST /usuarios/login              : 10 peticiones/minuto por IP
        GET  /usuarios/verificar/{nick}   : 20 peticiones/minuto por IP
        POST /usuarios/registrar          : 5 peticiones/minuto por IP
        POST /usuarios/regenerar-contrasena : 2 peticiones/minuto por IP

Dependencias:
    - slowapi>=0.1.9

Sprint: Sprint 2
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Instancia global del limitador. Se registra en main.py con:
#   app.state.limiter = limitador
#   app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
limitador = Limiter(key_func=get_remote_address)
