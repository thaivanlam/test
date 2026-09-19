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
  demonstrate the defect. **They were not executed during the original audit.**
  Where a finding has since been reproduced or fixed, its own section records
  what was actually run and what came back. Everywhere else the field remains
  a plan and nothing more.
- The status column is what keeps the two apart. A finding still at
  `Open — static` rests on reading alone; nothing is promoted past that without
  recorded output from a command that was really executed.

### Status vocabulary

| Status | Meaning |
|---|---|
| `Open — static` | Defect identified by source analysis. The code path is unambiguous, but no runtime demonstration has been performed. |
| `Open — suspected` | Possible defect. Source analysis is not sufficient to establish it; runtime verification is required before it is claimed as a bug. |
| `Reproduced` | Demonstrated by an executed test or command whose output is recorded in this document, but not yet fixed. |
| `Fixed` | Defect corrected, with a regression test that fails before the fix and passes after it. |

### Verification plan

Each fix follows the same sequence: write a test that reproduces the defect,
record it failing, apply the fix, record it passing, then run the full suite
to check for regressions. Findings are promoted only on that evidence.

Tier 1 closed with five findings fixed this way — SEC-01, SEC-02, SEC-03,
SEC-04 and SEC-07 — and one, SEC-23, observed at runtime but left alone.

Tier 2 fixed nothing further. Its manual test plan, `docs/TEST_PLAN.md`, ran
the authentication paths against the live stack and reproduced three findings
that until then rested on reading alone: SEC-09, SEC-11 and SEC-12. They move
to `Reproduced`, not `Fixed`.

Of the fourteen findings not yet demonstrated, thirteen are `Open — static`
and one is `Open — suspected`: read, reasoned about, and not run. They are
reported rather than claimed.

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
| `Open — static` | 13 |
| `Open — suspected` | 1 |
| `Reproduced` | 4 |
| `Fixed` | 5 |

### Index

| ID | Severity | Area | Summary | Status |
|---|---|---|---|---|
| SEC-01 | Critical | Auth | Token expiry verification disabled | `Fixed` (`1e6984c`) |
| SEC-02 | Critical | AuthZ | IDOR: any user can read/update/delete another user's todo | `Fixed` (`b6089e4`) |
| SEC-03 | Critical | Cache | Global cache key leaks todos across users | `Fixed` (`6a9ce9f`) |
| SEC-04 | High | Cache | No cache invalidation on create/update/delete | `Fixed` (`9957174`) |
| SEC-05 | High | Logic | `completed` cannot be toggled back to `false` | `Open — static` |
| SEC-06 | High | Logic | Partial update erases `description` | `Open — static` |
| SEC-07 | High | Frontend | Logout does not clear the query cache | `Fixed` (`ff7ce08`) |
| SEC-08 | High | Secrets | `.env` is tracked by Git and contains a signing key | `Open — static` |
| SEC-09 | High | Auth | Token type not validated; refresh token usable as access token | `Reproduced` |
| SEC-10 | Medium | Database | `users.email` has no unique constraint | `Open — static` |
| SEC-11 | Medium | Auth | User enumeration via distinct login error responses | `Reproduced` |
| SEC-12 | Medium | Auth | Logout is a no-op; no token revocation; refresh does not re-check user | `Reproduced` (logout half) |
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
| SEC-23 | Low | Dependencies | `passlib` / `bcrypt` version incompatibility | `Reproduced` |

---

## Critical

### SEC-01 — Token expiry verification disabled

- **Severity:** Critical
- **Location:** `backend/app/core/security.py:49-63`, `verify_token()`, specifically line 56
- **Status:** `Fixed` in `1e6984c`
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
- **Reproduction (executed):**
  `tests/test_auth.py::test_expired_access_token_is_rejected` registers a user,
  confirms a fresh token is accepted, then signs a correctly formed token for
  that same user with `exp` a minute in the past and calls
  `GET /api/v1/auth/me`. The user genuinely exists, so expiry is the only
  possible reason to reject it. Before the fix the test failed on
  `assert 200 == 401`.
- **Fix applied:** Removed the `options` argument so the library's default
  expiry validation applies. One line of production code; the authentication
  architecture is otherwise untouched.
- **Verification:** The regression test passes afterwards, and the backend suite
  went from 9 passing to 10 with nothing regressed.

### SEC-02 — IDOR: any user can read, update or delete another user's todo

