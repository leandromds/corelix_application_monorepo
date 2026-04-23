"""
Core database module: async engine, session factory, RLS support.

Nota de design: Base define apenas a PK (id UUID).
Timestamps ficam em mixins (core/mixins.py) porque nem todas as tabelas
precisam de updated_at — e usar um mixin explícito deixa essa intenção visível
no próprio model, não escondida numa classe base.
"""

from collections.abc import AsyncGenerator
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import UUID as SQLUUID

from core.config import settings


# ============================================================================
# Base Model — somente a PK
# ============================================================================


class Base(DeclarativeBase):
    """
    Classe base para todos os modelos SQLAlchemy.

    Define apenas o campo id (UUID gerado pelo PostgreSQL).
    Timestamps são adicionados via mixins em core/mixins.py:
      - TimestampMixin → created_at + updated_at
      - CreatedAtMixin  → created_at apenas
    """

    id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )


# ============================================================================
# Engine e Session Factory
# ============================================================================


def create_engine() -> AsyncEngine:
    return create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,
    )


engine: AsyncEngine = create_engine()

async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ============================================================================
# RLS — Row-Level Security
# ============================================================================


async def set_tenant_context(session: AsyncSession, professional_id: UUID) -> None:
    """
    Define o tenant ativo para a transação corrente via SET LOCAL.

    SET LOCAL aplica a configuração apenas à transação atual — ela é
    automaticamente removida no COMMIT ou ROLLBACK.

    REGRA CRÍTICA: nunca chamar session.commit() manualmente no service layer.
    Se a transação for commitada no meio do request, o SET LOCAL é perdido
    e o RLS fica inativo para o restante da requisição sem nenhum aviso.
    O commit é responsabilidade exclusiva de get_db() no finally.
    """
    await session.execute(
        text("SET LOCAL app.current_tenant = :tenant_id"),
        {"tenant_id": str(professional_id)},
    )


async def clear_tenant_context(session: AsyncSession) -> None:
    """Remove o tenant context (útil em testes)."""
    await session.execute(text("RESET app.current_tenant"))


# ============================================================================
# FastAPI Dependency
# ============================================================================


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Sessão de banco básica — sem RLS.
    Usar em rotas públicas (login, registro, webhook).

    Para rotas protegidas, usar TenantSession de core/deps.py,
    que combina get_db + validação JWT + set_tenant_context.
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ============================================================================
# Lifecycle e Utilitários
# ============================================================================


async def init_db() -> None:
    """Cria tabelas via SQLAlchemy (apenas para testes — produção usa Alembic)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Encerra o pool de conexões (chamado no shutdown do lifespan)."""
    await engine.dispose()


async def check_database_connection() -> bool:
    """Verifica se a conexão com o banco está saudável (usado no /health)."""
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
            return True
    except Exception:
        return False
