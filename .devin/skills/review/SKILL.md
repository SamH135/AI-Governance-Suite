---
name: review
description: Review the current branch or staged changes for bugs, security issues, missing tests and convention violations before opening a PR
allowed-tools:
  - read
  - grep
  - glob
  - exec
permissions:
  deny:
    - edit
---

Review changes read-only (do not edit files).

1. Diff: `git diff --staged`, else `git diff main...HEAD`, else `git diff`.
2. Read the root `AGENTS.md` and the `AGENTS.md` of each touched area.
3. Check, in priority order:
   - **Correctness**: logic errors, unhandled edge cases, async/blocking I/O in Python handlers.
   - **Security**: hardcoded secrets, logged PII/request bodies, `allow_origins=["*"]`, unvalidated input.
   - **Tests**: behavior changes without a matching test in `tests/unit/`.
   - **Conventions**: structured logger (no `print()`), Pydantic v2 validators, new evaluators as plugins, area `AGENTS.md` Change Log updated.
4. Report findings grouped as Blocker / Should fix / Nit, each with `file:line` and a suggested fix. End with a ship / don't-ship verdict.