- **Severity:** Critical
- **Location:** `backend/app/api/v1/todos.py:88-102` (`get_todo`), `:105-134`
  (`update_existing_todo`), `:137-153` (`delete_existing_todo`);
  `backend/app/services/todo_service.py:42-44` (`get_todo_by_id`)
- **Status:** `Fixed` in `b6089e4`
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
- **Reproduction (executed):** Three regression tests in `tests/test_todos.py`
  have user A create a todo and user B attempt to read, update and delete it
  over HTTP. All three failed before the fix, returning `200`, `200` and `204`
  where `404` was expected. The `204` is the one that matters most: user B's
  request did not merely expose another user's record, it destroyed it.
- **Fix applied:** `get_todo_by_id()` now takes a required `user_id` and filters
  on it inside the query, and all three call sites pass `current_user.id`. The
  parameter is required rather than optional so that a missed call site fails
  loudly instead of silently reverting to the old behaviour. Non-owners receive
  `404` rather than `403`, so the existence of another user's record is not
  disclosed.
- **Verification:** All three tests pass afterwards. The pre-existing tests that
  operate on a user's own todos stayed green, so the legitimate path is not
  blocked. Suite: 10 to 13 passing.

### SEC-03 — Global cache key leaks todos across users

- **Severity:** Critical
- **Location:** `backend/app/api/v1/todos.py:37`
- **Status:** `Fixed` in `6a9ce9f`
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
- **Reproduction (executed):** Reproducing this first required repairing the
  test setup. `override_get_redis` returned a `MagicMock` whose `get()` always
  answered `None`, and FastAPI rebuilt it on every request, so nothing written
  by one request could ever be read by the next. Run against that mock, both new
  tests **passed** while the Critical defect was present — a green suite that
  proved nothing. Replacing it with a dict-backed `FakeRedis` that keeps its
  store across requests made the defect visible at once: user B's list came back
  as `['Belongs to A']`, and page 2 of a paginated read returned 2 items where
  it holds 1.
- **Fix applied:** The key is built from the caller and the query,
  `todos:list:{user_id}:{page}:{size}`. One line of production code.
- **Verification:** Both tests pass afterwards; suite 13 to 15. The older tests
  stayed green even though they now run against a cache that actually functions,
  which is closer to production than the conditions they were written under.
- **Additional evidence (Tier 2):** the Playwright Cross-User Data Isolation
  test (`9a22c2f`) exercises this end to end, against real Redis rather than the
  test fake. User A reads the list — populating A's cache entry — before user
  B, in a separate browser session, reads theirs. Under the old shared key B
  would have been served A's cached list; B saw only its own empty list. The
  status is unchanged: this corroborates a fix, it does not make one.

---

## High

### SEC-04 — No cache invalidation on mutation

- **Severity:** High
- **Location:** `backend/app/api/v1/todos.py:77-85`, `:105-134`, `:137-153`
- **Status:** `Fixed` in `9957174`
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
- **Reproduction (executed):** Five regression tests were added against the
  stateful `FakeRedis`. Four failed before the fix: a created todo stayed absent
  from the list, an edited title kept its old value, a deleted todo kept being
  returned, and a second cached page kept its stale item count. The fifth guards
  against over-broad invalidation and passed before the fix, because nothing was
  being invalidated at all; its teeth were checked by temporarily widening the
  pattern to `todos:list:*`, which made it fail as intended, after which the
  correct pattern was restored.
- **Fix applied:** `RedisClient` gained `delete_pattern`, which walks the
  keyspace with `SCAN MATCH` through `scan_iter` rather than `KEYS`, so a large
  keyspace is never scanned under one blocking command. Create, update and
  delete all call a shared `invalidate_todo_list_cache` helper using the pattern
  `todos:list:{user_id}:*` — narrow enough to spare other users' entries, wide
  enough to cover every page and size the caller holds. `create_new_todo` also
  had to be given the `redis` dependency, which it never had.
- **Verification:** 5 of 5 regression tests pass; the full backend suite reports
  20 passing. Checked against real Redis as well as the fake, which matters
  because the fake matches keys with `fnmatch` and never exercises `scan_iter`:
  with two cached entries for one user and one for another, a create removed
  both of the caller's keys and left the other user's in place, and the caller's
  next read showed the new todo.

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
- **Status:** `Fixed` in `ff7ce08`
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
- **Reproduction (executed):** Demonstrated in a real browser against the full
  stack, the frontend having no test runner. The API was first confirmed by
  `curl` to isolate the two users correctly, so any leak visible in the UI had
  to be client-side. User A logged in, logged out, and user B logged in on the
  same tab: the dashboard showed A's email in the header and A's private todo in
  the list, to B.
