"""Todo tests."""

import pytest
from httpx import AsyncClient


async def get_auth_token(client: AsyncClient, email: str = "todo@example.com") -> str:
    """Helper to register and get auth token."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_create_todo(client: AsyncClient):
    """Test creating a new todo."""
    token = await get_auth_token(client, "create@example.com")

    response = await client.post(
        "/api/v1/todos",
        json={"title": "Test Todo", "description": "A test todo item"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Todo"
    assert data["description"] == "A test todo item"
    assert data["completed"] is False


@pytest.mark.asyncio
async def test_get_todos(client: AsyncClient):
    """Test getting todo list."""
    token = await get_auth_token(client, "list@example.com")

    # Create a todo first
    await client.post(
        "/api/v1/todos",
        json={"title": "List Todo"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Get todos
    response = await client.get(
        "/api/v1/todos",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_update_todo(client: AsyncClient):
    """Test updating a todo."""
    token = await get_auth_token(client, "update@example.com")

    # Create a todo
    create_response = await client.post(
        "/api/v1/todos",
        json={"title": "Update Me"},
        headers={"Authorization": f"Bearer {token}"},
    )
    todo_id = create_response.json()["id"]

    # Update it
    response = await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"title": "Updated Title", "completed": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"


@pytest.mark.asyncio
async def test_completed_can_be_set_back_to_false(client: AsyncClient):
    """A completed todo can be marked incomplete again, and that is stored.

    The update has to tell "completed was not sent" (None) apart from
    "completed was sent as false". A truthiness check treats the two alike,
    so false was silently ignored.
    """
    token = await get_auth_token(client, "toggle-back@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        "/api/v1/todos", json={"title": "Toggle me"}, headers=headers
    )
    todo_id = create_response.json()["id"]

    done = await client.put(
        f"/api/v1/todos/{todo_id}", json={"completed": True}, headers=headers
    )
    assert done.status_code == 200
    assert done.json()["completed"] is True

    undone = await client.put(
        f"/api/v1/todos/{todo_id}", json={"completed": False}, headers=headers
    )
    assert undone.status_code == 200
    assert undone.json()["completed"] is False

    # Read it back, so the assertion is about what was stored rather than
    # only about the response to the update.
    fetched = await client.get(f"/api/v1/todos/{todo_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["completed"] is False


@pytest.mark.asyncio
async def test_partial_update_keeps_description(client: AsyncClient):
    """Fields the client does not send must be left as they were.

    An update that omits description is not a request to clear it. Each step
    is read back with GET, so the check is on what was stored.
    """
    token = await get_auth_token(client, "partial-update@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        "/api/v1/todos",
        json={"title": "Keep my notes", "description": "important details"},
        headers=headers,
    )
    todo_id = create_response.json()["id"]

    # Only completed is sent.
    response = await client.put(
        f"/api/v1/todos/{todo_id}", json={"completed": True}, headers=headers
    )
    assert response.status_code == 200
    fetched = await client.get(f"/api/v1/todos/{todo_id}", headers=headers)
    assert fetched.json()["completed"] is True
    assert fetched.json()["description"] == "important details"

    # Only title is sent.
    response = await client.put(
        f"/api/v1/todos/{todo_id}", json={"title": "Renamed"}, headers=headers
    )
    assert response.status_code == 200
    fetched = await client.get(f"/api/v1/todos/{todo_id}", headers=headers)
    assert fetched.json()["title"] == "Renamed"
    assert fetched.json()["description"] == "important details"


@pytest.mark.asyncio
async def test_description_can_be_cleared_explicitly(client: AsyncClient):
    """Sending description as null still clears it.

    The schema allows null for description, so an explicit null is a
    deliberate request, and must stay distinct from leaving the field out.
    """
    token = await get_auth_token(client, "clear-description@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        "/api/v1/todos",
        json={"title": "Clear my notes", "description": "to be removed"},
        headers=headers,
    )
    todo_id = create_response.json()["id"]

    response = await client.put(
        f"/api/v1/todos/{todo_id}", json={"description": None}, headers=headers
    )
    assert response.status_code == 200
    fetched = await client.get(f"/api/v1/todos/{todo_id}", headers=headers)
    assert fetched.json()["description"] is None
    assert fetched.json()["title"] == "Clear my notes"


@pytest.mark.asyncio
async def test_delete_todo(client: AsyncClient):
    """Test deleting a todo."""
    token = await get_auth_token(client, "delete@example.com")

    # Create a todo
    create_response = await client.post(
        "/api/v1/todos",
        json={"title": "Delete Me"},
        headers={"Authorization": f"Bearer {token}"},
    )
    todo_id = create_response.json()["id"]

    # Delete it
    response = await client.delete(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_get_single_todo(client: AsyncClient):
    """Test getting a single todo by ID."""
    token = await get_auth_token(client, "single@example.com")

    # Create a todo
    create_response = await client.post(
        "/api/v1/todos",
        json={"title": "Single Todo", "description": "Get me"},
        headers={"Authorization": f"Bearer {token}"},
    )
    todo_id = create_response.json()["id"]

    # Get it
    response = await client.get(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Single Todo"


@pytest.mark.asyncio
async def test_user_cannot_read_another_users_todo(client: AsyncClient):
    """User B must not be able to read a todo owned by user A.

    404 rather than 403 is expected: answering 403 would confirm that the id
    exists, which tells an unauthorised caller something about another user's
    data.
    """
    token_a = await get_auth_token(client, "owner-read@example.com")
    token_b = await get_auth_token(client, "intruder-read@example.com")

    create_response = await client.post(
        "/api/v1/todos",
        json={"title": "Private to A", "description": "not for B"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    todo_id = create_response.json()["id"]

    response = await client.get(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_user_cannot_update_another_users_todo(client: AsyncClient):
    """User B must not be able to update a todo owned by user A."""
    token_a = await get_auth_token(client, "owner-update@example.com")
    token_b = await get_auth_token(client, "intruder-update@example.com")

    create_response = await client.post(
        "/api/v1/todos",
        json={"title": "Owned by A", "description": "original"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    todo_id = create_response.json()["id"]

    response = await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"title": "Hijacked by B"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 404

    # The rejection must also mean nothing was written.
    owner_view = await client.get(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert owner_view.status_code == 200
    assert owner_view.json()["title"] == "Owned by A"


@pytest.mark.asyncio
async def test_user_cannot_delete_another_users_todo(client: AsyncClient):
    """User B must not be able to delete a todo owned by user A."""
    token_a = await get_auth_token(client, "owner-delete@example.com")
    token_b = await get_auth_token(client, "intruder-delete@example.com")

    create_response = await client.post(
        "/api/v1/todos",
        json={"title": "Do not delete", "description": "belongs to A"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    todo_id = create_response.json()["id"]

    response = await client.delete(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 404

    # The todo must still be there for its owner.
    owner_view = await client.get(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert owner_view.status_code == 200


@pytest.mark.asyncio
async def test_todo_list_cache_is_not_shared_between_users(client: AsyncClient):
    """User B's list must not be served from a cache entry populated by user A.

    The assertions look at the data in the response rather than at the cache
    key, so the test describes the behaviour that matters and not the
    implementation that happens to provide it.
    """
    token_a = await get_auth_token(client, "cache-a@example.com")
    token_b = await get_auth_token(client, "cache-b@example.com")

    await client.post(
        "/api/v1/todos",
        json={"title": "Belongs to A"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    await client.post(
        "/api/v1/todos",
        json={"title": "Belongs to B"},
        headers={"Authorization": f"Bearer {token_b}"},
    )

    # A reads first, which is what populates the cache.
    list_a = await client.get(
        "/api/v1/todos",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert list_a.status_code == 200
    assert [item["title"] for item in list_a.json()["items"]] == ["Belongs to A"]

    list_b = await client.get(
        "/api/v1/todos",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert list_b.status_code == 200
    titles_b = [item["title"] for item in list_b.json()["items"]]
    assert titles_b == ["Belongs to B"]
    assert "Belongs to A" not in titles_b


@pytest.mark.asyncio
async def test_todo_list_cache_distinguishes_pagination(client: AsyncClient):
    """A cached page must not be served for a different page of the same user.

    Three todos with a page size of two means page 1 holds two items and page 2
    holds one, so a cache entry shared between the two pages is visible in the
    item count alone.
    """
    token = await get_auth_token(client, "cache-page@example.com")

    for index in range(3):
        await client.post(
            "/api/v1/todos",
            json={"title": f"Paged todo {index}"},
            headers={"Authorization": f"Bearer {token}"},
        )

    page_1 = await client.get(
        "/api/v1/todos",
        params={"page": 1, "size": 2},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert page_1.status_code == 200
    assert len(page_1.json()["items"]) == 2

    page_2 = await client.get(
        "/api/v1/todos",
        params={"page": 2, "size": 2},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert page_2.status_code == 200
    assert len(page_2.json()["items"]) == 1
    assert page_2.json()["page"] == 2


async def get_user_id(client: AsyncClient, token: str) -> str:
    """Helper to resolve the authenticated user's id."""
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    return response.json()["id"]


