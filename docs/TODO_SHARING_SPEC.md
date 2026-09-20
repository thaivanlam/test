# Technical Specification: Todo List Sharing

> **Status: Proposed design. Not implemented.**
> Nothing described here exists in the codebase. No table, route, cache key or
> UI element in this document has been built. Where the document refers to the
> *current* application, it says so explicitly and cites the code.

**Branch:** `assessment/thai-van-lam` · **Written against:** commit `3e71ee7`

---

## 1. Overview & Objective

- **Feature summary.** A user can share their todo list with another
  registered user, as either a **viewer** (read-only) or an **editor**
  (read and update). The owner can change the role or revoke access at any
  time, and revocation takes effect on the grantee's very next request.
- **Problem statement.** Today every todo is visible only to the user who
  created it; there is no way to collaborate on a list. The request from
  stakeholders: *"Users should be able to share their todo list with other
  users with either read-only (viewer) or edit (editor) permissions, and owners
  can revoke access anytime."*
- **Roles.**

| Role | Who | Relationship to a list |
|---|---|---|
| **Owner** | The user whose todos these are | Exactly one per list; always the user in `todos.user_id` |
| **Editor** | A user the owner shared with as `editor` | May read the list and update existing todos in it |
| **Viewer** | A user the owner shared with as `viewer` | May read the list only |
| **Other** | Any authenticated user with no share | No access; the list must be indistinguishable from one that does not exist |

### 1.1 Assumptions

These shape the whole design, so they are stated before it.

| # | Assumption | Consequence |
|---|---|---|
| A1 | The application has **no list entity**. Each user has exactly one implicit list: all todos whose `user_id` is theirs. | Sharing is **list-level**: an owner shares *all* their todos with a grantee. Per-todo sharing is out of scope (§3.2). The stakeholder request also says "their todo list". |
| A2 | The grantee must **already be registered**, and is identified by email. | No invitation-to-sign-up flow; see §3.2. |
| A3 | A share takes effect **immediately**, with no accept step. | No pending-invite state in the data model. |
| A4 | **Editor** means *update existing todos*. Editors cannot create or delete todos, and cannot manage shares. | Creation would raise an unresolved ownership question, and deletion is irreversible; both are out of scope. |
| A5 | `users.email` is **unique**. | **Prerequisite, not yet true.** See §6.4. |

### 1.2 Current conventions this design follows

Taken from the existing code, not invented for this feature:

| Convention | Where it is in the current code |
|---|---|
| All API routes under `/api/v1/` (only `/health` sits outside it) | `app/main.py` |
| Bearer JWT, resolved by the `get_current_user` dependency | `app/api/deps.py` |
| Errors as `{"detail": "<message>"}`; validation errors as `{"detail": [ ... ]}` (`422`) | FastAPI default, used throughout `app/api/v1/` |
| A resource the caller may not access returns **`404`**, not `403`, so its existence is not disclosed | `get_todo_by_id(db, todo_id, user_id)` in `app/services/todo_service.py` (the SEC-02 fix) |
| Primary keys are UUIDs; timestamps are `TIMESTAMPTZ` | `app/models/` |
| List responses are cached in Redis under `todos:list:{user_id}:{page}:{size}` for 300 s, and cleared by pattern on mutation | `app/api/v1/todos.py`, `invalidate_todo_list_cache` |

---

## 2. User Stories & Acceptance Criteria

Acceptance criteria are written to be directly testable: each names the
request and the exact expected response.

### US-1 — Owner shares their list

- **As an** owner
- **I want to** share my todo list with another user as a viewer or editor
- **So that** they can see — and, as an editor, help maintain — my todos

**Acceptance criteria**
- [ ] `POST /api/v1/shares` with a registered email and `role: "viewer"` returns
  `201` with the new share, and the grantee can then read the list (US-3).
- [ ] The same with `role: "editor"` returns `201`, and the grantee can update
  todos in the list (US-4).
- [ ] Sharing with my own email returns `400 {"detail": "Cannot share a list with yourself"}`
  and creates no row.
- [ ] Sharing with a user who already has access returns
  `409 {"detail": "This list is already shared with that user"}` and does not
  change the existing role.
- [ ] Sharing with an unregistered email returns `404 {"detail": "User not found"}`.
- [ ] A `role` other than `viewer` or `editor` returns `422`.
- [ ] With an invalid or expired token the request returns `401`; with no token
  at all it returns `403`, matching the current routes (§5).

