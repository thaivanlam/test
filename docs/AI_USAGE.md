# AI Usage Disclosure

**Assessment:** Fabbi Developer Assessment — Full-Stack Engineering & Quality Assurance
**Branch:** `assessment/thai-van-lam`
**Author:** Thái Văn Lâm
**Last updated:** 2026-09-20

The assessment brief requires that any use of AI coding assistants be
disclosed, together with prompt logs or configuration. This document is that
disclosure. It is intended to be read alongside the pull request.

---

## Tools Used

| Tool | Role in this assessment |
|---|---|
| **Claude Code** (Opus 5, VS Code extension) | Primary assistant for the work recorded in this repository: reading the codebase, the Tier 1 security and correctness audit, drafting documentation, and running read-only verification commands. |
| **ChatGPT** | Used as a secondary assistant for general reasoning, background questions and sanity-checking approaches. It was not connected to this repository and did not write files in it. |

### What AI was used for

- Code review and reading an unfamiliar codebase quickly.
- Security and bug auditing (Tier 1).
- Test design and planning.
- Debugging and working through failure hypotheses.
- Documentation drafting.
- General reasoning about trade-offs and prioritisation.

### What AI is not

AI output is **not treated as evidence**. Model reasoning is a hypothesis to be
checked, not a result. Specifically, the following are only accepted when
produced by an actually executed command, with its output recorded:

- test results (pass or fail),
- `git status`, `git diff` and any other repository state,
- build and lint results,
- runtime behaviour of the application,
- benchmark and query timing figures.

Where such evidence does not exist yet, the documentation says so explicitly
rather than implying a result. `docs/SECURITY_AUDIT.md` followed this rule from
the start: when it was first written every one of its findings was recorded as
static analysis and none as reproduced, because the container stack was
unavailable at the time. Statuses have moved since, each on recorded output;
the document's change log says when and on what evidence.

---

## AI Usage Principles

1. **Every AI suggestion is reviewed before it is applied.** Nothing is accepted
   because the model proposed it. Diffs are read before staging, and changes are
   staged explicitly by path rather than with a blanket `git add .`.

2. **Static analysis is never presented as runtime reproduction.** Reading code
   and concluding that a defect exists is a different claim from observing the
   defect. The audit separates the two, and its "Reproduction" fields are
   labelled as not yet executed.

3. **No test, build or check is claimed to pass unless it was actually run.** If
   a tool is unavailable, that is stated with the error that proves it, and the
   corresponding claim is withheld rather than estimated. Numbers are never
   guessed — this applies particularly to the Tier 3C benchmark table, which
   must come from real `EXPLAIN ANALYZE` output.

4. **The human author remains responsible for the final changes and their
   verification.** Responsibility for what is committed does not transfer to the
   tool that drafted it.

These principles are also written into `CLAUDE.md` at the repository root, so
they constrain the assistant during the work rather than only describing it
afterwards.

---

## Prompt Log

The entries below are **workflow-level summaries, not verbatim transcripts**.
The original instructions were given in Vietnamese and are summarised here in
English. They describe what was actually asked and what was actually produced;
no entry has been invented or embellished.

