import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_redis
from app.core.redis import RedisClient
from app.db.session import get_db
from app.models.user import User
from app.schemas.tag import TodoTagAttach
from app.schemas.todo import (
    TodoBulkStatusResponse,
    TodoBulkStatusUpdate,
    TodoCreate,
    TodoListResponse,
    TodoResponse,
    TodoUpdate,
)
from app.services.tag_service import attach_tag, detach_tag, get_tag_by_id
from app.services.todo_cache import invalidate_todo_list_cache, todo_list_cache_key
from app.services.todo_service import (
    TodoFilters,
    TodoStatus,
    bulk_set_completed,
    create_todo,
    delete_todo,
    get_todo_by_id,
    get_todos,
    update_todo,
)

router = APIRouter()

CACHE_TTL = 300  # 5 minutes
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


@router.get("", response_model=TodoListResponse)
async def list_todos(
    page: int = Query(1, ge=1),
    page_size: int | None = Query(None, ge=1, le=MAX_PAGE_SIZE),
    size: int | None = Query(
        None,
        ge=1,
        le=MAX_PAGE_SIZE,
        deprecated=True,
        description="Old name for page_size, kept for existing clients.",
    ),
    # "status" is also the name of the fastapi.status module used below, so
    # the parameter is bound under another name and exposed as "status".
    status_filter: TodoStatus | None = Query(None, alias="status"),
    tag_id: uuid.UUID | None = Query(None),
    keyword: str | None = Query(None, max_length=200),
    date_from: date | None = Query(
        None, description="Inclusive, whole UTC day, YYYY-MM-DD."
    ),
    date_to: date | None = Query(
        None, description="Inclusive, whole UTC day, YYYY-MM-DD."
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """List the current user's todos, newest first, filtered and paginated."""
    if page_size is not None and size is not None and page_size != size:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="page_size and size disagree; send only page_size",
        )
    effective_page_size = page_size or size or DEFAULT_PAGE_SIZE

    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_from must not be after date_to",
        )

    # Another user's tag is answered like a missing one, the same 404 the tag
    # endpoints give. Checked before the cache is read, so the answer does not
    # depend on what happens to be cached.
    if tag_id is not None and not await get_tag_by_id(db, tag_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found",
        )

    filters = TodoFilters.normalize(
        status=status_filter,
        tag_id=tag_id,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
    )
    cache_key = todo_list_cache_key(current_user.id, filters, page, effective_page_size)

    cached = await redis.get(cache_key)
    if cached:
        return TodoListResponse.model_validate_json(cached)

    todos, total = await get_todos(
        db,
        user_id=current_user.id,
        filters=filters,
        skip=(page - 1) * effective_page_size,
        limit=effective_page_size,
    )

    # Every todo here belongs to current_user, so the owner's email is already
    # known; looking it up once per todo was an N+1 query (SEC-14).
    items = [
        TodoResponse.model_validate(todo).model_copy(
            update={"user_email": current_user.email}
        )
        for todo in todos
    ]

    response = TodoListResponse(
        items=items,
        total=total,
        page=page,
        size=effective_page_size,
        page_size=effective_page_size,
        pages=(total + effective_page_size - 1) // effective_page_size,
    )

    await redis.set(cache_key, response.model_dump_json(), ex=CACHE_TTL)

    return response


@router.post("", response_model=TodoResponse, status_code=status.HTTP_201_CREATED)
async def create_new_todo(
    todo_data: TodoCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Create a new todo item."""
    todo = await create_todo(db, todo_data, current_user.id)
    await invalidate_todo_list_cache(redis, current_user.id)
    return todo


# Declared before the /{todo_id} routes so that "bulk-status" can never be
# read as a todo id, should a PATCH /{todo_id} be added later.
@router.patch("/bulk-status", response_model=TodoBulkStatusResponse)
async def bulk_update_status(
    body: TodoBulkStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Mark several todos completed or active, all or none.

    404 if any id is not one of the caller's todos, and then nothing changes.
    A repeated id is applied once.
    """
    todo_ids = set(body.todo_ids)
    if not await bulk_set_completed(db, current_user.id, todo_ids, body.completed):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todo not found",
        )

    await invalidate_todo_list_cache(redis, current_user.id)
    return TodoBulkStatusResponse(updated=len(todo_ids))


@router.get("/{todo_id}", response_model=TodoResponse)
async def get_todo(
    todo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific todo by ID."""
    todo = await get_todo_by_id(db, todo_id, current_user.id)
    if not todo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todo not found",
        )

    return todo


@router.put("/{todo_id}", response_model=TodoResponse)
async def update_existing_todo(
    todo_id: uuid.UUID,
    todo_data: TodoUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Update a todo item."""
    todo = await get_todo_by_id(db, todo_id, current_user.id)
    if not todo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todo not found",
        )

    # exclude_unset: only fields the client actually sent. Without it, an
    # omitted field appears as None and `"description" in update_data` is
    # always true, so any update cleared the description. An explicit
    # `"description": null` is still present and still clears it.
    update_data = todo_data.model_dump(exclude_unset=True)

    # `is not None`, not truthiness: False is a value the client sent, and
    # must be applied just like True.
    if todo_data.completed is not None:
        todo.completed = todo_data.completed

    # Apply other updates
    if update_data.get("title") is not None:
        todo.title = update_data["title"]
    if "description" in update_data:
        todo.description = update_data["description"]

    updated_todo = await update_todo(db, todo, {})
    await invalidate_todo_list_cache(redis, current_user.id)

    return updated_todo


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_todo(
    todo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Delete a todo item."""
    todo = await get_todo_by_id(db, todo_id, current_user.id)
    if not todo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todo not found",
        )

    await delete_todo(db, todo)
    await invalidate_todo_list_cache(redis, current_user.id)

    return None


async def ensure_own_todo_and_tag(
    db: AsyncSession, todo_id: uuid.UUID, tag_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """404 unless both the todo and the tag belong to user_id.

    Both lookups carry the owner in their WHERE clause, so another user's todo
    or tag is treated exactly like one that does not exist. Checking the tag
    as well as the todo is what stops a user attaching someone else's tag to
    their own todo.
    """
    if not await get_todo_by_id(db, todo_id, user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todo not found",
        )
    if not await get_tag_by_id(db, tag_id, user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found",
        )


# Attach and detach both answer 204 whether or not the link already existed:
# the outcome the client asked for holds either way, so repeating a request
# is safe and gives the same answer.
@router.post("/{todo_id}/tags", status_code=status.HTTP_204_NO_CONTENT)
async def attach_tag_to_todo(
    todo_id: uuid.UUID,
    body: TodoTagAttach,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Attach one of the user's tags to one of their todos."""
    await ensure_own_todo_and_tag(db, todo_id, body.tag_id, current_user.id)
    await attach_tag(db, todo_id, body.tag_id)
    await invalidate_todo_list_cache(redis, current_user.id)
    return None


@router.delete("/{todo_id}/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def detach_tag_from_todo(
    todo_id: uuid.UUID,
    tag_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Detach a tag from a todo. Both must belong to the user."""
    await ensure_own_todo_and_tag(db, todo_id, tag_id, current_user.id)
    await detach_tag(db, todo_id, tag_id)
    await invalidate_todo_list_cache(redis, current_user.id)
    return None
