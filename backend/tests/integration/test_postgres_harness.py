from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def test_postgres_harness_provides_real_async_postgres(postgres_url: str) -> None:
    assert postgres_url.startswith("postgresql+asyncpg://")

    engine = create_async_engine(postgres_url)
    try:
        async with engine.connect() as connection:
            database_name = await connection.scalar(text("SELECT current_database()"))
            server_version = await connection.scalar(text("SHOW server_version"))
    finally:
        await engine.dispose()

    assert database_name == "test"
    assert server_version is not None
