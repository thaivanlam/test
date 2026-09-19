# Tier 1 — Security & Correctness Audit

**Scope:** `backend/`, `frontend/`, repository configuration
**Branch:** `assessment/thai-van-lam`
**Baseline commit:** `c92fd72`
**Audit date:** 2026-09-19

---

## Audit Methodology

This audit was performed as **static source code analysis**. At the time of the
audit the runtime environment was not available:

| Dependency | State at audit time | Impact |
|---|---|---|
| Docker daemon | Not running (`failed to connect to the docker API at npipe:...`) | Could not start Postgres, Redis, backend or frontend |
| `pytest` | Not installed (`No module named pytest`) | Could not execute the backend test suite |
| `python-jose` / `PyJWT` | Not installed (`No module named 'jose'`, `No module named 'jwt'`) | Could not exercise token encode/decode paths |
| Python version | 3.14.6 locally; project targets 3.12 (`pyproject.toml`, `backend/Dockerfile`) | Local dependency install is unreliable; container is the supported path |
| `frontend/node_modules` | Not installed | Could not run the frontend or a browser session |

Consequences for how this document must be read:

- Every finding below was identified by **reading source code**, and the
  "Evidence" of each one is a direct source citation or the output of a
  read-only command (`grep`, `git ls-files`, `git check-ignore`).
- The **"Reproduction"** field of each finding describes the steps required to
  demonstrate the defect. **These steps were not executed during this audit.**
  They are a plan for Tier 2, not a record of an observed run.
- No finding in this document is marked `Reproduced`. That status is reserved
  for findings that have been demonstrated by an actually executed test or
  command, with its output recorded here.

### Status vocabulary

| Status | Meaning |
|---|---|
| `Open — static` | Defect identified by source analysis. The code path is unambiguous, but no runtime demonstration has been performed. |
| `Open — suspected` | Possible defect. Source analysis is not sufficient to establish it; runtime verification is required before it is claimed as a bug. |
| `Reproduced` | Demonstrated by an executed test or command whose output is recorded in this document. **No finding currently holds this status.** |
| `Fixed` | Defect corrected, with a regression test that fails before the fix and passes after it. |

### Verification plan

Findings will be promoted from `Open — static` to `Reproduced` in Tier 2, once
the container stack is running. Each fix is expected to follow the sequence:
write a failing test that reproduces the defect, record the failure, apply the
fix, record the pass. This document is to be updated as statuses change, so
that the final state accurately distinguishes what was proven from what was
merely read.

### A note on credentials

This document deliberately contains **no secret values**. Finding SEC-08
concerns a committed secret; it identifies the file and the variable name but
does not reproduce the value. No access token, refresh token, signing key or
password appears anywhere in this file.

---

## Summary

| Severity | Count |
|---|---|
| Critical | 3 |
| High | 6 |
| Medium | 10 |
| Low | 4 |
| **Total** | **23** |

| Area | Count |
|---|---|
| Backend | 15 |
| Frontend | 7 |
| Repository / secrets | 1 |

| Status | Count |
|---|---|
| `Open — static` | 21 |
| `Open — suspected` | 2 |
| `Reproduced` | 0 |
| `Fixed` | 0 |

### Index

