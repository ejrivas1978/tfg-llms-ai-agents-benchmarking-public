"""
Modulo: usuario_app
Ruta:   backend/app/models/usuario_app.py

Descripcion:
    Modelo ORM SQLAlchemy para la tabla usuarios_app.
    Tabla unificada que representa tanto a los usuarios web regulares
    como a los administradores del sistema (ADR-027 supersede ADR-024).

    El flag is_admin distingue las dos clases de usuario:
      - is_admin=False -> usuario web regular: nick + password, control
        de cuota (cuota_asignada / consultas_usadas), estados de ciclo
        de vida (pendiente_acceso / habilitado / pendiente_ampliar_tokens).
      - is_admin=True -> administrador: ademas exige email (check
        constraint ck_admin_requires_email). La cuota se ignora durante
        la ejecucion de benchmarks (admin = sin restriccion). Si el
        admin se degrada despues a usuario regular, los contadores
        reanudan su control segun el ultimo valor configurado.

    Hash de la contrasena: bcrypt 12 rondas (passlib CryptContext) para
    todos los registros, tanto admins como usuarios regulares. Centralizado
    en app/core/security.py.

Dependencias:
    - app.core.database.Base
    - app.models.enums.EstadoUsuarioApp

Sprint: Sprint 4
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import EstadoUsuarioApp


class UsuarioApp(Base):
    """Modelo ORM para la tabla unificada usuarios_app.

    Atributos:
        id: Clave primaria autoincrementada.
        nick: Identificador unico del usuario. Es el campo de login para
            todos (usuarios y admins).
        password_hash: Hash Argon2 (o bcrypt para el admin legacy migrado).
        email: Correo electronico unico. Obligatorio si is_admin=True
            (check constraint en BD); opcional para usuarios regulares.
        is_admin: True si el usuario tiene privilegios de administracion.
            Se controla mediante endpoints de promote/demote. Imposible
            tener admins sin email (constraint ck_admin_requires_email).
        es_root: True solo para el admin seeded en el despliegue (el
            que crea seed_admin.py). Es la unica cuenta que puede
            promover o degradar a otros administradores. Los admins
            promovidos via endpoint tienen is_admin=true pero
            es_root=false: heredan el resto de privilegios pero no
            pueden modificar roles de terceros.
        estado: Estado actual del ciclo de vida del usuario regular.
            Para admins el campo existe pero no se valida (estado='habilitado').
        cuota_asignada: Numero maximo de consultas permitidas. Se ignora
            mientras is_admin=True; al degradar a usuario regular vuelve
            a aplicar el ultimo valor configurado.
        consultas_usadas: Contador de comparaciones realizadas con exito.
            No se incrementa si el actor era admin (cuota ilimitada).
        intentos_fallidos: Contador de intentos de login fallidos consecutivos.
            Se resetea a 0 en cada login exitoso. Al llegar a 5 se bloquea.
        guia_vista: True cuando el usuario ya ha visto la guia de bienvenida.
        created_at: Marca de tiempo UTC de registro del usuario.
        updated_at: Marca de tiempo UTC de la ultima modificacion.
    """

    __tablename__ = "usuarios_app"
    __table_args__ = (
        # Si es admin debe tener email (paralelo a la antigua tabla users
        # donde email era NOT NULL UNIQUE). Para usuarios regulares el
        # email queda opcional.
        CheckConstraint(
            "(NOT is_admin) OR (email IS NOT NULL)",
            name="ck_admin_requires_email",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nick: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    es_root: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    estado: Mapped[EstadoUsuarioApp] = mapped_column(
        SAEnum(EstadoUsuarioApp, name="estadousuarioapp", create_type=True),
        nullable=False,
        default=EstadoUsuarioApp.pendiente_acceso,
    )
    cuota_asignada: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consultas_usadas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    intentos_fallidos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    guia_vista: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        rol = "admin" if self.is_admin else "usuario"
        return (
            f"<UsuarioApp id={self.id} nick={self.nick!r} rol={rol} "
            f"estado={self.estado} cuota={self.consultas_usadas}/{self.cuota_asignada}>"
        )
