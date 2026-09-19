"""add index on todos.user_id

Revision ID: a5ac6aec37c4
Revises: a0790c76a129
Create Date: 2026-09-19 18:30:00.000000

Every per-user todo query filters on user_id, and nothing indexed it, so each
one scanned the whole table. See docs/DB_PERFORMANCE.md for the measurements
and for why a single-column index was chosen over (user_id, created_at).
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a5ac6aec37c4"
down_revision: Union[str, None] = "a0790c76a129"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = "ix_todos_user_id"


def upgrade() -> None:
    # CONCURRENTLY builds the index without blocking writes to the table,
    # which matters on a large production table. It cannot run inside a
    # transaction block, and alembic/env.py runs migrations in one, so
    # autocommit_block ends that transaction around this statement.
    #
    # If a concurrent build fails part-way, Postgres leaves an INVALID index
    # of this name behind. Drop it with DROP INDEX CONCURRENTLY before
    # retrying.
    with op.get_context().autocommit_block():
        op.create_index(
            INDEX_NAME,
            "todos",
            ["user_id"],
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(
            INDEX_NAME,
            table_name="todos",
            postgresql_concurrently=True,
        )