| ID | Severity | Area | Summary | Status |
|---|---|---|---|---|
| SEC-01 | Critical | Auth | Token expiry verification disabled | `Open — static` |
| SEC-02 | Critical | AuthZ | IDOR: any user can read/update/delete another user's todo | `Open — static` |
| SEC-03 | Critical | Cache | Global cache key leaks todos across users | `Open — static` |
| SEC-04 | High | Cache | No cache invalidation on create/update/delete | `Open — static` |
| SEC-05 | High | Logic | `completed` cannot be toggled back to `false` | `Open — static` |
| SEC-06 | High | Logic | Partial update erases `description` | `Open — static` |
| SEC-07 | High | Frontend | Logout does not clear the query cache | `Open — static` |
| SEC-08 | High | Secrets | `.env` is tracked by Git and contains a signing key | `Open — static` |
| SEC-09 | High | Auth | Token type not validated; refresh token usable as access token | `Open — static` |
| SEC-10 | Medium | Database | `users.email` has no unique constraint | `Open — static` |
| SEC-11 | Medium | Auth | User enumeration via distinct login error responses | `Open — static` |
| SEC-12 | Medium | Auth | Logout is a no-op; no token revocation; refresh does not re-check user | `Open — static` |
| SEC-13 | Medium | Database | Pagination without `ORDER BY` | `Open — static` |
| SEC-14 | Medium | Performance | N+1 query in todo listing | `Open — static` |
| SEC-15 | Medium | Security | CORS wildcard origin combined with credentials | `Open — static` |
| SEC-16 | Medium | Frontend | Optimistic update never rolled back on error | `Open — static` |
| SEC-17 | Medium | Frontend | Query key omits pagination parameters; page size default 10000 | `Open — static` |
| SEC-18 | Medium | Frontend | Refresh token stored but never used | `Open — static` |
| SEC-19 | Medium | Frontend | List rendered with array index as React key | `Open — static` |
| SEC-20 | Low | Validation | No password policy on the backend | `Open — static` |
| SEC-21 | Low | Config | SQL echo enabled by default | `Open — static` |
| SEC-22 | Low | Frontend | Route guard checks only for token presence | `Open — suspected` |
| SEC-23 | Low | Dependencies | `passlib` / `bcrypt` version incompatibility | `Open — suspected` |

---

## Critical

### SEC-01 — Token expiry verification disabled

- **Severity:** Critical
- **Location:** `backend/app/core/security.py:49-63`, `verify_token()`, specifically line 56
- **Status:** `Open — static`
- **Reason:** `jwt.decode()` is called with `options={"verify_exp": False}`, which
  disables expiry checking entirely. Every access token is valid forever, making
  `ACCESS_TOKEN_EXPIRE_MINUTES` meaningless. A token that leaks through logs,
  browser history or a shared machine remains usable indefinitely, and there is
  no mechanism by which it can be retired.
- **Evidence:**
  ```
  49:def verify_token(token: str) -> dict[str, Any] | None:
  52:        payload = jwt.decode(
  56:            options={"verify_exp": False},
  ```
- **Reproduction (not yet executed):** Issue a token whose `exp` claim is in the
  past, then call `GET /api/v1/auth/me` with it. Expected `401`; the code path
  indicates `200` will be returned.
- **Proposed Fix:** Remove the `options` argument so the library's default expiry
  validation applies, and handle `ExpiredSignatureError` separately to return a
  clear `401`.

### SEC-02 — IDOR: any user can read, update or delete another user's todo

- **Severity:** Critical
- **Location:** `backend/app/api/v1/todos.py:88-102` (`get_todo`), `:105-134`
  (`update_existing_todo`), `:137-153` (`delete_existing_todo`);
  `backend/app/services/todo_service.py:42-44` (`get_todo_by_id`)
- **Status:** `Open — static`
- **Reason:** `get_todo_by_id()` filters on `Todo.id` only. All three endpoints
  declare a `current_user` dependency but never compare `todo.user_id` against
  `current_user.id`. Any authenticated user who knows or guesses a todo UUID can
  read, modify or delete a record belonging to somebody else. This is the most
  severe data isolation failure in the codebase.
- **Evidence:** `current_user` appears in these endpoints only as a dependency
  declaration; no ownership comparison exists anywhere in the file.
  ```
   91:    current_user: User = Depends(get_current_user),   # get_todo
  109:    current_user: User = Depends(get_current_user),   # update
  140:    current_user: User = Depends(get_current_user),   # delete
  ```
  ```
  42:async def get_todo_by_id(db: AsyncSession, todo_id: uuid.UUID) -> Todo | None:
  43-    result = await db.execute(select(Todo).where(Todo.id == todo_id))
  ```
- **Reproduction (not yet executed):** User A creates a todo. User B
  authenticates separately and issues `GET`, `PUT` and `DELETE` against that
  todo's id. Expected `404` for each; the code path indicates all three succeed.
