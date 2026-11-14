# AGENTS.md — services/ (all backend services)

> Inherits `/AGENTS.md`. Root Security Rules always apply and cannot be overridden here.
> Maintenance: keep it short — update the sections and add a dated Change Log line when this area's behavior, interfaces or conventions change; delete entries that stop being true.

## Purpose
Cross-service notes only. Each service has its own `AGENTS.md` (see the root table); put service-specific rules there.

## Change Log
- 2026-11-12 — Security upgrade: fastapi 0.104.1 -> 0.162.5, python-jose -> PyJWT in `services/shared/auth.py`, `Query(regex=)` -> `Query(pattern=)` (7 sites in analytics — `regex` removed in fastapi 0.116+), marshmallow >=3.26.2, pypdf2 -> pypdf, aiohttp >=3.14.4, pydantic >=2.9. Dockerfiles now `pip install --upgrade pip setuptools` first (clears build-tool CVEs).
