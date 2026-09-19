import hashlib
import json
import uuid

from app.core.redis import RedisClient
from app.services.todo_service import TodoFilters


def _user_prefix(user_id: uuid.UUID) -> str:
    return f"todos:list:{user_id}:"


def todo_list_cache_key(
    user_id: uuid.UUID, filters: TodoFilters, page: int, page_size: int
) -> str:
    """Cache key for one page of one user's filtered todo list.

    Every input that changes the result is in the key: without the filters,
    one filtered page would be served for another. They are serialized in a
    fixed order and hashed, so the key has a bounded length whatever the
    keyword, and equal (already normalized) filters always give the same key.

    The user id stays outside the hash, as the prefix, so that
    invalidate_todo_list_cache can still drop all of a user's entries by
    pattern without knowing which filters were used.
    """
    canonical = json.dumps(
        {
            "status": filters.status,
            "tag_id": str(filters.tag_id) if filters.tag_id else None,
            "keyword": filters.keyword,
            "date_from": filters.date_from.isoformat() if filters.date_from else None,
            "date_to": filters.date_to.isoformat() if filters.date_to else None,
            "page": page,
            "page_size": page_size,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{_user_prefix(user_id)}{digest}"


async def invalidate_todo_list_cache(redis: RedisClient, user_id: uuid.UUID) -> None:
    """Drop every cached list page belonging to one user.

    The cache key carries the page, page size and filters, so a user can hold
    many entries at once and a mutation makes all of them stale, not just the
    one read most recently. The pattern is scoped to the user so that nobody
    else's cache is thrown away.
    """
    await redis.delete_pattern(f"{_user_prefix(user_id)}*")