- **Proposed Fix:** Add a `user_id` parameter to `get_todo_by_id()` and filter on
  it inside the query. Return `404` rather than `403` so the existence of another
  user's record is not disclosed.

### SEC-03 — Global cache key leaks todos across users

- **Severity:** Critical
- **Location:** `backend/app/api/v1/todos.py:37`
- **Status:** `Open — static`
- **Reason:** The cache key is the constant string `"todos:list"`, scoped neither
  by user nor by pagination parameters. The first user to call `GET /todos`
  writes their own list under this shared key; for the next 300 seconds every
  other user receives that same cached payload. Because `TodoResponse` carries a
  `user_email` field, the leak includes email addresses. This occurs on the
  ordinary request path and requires no attacker action.
- **Evidence:**
  ```
  23:CACHE_TTL = 300  # 5 minutes
  37:    cache_key = "todos:list"
  40:    cached = await redis.get(cache_key)
  72:    await redis.set(cache_key, response.model_dump_json(), ex=CACHE_TTL)
  ```
- **Reproduction (not yet executed):** User A calls `GET /api/v1/todos`. Within
  the TTL window, User B calls the same endpoint and is expected to receive User
  A's items.
- **Proposed Fix:** Scope the key to the caller and the query:
  `f"todos:list:{current_user.id}:{page}:{size}"`.

---

## High

### SEC-04 — No cache invalidation on mutation

- **Severity:** High
- **Location:** `backend/app/api/v1/todos.py:77-85`, `:105-134`, `:137-153`
- **Status:** `Open — static`
- **Reason:** No cache deletion occurs after create, update or delete. The update
  and delete endpoints inject a `redis` dependency (lines 111 and 142) that is
  never used, indicating invalidation logic was removed. A newly created todo
  does not appear in the list for up to five minutes, and a deleted todo remains
  visible. Combined with SEC-03, the stale data is also served to other users.
- **Evidence:** `redis.delete` exists only as a method definition and is called
  nowhere in the application.
  ```
  backend/app/core/redis.py:32:        await self._redis.delete(key)   # definition only
  ```
  ```
  111:    redis: RedisClient = Depends(get_redis),   # injected, unused
  142:    redis: RedisClient = Depends(get_redis),   # injected, unused
  ```
- **Reproduction (not yet executed):** Call `GET /todos`, create a todo, call
  `GET /todos` again within the TTL; the new item is expected to be absent.
- **Proposed Fix:** Delete the caller's cache entries after every mutation. Use a
  per-user cache version counter rather than a `KEYS` scan. Note that
  `create_new_todo` does not currently inject `redis` and will need it.

### SEC-05 — `completed` cannot be toggled back to `false`

- **Severity:** High
- **Location:** `backend/app/api/v1/todos.py:123-124`
- **Status:** `Open — static`
- **Reason:** The guard `if todo_data.completed:` tests truthiness rather than
  `is not None`. When a client sends `completed: false` the condition is falsy
  and the assignment is skipped, so a completed todo can never be marked
  incomplete. The field effectively transitions in one direction only.
- **Evidence:**
  ```
  123:    if todo_data.completed:
  124:        todo.completed = todo_data.completed
  ```
- **Reproduction (not yet executed):** Create a todo, `PUT {"completed": true}`,
  then `PUT {"completed": false}`. The response is expected to report `200` while
  the stored value remains `true`.
- **Proposed Fix:** `if todo_data.completed is not None:`.

### SEC-06 — Partial update erases `description`

- **Severity:** High
- **Location:** `backend/app/api/v1/todos.py:121`, `:129-130`
- **Status:** `Open — static`
- **Reason:** `model_dump()` is called without `exclude_unset=True`, so fields the
  client omitted are still present in the resulting dict with a value of `None`.
  The guard `if "description" in update_data` is therefore always true, and
  updating only the title silently overwrites the description with `NULL`. This
  is unannounced data loss.
