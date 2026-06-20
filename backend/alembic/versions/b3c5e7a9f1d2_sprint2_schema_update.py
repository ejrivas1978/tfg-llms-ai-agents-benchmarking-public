"""sprint2: actualiza enums LLM/categoria y agrega metricas automaticas

Revision ID: b3c5e7a9f1d2
Revises: eea0e502294c
Create Date: 2026-05-02

Cambios:
    - llmprovider: sustituye deepseek/azure_openai por gemini/grok (ADR-010)
    - testcategory: valores en espanol y agrega imagen/libre (ADR-014)
    - sessionstatus: valores en espanol
    - llm_responses: agrega 7 columnas de metricas automaticas (ADR-016)
    - benchmark_sessions: agrega similitud_jaccard_media (ADR-016)
"""

from alembic import op
import sqlalchemy as sa


revision = "b3c5e7a9f1d2"
down_revision = "eea0e502294c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. llmprovider: deepseek/azure_openai → gemini/grok ────────────────
    op.execute("ALTER TYPE llmprovider RENAME TO llmprovider_v1")
    op.execute("CREATE TYPE llmprovider AS ENUM ('claude', 'openai', 'gemini', 'grok')")
    op.execute("""
        ALTER TABLE llm_responses
        ALTER COLUMN provider TYPE llmprovider
        USING CASE provider::text
            WHEN 'claude' THEN 'claude'::llmprovider
            WHEN 'openai' THEN 'openai'::llmprovider
            ELSE 'claude'::llmprovider
        END
    """)
    op.execute("DROP TYPE llmprovider_v1")

    # ── 2. testcategory: ingles → espanol + imagen/libre ───────────────────
    op.execute("ALTER TYPE testcategory RENAME TO testcategory_v1")
    op.execute(
        "CREATE TYPE testcategory AS ENUM "
        "('razonamiento', 'codigo', 'creativa', 'factual', 'traduccion', 'resumen', 'imagen', 'libre')"
    )
    op.execute("""
        ALTER TABLE benchmark_sessions
        ALTER COLUMN category TYPE testcategory
        USING CASE category::text
            WHEN 'reasoning'        THEN 'razonamiento'::testcategory
            WHEN 'coding'           THEN 'codigo'::testcategory
            WHEN 'creative_writing' THEN 'creativa'::testcategory
            WHEN 'factual_qa'       THEN 'factual'::testcategory
            WHEN 'translation'      THEN 'traduccion'::testcategory
            WHEN 'summarization'    THEN 'resumen'::testcategory
            ELSE 'libre'::testcategory
        END
    """)
    op.execute("DROP TYPE testcategory_v1")

    # ── 3. sessionstatus: ingles → espanol ─────────────────────────────────
    op.execute("ALTER TYPE sessionstatus RENAME TO sessionstatus_v1")
    op.execute(
        "CREATE TYPE sessionstatus AS ENUM ('pendiente', 'en_curso', 'completada', 'fallida')"
    )
    op.execute("""
        ALTER TABLE benchmark_sessions
        ALTER COLUMN status TYPE sessionstatus
        USING CASE status::text
            WHEN 'pending'   THEN 'pendiente'::sessionstatus
            WHEN 'running'   THEN 'en_curso'::sessionstatus
            WHEN 'completed' THEN 'completada'::sessionstatus
            WHEN 'failed'    THEN 'fallida'::sessionstatus
            ELSE 'pendiente'::sessionstatus
        END
    """)
    op.execute("DROP TYPE sessionstatus_v1")

    # ── 4. llm_responses: 7 nuevas columnas de metricas ────────────────────
    op.add_column("llm_responses", sa.Column("tokens_por_segundo", sa.Float(), nullable=False, server_default="0"))
    op.add_column("llm_responses", sa.Column("ratio_sal_ent", sa.Float(), nullable=False, server_default="0"))
    op.add_column("llm_responses", sa.Column("coste_por_100_palabras", sa.Numeric(10, 6), nullable=False, server_default="0"))
    op.add_column("llm_responses", sa.Column("palabras", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("llm_responses", sa.Column("diversidad_lexica", sa.Float(), nullable=False, server_default="0"))
    op.add_column("llm_responses", sa.Column("parrafos", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("llm_responses", sa.Column("bloques_codigo", sa.Integer(), nullable=False, server_default="0"))

    # ── 5. benchmark_sessions: similitud Jaccard media ─────────────────────
    op.add_column("benchmark_sessions", sa.Column("similitud_jaccard_media", sa.Float(), nullable=True))


def downgrade() -> None:
    # ── 5. Revertir similitud_jaccard_media ────────────────────────────────
    op.drop_column("benchmark_sessions", "similitud_jaccard_media")

    # ── 4. Revertir columnas de metricas ───────────────────────────────────
    for col in ["tokens_por_segundo", "ratio_sal_ent", "coste_por_100_palabras",
                "palabras", "diversidad_lexica", "parrafos", "bloques_codigo"]:
        op.drop_column("llm_responses", col)

    # ── 3. Revertir sessionstatus ──────────────────────────────────────────
    op.execute("ALTER TYPE sessionstatus RENAME TO sessionstatus_v2")
    op.execute("CREATE TYPE sessionstatus AS ENUM ('pending', 'running', 'completed', 'failed')")
    op.execute("""
        ALTER TABLE benchmark_sessions
        ALTER COLUMN status TYPE sessionstatus
        USING CASE status::text
            WHEN 'pendiente'  THEN 'pending'::sessionstatus
            WHEN 'en_curso'   THEN 'running'::sessionstatus
            WHEN 'completada' THEN 'completed'::sessionstatus
            WHEN 'fallida'    THEN 'failed'::sessionstatus
            ELSE 'pending'::sessionstatus
        END
    """)
    op.execute("DROP TYPE sessionstatus_v2")

    # ── 2. Revertir testcategory ───────────────────────────────────────────
    op.execute("ALTER TYPE testcategory RENAME TO testcategory_v2")
    op.execute(
        "CREATE TYPE testcategory AS ENUM "
        "('reasoning', 'coding', 'creative_writing', 'factual_qa', 'translation', 'summarization')"
    )
    op.execute("""
        ALTER TABLE benchmark_sessions
        ALTER COLUMN category TYPE testcategory
        USING CASE category::text
            WHEN 'razonamiento' THEN 'reasoning'::testcategory
            WHEN 'codigo'       THEN 'coding'::testcategory
            WHEN 'creativa'     THEN 'creative_writing'::testcategory
            WHEN 'factual'      THEN 'factual_qa'::testcategory
            WHEN 'traduccion'   THEN 'translation'::testcategory
            WHEN 'resumen'      THEN 'summarization'::testcategory
            ELSE 'reasoning'::testcategory
        END
    """)
    op.execute("DROP TYPE testcategory_v2")

    # ── 1. Revertir llmprovider ────────────────────────────────────────────
    op.execute("ALTER TYPE llmprovider RENAME TO llmprovider_v2")
    op.execute("CREATE TYPE llmprovider AS ENUM ('claude', 'openai', 'deepseek', 'azure_openai')")
    op.execute("""
        ALTER TABLE llm_responses
        ALTER COLUMN provider TYPE llmprovider
        USING CASE provider::text
            WHEN 'claude' THEN 'claude'::llmprovider
            WHEN 'openai' THEN 'openai'::llmprovider
            ELSE 'claude'::llmprovider
        END
    """)
    op.execute("DROP TYPE llmprovider_v2")
