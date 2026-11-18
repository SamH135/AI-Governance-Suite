# AGENTS.md — frontend/

> Inherits `/AGENTS.md`. Root Security Rules always apply and cannot be overridden here.
> Maintenance: keep it short — update the sections and add a dated Change Log line when this area's behavior, interfaces or conventions change; delete entries that stop being true.

## Purpose
React 18 + Vite SPA for managing AI systems, model configs, compliance tests/results, prompts, documents, and settings.

## Layout
- `src/App.jsx` — routes: `/compliance/*` (systems, models, api-keys, rag, test configure/results), `/prompts/*`, `/documents/*`, `/settings/*`, `/login`, `/register`
- `src/pages/` — route views (one folder per area)
- `src/components/` — `ui/` primitives, `layout/`, `compliance/`, `dashboard/`, `settings/`, `charts/`, `forms/`, `common/`
- `src/services/apiService.js`, `authService.js` — axios clients (base `VITE_API_URL` + `/api`)
- `src/contexts/` — `AuthContext`, `AppContext`, `WebSocketContext`
- `src/hooks/`, `src/utils/`, `src/constants/`, `src/styles/`

## Interfaces
- Container `frontend`, port **3000**. Local dev runs `npm run dev` on **5173**.
- Talks **only** to the gateway (port 8000), never directly to backend services.
- Env comes from `import.meta.env` (`VITE_*`). See `frontend/.env.example`.

## Rules
- UI uses MUI + Tailwind only. Don't add another component library. `lucide-react` (icons) and `framer-motion` are already installed; reuse them.
- State shared across more than two components goes in a context in `src/contexts/`. No prop drilling.
- All HTTP calls go through `src/services/`, not ad-hoc `fetch`/axios in components.
- Never put secrets in `VITE_*` vars. They ship to the browser.

## Verification
- `npm run lint` must pass with **0 warnings** (`--max-warnings 0`).
- `npm run test` = `vitest` (watch); CI/single runs use `npx vitest run`. First test: `src/services/authService.test.js` (axios interceptors via injected `api.defaults.adapter`). Environment is **happy-dom** (jsdom 31 needs Node ≥22.12 for `require(ESM)`). A new component, hook or context needs a test using `@testing-library/react`; put it next to the file as `*.test.jsx`.
- `npm run build` must succeed.
- Manual: run against the gateway with `docker-compose up` and click through the affected route.

## Decisions & Known Issues
- The auth token lives in `localStorage('token')` (read in 3 places). It's readable from JS if an XSS bug exists. Changing this needs a decision on cookie-based auth with the gateway.

## Change Log
- 2026-11-17 — First frontend test (`src/services/authService.test.js`, vitest + happy-dom via `vite.config.js` `test.environment`). `authService.js`: removed a debug line that dumped the full axios request config (Authorization bearer header + request body) into console logs.
- 2026-11-11 — AGENTS.md created (baseline).
- 2026-11-12 — Security upgrade: node:18-alpine -> node:22-alpine, react-router-dom 6 -> 7, vite 5 -> 6.4.6, vitest 1 -> 5, package-lock.json added (builds were non-reproducible), `overrides` pins for dompurify/postcss-selector-parser/esbuild<0.26/tinypool CVE fixes. Removed `zod` (unused). eslint config still references missing @typescript-eslint — pre-existing, lint was already broken.
- 2026-11-12 — `ApiKeysPage` shows env-sourced provider keys in a read-only "Environment Keys" section (`apiKeysService.getEnvApiKeys` → `GET /api-keys/env`). Managed keys remain editable.
- 2026-11-12 — ESLint fixed: removed `@typescript-eslint` refs (JS project), added `plugin:react` + `eslint-plugin-unused-imports`. Auto-fixed ~60 dead imports; fixed real bugs (`api` used unimported in `useApi.js`/`RAGTestPage.jsx`, `process.env` → `import.meta.env` in ErrorBoundary). `npm run lint` now passes 0 warnings.
- 2026-11-16 — Dockerfile is now a prod build: multi-stage `vite build` → `nginx:alpine` serving `dist/` on 3000, with `nginx.conf` template (envsubst'd into conf.d at start) proxying `/api` and `/ws` to `$GATEWAY_HOST` (default `gateway`). API/WS base URLs now default to same-origin, so `VITE_API_URL`/`VITE_WS_URL` are optional overrides; dead `REACT_APP_*` env vars removed from compose. Hot-reload dev = local `npm run dev` (5173) — the compose frontend is the static build.
- 2026-11-17 — `PluginManager.jsx` converted from raw `fetch` to the shared `api` axios client — the calls sent no Authorization header and would have 401-redirected; now handled by the interceptor.
- 2026-11-18 — Form label accessibility (S6853, 69 findings): every `<label>` now either pairs a control via `htmlFor`/`id` or wraps it; section captions over button/checkbox groups changed to `<span>` (they were misused labels). `ui/Input.jsx` associates its internal label via `useId`, fixing every `label=` usage site.