- **Evidence:**
  ```
  121:    update_data = todo_data.model_dump()        # missing exclude_unset=True
  129:    if "description" in update_data:            # always true
  130:        todo.description = update_data["description"]
  ```
  Line 132 additionally calls `update_todo(db, todo, {})` with an empty dict, so
  the assignment logic has been hoisted out of the service layer.
- **Reproduction (not yet executed):** Create a todo with both fields populated,
  then `PUT {"title": "..."}` alone; `description` is expected to become `null`.
- **Proposed Fix:** Use `todo_data.model_dump(exclude_unset=True)` and pass the
  resulting dict to `update_todo()`, removing the manual assignment block.

### SEC-07 — Logout does not clear the query cache

- **Severity:** High
- **Location:** `frontend/src/features/auth/api/auth.ts:46-56` (`useLogout`);
  `frontend/src/features/auth/hooks/useAuth.ts:23-35`
- **Status:** `Open — static`
- **Reason:** Logout clears `localStorage` but never touches `queryClient`. The
  client is a module-level singleton (`frontend/src/lib/queryClient.ts`) that
  lives for the lifetime of the tab, configured with a five-minute `staleTime`.
  After User A logs out and User B logs in within the same tab, User B is served
  User A's cached todos and email — and while the data remains within
  `staleTime`, no refetch is issued at all. This is a client-side cross-user data
  leak.
- **Evidence:** Searching both auth files for `queryClient`, `clear` or
  `removeQueries` returns a single line, and it is a comment rather than code.
  ```
  frontend/src/features/auth/hooks/useAuth.ts:29:  // Even on error, clear local tokens and redirect
  ```
- **Reproduction (not yet executed):** Log in as User A and load the dashboard,
  log out, then log in as User B in the same tab without reloading. User A's
  todos and email are expected to be displayed.
- **Proposed Fix:** Call `queryClient.clear()` in both the `onSuccess` and
  `onError` handlers of the logout mutation, and in the response interceptor when
  a `401` is handled.

### SEC-08 — `.env` is tracked by Git and contains a signing key

- **Severity:** High
- **Location:** `.env` (tracked in the repository); JWT signing key on line 8
- **Status:** `Open — static`
- **Reason:** The `.env` rule in `.gitignore` is commented out, so the file is
  tracked and its contents are present in the repository history and on the
  remote. The file defines the JWT signing key and the database password.
  Disclosure of the signing key means anyone with read access to the repository
  can mint valid tokens for an arbitrary user id; combined with SEC-01, which
  removes expiry, this amounts to unbounded account takeover. The same signing
  key is also hardcoded in `docker-compose.yml:24`.
- **Evidence:** (variable names only; values deliberately omitted)
  ```
  $ git ls-files --error-unmatch .env
  .env
  $ grep -n "SECRET" .env
  8:JWT_SECRET=<redacted>
  ```
- **Reproduction (not yet executed):** `git log --all --full-history -- .env`
  shows the file throughout the history.
- **Proposed Fix:** Uncomment the `.env` rule in `.gitignore`, run
  `git rm --cached .env`, keep `.env.example` as the tracked template, and rotate
  the signing key to a randomly generated value supplied by the environment.
  Rotation is required because the previous value must be treated as public.
- **Note:** Left untouched deliberately, so the finding remains demonstrable.

### SEC-09 — Token type not validated

- **Severity:** High
- **Location:** `backend/app/api/deps.py:16-51`, `get_current_user()`
- **Status:** `Open — static`
- **Reason:** The dependency does not check `payload.get("type") == "access"`,
  while `/auth/refresh` does perform that check (`auth.py:86`). The asymmetry
  means a refresh token is accepted as an access token on every protected
  endpoint. A refresh token is valid for seven days and is intended solely for
  obtaining new access tokens; accepting it as a credential defeats the purpose
  of separating the two token types.
- **Evidence:** Searching `deps.py` for `type` and `payload.get` returns one line,
  with no type check present.
  ```
  29:    user_id = payload.get("sub")
  ```
- **Reproduction (not yet executed):** Authenticate, then call
  `GET /api/v1/auth/me` presenting the refresh token as the bearer credential.
  Expected `401`; the code path indicates `200`.
