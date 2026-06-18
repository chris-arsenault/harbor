# Migrations

Alembic migration scripts for Harbor PostgreSQL schema changes live here.

The backend Alembic config is `backend/alembic.ini`; it points `script_location` at this directory and loads SQLAlchemy metadata from `harbor_bot.persistence.schema`.

TrueNAS database ownership and credentials are managed by the Ahara platform. Migrations define Harbor schema and seedable database structures only; they do not provision platform resources.
