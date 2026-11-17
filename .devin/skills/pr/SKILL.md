---
name: pr
description: Move current work onto a feature branch, commit with Conventional Commits, push, and open a well-described GitHub pull request
argument-hint: "[short description]"
allowed-tools:
  - read
  - grep
  - glob
  - exec
permissions:
  deny:
    - Exec(git push --force)
    - Exec(git push -f)
---

Open a pull request for the current work. Never commit or push to `main`.

1. Run `git status`, `git diff`, `git log --oneline -10` in parallel. Skip files that look like secrets (`.env`, keys) and flag anything unrelated to one feature; offer to split it into separate PRs.
2. If on `main`, create a branch: `feature/`, `fix/`, `chore/` or `plugin/<name>` + kebab-case description.
3. Run the checks listed in the touched area's `AGENTS.md` Verification section (e.g. `pytest tests/unit/ -v`, `npm run lint`). Stop and report if they fail.
4. Stage only relevant files by name (not `git add -A`). Commit as `<type>(<scope>): <summary>` (type: feat|fix|chore|docs|test|refactor; scope: gateway|compliance|prompts|documents|analytics|frontend|plugins|shared). Explain why, not what.
5. `git push -u origin <branch>` (never force).
6. `gh pr create` using `.github/pull_request_template.md` as the body: what/why, how to test manually, risks. Title = the commit summary. If `gh` is missing, print the compare URL `https://github.com/<owner>/<repo>/pull/new/<branch>` instead.
7. Return the PR URL. Do not merge.