- **Proposed Fix:** After decoding, reject the request when
  `payload.get("type") != "access"`.

---

## Medium

### SEC-10 — `users.email` has no unique constraint

- **Severity:** Medium
- **Location:** `backend/app/models/user.py:21-24`;
  `backend/alembic/versions/001_initial.py:26`
- **Status:** `Open — static`
- **Reason:** The column carries no unique constraint in either the model or the
  migration. Duplicate detection in `register` is a check-then-insert performed in
  application code, which is open to a race between concurrent requests. Once
  duplicates exist, `get_user_by_email()` uses `scalar_one_or_none()` and will
  raise `MultipleResultsFound`, turning login into a `500` for every account
  sharing that address.
- **Evidence:**
  ```
  # model — no unique=True
  21:    email: Mapped[str] = mapped_column(
  22-        String(255),
  23-        nullable=False,
  # migration — no unique constraint
  26:        sa.Column("email", sa.String(length=255), nullable=False),
  ```
- **Reproduction (not yet executed):** Issue concurrent `POST /auth/register`
  requests with the same address, then attempt to log in with it.
- **Proposed Fix:** Add `unique=True, index=True` to the model and a migration
  creating a unique index on `lower(email)`, then handle `IntegrityError` in
  `register` and return `400`.

### SEC-11 — User enumeration via distinct login errors

- **Severity:** Medium
- **Location:** `backend/app/api/v1/auth.py:52-66`
- **Status:** `Open — static`
- **Reason:** An unknown address returns `404 "User with this email not found"`
  while a known address with the wrong password returns `401 "Incorrect
  password"`. The distinction lets an attacker determine which addresses are
  registered, which supports credential stuffing and targeted phishing.
  `templates/TEST_PLAN_TEMPLATE.md` includes TC-02 for exactly this behaviour.
- **Evidence:**
  ```
      if not user:
          raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
              detail="User with this email not found",)
      if not verify_password(...):
          raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
              detail="Incorrect password",)
  ```
- **Reproduction (not yet executed):** Log in with an unregistered address, then
  with a registered address and an incorrect password; compare status codes.
- **Proposed Fix:** Collapse both branches into a single
  `401 "Invalid email or password"`. `authenticate_user()` already exists at
  `backend/app/services/auth_service.py:33-39` and is currently called nowhere.

### SEC-12 — Logout is a no-op and refresh does not re-check the user

- **Severity:** Medium
- **Location:** `backend/app/api/v1/auth.py:102-107` (`logout`), `:84-99`
  (`refresh_token`)
- **Status:** `Open — static`
- **Reason:** Two related gaps. `logout` returns a message and revokes nothing, so
  the presented token stays valid — indefinitely, given SEC-01. A `jti` claim is
  generated at `security.py:42` but is never stored or consulted, indicating an
  abandoned denylist mechanism. Separately, `refresh` issues new tokens purely
  from the payload without confirming the user still exists, so a deleted account
  can extend its session indefinitely.
- **Evidence:**
  ```
  backend/app/core/security.py:42:  to_encode.update({..., "jti": str(uuid.uuid4())})   # generated, never read
  ```
  ```
  @router.post("/logout")
  async def logout(current_user: User = Depends(get_current_user)):
      return {"message": "Successfully logged out"}
  ```
- **Reproduction (not yet executed):** Authenticate, call `POST /auth/logout`,
  then reuse the same token against a protected endpoint.
- **Proposed Fix:** On logout, record the refresh token's `jti` in a Redis denylist
  with a TTL matching the token's remaining lifetime. In `refresh`, load the user
  from the database and reject denylisted identifiers before issuing new tokens.

### SEC-13 — Pagination without `ORDER BY`

- **Severity:** Medium
- **Location:** `backend/app/services/todo_service.py:31`
- **Status:** `Open — static`
- **Reason:** The paginated query applies `.offset()` and `.limit()` with no
  ordering. PostgreSQL does not guarantee row order in the absence of `ORDER BY`,
  so successive page requests can return overlapping or missing rows. Tier 4 of
  the assessment specifies `created_at DESC, id DESC`, which suggests the omission
  is deliberate.
