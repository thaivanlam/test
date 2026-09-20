"""Todo list filtering, ordering, pagination, tags in responses, and caching."""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.models.todo import Todo
from tests import conftest


async def auth(client: AsyncClient, email: str) -> dict:
    """Register a user and return their Authorization header."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def new_todo(
    client: AsyncClient,
    headers: dict,
    title: str,
    description: str | None = None,
    completed: bool = False,
) -> str:
    response = await client.post(
        "/api/v1/todos",
        json={"title": title, "description": description},
        headers=headers,
    )
    todo_id = response.json()["id"]
    if completed:
        await client.put(
            f"/api/v1/todos/{todo_id}", json={"completed": True}, headers=headers
        )
    return todo_id


async def new_tag(
    client: AsyncClient, headers: dict, name: str, color: str | None = None
) -> str:
    response = await client.post(
        "/api/v1/tags", json={"name": name, "color": color}, headers=headers
    )
    return response.json()["id"]


async def attach(client: AsyncClient, headers: dict, todo_id: str, tag_id: str):
    response = await client.post(
        f"/api/v1/todos/{todo_id}/tags", json={"tag_id": tag_id}, headers=headers
    )
    assert response.status_code == 204


async def set_created_at(todo_id: str, when: datetime) -> None:
    """Backdate a todo. The API sets created_at itself, so date filters and
    ordering can only be tested by writing it directly. Done before any list
    request, so no cached list can be holding the old value."""
    async with conftest.test_session_maker() as session:
        await session.execute(
            update(Todo).where(Todo.id == uuid.UUID(todo_id)).values(created_at=when)
        )
        await session.commit()


def utc(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


async def list_todos(client: AsyncClient, headers: dict, **params):
    return await client.get("/api/v1/todos", params=params, headers=headers)


async def titles(client: AsyncClient, headers: dict, **params) -> list[str]:
    response = await list_todos(client, headers, **params)
    assert response.status_code == 200, response.text
    return [item["title"] for item in response.json()["items"]]


def current_generation(store: dict[str, str], user_id: str) -> str:
    """The generation the API would read now; absent means generation 0."""
    return store.get(f"todos:gen:{user_id}", "0")


def list_keys(store: dict[str, str], user_id: str) -> set[str]:
    """Cached pages the user can still be served: current generation only.

    Mutations bump the generation instead of deleting keys, so older entries
    may linger in the store while being unreachable.
    """
    generation = current_generation(store, user_id)
    prefix = f"todos:list:{user_id}:{generation}:"
    return {key for key in store if key.startswith(prefix)}


async def user_id_of(client: AsyncClient, headers: dict) -> str:
    return (await client.get("/api/v1/auth/me", headers=headers)).json()["id"]


# --- status ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_status_active_returns_only_incomplete(client: AsyncClient):
    headers = await auth(client, "f-active@example.com")
    await new_todo(client, headers, "open")
    await new_todo(client, headers, "done", completed=True)

    assert await titles(client, headers, status="active") == ["open"]


@pytest.mark.asyncio
async def test_status_completed_returns_only_complete(client: AsyncClient):
    headers = await auth(client, "f-completed@example.com")
    await new_todo(client, headers, "open")
    await new_todo(client, headers, "done", completed=True)

    assert await titles(client, headers, status="completed") == ["done"]


@pytest.mark.asyncio
async def test_status_follows_completed_set_back_to_false(client: AsyncClient):
    """SEC-05 regression through the filter: un-completing moves it back."""
    headers = await auth(client, "f-reopen@example.com")
    todo_id = await new_todo(client, headers, "reopened", completed=True)

    await client.put(
        f"/api/v1/todos/{todo_id}", json={"completed": False}, headers=headers
    )

    assert await titles(client, headers, status="active") == ["reopened"]
    assert await titles(client, headers, status="completed") == []


# --- tag --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tag_filter_returns_tagged_todos_once(client: AsyncClient):
    headers = await auth(client, "f-tag@example.com")
    work = await new_tag(client, headers, "work")
    urgent = await new_tag(client, headers, "urgent")
    both = await new_todo(client, headers, "both tags")
    only_urgent = await new_todo(client, headers, "urgent only")
    await new_todo(client, headers, "untagged")
    await attach(client, headers, both, work)
    await attach(client, headers, both, urgent)
    await attach(client, headers, only_urgent, urgent)

    work_response = await list_todos(client, headers, tag_id=work)
    urgent_response = await list_todos(client, headers, tag_id=urgent)

    # A todo with several tags is still one row, and counted once.
    assert [i["title"] for i in work_response.json()["items"]] == ["both tags"]
    assert work_response.json()["total"] == 1
    assert sorted(i["title"] for i in urgent_response.json()["items"]) == [
        "both tags",
        "urgent only",
    ]
    assert urgent_response.json()["total"] == 2


@pytest.mark.asyncio
async def test_tag_filter_with_other_users_tag_is_not_found(client: AsyncClient):
    owner = await auth(client, "f-tag-owner@example.com")
    intruder = await auth(client, "f-tag-intruder@example.com")
    owner_tag = await new_tag(client, owner, "secret")
    owner_todo = await new_todo(client, owner, "owner's todo")
    await attach(client, owner, owner_todo, owner_tag)
    await new_todo(client, intruder, "intruder's todo")

    response = await list_todos(client, intruder, tag_id=owner_tag)
    missing = await list_todos(client, intruder, tag_id=str(uuid.uuid4()))

    # Same answer as for a tag that does not exist, and no todo data.
    for result in (response, missing):
        assert result.status_code == 404
        assert result.json() == {"detail": "Tag not found"}


# --- keyword ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_keyword_matches_title(client: AsyncClient):
    headers = await auth(client, "f-kw-title@example.com")
    await new_todo(client, headers, "Buy groceries")
    await new_todo(client, headers, "Call mom")

    assert await titles(client, headers, keyword="grocer") == ["Buy groceries"]


@pytest.mark.asyncio
async def test_keyword_matches_description(client: AsyncClient):
    headers = await auth(client, "f-kw-desc@example.com")
    await new_todo(client, headers, "Errand", description="pick up the parcel")
    await new_todo(client, headers, "Other", description="nothing here")
    await new_todo(client, headers, "No description")

    assert await titles(client, headers, keyword="parcel") == ["Errand"]


@pytest.mark.asyncio
async def test_keyword_is_case_insensitive(client: AsyncClient):
    headers = await auth(client, "f-kw-case@example.com")
    await new_todo(client, headers, "Quarterly REPORT")
    await new_todo(client, headers, "misc", description="Report draft")

    for keyword in ("report", "REPORT", "RePoRt", "  report  "):
        assert sorted(await titles(client, headers, keyword=keyword)) == [
            "Quarterly REPORT",
            "misc",
        ]


@pytest.mark.asyncio
async def test_keyword_wildcards_are_literal(client: AsyncClient):
    headers = await auth(client, "f-kw-literal@example.com")
    await new_todo(client, headers, "50% off")
    await new_todo(client, headers, "500 items")
    await new_todo(client, headers, "snake_case")
    await new_todo(client, headers, "snakeXcase")

    assert await titles(client, headers, keyword="50%") == ["50% off"]
    assert await titles(client, headers, keyword="e_c") == ["snake_case"]


# --- dates ------------------------------------------------------------------


async def dated_todos(client: AsyncClient, headers: dict) -> None:
    """Todos on both sides of each day boundary, in UTC."""
    for title, when in [
        ("dec31-late", utc(2025, 12, 31, 23, 59, 59, 999999)),
        ("jan01-start", utc(2026, 1, 1, 0, 0, 0)),
        ("jan01-late", utc(2026, 1, 1, 23, 59, 59, 999999)),
        ("jan02-noon", utc(2026, 1, 2, 12, 0, 0)),
        ("jan03-start", utc(2026, 1, 3, 0, 0, 0)),
    ]:
        await set_created_at(await new_todo(client, headers, title), when)


@pytest.mark.asyncio
async def test_date_from_includes_that_whole_day(client: AsyncClient):
    headers = await auth(client, "f-date-from@example.com")
    await dated_todos(client, headers)

    assert await titles(client, headers, date_from="2026-01-02") == [
        "jan03-start",
        "jan02-noon",
    ]


@pytest.mark.asyncio
async def test_date_to_includes_that_whole_day(client: AsyncClient):
    headers = await auth(client, "f-date-to@example.com")
    await dated_todos(client, headers)

    assert await titles(client, headers, date_to="2026-01-01") == [
        "jan01-late",
        "jan01-start",
        "dec31-late",
    ]


@pytest.mark.asyncio
async def test_date_range_is_inclusive_at_both_ends(client: AsyncClient):
    headers = await auth(client, "f-date-range@example.com")
    await dated_todos(client, headers)

    assert await titles(
        client, headers, date_from="2026-01-01", date_to="2026-01-02"
    ) == ["jan02-noon", "jan01-late", "jan01-start"]
    # A single day: from and to the same date.
    assert await titles(
        client, headers, date_from="2026-01-01", date_to="2026-01-01"
    ) == ["jan01-late", "jan01-start"]


# --- combined ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_combined_filters_all_apply(client: AsyncClient):
    headers = await auth(client, "f-combined@example.com")
    work = await new_tag(client, headers, "work")
    cases = [
        # (title, completed, tagged, created_at)       matches?
        ("report match", False, True, utc(2026, 3, 10)),  # yes
        ("report done", True, True, utc(2026, 3, 10)),  # wrong status
        ("report untagged", False, False, utc(2026, 3, 10)),  # no tag
        ("report too early", False, True, utc(2026, 2, 1)),  # before range
        ("other match", False, True, utc(2026, 3, 10)),  # wrong keyword
    ]
    for title, completed, tagged, when in cases:
        todo_id = await new_todo(client, headers, title, completed=completed)
        if tagged:
            await attach(client, headers, todo_id, work)
        await set_created_at(todo_id, when)

    response = await list_todos(
        client,
        headers,
        status="active",
        tag_id=work,
        keyword="REPORT",
        date_from="2026-03-01",
        date_to="2026-03-31",
    )

    assert [i["title"] for i in response.json()["items"]] == ["report match"]
    assert response.json()["total"] == 1


# --- validation -------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "params",
    [
        {"status": "done"},
        {"status": "ACTIVE"},
        {"tag_id": "not-a-uuid"},
        {"date_from": "2026-13-01"},
        {"date_to": "yesterday"},
        {"date_from": "2026-01-02", "date_to": "2026-01-01"},
        {"page": 0},
        {"page_size": 0},
        {"page_size": 101},
        {"size": 101},
        {"page_size": 5, "size": 10},
    ],
)
async def test_invalid_list_parameters_are_rejected(client: AsyncClient, params):
    headers = await auth(client, "f-invalid@example.com")

    response = await list_todos(client, headers, **params)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_page_size_100_is_accepted(client: AsyncClient):
    headers = await auth(client, "f-max@example.com")

    response = await list_todos(client, headers, page_size=100)

    assert response.status_code == 200
    assert response.json()["page_size"] == 100


# --- ordering and pagination ------------------------------------------------


@pytest.mark.asyncio
async def test_ordering_is_created_at_desc_then_id_desc(client: AsyncClient):
    headers = await auth(client, "f-order@example.com")
    same_time = utc(2026, 5, 1, 12, 0, 0)
    tied = []
    for index in range(4):
        todo_id = await new_todo(client, headers, f"tied {index}")
        await set_created_at(todo_id, same_time)
        tied.append(todo_id)
    newer = await new_todo(client, headers, "newer")
    await set_created_at(newer, utc(2026, 5, 2))
    older = await new_todo(client, headers, "older")
    await set_created_at(older, utc(2026, 4, 30))

    response = await list_todos(client, headers)
    ids = [item["id"] for item in response.json()["items"]]

    # Newest first; todos with the same created_at by id, descending, which is
    # what makes the order the same on every request.
    tied_desc = [str(u) for u in sorted(map(uuid.UUID, tied), reverse=True)]
    assert ids == [newer, *tied_desc, older]


@pytest.mark.asyncio
async def test_pagination_pages_through_every_todo_once(client: AsyncClient):
    headers = await auth(client, "f-pages@example.com")
    for index in range(5):
        todo_id = await new_todo(client, headers, f"todo {index}")
        await set_created_at(todo_id, utc(2026, 6, 1 + index))

    pages = [await list_todos(client, headers, page=n, page_size=2) for n in (1, 2, 3)]
    beyond = await list_todos(client, headers, page=4, page_size=2)

    assert [[i["title"] for i in p.json()["items"]] for p in pages] == [
        ["todo 4", "todo 3"],
        ["todo 2", "todo 1"],
        ["todo 0"],
    ]
    first = pages[0].json()
    assert (first["total"], first["page"], first["page_size"], first["pages"]) == (
        5,
        1,
        2,
        3,
    )
    # size is kept as an alias in the response and carries the same value.
    assert first["size"] == 2
    assert beyond.json()["items"] == []
    assert beyond.json()["total"] == 5


@pytest.mark.asyncio
async def test_size_parameter_still_works_as_alias(client: AsyncClient):
    headers = await auth(client, "f-size-alias@example.com")
    for index in range(3):
        await new_todo(client, headers, f"todo {index}")

    response = await list_todos(client, headers, size=2)

    assert len(response.json()["items"]) == 2
    assert response.json()["page_size"] == 2
    assert response.json()["pages"] == 2


@pytest.mark.asyncio
async def test_default_page_size_is_20(client: AsyncClient):
    headers = await auth(client, "f-default@example.com")

    response = await list_todos(client, headers)

    assert response.json()["page_size"] == 20
    assert response.json()["pages"] == 0


@pytest.mark.asyncio
async def test_total_and_pages_respect_filters(client: AsyncClient):
    headers = await auth(client, "f-total@example.com")
    for index in range(5):
        await new_todo(client, headers, f"alpha {index}")
    for index in range(3):
        await new_todo(client, headers, f"beta {index}", completed=True)

    alpha = await list_todos(client, headers, keyword="alpha", page_size=2)
    done = await list_todos(client, headers, status="completed", page_size=2)
    everything = await list_todos(client, headers, page_size=2)

    assert (alpha.json()["total"], alpha.json()["pages"]) == (5, 3)
    assert (done.json()["total"], done.json()["pages"]) == (3, 2)
    assert (everything.json()["total"], everything.json()["pages"]) == (8, 4)


# --- tags in responses ------------------------------------------------------


@pytest.mark.asyncio
async def test_todo_responses_include_tags(client: AsyncClient):
    headers = await auth(client, "f-tags-shape@example.com")
    todo_id = await new_todo(client, headers, "tagged")
    zeta = await new_tag(client, headers, "zeta", color="#000000")
    alpha = await new_tag(client, headers, "alpha")
    await attach(client, headers, todo_id, zeta)
    await attach(client, headers, todo_id, alpha)
    expected = [
        {"id": alpha, "name": "alpha", "color": None},
        {"id": zeta, "name": "zeta", "color": "#000000"},
    ]

    listed = (await list_todos(client, headers)).json()["items"][0]
    fetched = (await client.get(f"/api/v1/todos/{todo_id}", headers=headers)).json()
    updated = (
        await client.put(
            f"/api/v1/todos/{todo_id}", json={"completed": True}, headers=headers
        )
    ).json()
    created = (
        await client.post("/api/v1/todos", json={"title": "fresh"}, headers=headers)
    ).json()

    # Tags come sorted by name, with only the fields the UI needs.
    assert listed["tags"] == expected
    assert fetched["tags"] == expected
    assert updated["tags"] == expected
    assert created["tags"] == []


# --- cache ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tag_rename_and_delete_refresh_cached_list(client: AsyncClient):
    headers = await auth(client, "f-cache-rename@example.com")
    todo_id = await new_todo(client, headers, "tagged")
    tag_id = await new_tag(client, headers, "before", color="red")
    await attach(client, headers, todo_id, tag_id)

    def tag_names(response) -> list[str]:
        return [t["name"] for t in response.json()["items"][0]["tags"]]

    assert tag_names(await list_todos(client, headers)) == ["before"]  # cached

    await client.patch(
        f"/api/v1/tags/{tag_id}", json={"name": "after"}, headers=headers
    )
    assert tag_names(await list_todos(client, headers)) == ["after"]  # cached

    await client.delete(f"/api/v1/tags/{tag_id}", headers=headers)
    assert tag_names(await list_todos(client, headers)) == []


@pytest.mark.asyncio
async def test_attach_and_detach_refresh_cached_list(client: AsyncClient):
    headers = await auth(client, "f-cache-attach@example.com")
    todo_id = await new_todo(client, headers, "todo")
    tag_id = await new_tag(client, headers, "label")

    def tag_names(response) -> list[str]:
        return [t["name"] for t in response.json()["items"][0]["tags"]]

    assert tag_names(await list_todos(client, headers)) == []  # cached
    filtered = await list_todos(client, headers, tag_id=tag_id)  # cached
    assert filtered.json()["total"] == 0

    await attach(client, headers, todo_id, tag_id)
    assert tag_names(await list_todos(client, headers)) == ["label"]
    assert (await list_todos(client, headers, tag_id=tag_id)).json()["total"] == 1

    await client.delete(f"/api/v1/todos/{todo_id}/tags/{tag_id}", headers=headers)
    assert tag_names(await list_todos(client, headers)) == []
    assert (await list_todos(client, headers, tag_id=tag_id)).json()["total"] == 0


@pytest.mark.asyncio
async def test_cache_key_differs_for_every_parameter(
    client: AsyncClient, redis_store: dict[str, str]
):
    headers = await auth(client, "f-keys-differ@example.com")
    user_id = await user_id_of(client, headers)
    tag_id = await new_tag(client, headers, "t")
    variants = [
        {},
        {"status": "active"},
        {"tag_id": tag_id},
        {"keyword": "x"},
        {"date_from": "2026-01-01"},
        {"date_to": "2026-01-01"},
        {"page": 2},
        {"page_size": 5},
    ]

    for count, params in enumerate(variants, start=1):
        assert (await list_todos(client, headers, **params)).status_code == 200
        assert len(list_keys(redis_store, user_id)) == count, params


@pytest.mark.asyncio
async def test_equivalent_queries_share_a_cache_key(
    client: AsyncClient, redis_store: dict[str, str]
):
    headers = await auth(client, "f-keys-same@example.com")
    user_id = await user_id_of(client, headers)
    equivalent = [
        "/api/v1/todos?keyword=Work&page_size=5",
        "/api/v1/todos?keyword=%20work%20&size=5",
        "/api/v1/todos?page=1&size=5&page_size=5&keyword=WORK",
    ]

    for url in equivalent:
        assert (await client.get(url, headers=headers)).status_code == 200

    assert len(list_keys(redis_store, user_id)) == 1
    # A blank keyword is no keyword: same key as the unfiltered default page.
    await client.get("/api/v1/todos?keyword=%20%20", headers=headers)
    await client.get("/api/v1/todos?page=1&page_size=20", headers=headers)
    assert len(list_keys(redis_store, user_id)) == 2


@pytest.mark.asyncio
async def test_filtered_cache_is_isolated_between_users(
    client: AsyncClient, redis_store: dict[str, str]
):
    alice = await auth(client, "f-iso-alice@example.com")
    bob = await auth(client, "f-iso-bob@example.com")
    alice_id, bob_id = await user_id_of(client, alice), await user_id_of(client, bob)
    await new_todo(client, alice, "shared word alice")
    await new_todo(client, bob, "shared word bob")

    # Identical filters for both: the cached answer for one must not be
    # served to the other.
    alice_titles = await titles(client, alice, keyword="shared", status="active")
    bob_titles = await titles(client, bob, keyword="shared", status="active")

    assert alice_titles == ["shared word alice"]
    assert bob_titles == ["shared word bob"]
    assert list_keys(redis_store, alice_id).isdisjoint(list_keys(redis_store, bob_id))

    # And Alice's mutation leaves Bob's cache alone.
    await new_todo(client, alice, "another")
    assert list_keys(redis_store, alice_id) == set()
    assert len(list_keys(redis_store, bob_id)) == 1
