"""stored files (S3/MinIO object storage)

Revision ID: 70f128639b04
Revises: 3a1c7d4e9b21
Create Date: 2026-06-19 19:06:09.019667

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "70f128639b04"
down_revision: str | None = "3a1c7d4e9b21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stored_files",
        sa.Column("key", sa.String(length=1024), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.Enum("pending", "stored", name="file_status"), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("team_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_stored_files_key"), "stored_files", ["key"], unique=True)
    op.create_index(op.f("ix_stored_files_owner_id"), "stored_files", ["owner_id"], unique=False)
    op.create_index(op.f("ix_stored_files_status"), "stored_files", ["status"], unique=False)
    op.create_index(op.f("ix_stored_files_team_id"), "stored_files", ["team_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_stored_files_team_id"), table_name="stored_files")
    op.drop_index(op.f("ix_stored_files_status"), table_name="stored_files")
    op.drop_index(op.f("ix_stored_files_owner_id"), table_name="stored_files")
    op.drop_index(op.f("ix_stored_files_key"), table_name="stored_files")
    op.drop_table("stored_files")
    # Postgres keeps the enum type after drop_table; clean it up so a re-run of
    # upgrade() does not collide with an existing "file_status" type.
    sa.Enum(name="file_status").drop(op.get_bind(), checkfirst=True)
