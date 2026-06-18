import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import select, text

from harbor_bot.persistence.database import create_engine, transaction
from harbor_bot.persistence.schema import config as config_table
from harbor_bot.settings import Settings


def test_transaction_commits_and_rolls_back(postgres_url: str) -> None:
    command.upgrade(_alembic_config(postgres_url), "head")

    asyncio.run(_assert_transaction_behavior(postgres_url))


async def _assert_transaction_behavior(postgres_url: str) -> None:
    engine = create_engine(Settings(DATABASE_URL=postgres_url))
    try:
        try:
            async with transaction(engine) as connection:
                await connection.execute(
                    config_table.insert().values(
                        key="rollback_probe",
                        value_json={"value": "discard"},
                    )
                )
                raise RuntimeError("force rollback")
        except RuntimeError:
            pass

        async with engine.connect() as connection:
            rollback_count = await connection.scalar(
                select(text("count(*)"))
                .select_from(config_table)
                .where(config_table.c.key == "rollback_probe")
            )
        assert rollback_count == 0

        async with transaction(engine) as connection:
            await connection.execute(
                config_table.insert().values(
                    key="commit_probe",
                    value_json={"value": "keep"},
                )
            )

        async with engine.connect() as connection:
            committed = await connection.scalar(
                select(config_table.c.value_json).where(config_table.c.key == "commit_probe")
            )
        assert committed == {"value": "keep"}
    finally:
        await engine.dispose()


def _alembic_config(database_url: str) -> Config:
    config = Config(Path("alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config