- **Scope correction:** the original analysis overstated the reach. The `401`
  interceptor uses `window.location.href`, a full page reload that destroys the
  heap and the cache with it, so that path never leaked. Only the explicit
  logout button did.
- **Fix applied:** `queryClient.clear()` on both the success and the error path
  of logout. The interceptor was left alone, since its reload already clears the
  cache.
- **Verification:** the same scenario re-run from a clean session showed B their
  own email and their own todo. `tsc -b && vite build` exits 0.
- **Known side effect:** clearing while the dashboard is still mounted leaves its
  `useTodos` observer without data, so React Query refetches immediately and the
  request comes back `403`, the token having already been removed. It is a failed
  background request: it changes nothing that is displayed and it is not a leak.
  Comparing console logs from before and after confirms it appeared only with
  this change. Deferring the clear with `setTimeout(..., 0)` was tried and did
  **not** suppress it, so that workaround was reverted rather than kept as
  unexplained complexity. The root cause is that the todo query is not gated on
  authentication, which is a separate defect and was left alone here. The cache
  leak itself was reproduced before the fix and is absent after it.

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
- **Status:** `Reproduced` — observed at runtime in Tier 2, not fixed
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
- **Reproduction (executed):** `docs/TEST_PLAN.md` TC-07. A freshly issued
  refresh token was presented as the bearer credential to `GET /auth/me`
  against the running stack. The endpoint answered `200` and returned the user,
  where `401` was expected. A seven-day refresh token therefore works as a
  credential on every protected endpoint.
- **Proposed Fix:** After decoding, reject the request when
  `payload.get("type") != "access"`. Not applied.

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
- **Status:** `Reproduced` — observed at runtime in Tier 2, not fixed
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
- **Reproduction (executed):** `docs/TEST_PLAN.md` TC-02 and TC-03, against the
  running stack. A registered address with a wrong password returned
  `401, detail: "Incorrect password"`; an unregistered address returned
  `404, detail: "User with this email not found"`. Status and message both
  differ, exactly as the source indicated, so whether an address is registered
  can be read off the response.
- **Proposed Fix:** Collapse both branches into a single
  `401 "Invalid email or password"`. `authenticate_user()` already exists at
  `backend/app/services/auth_service.py:33-39` and is currently called nowhere.
  Not applied.

### SEC-12 — Logout is a no-op and refresh does not re-check the user

- **Severity:** Medium
- **Location:** `backend/app/api/v1/auth.py:102-107` (`logout`), `:84-99`
  (`refresh_token`)
- **Status:** `Reproduced` for the logout half; the refresh half is still
  `Open — static`. Not fixed.
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
- **Reproduction (executed, logout half):** `docs/TEST_PLAN.md` TC-08 and TC-09.
  `POST /auth/logout` returned `200`, and the same access token was then reused
  on `GET /auth/me`, which also returned `200`. Logging out revoked nothing.
- **Not reproduced:** the second gap — `refresh` issuing tokens without
  confirming the user still exists — was not exercised. It would need a user
  deleted between issuing and presenting a refresh token, and no test or plan
  case does that. That half remains a static finding.
- **Correction to the reason above:** it says the token stays valid
  "indefinitely, given SEC-01". SEC-01 has since been fixed, so expiry is now
  enforced. A token reused after logout stays valid until its natural expiry —
  30 minutes for an access token, 7 days for a refresh token — not forever. The
  defect is real; its reach is bounded.
- **Proposed Fix:** On logout, record the refresh token's `jti` in a Redis denylist
  with a TTL matching the token's remaining lifetime. In `refresh`, load the user
  from the database and reject denylisted identifiers before issuing new tokens.
  Not applied.

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
- **Status:** `Reproduced` — observed at runtime, deliberately not fixed
- **Reason:** `passlib` 1.7.4 reads `bcrypt.__about__.__version__`, an attribute
  removed in `bcrypt` 4.1. The combination commonly emits a version-detection
  warning at import time. This is usually harmless, but in some environments it
  interferes with hashing.
