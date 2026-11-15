# AGENTS.md — AI Governance Suite

## Project Context
Enterprise-grade AI compliance platform for testing, documenting, and managing regulatory requirements (GDPR, HIPAA, EU AI Act, bias/safety). Built as a Python FastAPI microservices backend with a React 18 + Vite frontend. Core goal: automate the full AI compliance lifecycle—from evaluation to report generation—via a pluggable, multi-tenant system.

---

## Repository Map

```
gateway/              FastAPI API gateway — auth, routing, WebSocket (port 8000). slowapi limits enforced: 200/min default, 5/min on auth login/register, `/health` exempt.
services/
  compliance/         AI evaluation engine — runs evaluators, manages frameworks (port 8001)
  prompts/            Genetic-algorithm prompt optimization & generation (port 8002)
  documents/          Template & compliance report generation (port 8003)
  tests/              Test execution & orchestration service (port 8004) — not the pytest suite
  analytics/          Metrics aggregation & dashboard data (port 8005)
  shared/             Shared DB, Redis, exception, and type utilities used by all services
plugins/
  evaluators/         Custom evaluator plugins — THE extension point for new compliance checks
  configs/            Plugin configuration schemas
shared/               Root-level shared types (platform_types.py, unified_api/)
infrastructure/
  database/           SQL init scripts for PostgreSQL schema
tests/
  unit/               Pytest unit tests for service logic
  integration/        Integration tests (require live infra)
  manual/             Manual test scripts — not run in CI
scripts/              One-off admin scripts (create_test_user, validate_implementation, etc.)
frontend/src/
  pages/              Top-level route views
  components/         Reusable UI components
  services/           Axios API client modules
  hooks/              Custom React hooks
  contexts/           React context providers (auth, theme, etc.)
```

Non-obvious: `gateway/` mounts both `./services` and `./shared` as volumes, so it can import from `services.shared.*` at runtime without installing them as packages.

---

## Context Hierarchy (read this first)

This root file holds project-wide conventions, commands, security rules and navigation. Each major area (one container/service, shared library, or extension point) has its own `AGENTS.md` with: purpose, layout, interfaces (ports, endpoints, consumers), area rules, **Verification** (which tests to write and run), decisions/known issues, and a change log.

**Rules for agents:**
1. Before editing, read this file **and** the `AGENTS.md` of every area you touch.
2. On conflict, the area file wins for area-specific conventions. The Security Rules below can **never** be overridden.
3. Run the tests listed in the area file's **Verification** section. `tests/AGENTS.md` has the change → tests matrix.
4. When you change an area's behavior, interfaces, architecture or conventions, update that area's `AGENTS.md` in the same change, including a dated **Change Log** line. Don't log trivial edits, and delete entries that stop being true.
5. New AGENTS.md files go only at the root of a new major area, not in every subdirectory.

| Area | File |
|---|---|
| API gateway (8000) | `gateway/AGENTS.md` |
| Frontend (3000 / 5173) | `frontend/AGENTS.md` |
| Compliance service (8001) | `services/compliance/AGENTS.md` |
| Prompts service (8002) | `services/prompts/AGENTS.md` |
| Documents service (8003) | `services/documents/AGENTS.md` |
| Test execution service (8004) | `services/tests/AGENTS.md` |
| Analytics service (8005) | `services/analytics/AGENTS.md` |
| Backend shared library | `services/shared/AGENTS.md` |
| Unified AI API | `shared/AGENTS.md` |
| Evaluator plugins | `plugins/AGENTS.md` |
| Database schema | `infrastructure/AGENTS.md` |
| Pytest suite | `tests/AGENTS.md` |
| Services-wide notes | `services/AGENTS.md` |

`scripts/` (one-off admin scripts) and `docs/` (reference docs, which may be stale; check them against the code) are covered by this file.

## Active Plans

- `plan.md` — evaluator overhaul (OWASP LLM/Agentic, ATLAS, NIST, EU AI Act probes as plugins). Affects `plugins/` and `services/compliance/`. Tick its checkboxes and add to its Change Log as phases land.