### US-2 — Owner sees and manages who has access

- **As an** owner
- **I want to** list the people my list is shared with, and change their role
- **So that** I stay in control of who can do what

**Acceptance criteria**
- [ ] `GET /api/v1/shares` returns `200` with every share I own, and none that
  another owner created.
- [ ] `PATCH /api/v1/shares/{share_id}` with `{"role": "editor"}` returns `200`,
  and the grantee's next request is authorised as an editor.
- [ ] `PATCH` or `DELETE` on a share I do not own returns `404 {"detail": "Share not found"}`,
  exactly as for an id that does not exist.

### US-3 — Grantee reads a shared list

- **As a** viewer or editor
- **I want to** see the lists shared with me and read their todos
- **So that** I can follow someone else's work

**Acceptance criteria**
- [ ] `GET /api/v1/shared-lists` returns `200` with one entry per owner who has
  shared with me, including my role.
- [ ] `GET /api/v1/shared-lists/{owner_id}/todos` returns `200` with the owner's
  todos, paginated exactly as `GET /api/v1/todos` is.
- [ ] The same request for an owner who has not shared with me returns
  `404 {"detail": "Shared list not found"}` — identical to an owner id that does
  not exist.
- [ ] Nothing about sharing changes `GET /api/v1/todos`: it still returns only
  my own todos.

### US-4 — Editor updates a todo in a shared list

- **As an** editor
- **I want to** update a todo in a list shared with me
- **So that** I can help keep it current

**Acceptance criteria**
- [ ] `PUT /api/v1/shared-lists/{owner_id}/todos/{todo_id}` as an editor returns
  `200`, and the owner sees the change on their next read of `GET /api/v1/todos`.
- [ ] The same request as a **viewer** returns
  `403 {"detail": "Editor role required"}` and changes nothing.
- [ ] A `todo_id` that is not in that owner's list returns `404 {"detail": "Todo not found"}`.
- [ ] An update based on a stale version returns `409` (§6.3).

### US-5 — Owner revokes access

- **As an** owner
- **I want to** revoke a user's access at any time
- **So that** they can no longer see or change my todos

**Acceptance criteria**
- [ ] `DELETE /api/v1/shares/{share_id}` returns `204`.
- [ ] The former grantee's **next** request to any `/shared-lists/{owner_id}/...`
  route returns `404` — with no delay, and regardless of what either the server
  cache or the grantee's browser holds (§7).
- [ ] The owner no longer appears in the former grantee's `GET /api/v1/shared-lists`.
- [ ] A former editor's in-flight update either completes before the revoke or
  is rejected; it is never applied after the revoke has returned (§6.3).

---

## 3. Scope

### 3.1 In scope

- Sharing a whole list with a registered user, as viewer or editor.
- Listing, re-roling and revoking shares, by the owner only.
- Reading a shared list, and updating its existing todos as an editor.
- Optimistic concurrency control on todo updates.
- Server-side cache invalidation for every event that changes what a user may
  see (§7).

### 3.2 Out of scope

Each exclusion is a deliberate boundary, with the reason given.

| Excluded | Reason |
|---|---|
| **Sharing a single todo** | The request is for sharing a *list* (A1). Per-todo sharing needs a different data model and doubles the authorisation surface. |
| **Inviting unregistered users** / email notifications | Requires an invite-token flow and an email service; neither exists (A2). |
| **Accept/decline step** for shares | Shares take effect immediately (A3); a pending state would add a lifecycle and more states to test. |
| **Editors creating or deleting todos** | Creation leaves ownership of the new todo undefined; deletion is irreversible (A4). |
| **Re-sharing** by a grantee; **transfer of ownership** | Only the owner manages access. Keeps the permission model to one level. |
| **A grantee leaving a share themselves** | The request gives revocation to owners. Can be added later without schema change. |
| **Real-time push** of revocation or edits (WebSocket/SSE) | Revocation is enforced on the next request (§7.3); pushing it to an open screen is a separate feature. |
| **Groups, teams, public links** | Not requested. |
| **Audit log** of share changes | Not requested; `created_at`/`updated_at` on the share row cover basic history. |
| **Rate limiting** on `POST /shares` | Would mitigate the enumeration risk in §6.4, but is a platform-wide concern rather than part of this feature. |

