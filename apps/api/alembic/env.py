"""
Alembic migration environment — async-compatible.

Para o autogenerate detectar todas as tabelas, todos os models
precisam ser importados aqui antes de target_metadata ser lido.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from agenda.models import AvailabilitySlot, BlockedPeriod, Recurrence, Session  # noqa: F401
from alembic import context
from auth.models import RefreshToken  # noqa: F401
from clients.models import Client  # noqa: F401
from core.config import settings
from core.database import Base
from core.models import AuditLog  # noqa: F401

# --- Importar todos os models para registrá-los no Base.metadata ---
from professionals.models import Professional  # noqa: F401
from whatsapp.models import WhatsAppConversation, WhatsAppMessage  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = settings.DATABASE_URL
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
