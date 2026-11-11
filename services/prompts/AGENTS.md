# AGENTS.md — services/prompts/

> Inherits `/AGENTS.md`. Root Security Rules always apply and cannot be overridden here.

## Purpose
Prompt generation and optimization ("J1"): RL-based and genetic-algorithm prompt optimization, prompt categories, feedback collection, advanced RAG, streaming.

## Layout
- `main.py` — routers: `/prompts`, `/categories`, `/feedback`, `/rag`, `/streaming` (from `services/shared/streaming_router`)
- `services/j1_service.py`, `j1_enhanced_service.py` — J1 prompt optimization (thinking traces, GA, RL)
- `services/rl_optimizer.py`, `genetic_optimizer.py` — optimization algorithms
- `services/prompt_service.py`, `advanced_rag_service.py`
- `RL_OPTIMIZER_README.md` — optimizer design notes; `rl_integration_example.py` — usage example

## Interfaces
- Container `prompt-service`, host port **8002** → 8000. Build context is the repo root.
- Depends on: PostgreSQL (`prompt_categories`, `generated_prompts`, `prompt_feedback`), Redis, `shared/unified_api`.

## Rules
- Optimizers improve *prompts* (search over text), not model weights. Keep them provider-agnostic through `shared/unified_api`.
- Feedback data can contain user content. Don't log it raw.

## Verification
- No tests for this service in `tests/unit/`. `services/prompts/test_rl_optimizer.py` exists inside the service and hasn't been checked to pass. New behavior needs a test in `tests/unit/test_prompts_*.py` with the unified API mocked.
- Manual: `docker-compose up`, then hit `/prompts` and `/categories` via `http://localhost:8002/docs`.

## Decisions & Known Issues
- `advanced_rag_service.py` duplicates `services/compliance/services/advanced_rag_service.py`. If both need it, it belongs in `services/shared/` (root rule 3).
- Idea (not decided): verifiers v1 ships GEPA system-prompt optimization, which could be a reference or alternative for the J1 optimizer.

## Change Log
- 2026-11-11 — AGENTS.md created (baseline).
