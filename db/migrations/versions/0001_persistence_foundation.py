"""Create persistence foundation tables.

Revision ID: 0001_persistence_foundation
Revises:
Create Date: 2026-06-17
"""

from collections.abc import Sequence

from alembic import op

from harbor_bot.persistence.schema import metadata

revision: str = "0001_persistence_foundation"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    metadata.drop_all(bind=op.get_bind())
