# Manual Test Plan: Authentication & Authorization

**Branch:** `assessment/thai-van-lam`
**Executed against:** commit `23db3f6`
**Date:** 2026-09-19

## 1. Scope & Objective

- **Objective:** verify the authentication and authorization paths behave as a
  user of the system should be able to assume, and check for regressions in the
  defects fixed during Tier 1.
- **In scope:** Authentication (login, token handling, session termination) and
  Authorization (one user's ability to reach another user's data, directly and
  through the cache).
- **Out of scope:** Todo CRUD happy paths beyond what authorization requires,
  pagination, validation of todo fields, and the Docker and database work that
  belongs to Tier 3. These are exercised by the automated backend suite.

### How to read the results

Every row states what was expected and what actually happened. The two are kept
apart on purpose: several rows record a **Fail**, because the system really does
behave that way today, and those failures map to findings in
`docs/SECURITY_AUDIT.md` that were reported but not fixed during Tier 1.

| Status | Meaning |
|---|---|
| `Pass` | Executed. Actual result matched the expected result. |
| `Fail` | Executed. Actual result differed; the defect is named in the row. |
| `Not executed` | Written up but not run. The Actual Result column says so; nothing is inferred there. |

Execution method is given per row: `API` for a direct HTTP call against the
running stack, `Browser` for a manual run in a real browser, `Auto` where an
automated test in `backend/tests/` covers the same behaviour.

