"""replace todos user_id index with (user_id, completed, created_at)

Revision ID: 000a81696068
Revises: 94f6b4bb9642
Create Date: 2026-09-19 21:05:00.000000

The composite index has user_id as its leading column, so it serves every
query that filters on user_id alone, which is what ix_todos_user_id was for.
Keeping both would make every write to todos maintain two indexes to no gain.
The planner was checked with the composite index as the only one before this
was written: every per-user query still uses an index, and status-filtered
queries read far fewer pages.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "000a81696068"
down_revision: Union[str, None] = "94f6b4bb9642"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_INDEX = "ix_todos_user_id_completed_created_at"
OLD_INDEX = "ix_todos_user_id"


def upgrade() -> None:
    # CONCURRENTLY keeps todos writable during the build, and cannot run in a
    # transaction block; alembic/env.py runs migrations in one, so
    # autocommit_block ends that transaction around these statements.
    #
    # The new index is built before the old one is dropped, so there is never
    # a moment with no index on user_id.
    #
    # If a concurrent build fails part-way, Postgres leaves an INVALID index
    # behind. Drop it with DROP INDEX CONCURRENTLY before retrying.
    with op.get_context().autocommit_block():
        op.create_index(
            NEW_INDEX,
            "todos",
            ["user_id", "completed", "created_at"],
            postgresql_concurrently=True,
        )
        op.drop_index(
            OLD_INDEX,
            table_name="todos",
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    # Same order in reverse: restore the old index before removing the new one.
    with op.get_context().autocommit_block():
        op.create_index(
            OLD_INDEX,
            "todos",
            ["user_id"],
            postgresql_concurrently=True,
        )
        op.drop_index(
            NEW_INDEX,
            table_name="todos",
            postgresql_concurrently=True,
        )
