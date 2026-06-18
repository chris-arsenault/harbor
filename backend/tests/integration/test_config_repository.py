import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config

from harbor_bot.persistence.config_repository import get_config_value, upsert_config_value
from harbor_bot.persistence.database import create_engine, transaction
from harbor_bot.settings import Settings


def test_config_repository_upserts_and_reads_json_values(postgres_url: str) -> None:
    command.upgrade(_alembic_config(postgres_url), "head")

    asyncio.run(_assert_config_repository(postgres_url))


async def _assert_config_repository(postgres_url: str) -> None:
    engine = create_engine(Settings(DATABASE_URL=postgres_url))
    try:
        async with transaction(engine) as connection:
            assert await get_config_value(connection, "execution.trading_controls") is None
            await upsert_config_value(
                connection,
                key="execution.trading_controls",
                value={"trading_enabled": False},
            )
            assert await get_config_value(connection, "execution.trading_controls") == {
                "trading_enabled": False
            }
            await upsert_config_value(
                connection,
                key="execution.trading_controls",
                value={"trading_enabled": True},
            )
            assert await get_config_value(connection, "execution.trading_controls") == {
                "trading_enabled": True
            }
    finally:
        await engine.dispose()


def _alembic_config(database_url: str) -> Config:
    config = Config(Path("alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config