---

## 4. Database Design

### 4.1 New table — `todo_list_shares`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | no | app-generated | **Primary key** |
| `owner_id` | `UUID` | no | — | **FK → `users(id)` `ON DELETE CASCADE`** — the user whose list is shared |
| `grantee_id` | `UUID` | no | — | **FK → `users(id)` `ON DELETE CASCADE`** — the user given access |
| `role` | `VARCHAR(10)` | no | — | `CHECK (role IN ('viewer', 'editor'))` |
| `created_at` | `TIMESTAMPTZ` | no | `now()` | |
| `updated_at` | `TIMESTAMPTZ` | no | `now()` | Updated when the role changes |

**Constraints**

| Constraint | Definition | Purpose |
|---|---|---|
| `pk_todo_list_shares` | `PRIMARY KEY (id)` | |
| `uq_share_owner_grantee` | `UNIQUE (owner_id, grantee_id)` | **One share per owner–grantee pair.** Prevents duplicate invitations in the database, not only in application code, so concurrent requests cannot both succeed (§6.3). |
| `ck_share_not_self` | `CHECK (owner_id <> grantee_id)` | **Self-sharing is impossible in the database**, as a backstop to the API check. |
| `ck_share_role` | `CHECK (role IN ('viewer', 'editor'))` | A role cannot be stored outside the enum, whatever the application does. |

**Indexes**

| Index | Serves |
|---|---|
| `uq_share_owner_grantee (owner_id, grantee_id)` | The per-request authorisation lookup `WHERE owner_id = ? AND grantee_id = ?`, and "my outgoing shares" (`owner_id` is the leading column). |
| `ix_share_grantee (grantee_id)` | "Lists shared with me" — `grantee_id` is not a leading column of the unique index, so it needs its own. |

`role` is stored as a constrained `VARCHAR` rather than a PostgreSQL `ENUM`,
because adding a value to a native enum later needs its own migration step.

### 4.2 Altered table — `todos`

| Change | Definition | Purpose |
|---|---|---|
| Add `version` | `INTEGER NOT NULL DEFAULT 1` | Optimistic concurrency control (§6.3) |

On PostgreSQL 11 and later, adding a column with a constant default is a
metadata-only change: existing rows are not rewritten, so this is safe on a
large table.

### 4.3 Cascade behaviour

| Event | Effect on `todo_list_shares` | Why |
|---|---|---|
| Owner account deleted | Every share **they own** is deleted (`owner_id` cascade) | A share of a list that no longer exists is meaningless |
| Grantee account deleted | Every share **granted to them** is deleted (`grantee_id` cascade) | A share to a user who no longer exists grants nothing |
| A todo is deleted | **None** | Shares are list-level and do not reference individual todos |

> **Note on the current schema.** `todos.user_id` currently has no `ON DELETE`
> action (`alembic/versions/001_initial.py`), and the application has no
> account-deletion endpoint. So an account cannot be deleted today at all. The
> cascade rules above define the correct behaviour for when it can; they do not
> depend on it.

---

## 5. API Contracts & Endpoints

> **Proposed.** None of these routes exists. They are added alongside the
> current `/api/v1/todos` routes, which **keep their current behaviour
> unchanged**: `GET /todos` still returns only the caller's own todos, and
> `GET|PUT|DELETE /todos/{id}` still reach only the caller's own todo. Keeping
> shared access on separate routes leaves the owner-only guarantee of the
> existing endpoints — which is regression-tested — untouched.

All routes require `Authorization: Bearer <access token>`, and reject
unauthenticated requests exactly as the current protected routes do (observed
against the running app):

| Request | Status | Body |
|---|---|---|
| No `Authorization` header | `403` | `{"detail": "Not authenticated"}` — FastAPI's `HTTPBearer` default |
| Invalid, tampered or expired token | `401` | `{"detail": "Invalid authentication token"}` |

A missing token arguably ought to be `401`, but changing that is an
application-wide decision, not part of this feature; the new routes simply
follow the existing behaviour.

### 5.1 Endpoint summary