- **Evidence:**
  ```
  31: query = select(Todo).where(Todo.user_id == user_id).offset(skip).limit(limit)
  ```
  A search for `order_by` across `backend/app/` returns no matches.
- **Reproduction (not yet executed):** With a seeded dataset, request page 1 and
  page 2 repeatedly and compare the returned id sets.
- **Proposed Fix:** Add `.order_by(Todo.created_at.desc(), Todo.id.desc())`, which
  also aligns with the composite index planned for Tier 3C.

### SEC-14 — N+1 query in todo listing

- **Severity:** Medium
- **Location:** `backend/app/api/v1/todos.py:47-62`
- **Status:** `Open — static`
- **Reason:** The response-building loop issues a separate `SELECT` against
  `users` for every todo, although all todos in the list belong to the
  authenticated caller, whose email is already available as `current_user.email`.
  With the frontend's default page size of 10000 (SEC-17) a single page load
  issues on the order of ten thousand redundant queries.
- **Evidence:**
  ```
  48:    for todo in todos:
  49:        user_result = await db.execute(select(User).where(User.id == todo.user_id))
  50:        user = user_result.scalar_one_or_none()
  ```
- **Reproduction (not yet executed):** With `DB_ECHO` enabled (the current
  default, SEC-21), call `GET /todos` against a seeded account and count
  `SELECT users` statements in the container log.
- **Proposed Fix:** Remove the loop query and use `user_email=current_user.email`.

### SEC-15 — CORS wildcard origin combined with credentials

- **Severity:** Medium
- **Location:** `backend/app/main.py:29-35`
- **Status:** `Open — static`
- **Reason:** `allow_origins=["*"]` together with `allow_credentials=True` is
  disallowed by the CORS specification. Browsers reject the combination, and some
  Starlette versions respond by echoing the request's `Origin`, which effectively
  permits credentialed requests from any site.
- **Evidence:**
  ```
  30:    CORSMiddleware,
  31:    allow_origins=["*"],
  32:    allow_credentials=True,
  ```
- **Reproduction (not yet executed):** Issue a request carrying an arbitrary
  `Origin` header and inspect the `Access-Control-Allow-Origin` response header.
- **Proposed Fix:** Enumerate permitted origins from settings, or retain the
  wildcard and set `allow_credentials=False` — the API authenticates with bearer
  tokens and does not require credentialed CORS.

### SEC-16 — Optimistic update never rolled back on error

- **Severity:** Medium
- **Location:** `frontend/src/features/todos/api/todos.ts:95-97`
- **Status:** `Open — static`
- **Reason:** `onMutate` snapshots the previous list and returns it as mutation
  context, following the standard optimistic-update pattern, but `onError` never
  restores it. On failure the UI retains the optimistic state. `onSettled`
  invalidates the query, which masks the defect in most cases; when the failure is
  a network error the refetch fails too and the incorrect state persists.
- **Evidence:**
  ```
        return { previousTodos };     // snapshot returned
      },
      onError: () => {
        toast.error("Failed to update todo");   // context never used
      },
  ```
- **Reproduction (not yet executed):** Stop the backend and toggle a todo; the
  checkbox is expected to retain the optimistic state despite the error toast.
- **Proposed Fix:** Accept the context argument in `onError` and restore it with
  `queryClient.setQueryData(["todos"], context.previousTodos)`.

### SEC-17 — Query key omits pagination parameters

- **Severity:** Medium
- **Location:** `frontend/src/features/todos/api/todos.ts:35-45`
- **Status:** `Open — static`
- **Reason:** Two defects in one hook. The query key is the bare `["todos"]`
  although `page` and `size` are sent with the request, so every page shares one
  cache entry and navigating between pages reads the wrong data; Tier 4 of the
  assessment states explicitly that query keys must include all parameters.
  Separately, the default `size` of 10000 turns pagination into a full table
  fetch and amplifies SEC-14.