- **Evidence (executed):** the warning appeared in the captured log of the first
  test run inside the container, exactly as the version pins predicted:
  ```
  WARNING  passlib.handlers.bcrypt: (trapped) error reading bcrypt version
  AttributeError: module 'bcrypt' has no attribute '__about__'
  ```
- **Actual impact, stated precisely:** `passlib` traps this exception — the log
  line says so — and proceeds without the version information. Hashing continues
  to work: registration, login and every password-dependent test pass, and the
  backend serves traffic normally. **Nothing observed indicates that password
  hashing is broken or weakened, and no such claim is made here.** What is
  established is a noisy warning on worker start and a dependency pairing that
  is out of contract, which could break on a future release of either package.
- **Status rationale:** promoted from suspected to reproduced because the
  behaviour was observed, not because the impact turned out to be larger. It
  remains Low severity and was deliberately left unfixed during Tier 1.
- **Proposed Fix:** pin `bcrypt<4.1`, or drop `passlib` and use the `bcrypt`
  library directly. Neither is urgent.

---

## Remediation order

Seven findings were proposed for Tier 1, against a requirement of at least five
fixes covering at least two backend and one frontend defect. Five were carried
out; SEC-05 and SEC-06 were not reached before Tier 1 closed.

| Order | ID | Rationale | Outcome |
|---|---|---|---|
| 1 | SEC-02 | Most severe defect; covers the cross-user authorization scenario in both Tier 2A and the Tier 2B E2E isolation test. | `Fixed` (`b6089e4`) |
| 2 | SEC-01 | Critical, one-line change, unambiguous evidence; covers the expired-token scenario. | `Fixed` (`1e6984c`) |
| 3 | SEC-03 | Critical; leaks data on the ordinary request path; covers the cache scenario. | `Fixed` (`6a9ce9f`) |
| 4 | SEC-06 | Silent data loss; covers "updating title does not erase description". | Not done |
| 5 | SEC-05 | Covers "updating completed from true back to false"; one-line change, demonstrable in the UI. | Not done |
| 6 | SEC-07 | Strongest frontend finding; satisfies the frontend requirement and is what the E2E isolation test will surface. | `Fixed` (`ff7ce08`) |
| 7 | SEC-04 | Belongs with SEC-03; completes the cache invalidation scenario. | `Fixed` (`9957174`) |

Two findings are reported but handled with care. SEC-08 requires
`git rm --cached` and key rotation and should be isolated in its own commit.
SEC-12 needs a Redis denylist to fix properly, which is a wider change than
Tier 1 warrants; it may be better recorded under trade-offs.

### State at the close of Tier 1

Five fixes: three backend, one frontend, one spanning the cache layer, covering
all three Critical findings. The backend suite grew from 9 tests to 20, all
passing. Every fix followed the same sequence — a test that failed first, then
the change, then the test passing and the suite re-run.

Eighteen findings remain open. SEC-05 and SEC-06 are the two High-severity
logic defects that were queued and not reached; both live in
`update_existing_todo` and are small. SEC-23 is reproduced but unfixed. The
rest stand as read, not demonstrated.

One observation was made during Tier 1 that is not a finding in this document:
on a cold `docker compose up`, the backend exits 1 with
`ConnectionRefusedError` against Postgres, because `depends_on` does not wait
for the database to become ready. It was worked around by restarting the
container, not fixed, and it belongs to the Docker work in Tier 3B.

### State at the close of Tier 2

No finding was fixed in Tier 2. What changed is how much is demonstrated: three
authentication findings — SEC-09, SEC-11 and SEC-12 — were reproduced by the
manual test plan and now carry recorded runtime output. The remaining counts are
13 static, 1 suspected, 4 reproduced and 5 fixed.

---

## Test evidence

Recorded as run. Counts are from the suites executed at commit `9a22c2f`, not
estimated.

### Backend — pytest (Tier 2A)

`20 passed`, run inside the backend container:

```bash
docker compose run --rm --no-deps -v "$PWD/backend:/app" backend pytest tests/ -v
```

The assessment asks for at least three of five scenarios. Three are covered:

| Scenario | Tests |
|---|---|
| Expired or tampered JWT rejected | `test_expired_access_token_is_rejected` |
| User A cannot read, update or delete user B's todos | `test_user_cannot_read_another_users_todo`, `…_update_…`, `…_delete_…` |
| Mutation removes stale Redis cache | five tests in `test_todos.py`, from `test_creating_todo_invalidates_cached_list` to `test_mutation_does_not_invalidate_other_users_cache` |

