# AI Usage Disclosure

**Assessment:** Fabbi Developer Assessment — Full-Stack Engineering & Quality Assurance
**Branch:** `assessment/thai-van-lam`
**Author:** Thái Văn Lâm
**Last updated:** 2026-09-19

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
rather than implying a result. `docs/SECURITY_AUDIT.md` follows this rule: all
23 findings are recorded as static analysis, and none is marked as reproduced,
because the container stack was unavailable when the audit was performed.

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

### Notes on this log

- Entries 2 through 22 were carried out in a single Claude Code session, so the
  sequence is recorded from that session's history rather than reconstructed
  from memory.
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