| Method | Endpoint | Description | Who may call it |
|---|---|---|---|
| `POST` | `/api/v1/shares` | Share my list with a user | Owner |
| `GET` | `/api/v1/shares` | List the shares I own | Owner |
| `PATCH` | `/api/v1/shares/{share_id}` | Change a grantee's role | Owner of that share |
| `DELETE` | `/api/v1/shares/{share_id}` | Revoke access | Owner of that share |
| `GET` | `/api/v1/shared-lists` | List the lists shared with me | Any user (sees only their own grants) |
| `GET` | `/api/v1/shared-lists/{owner_id}/todos` | Read a shared list | Viewer or editor of that owner |
| `PUT` | `/api/v1/shared-lists/{owner_id}/todos/{todo_id}` | Update a todo in a shared list | Editor of that owner |

### 5.2 Schemas

```python
class ShareRole(str, Enum):
    viewer = "viewer"
    editor = "editor"

class ShareCreate(BaseModel):
    email: EmailStr
    role: ShareRole

class ShareUpdate(BaseModel):
    role: ShareRole

class UserSummary(BaseModel):
    id: uuid.UUID
    email: str

class ShareResponse(BaseModel):
    id: uuid.UUID
    grantee: UserSummary
    role: ShareRole
    created_at: datetime
    updated_at: datetime

class SharedListResponse(BaseModel):
    owner: UserSummary
    role: ShareRole          # the caller's role on this list
    shared_at: datetime

class SharedTodoUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    completed: bool | None = None
    version: int              # the version the client last read; required
```

Todo responses on the shared routes reuse the current `TodoResponse`, with
`version` added. `GET /shared-lists/{owner_id}/todos` returns the current
`TodoListResponse` shape.

### 5.3 Responses and error codes

**`POST /api/v1/shares`**

```http
POST /api/v1/shares
Authorization: Bearer <token>
Content-Type: application/json

{"email": "colleague@example.com", "role": "viewer"}
```

| Status | When | Body |
|---|---|---|
| `201` | Share created | `ShareResponse` |
| `400` | `email` is the caller's own | `{"detail": "Cannot share a list with yourself"}` |
| `404` | No registered user has that email | `{"detail": "User not found"}` |
| `409` | A share for this owner–grantee pair already exists | `{"detail": "This list is already shared with that user"}` |
| `422` | Malformed email, or `role` outside the enum | FastAPI validation `detail` array |

**`GET /api/v1/shares`** — `200`, `list[ShareResponse]`.

**`PATCH /api/v1/shares/{share_id}`**

| Status | When | Body |
|---|---|---|
| `200` | Role changed | `ShareResponse` |
| `404` | No such share, **or** it belongs to another owner | `{"detail": "Share not found"}` |
| `422` | `role` outside the enum | validation `detail` |

**`DELETE /api/v1/shares/{share_id}`**

| Status | When | Body |
|---|---|---|
| `204` | Revoked | — |
| `404` | No such share, or not the caller's | `{"detail": "Share not found"}` |

**`GET /api/v1/shared-lists`** — `200`, `list[SharedListResponse]`.

**`GET /api/v1/shared-lists/{owner_id}/todos?page=&size=`**

| Status | When | Body |
|---|---|---|
| `200` | Caller holds any role on this owner's list | `TodoListResponse` |
| `404` | No share, a revoked share, or no such owner — **indistinguishable** | `{"detail": "Shared list not found"}` |

**`PUT /api/v1/shared-lists/{owner_id}/todos/{todo_id}`**

| Status | When | Body |
|---|---|---|
| `200` | Updated | `TodoResponse` with the new `version` |
| `403` | Caller is a **viewer** of this list | `{"detail": "Editor role required"}` |
| `404` | No share on this list | `{"detail": "Shared list not found"}` |
| `404` | Share exists, but `todo_id` is not in this owner's list | `{"detail": "Todo not found"}` |
| `409` | `version` does not match the stored version | `{"detail": "Todo was modified by someone else; reload and retry"}` |
| `422` | Invalid body, or `version` missing | validation `detail` |

### 5.4 Why `403` for a viewer but `404` for everyone else

The current convention returns `404` for a resource the caller may not reach,
so that its existence is not disclosed. That reasoning holds for a user with
**no** share: to them the list must look like it does not exist.

