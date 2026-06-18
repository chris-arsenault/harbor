import asyncio
from copy import deepcopy
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from harbor_bot.config.defaults import load_default_config
from harbor_bot.persistence.config_repository import seed_default_config
from harbor_bot.persistence.schema import config as config_table


def test_default_config_seed_is_idempotent_and_preserves_edits(postgres_url: str) -> None:
    command.upgrade(_alembic_config(postgres_url), "head")

    asyncio.run(_seed_and_assert(postgres_url))


async def _seed_and_assert(postgres_url: str) -> None:
    defaults = load_default_config()
    engine = create_async_engine(postgres_url)
    try:
        async with engine.begin() as connection:
            inserted = await seed_default_config(connection, defaults)
        assert inserted == len(defaults)

        async with engine.begin() as connection:
            inserted_again = await seed_default_config(connection, defaults)
        assert inserted_again == 0

        edited = deepcopy(defaults["sweep_buffer_pips"])
        edited["value"] = 2.0
        async with engine.begin() as connection:
            await connection.execute(
                config_table.update()
                .where(config_table.c.key == "sweep_buffer_pips")
                .values(value_json=edited)
            )
            inserted_after_edit = await seed_default_config(connection, defaults)

        assert inserted_after_edit == 0

        async with engine.connect() as connection:
            rows = (
                await connection.execute(text("SELECT key, value_json FROM config ORDER BY key"))
            ).mappings()
            seeded = {row["key"]: row["value_json"] for row in rows}

        assert set(seeded) == set(defaults)
        assert seeded["instrument"] == {"value": "EUR_USD"}
        assert seeded["sweep_buffer_pips"] == edited
    finally:
        await engine.dispose()


def _alembic_config(database_url: str) -> Config:
    config = Config(Path("alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config
