from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from harbor_bot.persistence.schema import metadata
from harbor_bot.settings import Settings

config = context.config
DEFAULT_ALEMBIC_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/harbor"

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata


def configure_database_url() -> None:
    if config.get_main_option("sqlalchemy.url") == DEFAULT_ALEMBIC_URL:
        config.set_main_option("sqlalchemy.url", Settings().async_database_url)


def run_migrations_offline() -> None:
    configure_database_url()
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    configure_database_url()
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
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
