"""
Modulo: sanitizar_error
Ruta:   backend/app/llm_engine/sanitizar_error.py

Descripcion:
    Helper compartido por los clientes LLM para limpiar credenciales y tokens
    de los mensajes de error antes de persistirlos en BD.

    El problema que resuelve: httpx, los SDK oficiales y otras librerias
    incluyen la URL completa de la peticion fallida en str(exception). Cuando
    una API exige la clave como query param (caso Google AI Imagen 4) o cuando
    se incluye el token en el cuerpo del error, esa clave queda persistida en
    llm_responses.error_message y se exporta al CSV de admin.

    Patrones cubiertos:
        - Google AI: ?key=AIza... y &key=AIza...
        - Bearer tokens: 'Authorization: Bearer xxx' o 'Bearer xxx' suelto
        - OpenAI: sk-..., sk-proj-..., sk-ant-... (Anthropic)
        - xAI: xai-...
        - Google: AIza... (39 chars, formato canonico de API key) sueltos

    El reemplazo es '***REDACTED***' para que sea visible al revisar logs
    pero no exponga el secreto.

    DECISION: Aplicado en ResultadoLLM.__post_init__ en lugar de en cada
    call site. Esto cierra la fuga en un unico chokepoint y garantiza que
    cualquier cliente nuevo herede la proteccion automaticamente.

Sprint: Sprint 4
"""

import re

# Token de redaccion. Reconocible al revisar logs sin exponer el secreto.
_REDACTED = "***REDACTED***"

# Cada patron localiza un secreto y captura el delimitador previo cuando
# debe preservarse (p.ej. '?key=' o '&key='). Orden: del mas especifico
# al mas generico para que un patron mas amplio no se trague uno mas
# preciso antes de aplicarlo.
_PATRONES: list[tuple[re.Pattern[str], str]] = [
    # ?key=AIza... o &key=AIza... (Google AI URL param). Mantiene el delimitador.
    (re.compile(r"([?&])key=[A-Za-z0-9_\-]{20,}"), rf"\1key={_REDACTED}"),
    # Authorization: Bearer xxx (header completo)
    (re.compile(r"(?i)Authorization:\s*Bearer\s+[A-Za-z0-9._\-]+"), f"Authorization: Bearer {_REDACTED}"),
    # Bearer xxx suelto (sin el header)
    (re.compile(r"(?i)Bearer\s+[A-Za-z0-9._\-]{20,}"), f"Bearer {_REDACTED}"),
    # OpenAI sk-... (incluye sk-proj-, sk-ant-, etc.)
    (re.compile(r"sk-(?:proj-|ant-)?[A-Za-z0-9_\-]{20,}"), _REDACTED),
    # xAI xai-...
    (re.compile(r"xai-[A-Za-z0-9_\-]{20,}"), _REDACTED),
    # Google API key suelta (formato canonico AIza + 35 chars)
    (re.compile(r"AIza[A-Za-z0-9_\-]{35}"), _REDACTED),
]


def sanitizar_mensaje_error(texto: str | None) -> str | None:
    """Aplica todos los patrones de redaccion al texto de error.

    Devuelve None si la entrada es None (ResultadoLLM permite mensaje_error
    nullable cuando la llamada tuvo exito). El texto vacio se preserva tal
    cual (no es un secreto y conviene distinguirlo de None aguas abajo).

    Args:
        texto: Mensaje de error en bruto, posiblemente con secretos
            embebidos (URLs con query params sensibles, tokens Bearer, etc.).

    Returns:
        Mismo mensaje con los secretos sustituidos por '***REDACTED***'.
        None si la entrada era None.
    """
    if texto is None:
        return None
    sanitizado = texto
    for patron, reemplazo in _PATRONES:
        sanitizado = patron.sub(reemplazo, sanitizado)
    return sanitizado