- **Evidence:**
  ```
  35:export function useTodos(page: number = 1, size: number = 10000) {
  37:    queryKey: ["todos"],          // page and size absent
  40:        params: { page, size },   // but present in the request
  ```
- **Reproduction (not yet executed):** Call the hook with differing pagination
  arguments and observe that the first result is served for both.
- **Proposed Fix:** Use `queryKey: ["todos", { page, size }]`, reduce the default
  page size, and include the user identifier in the key to prevent cross-session
  reuse (see SEC-07).

### SEC-18 — Refresh token stored but never used

- **Severity:** Medium
- **Location:** `frontend/src/lib/api.ts:27-36`
- **Status:** `Open — static`
- **Reason:** On a `401` the response interceptor clears both tokens and navigates
  away without ever attempting `/auth/refresh`. The refresh token is written to
  `localStorage` and later removed, but is never transmitted — the backend's
  refresh endpoint is unreachable from the client. Users are logged out when the
  access token expires despite holding a refresh token valid for seven days.
  Additionally, `window.location.href` forces a full page reload, bypassing React
  Router and leaving the query cache intact (see SEC-07).
- **Evidence:** Searching `frontend/src/` for `refresh_token` and `/auth/refresh`
  finds only writes and deletions; no request is ever issued.
  ```
  auth.ts:28, auth.ts:41     localStorage.setItem("refresh_token", ...)
  auth.ts:53, useAuth.ts:31, api.ts:32     removeItem(...)
  # no call site for POST /auth/refresh
  ```
- **Reproduction (not yet executed):** Once SEC-01 is fixed, authenticate, allow
  the access token to expire, and perform any action; the session is expected to
  end rather than renew.
- **Proposed Fix:** On the first `401` for a request, attempt a refresh, store the
  new token and retry the original request behind a `_retry` flag to prevent
  loops. Only when the refresh fails should the cache be cleared and the user
  redirected through the router.

### SEC-19 — List rendered with array index as React key

- **Severity:** Medium
- **Location:** `frontend/src/features/todos/components/TodoList.tsx:42`
- **Status:** `Open — static`
- **Reason:** The list uses `key={index}` although every todo carries a stable
  UUID. React reconciles by key, so removing, inserting or reordering items
  misassigns component state — pending checkbox state, focus and transitions
  attach to the wrong row. Combined with the optimistic updates of SEC-16 this
  produces visibly incorrect toggle behaviour.
- **Evidence:**
  ```
  42:            key={index}
  ```
  The `index` prop is declared in `TodoItemProps` and passed down, but
  `TodoItem.tsx:14` destructures without it, so it is otherwise unused.
- **Reproduction (not yet executed):** Create several todos and delete the first;
  observe row state before the refetch completes.
- **Proposed Fix:** Use `key={todo.id}` and drop the unused `index` prop.

---

## Low

### SEC-20 — No password policy on the backend

- **Severity:** Low
- **Location:** `backend/app/schemas/user.py:7-9`
- **Status:** `Open — static`
- **Reason:** `UserCreate.password` is an unconstrained `str`, so the API accepts
  an empty or single-character password. The frontend enforces a six-character
  minimum (`frontend/src/features/auth/schemas/auth.ts:5`), but client-side
  validation is not a security control and is bypassed by calling the API
  directly. Backend and frontend validation are expected to agree.
- **Evidence:**
  ```
  7:class UserCreate(BaseModel):
  8:    email: EmailStr
  9:    password: str        # no Field(min_length=...)
  ```
- **Reproduction (not yet executed):** Register with a one-character password and
  observe `201`.
- **Proposed Fix:** `password: str = Field(..., min_length=8, max_length=72)` —
  72 being bcrypt's input limit — and align the Zod schema with it.

### SEC-21 — SQL echo enabled by default

- **Severity:** Low
- **Location:** `backend/app/core/config.py:9`
- **Status:** `Open — static`
- **Reason:** `DB_ECHO` defaults to `True`, so the engine logs every statement and
  its bound parameters to stdout in all environments. In production this both
  discloses user data through logs and measurably degrades throughput.
  `docker-compose.yml` does not override it.
