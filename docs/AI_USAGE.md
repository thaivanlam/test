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

### Notes on this log

- Entries 2 through 9 were carried out in a single Claude Code session, so the
  sequence is recorded from that session's history rather than reconstructed
  from memory.
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
demonstrates remains a static finding. This is why every entry in
`docs/SECURITY_AUDIT.md` currently carries a status of `Open — static` or
`Open — suspected`, and why the promotion of those findings to `Reproduced` is
scheduled for Tier 2, once the container stack is running and a failing test can
be recorded before each fix.

---

## Exclusions

This document contains no credentials of any kind. Specifically, it includes no
passwords, no JWT signing key, no access or refresh tokens, no API keys, and no
values taken from `.env`. The same rule was applied to `docs/SECURITY_AUDIT.md`:
finding SEC-08 concerns a committed secret and names the file and variable, but
does not reproduce the value.