The other two scenarios are **not covered**. Toggling `completed` back to
`false` and preserving `description` on a partial update both depend on
SEC-05 and SEC-06, which are unfixed, so a test for either would fail today.

The suite runs against SQLite and an in-memory `FakeRedis` defined in
`tests/conftest.py`; it does not exercise Postgres or a real Redis server.

### End-to-end — Playwright (Tier 2B)

`3 passed`, against the running Docker stack:

```bash
docker compose up -d
cd e2e && npm install && npx playwright install chromium
npx playwright test            # headless
npx playwright test --headed   # headed
```

| Test | Commit | What it establishes |
|---|---|---|
| `smoke.spec.ts` | `2043042` | The suite reaches a running frontend and the app has rendered |
| `full-user-journey.spec.ts` | `0653791` | Register, create a todo, complete it, verify it — including after a reload from the server — and log out, with the protected route confirmed to redirect afterwards |
| `cross-user-isolation.spec.ts` | `9a22c2f` | A todo created by user A is not visible to user B in a separate session |

How they were verified:

- All three pass headless and headed.
- Full User Journey passed five times in parallel under `--repeat-each=5`.
  The whole suite passed nine runs under `--repeat-each=3`.
- Cross-User Isolation opens two independent browser contexts from the same
  `browser` fixture, so each user has separate `localStorage` and therefore a
  separate session. Both users register through the UI.
- No API call is made anywhere in the three tests, and no token, cookie or
  storage value is injected. Every scenario runs through the browser.
- Credentials are generated per run and never logged; no test depends on a
  pre-existing account.
- The negative assertion in Cross-User Isolation was checked for teeth by
  temporarily pointing it at user A's page, where the todo is present. It
  failed with `Expected: hidden, Received: visible`, and was restored.
- The smoke test was pointed at a port with nothing listening and failed with
  `ERR_CONNECTION_REFUSED`, confirming it depends on the stack rather than
  passing vacuously.

Scope limits, stated so they are not inferred:

- There is no CI. Every run above was executed by hand against a local stack.
- The frontend has no unit-test runner. Playwright is its only automated
  coverage, and it drives the whole stack rather than components in isolation.
- No coverage measurement exists for either suite, and none is claimed.
- The tests start no stack of their own and leave their data behind; each run
  adds users and todos to the database.

### Manual — test plan (Tier 2C)

`docs/TEST_PLAN.md`: 17 cases, 11 authentication and 6 authorization. Fifteen
were executed — thirteen as HTTP calls against the running stack, one as a
manual browser session, and one covered by the automated backend suite — and
two were written but not run. Of the executed cases, eleven pass and four
fail. The four failures are SEC-09, SEC-11 (two cases) and SEC-12, all
recorded above as reproduced.

---

## Change log

| Date | Change |
|---|---|
| 2026-09-19 | Initial audit. 23 findings recorded from static analysis; none reproduced at runtime. |
| 2026-09-19 | Tier 1 close. SEC-01 (`1e6984c`), SEC-02 (`b6089e4`), SEC-03 (`6a9ce9f`), SEC-07 (`ff7ce08`) and SEC-04 (`9957174`) marked `Fixed`, each with a regression test that failed before the change and passed after it. SEC-23 promoted from `Open — suspected` to `Reproduced` on observed runtime output, with its impact stated precisely and left unfixed. SEC-07 annotated with a known side effect and with a correction narrowing its original scope. Counts updated: 5 fixed, 1 reproduced, 1 suspected, 16 static. |
| 2026-09-19 | Tier 2 close. No finding fixed. SEC-09, SEC-11 and SEC-12 promoted from `Open — static` to `Reproduced` on runtime output from `docs/TEST_PLAN.md` (TC-07; TC-02 and TC-03; TC-08 and TC-09). SEC-12 is reproduced for its logout half only; its refresh half was not exercised and stays static. SEC-12's reason corrected: since SEC-01 was fixed, a token survives logout until natural expiry, not indefinitely. SEC-03 given additional end-to-end evidence from the Playwright isolation test, status unchanged. Test evidence section added, recording 20 backend tests and 3 Playwright tests as run at `9a22c2f`. Counts updated: 5 fixed, 4 reproduced, 1 suspected, 13 static. |
