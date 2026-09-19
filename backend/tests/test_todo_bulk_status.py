"""PATCH /api/v1/todos/bulk-status."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.todo import Todo
from tests import conftest

URL = "/api/v1/todos/bulk-status"


async def auth(client: AsyncClient, email: str) -> dict:
    """Register a user and return their Authorization header."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def new_todos(client: AsyncClient, headers: dict, count: int) -> list[str]:
    ids = []
    for index in range(count):
        response = await client.post(
            "/api/v1/todos", json={"title": f"todo {index}"}, headers=headers
        )
        ids.append(response.json()["id"])
    return ids


async def bulk(client: AsyncClient, headers: dict, todo_ids: list, completed):
    return await client.patch(
        URL, json={"todo_ids": todo_ids, "completed": completed}, headers=headers
    )


async def db_state(todo_ids: list[str]) -> dict[str, tuple]:
    """(completed, updated_at) per todo, read from the database, not the API."""
    async with conftest.test_session_maker() as session:
        rows = await session.execute(
            select(Todo.id, Todo.completed, Todo.updated_at).where(
                Todo.id.in_([uuid.UUID(i) for i in todo_ids])
            )
        )
        return {str(r.id): (r.completed, r.updated_at) for r in rows}


def completed_flags(state: dict[str, tuple]) -> dict[str, bool]:
    return {todo_id: flags[0] for todo_id, flags in state.items()}


async def user_id_of(client: AsyncClient, headers: dict) -> str:
    return (await client.get("/api/v1/auth/me", headers=headers)).json()["id"]


def list_keys(store: dict[str, str], user_id: str) -> set[str]:
    return {key for key in store if key.startswith(f"todos:list:{user_id}:")}


# --- success ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_complete_several_todos(client: AsyncClient):
    headers = await auth(client, "bulk-complete@example.com")
    ids = await new_todos(client, headers, 3)
    untouched = (await new_todos(client, headers, 1))[0]
    before = await db_state(ids)

    response = await bulk(client, headers, ids, True)

    assert response.status_code == 200
    assert response.json() == {"updated": 3}
    after = await db_state([*ids, untouched])
    assert completed_flags(after) == {**{i: True for i in ids}, untouched: False}
    # updated_at moves too, as it does for a single update.
    assert all(after[i][1] > before[i][1] for i in ids)


@pytest.mark.asyncio
async def test_bulk_set_back_to_active(client: AsyncClient):
    """completed=false is a value like any other (the SEC-05 rule, in bulk)."""
    headers = await auth(client, "bulk-active@example.com")
    ids = await new_todos(client, headers, 3)
    await bulk(client, headers, ids, True)

    response = await bulk(client, headers, ids[:2], False)

    assert response.status_code == 200
    assert response.json() == {"updated": 2}
    assert completed_flags(await db_state(ids)) == {
        ids[0]: False,
        ids[1]: False,
        ids[2]: True,
    }


@pytest.mark.asyncio
async def test_duplicate_ids_are_applied_once(client: AsyncClient):
    headers = await auth(client, "bulk-dupes@example.com")
    first, second = await new_todos(client, headers, 2)

    response = await bulk(client, headers, [first, second, first, first], True)

    # Deterministic: the duplicates neither fail the request nor inflate the
    # count; the count is of distinct todos changed.
    assert response.status_code == 200
    assert response.json() == {"updated": 2}
    assert completed_flags(await db_state([first, second])) == {
        first: True,
        second: True,
    }


@pytest.mark.asyncio
async def test_bulk_update_keeps_other_fields_and_tags(client: AsyncClient):
    headers = await auth(client, "bulk-keeps@example.com")
    created = await client.post(
        "/api/v1/todos",
        json={"title": "keep me", "description": "and me"},
        headers=headers,
    )
    todo_id = created.json()["id"]
    tag = await client.post("/api/v1/tags", json={"name": "t"}, headers=headers)
    await client.post(
        f"/api/v1/todos/{todo_id}/tags",
        json={"tag_id": tag.json()["id"]},
        headers=headers,
    )

    await bulk(client, headers, [todo_id], True)

    fetched = (await client.get(f"/api/v1/todos/{todo_id}", headers=headers)).json()
    assert fetched["completed"] is True
    assert fetched["title"] == "keep me"
    assert fetched["description"] == "and me"
    assert [t["name"] for t in fetched["tags"]] == ["t"]


