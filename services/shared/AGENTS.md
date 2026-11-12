# AGENTS.md — services/shared/ (backend shared library)

> Inherits `/AGENTS.md`. Root Security Rules always apply and cannot be overridden here.

## Purpose
Code used by two or more backend services (root rule 3). Not a container. It's imported by every service and by the gateway through a mounted volume.

## Layout
- Core (most imported): `exceptions.py`, `schemas.py` (Pydantic v2), `auth.py` (JWT; fails fast if `JWT_SECRET` unset), `models.py`, `database.py`, `redis_client.py`, `logger_util.py`
- Model/keys: `models_service.py`, `api_key_manager.py` (encrypted key storage), `unified_api_auth.py`, `local_models.py`, `local_model_manager.py`
- Enterprise: `rbac_manager.py`, `multi_tenant_manager.py`, `sso_manager.py`, `enterprise_auth.py` + `enterprise_auth_router.py`, `audit_logging_service.py` + `audit_router.py`
- Ops: `caching_service.py`, `rate_limiter.py`, `monitoring_service.py`, `backup_restore_service.py`, `data_export_import_service.py`
- Realtime: `streaming_service.py` + `streaming_router.py`, `websocket_service.py`, `websocket_manager.py`
- `evaluator_plugin_system.py` — a second, DB-backed plugin system (`BaseEvaluatorPlugin`). The compliance `Registry` uses the other one (`PluginInterface`).

## Interfaces
- Imported as `services.shared.*` or relative `...shared.*`. Treat every public name as an API used by multiple services.

## Rules
- **Before changing a function, grep all callers** across `services/` and `gateway/`. A change here ships to every container.
- Only code used by 2+ services goes here. Single-service code stays in that service.
- Keep the fail-fast checks for secrets (`JWT_SECRET`, encryption key). Never add literal defaults.
- Async DB/Redis only.

## Verification
- Run the whole offline unit suite: `pytest tests/unit/ -v` (see `/tests/AGENTS.md` for which files need the live stack).
- Rebuild **all** containers (`docker-compose up --build`) and check each `/health`.
- New shared logic needs its own `tests/unit/test_shared_*.py`.

## Decisions & Known Issues
- Two plugin systems coexist (`evaluator_plugin_system.py` and `services/compliance/services/evaluators/plugin_manager.py`). New plugins target `PluginInterface`. Converge later.
- `gateway/src/shared/models_service.py` duplicates `models_service.py` here.

## Change Log
- 2026-11-11 — AGENTS.md created (baseline).
- 2026-11-11 — Added `UserAPIKey` ORM class: `AIModelConfig.api_key_id` FK referenced `user_api_keys` with no mapped class, breaking all model-config writes.
- 2026-11-12 — `api_key_manager.py`: `_setup_encryption` previously used a hardcoded Fernet key (`your-32-byte-encryption-key-here!!`), which could never decrypt keys written by the gateway. New module-level `get_encryption_fernet()` derives from `API_KEY_ENCRYPTION_KEY` (fail-fast if unset), identical derivation to the gateway's `SimpleAPIKeyService`.
