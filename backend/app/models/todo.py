import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class Todo(Base):
    """Todo model."""

    __tablename__ = "todos"
    # Created by migration 000a81696068, replacing the single-column
    # ix_todos_user_id from a5ac6aec37c4. user_id leads, so it also serves
    # every query that filters on user_id alone. Declared here so the model
    # matches the schema and autogenerate does not propose dropping it.
    __table_args__ = (
        Index(
            "ix_todos_user_id_completed_created_at",
            "user_id",
            "completed",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
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

    # Relationships
    user: Mapped["User"] = relationship(  # noqa: F821
        "User",
        back_populates="todos",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Todo {self.title}>"
