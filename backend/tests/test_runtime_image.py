from pathlib import Path


def test_backend_image_runs_migrations_before_serving() -> None:
    dockerfile = Path("Dockerfile").read_text()

    assert "COPY alembic.ini ./" in dockerfile
    assert "COPY db ./db" in dockerfile
    assert "alembic upgrade head" in dockerfile
    assert dockerfile.index("alembic upgrade head") < dockerfile.index("uvicorn")


def test_alembic_config_uses_backend_local_migrations() -> None:
    alembic_config = Path("alembic.ini").read_text()

    assert "script_location = db/migrations" in alembic_config
    assert Path("db/migrations/env.py").is_file()
