"""Tag CRUD tests."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, insert, select

from app.models.tag import todo_tags
from app.models.todo import Todo
from tests import conftest


async def auth(client: AsyncClient, email: str) -> dict:
    """Register a user and return their Authorization header."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def create_tag(client: AsyncClient, headers: dict, **body):
    return await client.post("/api/v1/tags", json=body, headers=headers)


@pytest.mark.asyncio
async def test_create_tag(client: AsyncClient):
    headers = await auth(client, "tag-create@example.com")
    me = (await client.get("/api/v1/auth/me", headers=headers)).json()

    response = await create_tag(client, headers, name="Work", color="#ff0000")

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Work"
    assert data["color"] == "#ff0000"
    assert data["user_id"] == me["id"]
    assert set(data) == {"id", "user_id", "name", "color", "created_at", "updated_at"}


@pytest.mark.asyncio
async def test_create_tag_without_color_or_with_explicit_null(client: AsyncClient):
    headers = await auth(client, "tag-color-null@example.com")

    omitted = await create_tag(client, headers, name="NoColor")
    explicit = await create_tag(client, headers, name="NullColor", color=None)

    assert omitted.status_code == 201
    assert omitted.json()["color"] is None
    assert explicit.status_code == 201
    assert explicit.json()["color"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {},
        {"name": ""},
        {"name": "   "},
        {"name": None},
        {"name": "x" * 51},
        {"name": "ok", "color": "c" * 21},
    ],
)
async def test_create_tag_rejects_invalid_input(client: AsyncClient, body: dict):
    headers = await auth(client, "tag-invalid@example.com")

    response = await client.post("/api/v1/tags", json=body, headers=headers)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_tags_returns_only_own_tags(client: AsyncClient):
    alice = await auth(client, "tag-list-alice@example.com")
    bob = await auth(client, "tag-list-bob@example.com")
    await create_tag(client, alice, name="alice-b")
    await create_tag(client, alice, name="alice-a")
    await create_tag(client, bob, name="bob-only")

    response = await client.get("/api/v1/tags", headers=alice)

    assert response.status_code == 200
    assert [tag["name"] for tag in response.json()] == ["alice-a", "alice-b"]


