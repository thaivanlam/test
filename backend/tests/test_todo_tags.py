"""Attaching tags to todos and detaching them."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.tag import todo_tags
from tests import conftest


async def auth(client: AsyncClient, email: str) -> dict:
    """Register a user and return their Authorization header."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def new_todo(client: AsyncClient, headers: dict, title: str = "Todo") -> str:
    response = await client.post(
        "/api/v1/todos", json={"title": title}, headers=headers
    )
    return response.json()["id"]


async def new_tag(client: AsyncClient, headers: dict, name: str = "Tag") -> str:
    response = await client.post("/api/v1/tags", json={"name": name}, headers=headers)
    return response.json()["id"]


async def attach(client: AsyncClient, headers: dict, todo_id: str, tag_id: str):
    return await client.post(
        f"/api/v1/todos/{todo_id}/tags", json={"tag_id": tag_id}, headers=headers
    )


async def detach(client: AsyncClient, headers: dict, todo_id: str, tag_id: str):
    return await client.delete(
        f"/api/v1/todos/{todo_id}/tags/{tag_id}", headers=headers
    )


async def links() -> set[tuple[str, str]]:
    """Every (todo_id, tag_id) row in todo_tags, read from the database."""
    async with conftest.test_session_maker() as session:
        rows = (await session.execute(select(todo_tags))).all()
    return {(str(todo_id), str(tag_id)) for todo_id, tag_id in rows}


@pytest.mark.asyncio
async def test_attach_own_tag_to_own_todo(client: AsyncClient):
    headers = await auth(client, "attach@example.com")
    todo_id = await new_todo(client, headers)
    tag_id = await new_tag(client, headers)

    response = await attach(client, headers, todo_id, tag_id)

    assert response.status_code == 204
    assert await links() == {(todo_id, tag_id)}


@pytest.mark.asyncio
async def test_attach_same_tag_twice_is_idempotent(client: AsyncClient):
    """A repeat attach answers 204 like the first one and adds no second row."""
    headers = await auth(client, "attach-twice@example.com")
    todo_id = await new_todo(client, headers)
    tag_id = await new_tag(client, headers)

    first = await attach(client, headers, todo_id, tag_id)
    second = await attach(client, headers, todo_id, tag_id)

    assert first.status_code == 204
    assert second.status_code == 204
    assert await links() == {(todo_id, tag_id)}


@pytest.mark.asyncio
async def test_detach_attached_tag(client: AsyncClient):
    headers = await auth(client, "detach@example.com")
    todo_id = await new_todo(client, headers)
    removed = await new_tag(client, headers, "Removed")
    kept = await new_tag(client, headers, "Kept")
    await attach(client, headers, todo_id, removed)
    await attach(client, headers, todo_id, kept)

    response = await detach(client, headers, todo_id, removed)

    assert response.status_code == 204
    assert await links() == {(todo_id, kept)}
    # Only the link goes; the tag and the todo are both still there.
    tag = await client.get(f"/api/v1/tags/{removed}", headers=headers)
    todo = await client.get(f"/api/v1/todos/{todo_id}", headers=headers)
    assert tag.status_code == 200
    assert todo.status_code == 200


@pytest.mark.asyncio
async def test_detach_same_tag_twice_is_idempotent(client: AsyncClient):
    """Detaching a tag that is not attached answers 204, not 404 or 500."""
    headers = await auth(client, "detach-twice@example.com")
    todo_id = await new_todo(client, headers)
    tag_id = await new_tag(client, headers)
    await attach(client, headers, todo_id, tag_id)

    first = await detach(client, headers, todo_id, tag_id)
    second = await detach(client, headers, todo_id, tag_id)

    assert first.status_code == 204
    assert second.status_code == 204
    assert await links() == set()


@pytest.mark.asyncio
async def test_other_users_todo_is_not_found(client: AsyncClient):
    owner = await auth(client, "tt-todo-owner@example.com")
    intruder = await auth(client, "tt-todo-intruder@example.com")
    owner_todo = await new_todo(client, owner)
    owner_tag = await new_tag(client, owner)
    await attach(client, owner, owner_todo, owner_tag)
    intruder_tag = await new_tag(client, intruder)

    attach_response = await attach(client, intruder, owner_todo, intruder_tag)
    detach_response = await detach(client, intruder, owner_todo, owner_tag)

    for response in (attach_response, detach_response):
        assert response.status_code == 404
        assert response.json() == {"detail": "Todo not found"}
    # The intruder's tag was not attached, and the owner's link was not removed.
    assert await links() == {(owner_todo, owner_tag)}


@pytest.mark.asyncio
async def test_other_users_tag_is_not_found(client: AsyncClient):
    """A user cannot attach someone else's tag to their own todo."""
    owner = await auth(client, "tt-tag-owner@example.com")
    intruder = await auth(client, "tt-tag-intruder@example.com")
    owner_tag = await new_tag(client, owner)
    intruder_todo = await new_todo(client, intruder)

    attach_response = await attach(client, intruder, intruder_todo, owner_tag)
    detach_response = await detach(client, intruder, intruder_todo, owner_tag)

    for response in (attach_response, detach_response):
        assert response.status_code == 404
        assert response.json() == {"detail": "Tag not found"}
    assert await links() == set()
    # The owner's tag is unchanged.
    tag = await client.get(f"/api/v1/tags/{owner_tag}", headers=owner)
    assert tag.status_code == 200