| # | Date | Stage | Instruction given (summarised) | AI output | Verification performed |
|---|---|---|---|---|---|
| 1 | 2026-09-18 | Planning | Review the assessment requirements and propose an effective prompting strategy for completing it. | A tier-by-tier plan: audit before fixing, one concern per session, insist on real command output. Identified that `frontend/README.md` is the unmodified Vite template and that the real requirements live in the root `README.md`. | Read `README.md`, `GUIDE.md` and the repository file listing directly. |
| 2 | 2026-09-19 | Setup | Read the full codebase and configuration. Confirm the requirements, summarise the stack, determine how to run the app and tests, check the commit convention and the current git state. Propose the contents of `CLAUDE.md`. Do not modify anything. | Stack summary, run/test commands, and a proposed `CLAUDE.md`. Flagged two repository traps: `.gitignore` excluded all of `docs/`, and `.env` is tracked. | `docker --version`, `docker ps`, `python --version`, `node --version`, `git branch -a`, `git status`, `git log`, `git remote -v`, `py -0p`, plus reading every source file. Docker daemon found not running; `pytest`, `jose` and `node_modules` found absent. |
| 3 | 2026-09-19 | Setup | Create `CLAUDE.md`, remove the blanket `docs/` ignore rule, create branch `assessment/thai-van-lam`. Leave `.env` alone. Do not commit. | Branch created; `CLAUDE.md` written; one line removed from `.gitignore`. | `git status`, `git diff`, `git check-ignore` on each documentation path to confirm `docs/` became committable while `docs/ANSWER_KEY.md` stayed ignored. `git ls-files --error-unmatch .env` confirmed `.env` untouched and still tracked. |
| 4 | 2026-09-19 | Setup | Correct the "known traps" section of `CLAUDE.md` so it reflects the state after the `.gitignore` change. | Section rewritten. | `git diff --check`, `git status --porcelain` — confirmed exactly two changed paths. |
| 5 | 2026-09-19 | Commit | Stage only `.gitignore` and `CLAUDE.md`, commit as `chore(docs): prepare assessment documentation`, push the branch. | Commit created and pushed. **The assistant's first commit command used PowerShell here-string syntax inside a Bash shell, which put a stray `@` on the first line of the message and pushed the subject to line two — breaking the Conventional Commits format.** It was caught by inspecting the raw message, and corrected with `git commit --amend` before the commit was pushed. | `git diff --cached --name-status` before committing; `git log -1 --format=%B \| cat -A` to inspect the raw message; `git ls-remote` after pushing to confirm the remote SHA matched local `HEAD`. |
| 6 | 2026-09-19 | Tier 1 audit | Audit `backend/` and `frontend/` for authentication, authorization, partial-update, cache, frontend state and secret-exposure defects. Audit only — change nothing. Mark unproven issues as suspected. | 23 findings: 3 Critical, 6 High, 10 Medium, 4 Low; 21 confirmed by source analysis, 2 marked suspected. A remediation order of seven findings was proposed. | Targeted `grep` over each suspected code path to obtain exact line numbers and quote the relevant source. `git ls-files --error-unmatch .env` for the secret finding. Attempts to import `jose` and `jwt` failed, and were reported as a limitation rather than worked around. |
| 7 | 2026-09-19 | Documentation | Record all 23 findings in `docs/SECURITY_AUDIT.md`, with statuses that reflect the evidence actually held. Include a methodology section explaining the static-analysis limitation. Include no secrets. | `docs/SECURITY_AUDIT.md`, 691 lines. Four status values defined; `Reproduced` deliberately left with a count of zero. | `git diff --check`; `git status --porcelain -uall`; a `grep` sweep for the signing key value, the database password, the demo password and any `eyJ`-prefixed token string — all returned zero matches. |
| 8 | 2026-09-19 | Commit | Stage only `docs/SECURITY_AUDIT.md` and commit as `docs(security): add tier 1 audit findings`, then push and verify. | Commit `e54235b` created and pushed. | `git diff --cached --name-status`; raw message inspected with `cat -A`; `git ls-remote` confirmed the remote SHA matched local `HEAD`; `git ls-tree` confirmed the file exists in the remote tree. |
| 9 | 2026-09-19 | Documentation | Create this disclosure document. | This file. | See the verification section of the pull request. |
| 10 | 2026-09-19 | Tier 1 fix — SEC-01 | Fix the disabled JWT expiry check. Reproduce before fixing; smallest possible change. | A regression test signing a correctly formed but expired token for a user that really exists, then a one-line production change removing `options={"verify_exp": False}`. | Docker was started for this step, so tests could run at last. Test failed first on `assert 200 == 401`, passed after. Full suite 9 to 10 passing. Diff and changed-file list checked before staging. |
| 11 | 2026-09-19 | Tier 1 fix — SEC-02 | Fix the todo ownership/IDOR defect. Prove cross-user read, update and delete first. | Three regression tests over HTTP; `get_todo_by_id` given a required `user_id` and all three call sites updated. | All three failed first, returning `200`, `200` and `204` — the delete really removed another user's todo. All passed after. Suite 10 to 13. `grep` confirmed no call site was left un-scoped. |
| 12 | 2026-09-19 | Tier 1 fix — SEC-03 | Fix the shared todo-list cache key. Reproduce with real data, not by inspecting key names. | Discovered that the existing Redis mock could not express the defect: `get()` always returned `None` and the mock was rebuilt per request. Replaced it with a stateful dict-backed `FakeRedis`, then scoped the key by user, page and size. | Run against the old mock the new tests **passed while the Critical defect was present** — evidence that the mock was hiding it, recorded rather than glossed over. Against the stateful fake they failed, showing user B receiving A's todo; they passed after the fix. Suite 13 to 15. |
| 13 | 2026-09-19 | Tier 1 fix — SEC-07 | Fix the frontend logout cache leak. Report the verification options before building any test infrastructure. | Reported that the frontend has no test runner at all, and proposed driving a real browser rather than introducing Vitest. On approval: full stack brought up, scenario driven in a browser, then `queryClient.clear()` added to both logout paths. | The API was checked by `curl` first, so the leak could be attributed to the client. Before the fix the browser showed A's email and A's private todo to B; after, B's own. `tsc -b && vite build` exits 0. **No automated frontend test exists**; this was manual browser verification. |
| 14 | 2026-09-19 | Tier 1 fix — SEC-04 | Fix the missing cache invalidation. Cover multiple pages and confirm other users keep their cache. | `RedisClient.delete_pattern` using `SCAN MATCH` via `scan_iter` rather than blocking `KEYS`, and a shared invalidation helper called from create, update and delete. | Four of five tests failed before the fix and all five passed after; full suite 20 passing. The fifth test passes either way, so its teeth were checked by temporarily widening the pattern until it failed, then reverting. Also verified against real Redis, since the fake matches keys with `fnmatch` and never exercises `scan_iter`. |
| 15 | 2026-09-19 | Documentation | Close Tier 1: update the audit statuses and this log to match what was actually done. | Five findings moved to `Fixed` with commit references, SEC-23 promoted to `Reproduced` on observed output, SEC-07 annotated with its side effect and a scope correction. | Statuses cross-checked against `git log` and the recorded test output. The distinction between the original static audit and what has since been demonstrated was preserved rather than flattened. |
| 16 | 2026-09-19 | Tier 2 — inspect | Read the Tier 2 rubric from the root README and map it against the repository. Change nothing. | A rubric-to-evidence table. Tier 2A was already over its threshold of three scenarios, from tests written during Tier 1; the two uncovered scenarios both depend on SEC-05 and SEC-06, which are unfixed. Playwright and the manual test plan did not exist. | Read-only commands only. `git status --short` empty at the end. |
| 17 | 2026-09-19 | Tier 2A — backend tests | No new backend tests were written in Tier 2. The existing suite was re-run to record current evidence. | — | `20 passed` inside the backend container, at commits `9957174` and again at `9a22c2f`. |
| 18 | 2026-09-19 | Tier 2C — manual test plan | Write an authentication and authorization test plan from the template, with actual results drawn from real evidence and executed and unexecuted cases kept apart. | `docs/TEST_PLAN.md`, 17 cases. The template had no Actual Result column, which the rubric requires, so one was added. Rather than fill most rows with "not executed", the assistant restarted the stack — which had stopped between sessions — and ran a read-only probe script that registered throwaway accounts and walked the cases. | Fifteen cases executed and two not. Of the fifteen, thirteen were HTTP calls against the running stack, one a manual browser session, one covered by the automated suite. Four failed, confirming SEC-09, SEC-11 and SEC-12 at runtime for the first time. No password or token appears in the document. |
| 19 | 2026-09-19 | Tier 2B — Playwright setup | Set up Playwright from scratch in `e2e/`, targeting the running stack without a `webServer` block, with one smoke test. | `e2e/package.json`, `playwright.config.ts` and a smoke test using role-based locators. `.gitignore` extended for Playwright's report and results directories. | Passes headless, headed, and through both npm scripts. Pointed at a port with nothing listening, it failed with `ERR_CONNECTION_REFUSED`, confirming the `BASE_URL` override and that the test is not vacuous. That failing run also showed the output directories would have been committed, which is why they were ignored. |
| 20 | 2026-09-19 | Tier 2B — Full User Journey | Register, create a todo, complete it, verify it, log out — through the browser, with meaningful assertions and no API shortcuts. | A test whose assertions were chosen from the components: `toBeChecked` on the Radix checkbox, computed `text-decoration-line` for the visible strike-through, a reload to read completion back from the server rather than the optimistic update, and a protected-route redirect to prove logout ended the session. | Passes headless and headed; five parallel repeats under `--repeat-each=5`. Credentials generated per run and never logged. |
| 21 | 2026-09-19 | Tier 2B — Cross-User Isolation | User A creates a private todo; user B, in a separate session, must not see it. Independent contexts, no injected state, no API calls. | Two contexts from `browser.newContext()`, both users registering through the UI. The test waits for B's list to reach its loaded-empty state before asserting absence, since loading and error states would also hide the todo. | Passes alone, in the full suite, under `--repeat-each=3` (nine runs), and headed. The negative assertion was temporarily pointed at A's page and failed with `Expected: hidden, Received: visible`, then restored. |
| 22 | 2026-09-19 | Documentation | Close Tier 2: update the audit and this log. | SEC-09, SEC-11 and SEC-12 moved to `Reproduced`; a test evidence section added to the audit. | Both suites re-run immediately beforehand, so the counts recorded are from that run: 20 backend, 3 Playwright. Statuses cross-checked mechanically across the audit's index, summary and every finding section. |
| 23 | 2026-09-19 | Tier 3 — inspect | Read the Tier 3 rubric and audit the repository against it. Change nothing. | A plan per task. It flagged that 3A asks for a design spec of a new feature, not documentation of the existing API; and, for 3C, that the seed script skips todos when any exist and that the app's list query has no `ORDER BY`. | Read-only commands only. The human then set the scope: four of five 3B items, no SEC-13 fix inside 3C, deleting todo rows allowed but not the data volume. |
| 24 | 2026-09-19 | Tier 3A — specification | Write `docs/TODO_SHARING_SPEC.md` from the spec template. Design only; implement nothing. | A specification for list-level sharing (the request says "their todo list"). Authorization is checked in the database on every request, before any cache read, so revocation takes effect immediately rather than when a cache entry expires. It also records which cache keys a revocation clears. Commit `a38f1bc`. | Checked section by section against the template and bullet by bullet against the rubric. The assistant had written that a request without a token returns `401`; it was checked against the running app, which returns `403` with no token and `401` with a bad one, and three sentences were corrected before commit. |
| 25 | 2026-09-19 | Tier 3B — healthchecks | Add Postgres and Redis healthchecks and make the backend wait for `service_healthy`. | Healthchecks in `docker-compose.yml`, with `pg_isready -h localhost` to check over TCP rather than the socket used during `initdb`. Commit `8517b7d`. | The failure was reproduced first. On the existing volume the old config booted cleanly three times out of three, so it was retried on a fresh volume in a separate compose project, where it failed with `ConnectionRefusedError`. After the fix, three fresh-volume boots all succeeded. The real data volume was never touched. |
| 26 | 2026-09-19 | Tier 3B — `.dockerignore` | Exclude local artifacts from both build contexts. | Two `.dockerignore` files. `tests/` kept in the backend image and `.env` kept for the frontend build, both on purpose. Commit `7aea7f2`. | `test.db` and `.pytest_cache` confirmed absent from the rebuilt image; image sizes compared, and unchanged. A `--no-cache` rebuild the assistant started stalled for 17 minutes and was stopped; a normal build was enough to prove the change. |
| 27 | 2026-09-19 | Tier 3B — nginx | Serve the frontend from `nginx:alpine` instead of Node. | A new runtime stage and `nginx.conf` with single-page-app fallback on port 3000. Commit `63238f5`. | Image size compared: 218MB to 94.4MB. Status and Content-Type of six paths recorded before the change and matched after. The first nginx config did not match — it added a charset to SVG — and was corrected. |
| 28 | 2026-09-19 | Tier 3B — Redis and secrets | Require a Redis password and stop writing secrets in `docker-compose.yml`. | Redis behind `--requirepass`, bound to `127.0.0.1`; `JWT_SECRET` and `REDIS_PASSWORD` read from the environment with a fail-fast check. Where to keep the Redis value was put to the human, who chose a placeholder in the tracked `.env` so the stack still starts with one command. Commit `ae29359`. | Connections without a password and with a wrong one both refused. The application's own cache write confirmed on the exact key for a fresh user. A key count was rejected as evidence, because Redis keeps `/data` in an anonymous volume that survives recreation. No secret in any image layer. **SEC-08 remains open and was not remediated**: `.env` is still tracked, and this change added to it. |
| 29 | 2026-09-19 | Documentation | Close Tier 3B in the working guide, the test plan and the audit. | Current Compose behaviour documented; the cold-boot limitation kept as observed with its resolution added beside it; a Tier 3B section and a SEC-08 annotation in the audit. Commit `53afd38`. | Only documentation changed; no recorded test result altered; finding counts unchanged; SEC-08 left at `Open — static`. |
| 30 | 2026-09-19 | Documentation | Record Tier 3 in this log. | Entries 23 to 30. | Existing entries left as they were; no secret values. |
| 31 | 2026-09-19 | Tier 3C — database performance | Seed 10,000 users and 1,000,000 todos, measure the per-user queries with `EXPLAIN ANALYZE` before indexing, choose an index from the evidence, add it by migration, measure again. Do not fix SEC-13. | Query plans read and a repeatable benchmark designed: a fixed user chosen by rule, 7 runs per query, every run kept. The rubric's suggested composite `(user_id, created_at DESC)` was **tested rather than assumed**, alongside `(user_id)`. The composite was no faster on the measured queries, 39 MB against 7,096 kB, and slower to write, so `(user_id)` was chosen. Migration `a5ac6aec37c4` uses `CREATE INDEX CONCURRENTLY` inside an autocommit block. Commits `7716d12` and `3731351`. | `EXPLAIN (ANALYZE, BUFFERS)` 7 times per query, before and after; write overhead measured with rolled-back inserts. Upgrade, downgrade and re-upgrade run against the full table. Backend suite (20), Playwright (3) and flake8 passed. Every figure in `docs/DB_PERFORMANCE.md` was checked by script against the raw output. |
| 32 | 2026-09-19 | Documentation | Close Tier 3 in the audit and this log, and check the documents for statements Tier 3 made outdated. | "State after Tier 3" in the audit; entries 31 and 32 here. | The check found two factual errors, both fixed: SEC-13's proposed fix still pointed to a composite index planned for Tier 3C, and `DB_PERFORMANCE.md` understated the index size ratio as 5.5× where the measured sizes give about 5.6×. SEC-08 and SEC-13 left `Open — static`; no benchmark figure changed. |
| 33 | 2026-09-19 | Tier 4 — inspect | Audit the repository against the Tier 4 rubric (tags, filtering, pagination, bulk actions) and propose a plan. Change nothing. | A plan in small commits, with the risks it foresaw: invalidation running before commit, E2E locators breaking once rows gain a second checkbox, SQLite ignoring foreign keys, and the frontend's `size=10000`. The human fixed the open semantics: `status` is `active`/`completed`; date filters use `created_at` as whole UTC days, inclusive; attaching twice is idempotent; bulk update is all-or-nothing with `404`; SEC-05 and SEC-06 first; the Tier 3C index replaced by a composite; Vitest kept minimal. | Read-only commands only. |
| 34 | 2026-09-19 | Tier 4 — SEC-05 | Fix `completed` being impossible to set back to `false`. | Guard changed to `is not None`; regression test `test_completed_can_be_set_back_to_false`. Commit `2e63ab5`. | Suite re-run and passing. The test's failing run against the pre-fix commit was recorded later, in entry 42. |
| 35 | 2026-09-19 | Tier 4 — SEC-06 | Stop a partial update from erasing `description`, while an explicit `null` still clears it. | `model_dump(exclude_unset=True)`; two tests, one for each half of that rule. Commit `f21ec44`. | 23 backend tests passing. The fail-first run was recorded later, in entry 42. |
| 36 | 2026-09-19 | Tier 4 — schema | Add `tags` and `todo_tags` with case-insensitive per-user name uniqueness and cascading deletes, and replace `ix_todos_user_id` with `(user_id, completed, created_at)`, built concurrently. No API. | Two migrations; the new index is built before the old one is dropped. Commit `d982c8c`. | Upgrade, downgrade and upgrade again on the 1,000,000-row development database; no invalid index left. Query plans read with only the composite present, inside a rolled-back transaction: every per-user query still used an index. Uniqueness and both cascades exercised on Postgres, also rolled back. The assistant's first reading of the SQLite schema suggested the expression index was missing; `sqlite_master` and a real duplicate insert showed it was present. |
| 37 | 2026-09-19 | Tier 4 — tag CRUD | `/api/v1/tags` with ownership in the `WHERE` clause, `404` across users, and `409` on a duplicate name decided by the unique index, not by a prior lookup. | Schemas, service, router; 23 tests; `PRAGMA foreign_keys=ON` for the SQLite test engine. Commit `8ce1a27`. | 46 passing. The cascade test was run with the pragma switched off and failed, showing it depends on it. Pre-existing black and flake8 findings in untouched files were reported, not fixed. |
| 38 | 2026-09-19 | Tier 4 — attach/detach | Attach and detach tags, both idempotent, requiring the user to own both the todo and the tag. | `INSERT … ON CONFLICT DO NOTHING` and a scoped `DELETE`; 14 tests. Commit `39998fc`. | 60 passing. SQLite only exercises its own dialect's branch, so the Postgres branch was run once in a rolled-back transaction: link counts 1, 1, 0, 0 across attach, attach, detach, detach. |
| 39 | 2026-09-19 | Tier 4 — filtering | Filters, `page`/`page_size` with a limit of 100, ordering by `created_at DESC, id DESC`, tags in responses loaded with `selectinload`, and cache keys covering every filter. | 36 tests; SEC-13 and SEC-14 fixed along the way. Commit `de419ef`. | 96 passing. The tie-break and the `LIKE` escaping were each removed on purpose and the matching test failed. Query plans on Postgres confirmed the composite index is used. The first plan for the keyword query errored; the assistant traced this to its measurement script compiling SQL with an unconnected dialect, then ran the real service path on Postgres to confirm the application was not affected. It also ran black over a whole directory by mistake and reformatted an unrelated file; that was reverted before the commit. |
| 40 | 2026-09-19 | Tier 4 — bulk status | `PATCH /todos/bulk-status`, all or nothing, in one transaction. | One `SELECT … FOR UPDATE` to check ownership, one `UPDATE`, a row-count check that rolls back on mismatch; 22 tests. The assistant chose a limit of 100 ids and said so. Commit `86ac5a7`. | 118 passing. With the ownership check removed, the row-count rollback alone still kept the failure cases intact; with both removed, five tests failed. The Postgres path, including `FOR UPDATE`, was run once in a rolled-back transaction. |
| 41 | 2026-09-19 | Tier 4 — frontend | Filter bar, pagination, tag management, attach/detach, bulk selection; query keys containing every filter; React Hook Form and Zod for tags; minimal Vitest. | Commit `612c9be`. The optimistic toggle now covers every cached list and rolls back on error (SEC-16); the list is keyed by id (SEC-19). Two existing E2E locators were made exact because each row now has a selection checkbox. | Vitest 31 passing, and one test failed when `date_to` was removed from the key on purpose. Build, type check and lint clean. Images rebuilt, with the route and the bundle checked, before running E2E: 3 passing. A temporary Playwright script, never committed, made 31 checks against the stack; its first runs failed six times, every time because of the script (a request served from cache, and substring-matching locators), not the app. |
| 42 | 2026-09-19 | Tier 4 — E2E and documentation | Turn the important Tier 4 checks into committed Playwright tests and bring the test plan, the audit and this log up to date. | `e2e/tests/tier4-todos.spec.ts` with ten tests; `docs/TEST_PLAN.md` §5; audit statuses for seven findings, with a new status `Fixed — no fail-first test` for fixes without a recorded failing run. | Tier 4 spec 30/30 under `--repeat-each=3`; full Playwright suite 13 passing; backend 118; Vitest 31. The SEC-16 test failed against a dev server built with the rollback removed and passed with it restored. The regression tests for SEC-05, SEC-06 and SEC-13 were run against the commits before each fix and failed; the N+1 in SEC-14 was measured before and after. Audit statuses checked by script across the index, every section and the summary counts. |
| 43 | 2026-09-20 | Final audit | Audit all nine unpushed Tier 4 commits before allowing a push: git state, secrets, migrations, contract, docs, and every suite. Do not push. | The branch checked out clean on every count except one: the full Playwright suite failed a test that had passed the day before. Rather than rerun until green, the assistant traced it to the application — the todo list cache was invalidated before the transaction committed — and reported it with evidence instead of committing a workaround. | Redis and Postgres were read side by side for the failing user: one todo in the database, an empty list in the cache with 188 seconds left. Flake rate counted over 130 test executions: 4 failures. A first hypothesis-driven reproduction attempt failed (0 of 15) and was reported as not reproducing rather than presented as proof. |
| 44 | 2026-09-20 | Fix — SEC-24 | Fix the race with a per-user cache generation, add regression tests, re-run everything, update the documentation. | Cache keys gained a generation segment; mutations now commit and then bump the counter. The assistant flagged that the ordering sketched in the request — bump inside the transaction — would leave the same defect one generation along, and implemented commit-then-bump instead, with the reasoning written into the code. Commits `38b1685` and the documentation commit that follows it. | Seven new tests, all failing against the pre-fix code. The ordering test was checked for teeth by swapping the commit and the bump: it fails and the other six still pass, so it is the only one that distinguishes the two orderings. Backend 125. On the real stack, generation 0 → create → generation 1, with the old entry left unread. Playwright: 10/10, 60/60 under `--repeat-each=6`, full suite 13/13, against a rebuilt image. |