# --- validation -------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {"todo_ids": [], "completed": True},
        {"todo_ids": ["not-a-uuid"], "completed": True},
        {"completed": True},
        {"todo_ids": None, "completed": True},
        {"todo_ids": "00000000-0000-0000-0000-000000000001", "completed": True},
        {"todo_ids": ["00000000-0000-0000-0000-000000000001"]},
        {"todo_ids": ["00000000-0000-0000-0000-000000000001"], "completed": None},
        {"todo_ids": ["00000000-0000-0000-0000-000000000001"], "completed": "yes"},
        {"todo_ids": ["00000000-0000-0000-0000-000000000001"], "completed": 1},
        {"todo_ids": [str(uuid.uuid4()) for _ in range(101)], "completed": True},
    ],
    ids=[
        "empty",
        "malformed-uuid",
        "ids-missing",
        "ids-null",
        "ids-not-a-list",
        "completed-missing",
        "completed-null",
        "completed-string",
        "completed-int",
        "over-100-ids",
    ],
)
async def test_malformed_payload_is_rejected(client: AsyncClient, body: dict):
    headers = await auth(client, "bulk-invalid@example.com")

    response = await client.patch(URL, json=body, headers=headers)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_malformed_uuid_among_valid_ids_changes_nothing(client: AsyncClient):
    headers = await auth(client, "bulk-invalid-mixed@example.com")
    ids = await new_todos(client, headers, 2)

    response = await bulk(client, headers, [*ids, "not-a-uuid"], True)

    assert response.status_code == 422
    assert completed_flags(await db_state(ids)) == {i: False for i in ids}


@pytest.mark.asyncio
async def test_bulk_requires_authentication(client: AsyncClient):
    response = await client.patch(
        URL, json={"todo_ids": [str(uuid.uuid4())], "completed": True}
    )

    assert response.status_code == 403


# --- ownership and all-or-nothing -------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("position", ["first", "last"])
async def test_nonexistent_id_fails_whole_request(client: AsyncClient, position):
    headers = await auth(client, f"bulk-missing-{position}@example.com")
    ids = await new_todos(client, headers, 3)
    before = await db_state(ids)
    missing = str(uuid.uuid4())
    todo_ids = [missing, *ids] if position == "first" else [*ids, missing]

    response = await bulk(client, headers, todo_ids, True)

    assert response.status_code == 404
    assert response.json() == {"detail": "Todo not found"}
    # Not one of the valid todos changed, not even updated_at.
    assert await db_state(ids) == before


@pytest.mark.asyncio
async def test_mixed_ownership_fails_and_changes_neither_user(client: AsyncClient):
    alice = await auth(client, "bulk-mixed-alice@example.com")
    bob = await auth(client, "bulk-mixed-bob@example.com")
    alice_ids = await new_todos(client, alice, 2)
    bob_ids = await new_todos(client, bob, 1)
    before = await db_state([*alice_ids, *bob_ids])

    response = await bulk(client, alice, [*alice_ids, *bob_ids], True)

    # The same 404 as for an id that does not exist: the response does not
    # reveal that Bob's todo is there.
    assert response.status_code == 404
    assert response.json() == {"detail": "Todo not found"}
    assert await db_state([*alice_ids, *bob_ids]) == before


@pytest.mark.asyncio
async def test_cannot_bulk_update_only_other_users_todos(client: AsyncClient):
    alice = await auth(client, "bulk-iso-alice@example.com")
    bob = await auth(client, "bulk-iso-bob@example.com")
    bob_ids = await new_todos(client, bob, 2)
    before = await db_state(bob_ids)

    response = await bulk(client, alice, bob_ids, True)

    assert response.status_code == 404
    assert await db_state(bob_ids) == before
    listed = await client.get("/api/v1/todos", headers=bob)
    assert [i["completed"] for i in listed.json()["items"]] == [False, False]


# --- cache ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_update_invalidates_every_cached_list_of_the_user(
    client: AsyncClient, redis_store: dict[str, str]
):
    alice = await auth(client, "bulk-cache-alice@example.com")
    bob = await auth(client, "bulk-cache-bob@example.com")
    alice_id, bob_id = await user_id_of(client, alice), await user_id_of(client, bob)
    ids = await new_todos(client, alice, 3)
    await new_todos(client, bob, 1)

    for params in (
        {},
        {"status": "active"},
        {"status": "completed"},
        {"page": 2, "page_size": 2},
        {"keyword": "todo"},
    ):
        await client.get("/api/v1/todos", params=params, headers=alice)
    await client.get("/api/v1/todos", headers=bob)
    assert len(list_keys(redis_store, alice_id)) == 5
    assert len(list_keys(redis_store, bob_id)) == 1

    response = await bulk(client, alice, ids, True)

    assert response.status_code == 200
    assert list_keys(redis_store, alice_id) == set()
    assert len(list_keys(redis_store, bob_id)) == 1
    # And the next read reflects the change rather than a stale page.
    done = await client.get(
        "/api/v1/todos", params={"status": "completed"}, headers=alice
    )
    assert done.json()["total"] == 3


@pytest.mark.asyncio
async def test_failed_bulk_update_leaves_cache_alone(
    client: AsyncClient, redis_store: dict[str, str]
):
    """Nothing changed, so nothing cached is stale and nothing is dropped."""
    alice = await auth(client, "bulk-cache-fail@example.com")
    alice_id = await user_id_of(client, alice)
    ids = await new_todos(client, alice, 2)
    await client.get("/api/v1/todos", headers=alice)
    cached = list_keys(redis_store, alice_id)
    assert len(cached) == 1

    response = await bulk(client, alice, [*ids, str(uuid.uuid4())], True)

    assert response.status_code == 404
    assert list_keys(redis_store, alice_id) == cached