@pytest.mark.asyncio
async def test_nonexistent_todo_is_not_found(client: AsyncClient):
    headers = await auth(client, "tt-no-todo@example.com")
    tag_id = await new_tag(client, headers)
    missing = str(uuid.uuid4())

    attach_response = await attach(client, headers, missing, tag_id)
    detach_response = await detach(client, headers, missing, tag_id)

    for response in (attach_response, detach_response):
        assert response.status_code == 404
        assert response.json() == {"detail": "Todo not found"}
    assert await links() == set()


@pytest.mark.asyncio
async def test_nonexistent_tag_is_not_found(client: AsyncClient):
    headers = await auth(client, "tt-no-tag@example.com")
    todo_id = await new_todo(client, headers)
    missing = str(uuid.uuid4())

    attach_response = await attach(client, headers, todo_id, missing)
    detach_response = await detach(client, headers, todo_id, missing)

    for response in (attach_response, detach_response):
        assert response.status_code == 404
        assert response.json() == {"detail": "Tag not found"}
    assert await links() == set()


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [{}, {"tag_id": None}, {"tag_id": "not-a-uuid"}])
async def test_attach_rejects_invalid_body(client: AsyncClient, body: dict):
    headers = await auth(client, "tt-invalid@example.com")
    todo_id = await new_todo(client, headers)

    response = await client.post(
        f"/api/v1/todos/{todo_id}/tags", json=body, headers=headers
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_attach_and_detach_require_authentication(client: AsyncClient):
    todo_id, tag_id = uuid.uuid4(), uuid.uuid4()

    attach_response = await client.post(
        f"/api/v1/todos/{todo_id}/tags", json={"tag_id": str(tag_id)}
    )
    detach_response = await client.delete(f"/api/v1/todos/{todo_id}/tags/{tag_id}")

    assert attach_response.status_code == 403
    assert detach_response.status_code == 403


def current_generation(store: dict[str, str], user_id: str) -> str:
    """The generation the API would read now; absent means generation 0."""
    return store.get(f"todos:gen:{user_id}", "0")


def cached_list_keys(store: dict[str, str], user_id: str) -> list[str]:
    """Cached pages the user can still be served.

    A mutation moves the user to a new generation rather than deleting keys,
    so entries from earlier generations may remain in the store; they can
    never be read again and are not counted here.
    """
    generation = current_generation(store, user_id)
    prefix = f"todos:list:{user_id}:{generation}:"
    return [key for key in store if key.startswith(prefix)]


async def user_id_of(client: AsyncClient, headers: dict) -> str:
    return (await client.get("/api/v1/auth/me", headers=headers)).json()["id"]


# The list response does not include tags yet, so an attach or detach does not
# change what a stale cache entry would return. These tests therefore look at
# the cache keys themselves, through the redis_store fixture, rather than at
# the list contents as the todo cache tests do.
@pytest.mark.asyncio
async def test_attach_invalidates_only_own_cached_lists(
    client: AsyncClient, redis_store: dict[str, str]
):
    alice = await auth(client, "tt-cache-attach-a@example.com")
    bob = await auth(client, "tt-cache-attach-b@example.com")
    todo_id = await new_todo(client, alice)
    tag_id = await new_tag(client, alice)
    alice_id, bob_id = await user_id_of(client, alice), await user_id_of(client, bob)

    await client.get("/api/v1/todos?page=1&size=5", headers=alice)
    await client.get("/api/v1/todos?page=2&size=5", headers=alice)
    await client.get("/api/v1/todos", headers=bob)
    assert len(cached_list_keys(redis_store, alice_id)) == 2
    assert len(cached_list_keys(redis_store, bob_id)) == 1

    response = await attach(client, alice, todo_id, tag_id)

    assert response.status_code == 204
    assert cached_list_keys(redis_store, alice_id) == []
    assert len(cached_list_keys(redis_store, bob_id)) == 1


@pytest.mark.asyncio
async def test_detach_invalidates_only_own_cached_lists(
    client: AsyncClient, redis_store: dict[str, str]
):
    alice = await auth(client, "tt-cache-detach-a@example.com")
    bob = await auth(client, "tt-cache-detach-b@example.com")
    todo_id = await new_todo(client, alice)
    tag_id = await new_tag(client, alice)
    await attach(client, alice, todo_id, tag_id)
    alice_id, bob_id = await user_id_of(client, alice), await user_id_of(client, bob)

    await client.get("/api/v1/todos?page=1&size=5", headers=alice)
    await client.get("/api/v1/todos?page=2&size=5", headers=alice)
    await client.get("/api/v1/todos", headers=bob)
    assert len(cached_list_keys(redis_store, alice_id)) == 2
    assert len(cached_list_keys(redis_store, bob_id)) == 1

    response = await detach(client, alice, todo_id, tag_id)

    assert response.status_code == 204
    assert cached_list_keys(redis_store, alice_id) == []
    assert len(cached_list_keys(redis_store, bob_id)) == 1