### Notes on this log

- Entries 2 through 22 were carried out in a single Claude Code session, so the
  sequence is recorded from that session's history rather than reconstructed
  from memory.
- Entries 23 to 30 continue that same session. The Playwright suite (3 tests)
  was re-run and passed after each of the four Tier 3B changes. The backend
  suite (20 tests) was re-run and passed after the healthcheck, `.dockerignore`
  and Redis changes; it was not re-run for the nginx change, which touched only
  the frontend image.
- Entries 31 and 32 continue the same session. Three deviations in Tier 3C are
  recorded so they are not mistaken for oversights. The development database
  held 41 todos; they were exported with `pg_dump` to a file outside the
  repository, and then **only the `todos` table** was truncated, because the
  seed script refuses to add todos while any exist. Users were not touched.
  The benchmark itself ran on **exactly 10,000 users and 1,000,000 todos**. The
  Playwright regression run afterwards added 3 users and 2 todos, so the
  database now holds **10,003 and 1,000,002** — a later state, not the one
  measured.
- In Tier 2 the assistant checked its own tests for false passes, not just for
  passing. The smoke test was run against nothing, and the isolation test's key
  assertion was aimed where it had to fail. A passing test was only accepted
  once it had been shown it could fail.
- The Playwright tests use no API shortcuts, inject no auth state, and depend on
  no pre-existing account; each run registers fresh users with generated
  credentials. No secret or token was committed. There is no CI, no frontend
  unit-test runner and no coverage measurement, and none is claimed.
