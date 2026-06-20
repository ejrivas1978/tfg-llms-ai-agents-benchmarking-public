"""
Modulo: seed_admin
Ruta:   backend/scripts/seed_admin.py

Descripcion:
    Script puntual para crear la primera cuenta de administrador en la
    tabla unificada usuarios_app (ADR-027). Ejecutarlo una vez tras
    aplicar las migraciones.

    Uso (desde backend/ con el entorno virtual activo):
        python scripts/seed_admin.py

    Lee ADMIN_USERNAME (= nick), ADMIN_EMAIL (obligatorio para admins) y
    ADMIN_PASSWORD del entorno o usa defaults. Idempotente: si ya existe
    un admin con ese nick, no hace nada.

Sprint: Sprint 1 / actualizado Sprint 4
"""

import asyncio
import os
import sys

# Permite importar modulos de app desde backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.enums import EstadoUsuarioApp
from app.models.usuario_app import UsuarioApp


async def crear_admin() -> None:
    """Crea la primera cuenta de administrador si no existe ninguna con ese nick."""
    nick_admin     = os.getenv("ADMIN_USERNAME", "admin")
    email_admin    = os.getenv("ADMIN_EMAIL", "admin@tfg-llm.es")
    password_admin = os.getenv("ADMIN_PASSWORD", "changeme123")

    async with AsyncSessionLocal() as sesion:
        existente = await sesion.execute(
            select(UsuarioApp).where(UsuarioApp.nick == nick_admin)
        )
        if existente.scalar_one_or_none() is not None:
            print(f"[!] El admin con nick='{nick_admin}' ya existe. No se realiza ninguna accion.")
            return

        admin = UsuarioApp(
            nick=nick_admin,
            password_hash=hash_password(password_admin),
            email=email_admin,
            is_admin=True,
            es_root=True,  # ADR-027: solo el admin seeded es root y puede promover/degradar.
            estado=EstadoUsuarioApp.habilitado,
            cuota_asignada=0,
            consultas_usadas=0,
            intentos_fallidos=0,
            guia_vista=False,
        )
        sesion.add(admin)
        await sesion.commit()
        print("[OK] Cuenta de administrador root creada en usuarios_app:")
        print(f"     Nick     : {nick_admin}")
        print(f"     Email    : {email_admin}")
        print(f"     Rol      : root (puede promover y degradar a otros admins)")
        print("     Cambia la contrasena tras el primer inicio de sesion.")


if __name__ == "__main__":
    asyncio.run(crear_admin())