A **viewer** is different — they can already read the list, so a `403` tells
them nothing they do not know. Answering `404` would be misleading ("this todo
does not exist" about a todo on their screen), and `403` states the actual
reason. The rule is therefore: **`404` when the caller has no access at all,
`403` when they have access of the wrong kind.**

---

## 6. Business Logic & Security Considerations

### 6.1 Permission matrix

| Action | Owner | Editor | Viewer | Other |
|---|---|---|---|---|
| Read the list | ✅ | ✅ | ✅ | ❌ `404` |
| Update an existing todo | ✅ | ✅ | ❌ `403` | ❌ `404` |
| Create a todo in the list | ✅ | ❌ (A4) | ❌ | ❌ |
| Delete a todo | ✅ | ❌ (A4) | ❌ | ❌ |
| Share the list | ✅ | ❌ | ❌ | ❌ |
| Change a role | ✅ | ❌ | ❌ | ❌ |
| Revoke access | ✅ | ❌ | ❌ | ❌ |

**Re-sharing.** A grantee cannot share onward. Shares are always created with
`owner_id = current_user.id`, so a grantee who calls `POST /shares` shares
*their own* list, never the one shared with them. No separate check is needed;
the model makes onward sharing unrepresentable.

### 6.2 Authorisation is checked on every request, never cached

Every request to a `/shared-lists/{owner_id}/...` route looks up
`WHERE owner_id = :owner AND grantee_id = :caller` in PostgreSQL before doing
anything else. This is a unique-index lookup and costs well under a
millisecond.

Permission is deliberately **not** cached. A cached permission would outlive a
revocation until it expired; with no cache there is nothing to outlive it, and
revocation is immediate by construction. This is the single most important
decision in the design, and §7 depends on it.

### 6.3 Edge cases and race conditions

| # | Case | Behaviour | Mechanism |
|---|---|---|---|
| E1 | **Self-share** | `400 "Cannot share a list with yourself"` | API check before insert; `ck_share_not_self` rejects it in the database as a backstop |
| E2 | **Duplicate share** | `409`, existing role unchanged | `uq_share_owner_grantee`. Changing a role is `PATCH`, never a second `POST`. |
| E3 | **Concurrent duplicate share** — two `POST`s for the same pair at once | Exactly one `201`, the other `409` | Both pass the application's "already shared?" check; the database's unique constraint rejects the second insert, and the resulting `IntegrityError` maps to `409`. Relying on the application check alone would allow both — the same race that SEC-10 describes for `users.email`. |
| E4 | **Concurrent update** — owner and editor, or two editors, edit one todo | The first write wins; the second gets `409` and must reload | Optimistic locking: `UPDATE todos SET ..., version = version + 1 WHERE id = :id AND version = :expected`. Zero rows updated means someone else wrote first. Without this the second write would silently overwrite the first. |
| E5 | **Revoke while an editor's update is in flight** | Either the update commits before the revoke, or it is rejected — never applied afterwards | The update re-checks the share and writes in **one transaction**, taking `SELECT ... FOR SHARE` on the share row. A concurrent `DELETE` of that row waits for the update's transaction to end; the next update sees no share and gets `404`. |
| E6 | **Owner deletes a todo** | It disappears from every grantee's view on their next read. An editor who then submits an update for it gets `404 "Todo not found"`. | No share rows reference todos. The owner's list cache is cleared as today (§7). |
| E7 | **Grantee deletes their account** | All their shares are removed | `grantee_id ON DELETE CASCADE`. See the note in §4.3 — deletion is not yet possible in the current app. |
| E8 | **Owner deletes their account** | All shares of their list are removed | `owner_id ON DELETE CASCADE` |
| E9 | **Revoked user tries to reach a cached copy** | `404` from the server, immediately | Authorisation is never cached (§6.2), so there is no server-side cache a revoked user can reach. Their browser may still be displaying data it already received; see §7.3. |
| E10 | **Role downgraded from editor to viewer** | The next update returns `403` | Same live check as revocation |

### 6.4 Security notes

- **Prerequisite — SEC-10 must be fixed first.** Grantees are looked up by
  email, and the current `users.email` column has no unique constraint
  (`docs/SECURITY_AUDIT.md`, SEC-10). The current lookup,
  `get_user_by_email`, uses `scalar_one_or_none()`, which raises if two rows
  share an email — so a duplicate would turn a share request into a `500`, and
  a share could resolve to the wrong account. A unique index on `lower(email)`
  is required before this feature ships.
- **Email enumeration.** `POST /shares` answers `404 "User not found"` for an
  unregistered address, which tells the caller whether an address is
  registered. This is the same class of disclosure as SEC-11 on login. It is
  accepted here because the owner needs to know the share failed; the
  mitigation, rate limiting, is out of scope (§3.2) and is recorded as a known
  trade-off.
- **No existence leakage for non-grantees.** Every route under
  `/shared-lists/{owner_id}/` answers `404` identically for "no share", "share
  revoked" and "no such owner", so a caller cannot probe which users exist.
- **Existing routes are unchanged.** Because shared access uses separate routes,
  the owner-only filtering of `/api/v1/todos` introduced by the SEC-02 fix is
  not modified and keeps its regression tests.

---

## 7. Caching & Invalidation Strategy

### 7.1 Keys

| Key | Holds | Status |
|---|---|---|
| `todos:list:{owner_id}:{page}:{size}` | A page of one owner's todos | **Exists today.** Reused unchanged for shared reads. |
| `shares:outgoing:{owner_id}` | The owner's `GET /shares` response | Proposed |
| `shares:incoming:{grantee_id}` | The grantee's `GET /shared-lists` response | Proposed |
| *(none)* | Permission for an owner–grantee pair | **Deliberately not cached** (§6.2) |

A shared read serves the **owner's own** list cache, after a live permission
check. It is keyed by owner and page, not by grantee, so every grantee reads the
same entry the owner does, and one invalidation reaches all of them.

### 7.2 What is invalidated, and for whom

| Event | Keys invalidated | Users whose view is refreshed |
|---|---|---|
| Owner creates, updates or deletes a todo | `todos:list:{owner_id}:*` | Owner and every grantee |
| **Editor updates a todo** | `todos:list:{todo.user_id}:*` — the **owner's** key | Owner and every grantee |
| Share created | `shares:outgoing:{owner_id}`, `shares:incoming:{grantee_id}` | Owner; the new grantee |
| Role changed | `shares:outgoing:{owner_id}`, `shares:incoming:{grantee_id}` | Owner; that grantee |
| **Share revoked** | `shares:outgoing:{owner_id}`, `shares:incoming:{grantee_id}` | Owner; the revoked grantee |
| Owner account deleted | `shares:incoming:{g}` for each former grantee `g` | Every former grantee |
| Grantee account deleted | `shares:outgoing:{o}` for each owner `o` who had shared with them | Every affected owner |

**A required change from current behaviour.** The existing helper is called as
`invalidate_todo_list_cache(redis, current_user.id)`, clearing the *caller's*
cache (`app/api/v1/todos.py`). Today the caller is always the owner, so that is
correct. Once an editor can update someone else's todo, the caller is no
longer the owner: clearing the editor's key would leave the owner and every
other grantee reading a stale list for up to 300 s. Invalidation on the shared
update path must be keyed by **`todo.user_id`**, the owner.

### 7.3 Revocation takes effect immediately

The requirement is that revoking access takes effect at once. Three layers are
involved, and each is handled explicitly:

1. **Permission — immediate, by design.** It is checked in PostgreSQL on every
   request (§6.2). The revoke commits, and the grantee's next request fails
   `404`. There is no window.
2. **Server-side data cache — cannot leak after revocation.**
   `todos:list:{owner_id}:*` is **not** cleared on revoke, because its contents
   did not change: the owner and remaining grantees are still entitled to it.
   A revoked grantee cannot reach it, because it is served only *after* the
   live permission check passes. The listing caches that *did* change,
   `shares:incoming:{grantee_id}` and `shares:outgoing:{owner_id}`, are deleted
   in the same request, after the database commit and before `204` is returned.
3. **Client-side cache — not controllable from the server.** A former grantee
   with the list already open may keep seeing what their browser received,
   until their next request, which fails `404`. The client must respond to a
   `404` on a shared route by removing that owner's queries, and shared-list
   queries should use a short `staleTime`. Pushing the revocation to an open
   screen is out of scope (§3.2).

**The design this avoids.** A tempting alternative is to cache each grantee's
view under a key that includes the grantee, such as
`shared:{grantee_id}:{owner_id}:{page}`, and to return it on a cache hit before
checking permission. A revoked grantee would then keep reading the owner's list
until the entry expired — up to 300 s after revocation. That is the same class
of defect as SEC-03, where a cache key that did not match the authorisation
boundary served one user's todos to another. Keying the data cache by owner and
checking permission live, before any cache read, is what rules it out.