- **A correction.** The commit message of `b705166` and the assistant's report at
  the time both said fourteen test plan cases were executed as HTTP calls. The
  correct figure is thirteen: the fifteenth executed case, TC-17, is covered by
  the automated suite, not by an HTTP call. `docs/TEST_PLAN.md` itself labels
  every row correctly; only the summary sentence was wrong. The commit had
  already been pushed, so it was not rewritten; the correct figure appears in
  entry 18 and in the audit. The error was found while cross-checking counts for
  entry 22.
- Entries 10 to 14 are the five Tier 1 fixes. Each followed the same sequence:
  a test written to reproduce the defect, the failure recorded, the change made,
  the test passing recorded, then the full suite re-run. No fix was committed on
  reasoning alone.
- Two corrections are recorded rather than quietly dropped. In entry 12 the
  assistant found that a mock in the existing test setup made a Critical defect
  invisible, so a green suite was proving nothing. In entry 13 it tried
  `setTimeout(..., 0)` to suppress a side effect it had introduced, measured
  that this did not work, and reverted the attempt instead of leaving behind
  code that looked like a fix.
- A cold-boot failure in `docker compose` was observed during entry 13: the
  backend exits 1 against Postgres because `depends_on` does not wait for the
  database. It was worked around by restarting the container. **It was not
  fixed** — it is an observation belonging to Tier 3B.
