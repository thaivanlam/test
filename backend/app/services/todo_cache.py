import hashlib
import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import RedisClient
from app.services.todo_service import TodoFilters


def todo_list_generation_key(user_id: uuid.UUID) -> str:
    return f"todos:gen:{user_id}"


async def current_todo_list_generation(redis: RedisClient, user_id: uuid.UUID) -> int:
    """The generation a read should cache under.

    Absent means nobody has written yet, which is generation 0. The read path
    never creates the counter: a write on the read path would be one more
    thing that can interleave with a mutation.
    """
    value = await redis.get(todo_list_generation_key(user_id))
    return int(value) if value is not None else 0


def todo_list_cache_key(
    user_id: uuid.UUID,
    generation: int,
    filters: TodoFilters,
    page: int,
    page_size: int,
) -> str:
    """Cache key for one page of one user's filtered todo list.

    Every input that changes the result is in the key: without the filters,
    one filtered page would be served for another. They are serialized in a
    fixed order and hashed, so the key has a bounded length whatever the
    keyword, and equal (already normalized) filters always give the same key.

    The user id and the generation stay outside the hash so that a key can be
    read back as belonging to one user and one generation.
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
    return f"todos:list:{user_id}:{generation}:{digest}"


async def commit_and_bump_todo_list_generation(
    db: AsyncSession, redis: RedisClient, user_id: uuid.UUID
) -> None:
    """Commit the mutation, then move the user's cached lists out of reach.

    The order is the whole point, and it is the opposite of deleting the keys
    before the commit, which is what this replaces.

    A read caches under the generation it read *before* it queried the
    database. So:

    * A read that saw generation V may hold a snapshot from before this
      commit, and may still be in flight — it will write that snapshot under
      V. After the bump below, current is V+1, so nothing will ever read it
      again; it expires on its own TTL.
    * A read that sees V+1 can only have seen it after this bump, which is
      after the commit, so the database it then queries already contains this
      mutation.

    Bumping before the commit instead would put the stale snapshot under the
    generation that stays current afterwards, which is the defect this fixes.

    The window between the commit and the bump is the one thing that cannot be
    removed without a transaction spanning Postgres and Redis: a read landing
    inside it still sees generation V and may be served a V entry. It is the
    length of one INCR, against the five-minute TTL of the entry itself.

    get_db commits again after the endpoint returns; with nothing left pending
    that is a no-op.
    """
    await db.commit()
    await redis.incr(todo_list_generation_key(user_id))
