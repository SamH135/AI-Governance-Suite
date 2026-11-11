# AGENTS.md — gateway/

> Inherits `/AGENTS.md`. Root Security Rules always apply and cannot be overridden here.

## Purpose
Single public entry point. Handles auth (JWT), CORS, routing/proxying to backend services, and WebSockets.

## Layout
- `main.py` — FastAPI app, router registration, proxy routes to backend services
- `start.py` — local dev launcher (uvicorn reload)
- `src/routes/` — `auth`, `health`, `models`, `api_keys`, `systems`, `test_execution`
- `src/websocket_routes.py`, `src/websocket/manager.py` — WebSocket endpoints + connection manager
- `src/shared/` — gateway-local `config.py` (pydantic settings), `database.py`, `cache.py`, `models_service.py`, `simple_api_key_service.py`
- `src/logger_util.py` — structured logger (use this, not `print`/`logging`)

## Interfaces
- Container `gateway`, port **8000**. Built from `./gateway`; mounts `./services` and `./shared` so it can import `services.shared.*`.
- Routers mounted under `/api` (except `health` and WebSocket).
- Proxies to `ANALYTICS_SERVICE_URL`, `COMPLIANCE_SERVICE_URL`, `PROMPTS_SERVICE_URL`, `DOCUMENTS_SERVICE_URL`, `TESTS_SERVICE_URL` (env, see `src/shared/config.py`).
- Consumed by: `frontend` (axios base `VITE_API_URL` + `/api`).

## Rules
- CORS comes only from the `ALLOWED_ORIGINS` allowlist. Never use `*`.
- New endpoints that need auth use the existing JWT dependency in `src/routes/auth.py`. Don't build a second auth path.
- Gateway routes stay thin. Business logic belongs in the owning service; the gateway proxies to it.
- Don't log request bodies (they can contain API keys or PII).

## Verification
- No gateway unit tests exist yet. A new route needs a `tests/unit/` test using FastAPI `TestClient` with dependency overrides (no live services). The first one you write sets the pattern.
- Integration coverage (needs the stack running): `tests/integration/test_gateway_integration.py`, `tests/integration/test_api.py`.
- Manual check: `docker-compose up --build`, then `GET http://localhost:8000/health` and `/docs`.

## Decisions & Known Issues
- `src/shared/config.py` ships a literal default for `JWT_SECRET`. That violates the root security rule. It should fail fast the way `services/shared/auth.py` does.
- `src/shared/models_service.py` duplicates `services/shared/models_service.py`. Converge before changing either one.

## Change Log
- 2026-11-11 — AGENTS.md created (baseline).
