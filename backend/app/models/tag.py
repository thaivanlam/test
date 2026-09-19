import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Table, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Links todos to tags. Both foreign keys cascade on delete, so removing a todo
# or a tag removes its links in the database without a separate step.
todo_tags = Table(
    "todo_tags",
    Base.metadata,
    Column(
        "todo_id",
        Uuid,
        ForeignKey("todos.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        Uuid,
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Index("ix_todo_tags_todo_id", "todo_id"),
    Index("ix_todo_tags_tag_id", "tag_id"),
)


class Tag(Base):
    """A label a user can attach to their own todos."""

    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    color: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Tag {self.name}>"


# Tag names are unique per user regardless of case, so "Work" and "work"
# conflict for one user but not across users. Enforced by the database, so
# concurrent inserts cannot both succeed.
Index(
    "uq_tags_user_id_lower_name",
    Tag.user_id,
    func.lower(Tag.name),
    unique=True,
)