@pytest.mark.asyncio
async def test_update_own_tag(client: AsyncClient):
    headers = await auth(client, "tag-update@example.com")
    tag = (await create_tag(client, headers, name="Old", color="red")).json()

    response = await client.patch(
        f"/api/v1/tags/{tag['id']}",
        json={"name": "New", "color": "blue"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["name"] == "New"
    assert response.json()["color"] == "blue"
    fetched = await client.get(f"/api/v1/tags/{tag['id']}", headers=headers)
    assert fetched.json()["name"] == "New"


@pytest.mark.asyncio
async def test_partial_update_keeps_omitted_fields(client: AsyncClient):
    headers = await auth(client, "tag-partial@example.com")
    tag = (await create_tag(client, headers, name="Keep", color="green")).json()

    renamed = await client.patch(
        f"/api/v1/tags/{tag['id']}", json={"name": "Renamed"}, headers=headers
    )
    recolored = await client.patch(
        f"/api/v1/tags/{tag['id']}", json={"color": "purple"}, headers=headers
    )

    assert renamed.status_code == 200
    assert renamed.json()["color"] == "green"
    assert recolored.status_code == 200
    assert recolored.json()["name"] == "Renamed"
    assert recolored.json()["color"] == "purple"


@pytest.mark.asyncio
async def test_update_can_clear_color_but_not_name(client: AsyncClient):
    headers = await auth(client, "tag-clear@example.com")
    tag = (await create_tag(client, headers, name="Clear", color="red")).json()

    null_name = await client.patch(
        f"/api/v1/tags/{tag['id']}", json={"name": None}, headers=headers
    )
    null_color = await client.patch(
        f"/api/v1/tags/{tag['id']}", json={"color": None}, headers=headers
    )

    assert null_name.status_code == 422
    assert null_color.status_code == 200
    assert null_color.json()["name"] == "Clear"
    assert null_color.json()["color"] is None


@pytest.mark.asyncio
async def test_delete_own_tag(client: AsyncClient):
    headers = await auth(client, "tag-delete@example.com")
    tag = (await create_tag(client, headers, name="Gone")).json()

    response = await client.delete(f"/api/v1/tags/{tag['id']}", headers=headers)

    assert response.status_code == 204
    fetched = await client.get(f"/api/v1/tags/{tag['id']}", headers=headers)
    assert fetched.status_code == 404


@pytest.mark.asyncio
async def test_other_users_tag_is_not_found(client: AsyncClient):
    owner = await auth(client, "tag-owner@example.com")
    intruder = await auth(client, "tag-intruder@example.com")
    tag = (await create_tag(client, owner, name="Private", color="red")).json()
    url = f"/api/v1/tags/{tag['id']}"

    get_response = await client.get(url, headers=intruder)
    patch_response = await client.patch(
        url, json={"name": "Hijacked", "color": None}, headers=intruder
    )
    delete_response = await client.delete(url, headers=intruder)

    # Same answer as for an id that does not exist, so the response does not
    # reveal that the tag is there.
    missing = await client.get(f"/api/v1/tags/{uuid.uuid4()}", headers=intruder)
    for response in (get_response, patch_response, delete_response, missing):
        assert response.status_code == 404
        assert response.json() == {"detail": "Tag not found"}

    unchanged = await client.get(url, headers=owner)
    assert unchanged.status_code == 200
    assert unchanged.json()["name"] == "Private"
    assert unchanged.json()["color"] == "red"


@pytest.mark.asyncio
async def test_tag_endpoints_require_authentication(client: AsyncClient):
    response = await client.get("/api/v1/tags")

    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("duplicate", ["Work", "work", "WORK", "  wOrK  "])
async def test_duplicate_name_is_conflict(client: AsyncClient, duplicate: str):
    headers = await auth(client, "tag-dup@example.com")
    await create_tag(client, headers, name="Work")

    response = await create_tag(client, headers, name=duplicate)

    assert response.status_code == 409
    assert response.json() == {"detail": "Tag with this name already exists"}
    # The failed insert was rolled back and left nothing behind.
    tags = (await client.get("/api/v1/tags", headers=headers)).json()
    assert [tag["name"] for tag in tags] == ["Work"]


@pytest.mark.asyncio
async def test_rename_to_existing_name_is_conflict(client: AsyncClient):
    headers = await auth(client, "tag-rename-dup@example.com")
    await create_tag(client, headers, name="Home")
    tag = (await create_tag(client, headers, name="Errands")).json()

    response = await client.patch(
        f"/api/v1/tags/{tag['id']}", json={"name": "HOME"}, headers=headers
    )

    assert response.status_code == 409
    fetched = await client.get(f"/api/v1/tags/{tag['id']}", headers=headers)
    assert fetched.json()["name"] == "Errands"


@pytest.mark.asyncio
async def test_rename_changing_only_case_of_own_name_is_allowed(client: AsyncClient):
    headers = await auth(client, "tag-recase@example.com")
    tag = (await create_tag(client, headers, name="work")).json()

    response = await client.patch(
        f"/api/v1/tags/{tag['id']}", json={"name": "Work"}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Work"


@pytest.mark.asyncio
async def test_same_name_is_allowed_for_different_users(client: AsyncClient):
    alice = await auth(client, "tag-same-alice@example.com")
    bob = await auth(client, "tag-same-bob@example.com")

    first = await create_tag(client, alice, name="Work")
    second = await create_tag(client, bob, name="work")

    assert first.status_code == 201
    assert second.status_code == 201


@pytest.mark.asyncio
async def test_delete_tag_removes_links_but_keeps_todos(client: AsyncClient):
    headers = await auth(client, "tag-cascade@example.com")
    todo = (
        await client.post("/api/v1/todos", json={"title": "Tagged"}, headers=headers)
    ).json()
    doomed = (await create_tag(client, headers, name="Doomed")).json()
    kept = (await create_tag(client, headers, name="Kept")).json()

    # There is no attach endpoint yet, so the links are written directly.
    todo_id = uuid.UUID(todo["id"])
    async with conftest.test_session_maker() as session:
        await session.execute(
            insert(todo_tags),
            [
                {"todo_id": todo_id, "tag_id": uuid.UUID(doomed["id"])},
                {"todo_id": todo_id, "tag_id": uuid.UUID(kept["id"])},
            ],
        )
        await session.commit()

    response = await client.delete(f"/api/v1/tags/{doomed['id']}", headers=headers)

    assert response.status_code == 204
    async with conftest.test_session_maker() as session:
        links = (await session.execute(select(todo_tags.c.tag_id))).scalars().all()
        todos = await session.scalar(select(func.count()).select_from(Todo))
    assert links == [uuid.UUID(kept["id"])]
    assert todos == 1
    still_there = await client.get(f"/api/v1/todos/{todo['id']}", headers=headers)
    assert still_there.status_code == 200
