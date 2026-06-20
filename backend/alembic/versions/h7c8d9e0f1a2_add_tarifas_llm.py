"""Crea tabla tarifas_llm con seed de los 4 precios actuales

Revision ID: h7c8d9e0f1a2
Revises: g6b7c8d9e0f1
Create Date: 2026-05-13

Contexto:
    Hasta ahora los precios por millon de tokens estaban hardcoded en
    backend/app/llm_engine/metricas.py como un diccionario inmutable.
    Cada vez que un proveedor actualizaba su tarifa habia que tocar
    codigo y desplegar.

    Esta migracion mueve esos valores a una tabla 'tarifas_llm' editable
    desde el panel admin (nueva pestana 'Tarifas'). Solo el admin puede
    modificar precio_entrada_usd_por_mtoken y precio_salida_usd_por_mtoken;
    los costes relativos se calculan en el backend a partir de la columna
    correspondiente (cada uno con su propio baseline = minimo de su columna)
    y no se almacenan.

    Tipos:
      - precio_entrada/salida: Numeric(10, 4). Permite hasta 999999.9999
        que cubre cualquier tarifa razonable (la mas alta hoy es $15/Mtok).
        Cuatro decimales son suficientes porque la tarifa mas barata
        (Gemini entrada) es 0.0750.

      - actualizado_por: String(64) nullable. Guarda el nick del admin
        que toco la fila la ultima vez (auditoria minima). No es FK a
        usuarios_app para evitar dependencia ciclica de eliminacion:
        si borras al admin no quieres que pierdas el historial de quien
        cambio una tarifa.

    Seed inicial (los mismos valores que tenia _PRECIOS_POR_MTOKEN en
    mayo 2026):
      claude  3.00  / 15.00
      openai  2.50  / 10.00
      gemini  0.075 /  0.30
      grok    1.25  /  2.50
"""

from datetime import datetime, timezone
from decimal import Decimal

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = 'h7c8d9e0f1a2'
down_revision = 'g6b7c8d9e0f1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # El tipo enum 'llmprovider' ya existe en la BD (lo creo la migracion
    # inicial junto a llm_responses), asi que aqui solo lo referencio con
    # postgresql.ENUM + create_type=False para que Alembic no intente
    # crearlo de nuevo (sa.Enum ignora ese flag dentro de create_table).
    llmprovider_enum = postgresql.ENUM(
        'claude', 'openai', 'gemini', 'grok',
        name='llmprovider',
        create_type=False,
    )

    tarifas = op.create_table(
        'tarifas_llm',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('proveedor', llmprovider_enum, nullable=False, unique=True),
        sa.Column('precio_entrada_usd_por_mtoken', sa.Numeric(10, 4), nullable=False),
        sa.Column('precio_salida_usd_por_mtoken',  sa.Numeric(10, 4), nullable=False),
        sa.Column(
            'actualizado_en',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column('actualizado_por', sa.String(64), nullable=True),
    )

    ahora = datetime.now(timezone.utc)
    op.bulk_insert(
        tarifas,
        [
            {
                'proveedor': 'claude',
                'precio_entrada_usd_por_mtoken': Decimal('3.0000'),
                'precio_salida_usd_por_mtoken':  Decimal('15.0000'),
                'actualizado_en': ahora,
                'actualizado_por': 'seed',
            },
            {
                'proveedor': 'openai',
                'precio_entrada_usd_por_mtoken': Decimal('2.5000'),
                'precio_salida_usd_por_mtoken':  Decimal('10.0000'),
                'actualizado_en': ahora,
                'actualizado_por': 'seed',
            },
            {
                'proveedor': 'gemini',
                'precio_entrada_usd_por_mtoken': Decimal('0.0750'),
                'precio_salida_usd_por_mtoken':  Decimal('0.3000'),
                'actualizado_en': ahora,
                'actualizado_por': 'seed',
            },
            {
                'proveedor': 'grok',
                'precio_entrada_usd_por_mtoken': Decimal('1.2500'),
                'precio_salida_usd_por_mtoken':  Decimal('2.5000'),
                'actualizado_en': ahora,
                'actualizado_por': 'seed',
            },
        ],
    )


def downgrade() -> None:
    op.drop_table('tarifas_llm')