- ChatGPT use is disclosed because it occurred, but it is not itemised in this
  table. It was not connected to the repository, produced no files in it, and no
  accurate per-prompt record of it exists. Claiming otherwise would defeat the
  purpose of this document.
- Entry 5 records a mistake made by the assistant. It is included because a
  disclosure that only lists successes is not a useful disclosure. It is also a
  concrete example of why generated output is inspected before it is trusted.
- Entries 33 to 42 are Tier 4, continued in the same way. The human read the
  report of each commit — changed files, test output, trade-offs — and approved
  it before the next step began. Nothing from Tier 4 had been pushed when this
  was written.
- The temporary verification script in entry 41 is **not** counted as automated
  coverage anywhere. It was deleted, never committed, and only selected
  scenarios from it became the committed tests of entry 42.
- In entry 42 the human's list of findings to mark fixed did not include
  SEC-19, but the frontend commit had in fact changed that code. The assistant
  pointed this out and recorded SEC-19 with the weaker status, stating exactly
  what evidence exists, instead of either leaving a fixed defect listed as open
  or claiming more than was shown.
- Four Tier 4 fixes — SEC-14, SEC-16, SEC-17 and SEC-19 — have no committed test
  recorded failing on the unfixed code. Rather than call them `Fixed` under a
  definition they do not meet, the audit gained a separate status for them.
