"""The todo list cache: generations, and the race they exist to close.

The defect these guard against: the cache used to be invalidated by deleting
the user's keys *before* the transaction committed. A read that was already in
flight could then query the database before that commit, finish after the
delete, and write its stale answer back into the cache, where it stayed until
the entry expired five minutes later. It was reproduced in the Tier 4 final
audit: the database held one todo while Redis held an empty list for the same
user, with 188 seconds left to live.

A mutation now commits first and then bumps a per-user generation counter,
which is part of every cache key.
"""

import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.todo import Todo
from tests import conftest

EMPTY_PAGE = {
    "items": [],
    "total": 0,
    "page": 1,
    "size": 20,
    "page_size": 20,
    "pages": 0,
}


async def auth(client: AsyncClient, email: str) -> dict:
    """Register a user and return their Authorization header."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def user_id_of(client: AsyncClient, headers: dict) -> str:
    return (await client.get("/api/v1/auth/me", headers=headers)).json()["id"]


def generation(store: dict[str, str], user_id: str) -> int:
    """What the API would read now. No counter yet means generation 0."""
    return int(store.get(f"todos:gen:{user_id}", "0"))


def keys_under(store: dict[str, str], user_id: str, generation_value: int) -> list[str]:
    prefix = f"todos:list:{user_id}:{generation_value}:"
    return [key for key in store if key.startswith(prefix)]


@pytest.mark.asyncio
async def test_a_cached_page_of_the_current_generation_is_served(
    client: AsyncClient, redis_store: dict[str, str]
):
    """The read path really does read the cache.

    Without this, the race test below could pass simply because nothing is
    ever read from the cache at all. A sentinel is written over the entry the
    list request just cached, and has to come back.
    """
    headers = await auth(client, "cache-hit@example.com")
    user_id = await user_id_of(client, headers)
    await client.post("/api/v1/todos", json={"title": "Real"}, headers=headers)

    first = await client.get("/api/v1/todos", headers=headers)
    assert [item["title"] for item in first.json()["items"]] == ["Real"]

    cached_key = keys_under(redis_store, user_id, generation(redis_store, user_id))
    assert len(cached_key) == 1
    redis_store[cached_key[0]] = json.dumps({**EMPTY_PAGE, "total": 99})

    second = await client.get("/api/v1/todos", headers=headers)
    assert second.json()["total"] == 99


@pytest.mark.asyncio
async def test_a_stale_page_written_during_a_mutation_is_never_served(
    client: AsyncClient, redis_store: dict[str, str]
):
    """The race itself, played out step by step.

    A read that began before the mutation writes its stale snapshot under the
    generation it had read. The mutation has since committed and bumped, so
    that entry is no longer addressable and the next read cannot receive it.
    """
    headers = await auth(client, "cache-race@example.com")
    user_id = await user_id_of(client, headers)

    # 1. A read populates the cache under the generation current at the time.
    await client.get("/api/v1/todos", headers=headers)
    stale_generation = generation(redis_store, user_id)
    stale_key = keys_under(redis_store, user_id, stale_generation)[0]

    # 2. A mutation commits and moves the user to the next generation.
    await client.post("/api/v1/todos", json={"title": "Fresh"}, headers=headers)
    assert generation(redis_store, user_id) == stale_generation + 1

    # 3. The read from step 1 — still in flight when the mutation committed —
    #    now writes the empty list it saw, under the generation it read.
    redis_store[stale_key] = json.dumps(EMPTY_PAGE)

    # 4. The next read must not be given it.
    response = await client.get("/api/v1/todos", headers=headers)
    assert response.status_code == 200
    assert [item["title"] for item in response.json()["items"]] == ["Fresh"]
    assert response.json()["total"] == 1
    # The stale entry is still in the store; it is simply unreachable, and
    # will lapse with its own TTL.
    assert redis_store[stale_key] == json.dumps(EMPTY_PAGE)


@pytest.mark.asyncio
async def test_a_stale_filtered_page_is_unreachable_too(
    client: AsyncClient, redis_store: dict[str, str]
):
    """The generation covers every filter variant, not just the default page."""
    headers = await auth(client, "cache-race-filtered@example.com")
    user_id = await user_id_of(client, headers)
    params = {"status": "active", "keyword": "fresh", "page_size": 5}

    await client.get("/api/v1/todos", params=params, headers=headers)
    stale_generation = generation(redis_store, user_id)
    stale_key = keys_under(redis_store, user_id, stale_generation)[0]

    await client.post("/api/v1/todos", json={"title": "Fresh one"}, headers=headers)
    redis_store[stale_key] = json.dumps({**EMPTY_PAGE, "page_size": 5, "size": 5})

    response = await client.get("/api/v1/todos", params=params, headers=headers)
    assert [item["title"] for item in response.json()["items"]] == ["Fresh one"]


@pytest.mark.asyncio
async def test_every_mutation_moves_the_user_to_a_new_generation(
    client: AsyncClient, redis_store: dict[str, str]
):
    """SEC-04's rule, and Tier 4's additions to it, in one place.

    Each of these used to delete the user's cache keys; each must now leave
    the user on a higher generation than before, which is what makes the
    pages cached under the old one unreachable.
    """
    headers = await auth(client, "cache-bumps@example.com")
    user_id = await user_id_of(client, headers)
    todo_id = (
        await client.post("/api/v1/todos", json={"title": "Subject"}, headers=headers)
    ).json()["id"]
    tag_id = (
        await client.post("/api/v1/tags", json={"name": "label"}, headers=headers)
    ).json()["id"]

    mutations = {
        "create todo": lambda: client.post(
            "/api/v1/todos", json={"title": "Another"}, headers=headers
        ),
        "update todo": lambda: client.put(
            f"/api/v1/todos/{todo_id}", json={"completed": True}, headers=headers
        ),
        "attach tag": lambda: client.post(
            f"/api/v1/todos/{todo_id}/tags", json={"tag_id": tag_id}, headers=headers
        ),
        "detach tag": lambda: client.delete(
            f"/api/v1/todos/{todo_id}/tags/{tag_id}", headers=headers
        ),
        "bulk status": lambda: client.patch(
            "/api/v1/todos/bulk-status",
            json={"todo_ids": [todo_id], "completed": False},
            headers=headers,
        ),
        "rename tag": lambda: client.patch(
            f"/api/v1/tags/{tag_id}", json={"name": "renamed"}, headers=headers
        ),
        "delete tag": lambda: client.delete(f"/api/v1/tags/{tag_id}", headers=headers),
        "delete todo": lambda: client.delete(
            f"/api/v1/todos/{todo_id}", headers=headers
        ),
    }

    for name, mutate in mutations.items():
        # Cache a page, so there is something the old generation would serve.
        await client.get("/api/v1/todos", headers=headers)
        before = generation(redis_store, user_id)
        assert keys_under(redis_store, user_id, before), name

        response = await mutate()
        assert response.status_code in (200, 201, 204), (name, response.text)

        after = generation(redis_store, user_id)
        assert after > before, name
        assert keys_under(redis_store, user_id, after) == [], name


@pytest.mark.asyncio
async def test_a_failed_mutation_does_not_move_the_generation(
    client: AsyncClient, redis_store: dict[str, str]
):
    """Nothing was written, so nothing cached is stale."""
    headers = await auth(client, "cache-no-bump@example.com")
    user_id = await user_id_of(client, headers)
    await client.get("/api/v1/todos", headers=headers)
    before = generation(redis_store, user_id)

    missing = str(uuid.uuid4())
    refused = [
        await client.put(
            f"/api/v1/todos/{missing}", json={"completed": True}, headers=headers
        ),
        await client.delete(f"/api/v1/todos/{missing}", headers=headers),
        await client.patch(
            "/api/v1/todos/bulk-status",
            json={"todo_ids": [missing], "completed": True},
            headers=headers,
        ),
        await client.patch(
            f"/api/v1/tags/{missing}", json={"name": "x"}, headers=headers
        ),
    ]

    assert [response.status_code for response in refused] == [404, 404, 404, 404]
    assert generation(redis_store, user_id) == before
    assert keys_under(redis_store, user_id, before)


@pytest.mark.asyncio
async def test_one_users_mutation_leaves_another_users_generation_alone(
    client: AsyncClient, redis_store: dict[str, str]
):
    alice = await auth(client, "cache-gen-alice@example.com")
    bob = await auth(client, "cache-gen-bob@example.com")
    alice_id, bob_id = await user_id_of(client, alice), await user_id_of(client, bob)
    await client.get("/api/v1/todos", headers=alice)
    await client.get("/api/v1/todos", headers=bob)
    bob_generation = generation(redis_store, bob_id)
    bob_keys = keys_under(redis_store, bob_id, bob_generation)

    await client.post("/api/v1/todos", json={"title": "A's"}, headers=alice)

    assert generation(redis_store, alice_id) > 0
    assert generation(redis_store, bob_id) == bob_generation
    # Bob's cached page is still the one he can be served.
    assert keys_under(redis_store, bob_id, bob_generation) == bob_keys


@pytest.mark.asyncio
async def test_the_generation_is_bumped_only_after_the_commit(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    """The ordering the fix depends on, asserted rather than assumed.

    Bumping inside the transaction would look equally correct in the tests
    above, and would still be wrong: a read that saw the new generation could
    query the database before the commit landed and cache that snapshot under
    the generation that stays current afterwards — the original defect, one
    generation along.

    So this checks the property that rules it out: at the moment the counter
    is bumped, the mutation is already visible to a *different* connection,
    which is only true once it is committed.
    """
    headers = await auth(client, "cache-order@example.com")
    user_id = await user_id_of(client, headers)
    committed_rows: list[int] = []
    real_incr = conftest.fake_redis.incr

    async def spy_on_incr(key: str) -> int:
        async with conftest.test_session_maker() as other_connection:
            committed_rows.append(
                await other_connection.scalar(
                    select(func.count())
                    .select_from(Todo)
                    .where(Todo.user_id == uuid.UUID(user_id))
                )
            )
        return await real_incr(key)

    monkeypatch.setattr(conftest.fake_redis, "incr", spy_on_incr)

    response = await client.post(
        "/api/v1/todos", json={"title": "Committed first"}, headers=headers
    )

    assert response.status_code == 201
    assert committed_rows == [1], "the generation moved before the commit"