- **Evidence:**
  ```
  backend/app/core/config.py:9:    DB_ECHO: bool = True
  backend/app/db/session.py:9:    echo=settings.DB_ECHO,
  ```
- **Reproduction (not yet executed):** Start the stack and call any endpoint;
  statements appear in the container log.
- **Proposed Fix:** Default to `False` and enable it explicitly via the
  environment when debugging.

### SEC-22 — Route guard checks only for token presence

- **Severity:** Low
- **Location:** `frontend/src/router/ProtectedRoute.tsx:9-13`
- **Status:** `Open — suspected`
- **Reason:** The guard tests only that a string exists in `localStorage`, not
  that it is a well-formed or unexpired token, so writing an arbitrary value grants
  access to the dashboard route. Recorded as suspected rather than confirmed: the
  authoritative check is server-side and the `401` interceptor redirects, so the
  practical consequence is a brief render of an empty dashboard rather than a
  disclosure. Runtime observation is needed to judge the real impact.
- **Evidence:**
  ```
   9:  const token = localStorage.getItem("access_token");
  11:  if (!token) {
  ```
- **Reproduction (not yet executed):** Write an arbitrary string to the
  `access_token` key and navigate to the protected route.
- **Proposed Fix:** Derive the guard from `useAuth()` and render a loading state
  while the identity query resolves.

### SEC-23 — `passlib` / `bcrypt` version incompatibility

- **Severity:** Low
- **Location:** `backend/requirements.txt` — `passlib==1.7.4`, `bcrypt==4.3.0`
- **Status:** `Open — suspected`
- **Reason:** `passlib` 1.7.4 reads `bcrypt.__about__.__version__`, an attribute
  removed in `bcrypt` 4.1. The combination commonly emits a version-detection
  warning at import time. This is usually harmless, but in some environments it
  interferes with hashing. **This finding rests on dependency versions alone**;
  it was not verified, because the container was unavailable and the packages
  cannot be installed reliably on the local Python 3.14 interpreter.
- **Evidence:** Version pins in `requirements.txt`. No runtime output was
  obtained, and none is claimed.
- **Reproduction (not yet executed):** Start the backend container and inspect
  the startup log, or exercise `get_password_hash()` inside the container.
- **Proposed Fix:** If the warning is confirmed, pin `bcrypt<4.1` or replace
  `passlib` with direct use of the `bcrypt` library. Take no action unless the
  behaviour is observed.

---

## Remediation order

The findings below are proposed for Tier 1 remediation. The assessment requires
at least five fixes covering at least two backend and one frontend defect; this
selection covers seven and maps onto all five backend test scenarios listed in
Tier 2A.

| Order | ID | Rationale |
|---|---|---|
| 1 | SEC-02 | Most severe defect; covers the cross-user authorization scenario in both Tier 2A and the Tier 2B E2E isolation test. |
| 2 | SEC-01 | Critical, one-line change, unambiguous evidence; covers the expired-token scenario. |
| 3 | SEC-03 | Critical; leaks data on the ordinary request path; covers the cache scenario. |
| 4 | SEC-06 | Silent data loss; covers "updating title does not erase description". |
| 5 | SEC-05 | Covers "updating completed from true back to false"; one-line change, demonstrable in the UI. |
| 6 | SEC-07 | Strongest frontend finding; satisfies the frontend requirement and is what the E2E isolation test will surface. |
| 7 | SEC-04 | Belongs with SEC-03; completes the cache invalidation scenario. |

Two findings are to be reported but handled with care. SEC-08 requires
`git rm --cached` and key rotation and should be isolated in its own commit.
SEC-12 needs a Redis denylist to fix properly, which is a wider change than
Tier 1 warrants; it may be better recorded under trade-offs.

---

## Change log

| Date | Change |
|---|---|
| 2026-09-19 | Initial audit. 23 findings recorded from static analysis; none reproduced at runtime. |