- Docker Desktop was not running when the tag CRUD work began, and the
  assistant started it; later the Compose stack itself was found stopped and
  was brought up again, without touching any volume. The E2E runs and the
  temporary script left their test users, todos and tags in the development
  database.

---

## Verification Responsibility

The division of responsibility for this assessment is as follows.

**The AI assistant proposes.** It reads code, suggests where defects are likely,
drafts documents and tests, and runs commands when asked. Its conclusions are
hypotheses with citations attached, and it is expected to state plainly when it
does not have the evidence for a claim.

**I inspect the output.** Diffs are read before staging. Commit messages are
checked in their raw form. Command results are read rather than assumed —
including when the assistant reports success, as entry 5 above demonstrates.

**I decide what is applied.** Changes are staged by explicit path. Each fix is a
separate commit. Nothing reaches a commit without being reviewed first, and
changes outside the scope of the current task are rejected rather than accepted
because they happened to be suggested.

**Runtime and test evidence outrank AI reasoning.** Where the two disagree, the
executed result wins. A finding that a model is confident about but that no test
demonstrates remains a static finding.

That rule decided what each finding is allowed to claim. Five were promoted to
`Fixed` because a test failed before the change and passed after it. Four are
`Reproduced`: one because its warning was observed in captured output, three
because the manual test plan ran them against the live stack — and none of
those four is called fixed, because none was. The other fourteen still say
`Open — static` or `Open — suspected`, because nothing has been run against
them. The document says which is which rather than presenting twenty-three
equally confident conclusions.

The same rule cut the other way twice. In SEC-03 a passing test was rejected as
evidence once it turned out the mock could not express the defect. In SEC-07 a
proposed workaround was measured, found not to work, and removed — the
measurement outranked the reasoning that produced it.

**Each commit was verified before and after.** Diffs were read before staging,
files were staged by explicit path, raw commit messages were inspected with
`cat -A` after the first one was malformed, and every push was confirmed by
comparing the SHA from `git ls-remote` against local `HEAD` rather than trusting
the push output alone.

---

## Exclusions

This document contains no credentials of any kind. Specifically, it includes no
passwords, no JWT signing key, no access or refresh tokens, no API keys, and no
values taken from `.env`. The same rule was applied to `docs/SECURITY_AUDIT.md`:
finding SEC-08 concerns a committed secret and names the file and variable, but
does not reproduce the value.
