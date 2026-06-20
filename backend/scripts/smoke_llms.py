"""
Modulo: smoke_llms
Ruta:   backend/scripts/smoke_llms.py

Descripcion:
    Script de verificacion manual de las cuatro claves de API LLM configuradas
    en backend/.env. No forma parte de la suite pytest; se ejecuta a mano:

        cd backend
        python scripts/smoke_llms.py

    Llama a completar() en paralelo sobre los cuatro clientes con un prompt
    minimo, imprime el resultado de cada uno (OK / ERROR) y un resumen final.
    No escribe en la base de datos; no requiere que PostgreSQL este activo.

Sprint: Sprint 2
"""

import asyncio
import os
import sys
from pathlib import Path

# Permite importar desde app/ sin instalar el paquete
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app.llm_engine.clients.claude_client import ClaudeClient  # noqa: E402
from app.llm_engine.clients.gemini_client import GeminiClient  # noqa: E402
from app.llm_engine.clients.grok_client import GrokClient  # noqa: E402
from app.llm_engine.clients.openai_client import OpenAIClient  # noqa: E402

PROMPT = "Responde unicamente con la palabra: OK"
# Gemini 2.5 Flash usa thinking tokens; con menos de ~50 tokens no queda
# presupuesto para la respuesta real. Se usa 200 para todos por uniformidad.
MAX_TOKENS = 200

VERDE = "\033[92m"
ROJO = "\033[91m"
RESET = "\033[0m"
NEGRITA = "\033[1m"


def _leer_keys() -> dict[str, str]:
    """Lee las cuatro claves de API desde las variables de entorno."""
    claves = {
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY", ""),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
        "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY", ""),
        "XAI_API_KEY": os.getenv("XAI_API_KEY", ""),
    }
    ausentes = [k for k, v in claves.items() if not v]
    if ausentes:
        print(f"{ROJO}ERROR: variables no encontradas en .env: {', '.join(ausentes)}{RESET}")
        sys.exit(1)
    return claves


def _preview_key(key: str) -> str:
    """Muestra solo los primeros y ultimos 4 caracteres de la clave."""
    if len(key) <= 12:
        return "****"
    return f"{key[:6]}...{key[-4:]}"


async def _probar_cliente(nombre: str, cliente) -> dict:
    """Llama a completar() y devuelve un diccionario con el resultado."""
    resultado = await cliente.completar(PROMPT, max_tokens=MAX_TOKENS)
    return {
        "nombre": nombre,
        "ok": not resultado.tuvo_error,
        "respuesta": resultado.texto_respuesta or "",
        "latencia_ms": resultado.latencia_ms,
        "tokens_entrada": resultado.tokens_entrada,
        "tokens_salida": resultado.tokens_salida,
        "coste_usd": resultado.coste_usd,
        "error": resultado.mensaje_error or "",
    }


async def main() -> None:
    """Punto de entrada principal del smoke test."""
    keys = _leer_keys()

    clientes = [
        ("Claude Sonnet 4.6", ClaudeClient(keys["ANTHROPIC_API_KEY"])),
        ("GPT-4o", OpenAIClient(keys["OPENAI_API_KEY"])),
        ("Gemini 2.5 Flash", GeminiClient(keys["GOOGLE_API_KEY"])),
        ("Grok 3", GrokClient(keys["XAI_API_KEY"])),
    ]

    print(f"\n{NEGRITA}=== Smoke test LLMs — TFG Benchmarking ==={RESET}")
    print(f"Prompt enviado: \"{PROMPT}\"")
    print(f"Max tokens: {MAX_TOKENS}")
    print(f"Claves cargadas desde .env:")
    print(f"  ANTHROPIC : {_preview_key(keys['ANTHROPIC_API_KEY'])}")
    print(f"  OPENAI    : {_preview_key(keys['OPENAI_API_KEY'])}")
    print(f"  GOOGLE    : {_preview_key(keys['GOOGLE_API_KEY'])}")
    print(f"  XAI       : {_preview_key(keys['XAI_API_KEY'])}")
    print()

    tareas = [_probar_cliente(nombre, cliente) for nombre, cliente in clientes]
    print("Enviando llamadas en paralelo...")
    resultados = await asyncio.gather(*tareas)

    print()
    print(f"{'Proveedor':<20} {'Estado':<8} {'Latencia':>10} {'In/Out tok':>12} {'Coste USD':>12}  Respuesta")
    print("-" * 85)

    ok_count = 0
    for r in resultados:
        if r["ok"]:
            estado = f"{VERDE}OK{RESET}"
            ok_count += 1
            detalle = repr(r["respuesta"][:40])
        else:
            estado = f"{ROJO}ERROR{RESET}"
            detalle = f"  >> {r['error'][:60]}"

        tokens = f"{r['tokens_entrada']}/{r['tokens_salida']}"
        print(
            f"{r['nombre']:<20} {estado:<8} {r['latencia_ms']:>8} ms {tokens:>12} "
            f"${r['coste_usd']:>10.6f}  {detalle}"
        )

    print()
    total = len(resultados)
    if ok_count == total:
        print(f"{VERDE}{NEGRITA}Resultado: {ok_count}/{total} proveedores operativos. Backend listo para Sprint 3.{RESET}")
    else:
        fallidos = [r["nombre"] for r in resultados if not r["ok"]]
        print(f"{ROJO}{NEGRITA}Resultado: {ok_count}/{total} operativos. Revisar: {', '.join(fallidos)}{RESET}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
