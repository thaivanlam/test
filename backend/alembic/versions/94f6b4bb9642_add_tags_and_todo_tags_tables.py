"""add tags and todo_tags tables

Revision ID: 94f6b4bb9642
Revises: a5ac6aec37c4
Create Date: 2026-09-19 21:00:00.000000

Both tables are new and empty, so their indexes are built inside the
migration's transaction; nothing here scans an existing large table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "94f6b4bb9642"
down_revision: Union[str, None] = "a5ac6aec37c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tags_user_id", "tags", ["user_id"])
    # Case-insensitive uniqueness per user: "Work" and "work" conflict for the
    # same user, but two users may each have a tag of that name.
    op.create_index(
        "uq_tags_user_id_lower_name",
        "tags",
        ["user_id", sa.text("lower(name)")],
        unique=True,
    )

    op.create_table(
        "todo_tags",
        sa.Column("todo_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        # Deleting a todo or a tag removes its links.
        sa.ForeignKeyConstraint(["todo_id"], ["todos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("todo_id", "tag_id"),
    )
    op.create_index("ix_todo_tags_todo_id", "todo_tags", ["todo_id"])
    op.create_index("ix_todo_tags_tag_id", "todo_tags", ["tag_id"])


def downgrade() -> None:
    # todo_tags references tags, so it goes first. Dropping a table drops its
    # indexes with it.
    op.drop_table("todo_tags")
    op.drop_table("tags")