## 2. Test Environment & Prerequisites

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3000`
- Stack started with `docker compose up -d`. The backend must be started after
  Postgres is accepting connections; on a cold boot it exits 1 (see §4).
- Test accounts are disposable and created by the test steps themselves, so the
  plan can be re-run from an empty database. The API run used
  `tc-alice-<timestamp>@example.com` and `tc-bob-<timestamp>@example.com`; the
  browser run used `sec07-alice@example.com` and `sec07-bob@example.com`. Any
  password accepted by the backend works — it currently enforces no minimum
  (TC-11).
- Referred to below as **User A** and **User B**.

## 3. Test Cases Matrix

### 3.1 Authentication

| TC ID | Module | Test Scenario | Preconditions | Test Steps | Expected Result | Actual Result | Priority / Severity | Status |
|---|---|---|---|---|---|---|---|---|
| TC-01 | Auth | Login succeeds with the correct password | User A registered | 1. `POST /api/v1/auth/login` with the correct email and password | `200` with an access token and a refresh token | `200`, both tokens present | High / Blocker | `Pass` (API) |
| TC-02 | Auth | Login fails with the wrong password | User A registered | 1. `POST /auth/login` with the correct email and a wrong password | Rejected with a message that does not say which factor was wrong | `401`, `detail: "Incorrect password"` — states that the password specifically was wrong | Medium / Security | `Fail` — SEC-11 |
| TC-03 | Auth | Login with an unregistered email is indistinguishable from a wrong password | No account for the address | 1. `POST /auth/login` with an unknown email | Same status and message as TC-02, so registration cannot be probed | `404`, `detail: "User with this email not found"` — a different status *and* message from TC-02, which confirms whether an address is registered | Medium / Security | `Fail` — SEC-11 |
| TC-04 | Auth | A protected endpoint refuses an unauthenticated request | None | 1. `GET /auth/me` with no `Authorization` header | Request refused | `403`, `detail: "Not authenticated"`. Access is correctly denied; `401` would be the conventional status here, and `403` is FastAPI's `HTTPBearer` default rather than application logic | Low / Minor | `Pass` (API), with the note above |
| TC-05 | Auth | A token with a tampered signature is rejected | User A registered | 1. Take a valid token, alter its final characters<br>2. `GET /auth/me` with it | `401` | `401`, `detail: "Invalid authentication token"` | High / Critical | `Pass` (API) |
| TC-06 | Auth | An expired token is rejected — regression for SEC-01 | User A registered | 1. Sign a well-formed token for User A with `exp` one hour in the past<br>2. `GET /auth/me` with it | `401` | `401`, `detail: "Invalid authentication token"` | High / Critical | `Pass` (API, `Auto`) |
| TC-07 | Auth | A refresh token cannot be used as an access token | User A logged in | 1. `GET /auth/me` presenting the refresh token as the bearer credential | `401` — a refresh token is only for obtaining access tokens | `200`, the endpoint returned the user. A seven-day refresh token works as a credential on every protected endpoint | High / Major | `Fail` — SEC-09 |
| TC-08 | Auth | Logout returns successfully | User A logged in | 1. `POST /auth/logout` with a valid token | `200` | `200` | Low / Minor | `Pass` (API, `Auto`) |
| TC-09 | Auth | A token stops working after logout | TC-08 completed | 1. Reuse the same access token on `GET /auth/me` after logging out | `401` — the session was ended | `200`, the token still works. Logout revokes nothing; a `jti` claim is generated but never stored or checked | Medium / Major | `Fail` — SEC-12 |
| TC-10 | Auth | Registering an already-registered email is rejected | User A registered | 1. Two concurrent `POST /auth/register` calls with the same address | One `201`, the other `400` | Not executed. Requires driving concurrent requests; `users.email` carries no unique constraint, so SEC-10 predicts both can succeed | Medium / Major | `Not executed` |
| TC-11 | Auth | A password below the minimum length is rejected | None | 1. `POST /auth/register` with a one-character password | `422` | Not executed as a discrete case. `UserCreate.password` is an unconstrained `str`, so SEC-20 predicts `201`. The frontend enforces six characters, which a direct API call bypasses | Low / Minor | `Not executed` |

### 3.2 Authorization

| TC ID | Module | Test Scenario | Preconditions | Test Steps | Expected Result | Actual Result | Priority / Severity | Status |
|---|---|---|---|---|---|---|---|---|
| TC-12 | Todo Security | User B cannot read User A's todo | A and B registered; A owns todo `X` | 1. `GET /todos/X` with B's token | `404`, so the existence of A's record is not disclosed | `404`, `detail: "Todo not found"` | High / Critical | `Pass` (API, `Auto`) |
| TC-13 | Todo Security | User B cannot update User A's todo | As TC-12 | 1. `PUT /todos/X` with B's token and a new title<br>2. Re-read the todo as A | `404`, and A's data unchanged | `404`. Re-read as A returned the original title | High / Critical | `Pass` (API, `Auto`) |
| TC-14 | Todo Security | User B cannot delete User A's todo | As TC-12 | 1. `DELETE /todos/X` with B's token<br>2. Re-read the todo as A | `404`, and the todo still exists | `404`. Re-read as A returned `200` with the todo intact | High / Critical | `Pass` (API, `Auto`) |
| TC-15 | Cache | One user's list is not served from another user's cached entry | A owns a todo; B owns none | 1. `GET /todos` as A, which populates the cache<br>2. `GET /todos` as B within the 300s TTL | B sees only B's own todos | A saw `['A private']`; B saw `[]` | High / Critical | `Pass` (API, `Auto`) |
| TC-16 | Session | After logout, the next user in the same browser tab sees only their own data | A logged in on the dashboard | 1. Log in as A and load the todo list<br>2. Click Logout<br>3. Log in as B in the same tab without reloading | B's own email in the header and B's own todos | B's own email and B's own todo. Before the SEC-07 fix this same run showed A's email and A's private todo to B | High / Critical | `Pass` (Browser) |
| TC-17 | Cache | A mutation clears the cached list so the next read is current | A has a cached list | 1. `GET /todos` as A<br>2. Create, update, then delete a todo<br>3. `GET /todos` again after each | Each read reflects the change immediately | Covered by five automated tests; every page and size cached for that user is cleared, and other users' entries are left in place | Medium / Major | `Pass` (`Auto`) |

## 4. Defect Tracking & Known Limitations

### Failures recorded above

| TC | Finding | Severity | Note |
|---|---|---|---|
| TC-02, TC-03 | SEC-11 — user enumeration | Medium | Login answers `404` for an unknown address and `401` for a wrong password, with distinct messages. This plan is the first runtime confirmation; the audit had it as static analysis only. |
| TC-07 | SEC-09 — token type not validated | High | `get_current_user` never checks `payload["type"]`, while `/auth/refresh` does. |
| TC-09 | SEC-12 — logout is a no-op | Medium | Fixing this properly needs a Redis denylist keyed by `jti`, which is wider than Tier 1 warranted. |

None of these were fixed during Tier 1. They are reported in
`docs/SECURITY_AUDIT.md` with locations and proposed fixes.

### Coverage this plan does not claim

- TC-10 and TC-11 were written but **not run**. Their Actual Result columns say
  what the source predicts and label it as a prediction.
- TC-17 is marked `Auto`: it is covered by the automated suite, not by a manual
  run. It is listed because the template includes a cache case and because cache
  staleness is how an authorization boundary can be bypassed indirectly.
- Only the browser row (TC-16) exercises the frontend. There is no frontend test
  runner in the repository, so every other row is an API-level check. Browser
  coverage of these paths is Tier 2B's job.

### Environment limitation

On a cold `docker compose up`, the backend container exits 1 with
`ConnectionRefusedError` against Postgres, because `depends_on` does not wait
for the database to be ready. The workaround while running this plan was to
start the backend again once Postgres was accepting connections. It is not a
defect in the application and belongs to the Docker work in Tier 3B.

### Re-running this plan

The API rows were executed by a script that registers two throwaway accounts and
walks the cases in order, so the plan can be repeated against a fresh database
without manual setup. TC-16 is a manual browser run: log in as one user, log
out, log in as another in the same tab, and read the header and the list.
