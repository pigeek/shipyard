"""user locale preference (i18n)

Revision ID: a1b2c3d4e5f6
Revises: 70f128639b04
Create Date: 2026-06-19 22:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "70f128639b04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("locale", sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "locale")