@pytest.mark.asyncio
async def test_creating_todo_invalidates_cached_list(client: AsyncClient):
    """A todo created after the list was cached must appear in the next list."""
    token = await get_auth_token(client, "invalidate-create@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    await client.post("/api/v1/todos", json={"title": "First"}, headers=headers)

    # Populate the cache.
    first_list = await client.get("/api/v1/todos", headers=headers)
    assert [item["title"] for item in first_list.json()["items"]] == ["First"]

    await client.post("/api/v1/todos", json={"title": "Second"}, headers=headers)

    second_list = await client.get("/api/v1/todos", headers=headers)
    titles = [item["title"] for item in second_list.json()["items"]]
    assert "Second" in titles
    assert second_list.json()["total"] == 2


@pytest.mark.asyncio
async def test_updating_todo_invalidates_cached_list(client: AsyncClient):
    """An edited title must be visible in the next list, not the cached one."""
    token = await get_auth_token(client, "invalidate-update@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        "/api/v1/todos", json={"title": "Before edit"}, headers=headers
    )
    todo_id = create_response.json()["id"]

    first_list = await client.get("/api/v1/todos", headers=headers)
    assert [item["title"] for item in first_list.json()["items"]] == ["Before edit"]

    await client.put(
        f"/api/v1/todos/{todo_id}", json={"title": "After edit"}, headers=headers
    )

    second_list = await client.get("/api/v1/todos", headers=headers)
    assert [item["title"] for item in second_list.json()["items"]] == ["After edit"]


@pytest.mark.asyncio
async def test_deleting_todo_invalidates_cached_list(client: AsyncClient):
    """A deleted todo must not survive in the cached list."""
    token = await get_auth_token(client, "invalidate-delete@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        "/api/v1/todos", json={"title": "Doomed"}, headers=headers
    )
    todo_id = create_response.json()["id"]

    first_list = await client.get("/api/v1/todos", headers=headers)
    assert [item["title"] for item in first_list.json()["items"]] == ["Doomed"]

    await client.delete(f"/api/v1/todos/{todo_id}", headers=headers)

    second_list = await client.get("/api/v1/todos", headers=headers)
    assert second_list.json()["items"] == []
    assert second_list.json()["total"] == 0


@pytest.mark.asyncio
async def test_mutation_invalidates_every_cached_page(client: AsyncClient):
    """Invalidation must reach pages other than the one most recently read.

    The cache key carries page and size, so a mutation has to clear all of a
    user's entries rather than a single page's.
    """
    token = await get_auth_token(client, "invalidate-pages@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    for index in range(3):
        await client.post(
            "/api/v1/todos", json={"title": f"Todo {index}"}, headers=headers
        )

    # Populate both pages.
    page_1 = await client.get(
        "/api/v1/todos", params={"page": 1, "size": 2}, headers=headers
    )
    assert len(page_1.json()["items"]) == 2
    page_2 = await client.get(
        "/api/v1/todos", params={"page": 2, "size": 2}, headers=headers
    )
    assert len(page_2.json()["items"]) == 1

    await client.post("/api/v1/todos", json={"title": "Todo 3"}, headers=headers)

    page_2_again = await client.get(
        "/api/v1/todos", params={"page": 2, "size": 2}, headers=headers
    )
    assert len(page_2_again.json()["items"]) == 2
    assert page_2_again.json()["total"] == 4


@pytest.mark.asyncio
async def test_mutation_does_not_invalidate_other_users_cache(
    client: AsyncClient, redis_store: dict
):
    """One user's mutation must not evict another user's cached list.

    This one guards against over-broad invalidation — a flush of the whole
    cache would still be correct for the caller but would throw away everyone
    else's entries. It asserts on keys because the difference is not otherwise
    observable: a discarded cache and a valid one return the same data.
    """
    token_a = await get_auth_token(client, "invalidate-keep-a@example.com")
    token_b = await get_auth_token(client, "invalidate-keep-b@example.com")
    user_a_id = await get_user_id(client, token_a)

    await client.post(
        "/api/v1/todos",
        json={"title": "A's todo"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    await client.get("/api/v1/todos", headers={"Authorization": f"Bearer {token_a}"})
    assert any(key.startswith(f"todos:list:{user_a_id}:") for key in redis_store)

    await client.post(
        "/api/v1/todos",
        json={"title": "B's todo"},
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert any(
        key.startswith(f"todos:list:{user_a_id}:") for key in redis_store
    ), "user B's mutation evicted user A's cached list"
