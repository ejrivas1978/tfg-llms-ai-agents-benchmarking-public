"""
Modulo: enums
Ruta:   backend/app/models/enums.py

Descripcion:
    Enumeraciones Python usadas como tipos de columna en los modelos SQLAlchemy
    y como valores validos en los esquemas Pydantic. Se centralizan aqui para
    que modelos y esquemas importen desde una unica fuente de verdad.

    DECISION(ADR-010): Stack de LLMs es Claude, GPT-4o, Gemini 2.0, Grok 2.
    DECISION(ADR-014): La subcategoria solo existe en la UI; la BD almacena
                       la categoria padre con valores cortos en espanol.

Sprint: Sprint 2
"""

import enum


class LLMProvider(str, enum.Enum):
    """Identificadores de los cuatro proveedores LLM del estudio."""

    claude = "claude"
    openai = "openai"
    gemini = "gemini"
    grok = "grok"


class TestCategory(str, enum.Enum):
    """Ocho categorias de prompt. Valores cortos en espanol, coherentes con el frontend."""

    razonamiento = "razonamiento"
    codigo = "codigo"
    creativa = "creativa"
    concretas = "concretas"
    traduccion = "traduccion"
    resumen = "resumen"
    imagen = "imagen"
    libre = "libre"


class SessionStatus(str, enum.Enum):
    """Estado del ciclo de vida de una sesion de benchmark."""

    pendiente = "pendiente"
    en_curso = "en_curso"
    completada = "completada"
    fallida = "fallida"
    solicitud_borrado = "solicitud_borrado"


class EstadoUsuarioApp(str, enum.Enum):
    """Estado del ciclo de vida de un usuario de la aplicacion web.

    Transiciones validas:
        pendiente_acceso  -> habilitado              (admin concede acceso)
        habilitado        -> pendiente_ampliar_tokens (usuario agota cuota)
        pendiente_ampliar_tokens -> habilitado        (admin amplia tokens)
        habilitado        -> pendiente_acceso         (usuario regenera contrasena)
    """

    pendiente_acceso = "pendiente_acceso"
    habilitado = "habilitado"
    pendiente_ampliar_tokens = "pendiente_ampliar_tokens"
