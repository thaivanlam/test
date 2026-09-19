import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from sqlalchemy import ColumnElement, exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.tag import todo_tags
from app.models.todo import Todo
from app.schemas.todo import TodoCreate

TodoStatus = Literal["active", "completed"]


@dataclass(frozen=True)
class TodoFilters:
    """The filters of a todo list request, in canonical form.

    Build it with TodoFilters.normalize so that two requests that mean the same
    thing produce equal instances: both the query and the cache key are derived
    from this object, so equal filters always mean equal results.
    """

    status: TodoStatus | None = None
    tag_id: uuid.UUID | None = None
    keyword: str | None = None
    date_from: date | None = None
    date_to: date | None = None

    @classmethod
    def normalize(
        cls,
        status: TodoStatus | None = None,
        tag_id: uuid.UUID | None = None,
        keyword: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> "TodoFilters":
        # The keyword is matched case-insensitively, so "Work", " work " and
        # "WORK" are one search. Lowercasing it here, and searching with the
        # lowercased form, makes that literally true rather than just likely,
        # which is what lets them share a cache entry safely. A blank keyword
        # is no keyword.
        if keyword is not None:
            keyword = keyword.strip().lower() or None
        return cls(status, tag_id, keyword, date_from, date_to)


def _like_pattern(keyword: str) -> str:
    # % and _ are LIKE wildcards; escaped, so a search for "50%" finds "50%"
    # and not every title starting with "50".
    escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _start_of_day_utc(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=timezone.utc)


def _filter_conditions(
    user_id: uuid.UUID, filters: TodoFilters
) -> list[ColumnElement[bool]]:
    """WHERE conditions shared by the page query and the count query.

    One list for both is what keeps total consistent with the items: a filter
    added to one and forgotten in the other is not possible.
    """
    conditions: list[ColumnElement[bool]] = [Todo.user_id == user_id]

    if filters.status == "active":
        conditions.append(Todo.completed.is_(False))
    elif filters.status == "completed":
        conditions.append(Todo.completed.is_(True))

    if filters.tag_id is not None:
        # EXISTS rather than a JOIN: a join yields one row per matching link,
        # so a todo could appear twice and the count would be inflated. With
        # the (todo_id, tag_id) primary key it could not happen for a single
        # tag, but EXISTS does not depend on that. The tag's ownership is
        # checked by the caller; the todo side is covered by user_id above.
        conditions.append(
            exists().where(
                todo_tags.c.todo_id == Todo.id,
                todo_tags.c.tag_id == filters.tag_id,
            )
        )

    if filters.keyword is not None:
        pattern = _like_pattern(filters.keyword)
        conditions.append(
            or_(
                Todo.title.ilike(pattern, escape="\\"),
                Todo.description.ilike(pattern, escape="\\"),
            )
        )

    # Dates are whole UTC days and both ends are inclusive: date_to=2026-09-19
    # takes everything created on the 19th, so the bound is "before the start
    # of the 20th" rather than "at or before midnight of the 19th".
    if filters.date_from is not None:
        conditions.append(Todo.created_at >= _start_of_day_utc(filters.date_from))
    if filters.date_to is not None:
        next_day = filters.date_to + timedelta(days=1)
        conditions.append(Todo.created_at < _start_of_day_utc(next_day))

    return conditions


# Everything TodoResponse reads. refresh() with no names would expire tags
# and leave them unloaded (lazy="raise"), so they are named explicitly.
_RESPONSE_ATTRIBUTES = [
    "id",
    "title",
    "description",
    "completed",
    "user_id",
    "created_at",
    "updated_at",
    "tags",
]


async def create_todo(
    db: AsyncSession, todo_data: TodoCreate, user_id: uuid.UUID
) -> Todo:
    todo = Todo(
        title=todo_data.title,
        description=todo_data.description,
        user_id=user_id,
    )
    db.add(todo)
    await db.flush()
    await db.refresh(todo, attribute_names=_RESPONSE_ATTRIBUTES)
    return todo


async def get_todos(
    db: AsyncSession,
    user_id: uuid.UUID,
    filters: TodoFilters = TodoFilters(),
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[Todo], int]:
    """One page of a user's todos matching filters, and the matching total."""
    conditions = _filter_conditions(user_id, filters)

    # created_at alone is not a total order — todos created in the same
    # microsecond, or imported in bulk, tie — and without a total order rows
    # can move between pages from one request to the next. id breaks the tie.
    query = (
        select(Todo)
        .where(*conditions)
        .options(selectinload(Todo.tags))
        .order_by(Todo.created_at.desc(), Todo.id.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    todos = list(result.scalars().all())

    count_query = select(func.count()).select_from(Todo).where(*conditions)
    total = await db.execute(count_query)

    return todos, total.scalar_one()


async def get_todo_by_id(
    db: AsyncSession, todo_id: uuid.UUID, user_id: uuid.UUID
) -> Todo | None:
    """Get a todo by id, scoped to its owner.

    user_id is required rather than optional so that a caller cannot fetch a
    todo without stating whose it should be.
    """
    result = await db.execute(
        select(Todo)
        .where(Todo.id == todo_id, Todo.user_id == user_id)
        .options(selectinload(Todo.tags))
    )
    return result.scalar_one_or_none()


async def update_todo(db: AsyncSession, todo: Todo, update_data: dict) -> Todo:
    for key, value in update_data.items():
        setattr(todo, key, value)
    await db.flush()
    await db.refresh(todo, attribute_names=_RESPONSE_ATTRIBUTES)
    return todo


async def delete_todo(db: AsyncSession, todo: Todo) -> None:
    await db.delete(todo)
    await db.flush()


async def bulk_set_completed(
    db: AsyncSession,
    user_id: uuid.UUID,
    todo_ids: set[uuid.UUID],
    completed: bool,
) -> bool:
    """Set completed on every todo in todo_ids, or on none of them.

    Returns False, having written nothing, unless every id is a todo owned by
    user_id; a missing id and another user's id are not told apart.

    The ownership check is one SELECT, not one per id, and it locks the rows
    it finds (FOR UPDATE; SQLite ignores it) so none can be deleted or change
    owner between the check and the write. The write is then a single UPDATE
    in the same transaction, still scoped by user_id; its row count is checked
    as well, and a mismatch rolls the whole thing back.
    """
    owned = await db.scalars(
        select(Todo.id)
        .where(Todo.user_id == user_id, Todo.id.in_(todo_ids))
        .with_for_update()
    )
    if set(owned) != todo_ids:
        return False

    result = await db.execute(
        update(Todo)
        .where(Todo.user_id == user_id, Todo.id.in_(todo_ids))
        .values(completed=completed)
        # Nothing in the session holds these todos, so there is nothing to
        # synchronize; updated_at is still set by the column's onupdate.
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != len(todo_ids):
        await db.rollback()
        return False
    return True