---

## Commands

> **Docker-first.** Don't run services directly.

```bash
docker-compose up --build                                   # full stack
docker-compose -f docker-compose.simple.yml up --build      # no Milvus/MinIO/etcd
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build  # hot-reload
docker-compose down -v                                      # tear down + clean volumes

cd frontend && npm install && npm run dev                   # UI only (5173); also lint, lint:fix, format, test
pytest tests/unit/ -v                                       # integration: tests/integration/ (needs infra)
black services/ gateway/ && isort services/ gateway/ && flake8 services/ gateway/ && mypy services/ gateway/
python scripts/create_test_user.py                          # seed user; scripts/validate_implementation.py = smoke check
```

---

## Implementation Rules

1. **Follow existing conventions.** Python services use structured logging via the custom logger wrapper (`services/shared/logger_util.py` or root `logger.py`) — never use `print()` or bare `logging` module directly. React components use MUI + Tailwind together; do not introduce a third UI library.
2. **Minimal, scoped diffs.** Each PR should touch one service or one feature area. Do not refactor unrelated code in the same PR.
3. **Shared utilities go in `services/shared/`.** If two or more services need the same logic, it belongs in `services/shared/`, not duplicated per-service.
4. **New compliance evaluators must be plugins.** Never hardcode evaluation logic directly into `services/compliance/`. All new evaluators belong in `plugins/evaluators/<your_evaluator>/`. Use existing examples (e.g., `plugins/evaluators/hallucination_checker/`) as the reference implementation.
5. **Pydantic v2 throughout.** All request/response models use Pydantic v2 (`model_validator`, `field_validator`, not v1 `@validator`). Do not introduce v1-style validators.
6. **Async everywhere in Python.** All database and Redis operations must use `async/await`. Do not use synchronous DB or blocking I/O in service handlers.
7. **Tests required for behavior changes.** Any new route, evaluator logic, or business rule needs a corresponding test in `tests/unit/`. Integration tests for any new service-to-service interaction.
8. **React: hooks and context, not prop drilling.** New state shared across more than two components goes into a context in `frontend/src/contexts/`.
9. **No unsolicited markdown files.** Do not create `.md` files (READMEs, changelogs, notes, summaries, analysis docs) unless explicitly asked. Exceptions: maintaining existing `AGENTS.md` files and `plan.md` per the Context Hierarchy rules. Write code; communicate in your response.

---

## Security Rules

- **Never read, print, log, or commit `.env` or any secret values.** `.env` is gitignored — keep it that way.
- **Never commit directly to `main`.** All changes go through a PR — no exceptions.
- **Never hardcode credentials, API keys, or JWT secrets.** Always use environment variables via `get_settings()` (Python) or `import.meta.env` (Vite).
- **Do not log request bodies containing PII or API keys.** The platform handles healthcare and financial data — treat all user inputs as potentially sensitive.
- **JWT secret must differ between environments.** The docker-compose default (`dev-secret-key-change-in-production`) must never be used in staging or production.
- **CORS origins are allowlist-only.** Do not set `allow_origins=["*"]` in any FastAPI app.

---

## Git / PR Workflow

- Branches: `feature/`, `fix/`, `chore/`, `plugin/<name>` + short description. Never commit to `main`; squash-merge PRs, delete branch after.
- Conventional Commits: `<type>(<scope>): <summary>`; type: feat|fix|chore|docs|test|refactor; scope: gateway|compliance|prompts|documents|analytics|frontend|plugins|shared.
- PRs need passing tests, clean lint, and a description of what/why/how to test manually.

---

## Definition of Done

- Works end-to-end via `docker-compose up`; existing `tests/unit/` pass unmodified; new behavior has tests.
- `black`, `isort`, `flake8`, `mypy` clean; `npm run lint` 0 warnings.
- Security Rules respected (no secrets in changed files); structlog only, no `print()`.
- Touched areas' `AGENTS.md` updated with a Change Log line when behavior/interfaces/conventions changed.
