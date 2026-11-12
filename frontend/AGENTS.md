# AGENTS.md — frontend/

> Inherits `/AGENTS.md`. Root Security Rules always apply and cannot be overridden here.

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
- `npm run test` (vitest). **No frontend tests exist yet.** A new component, hook or context needs a test using `@testing-library/react` (already installed). Put it next to the file as `*.test.jsx`.
- `npm run build` must succeed.
- Manual: run against the gateway with `docker-compose up` and click through the affected route.

## Decisions & Known Issues
- The auth token lives in `localStorage('token')` (read in 3 places). It's readable from JS if an XSS bug exists. Changing this needs a decision on cookie-based auth with the gateway.

## Change Log
- 2026-11-11 — AGENTS.md created (baseline).
- 2026-11-12 — Security upgrade: node:18-alpine -> node:22-alpine, react-router-dom 6 -> 7, vite 5 -> 6.4.6, vitest 1 -> 5, package-lock.json added (builds were non-reproducible), `overrides` pins for dompurify/postcss-selector-parser/esbuild<0.26/tinypool CVE fixes. Removed `zod` (unused). eslint config still references missing @typescript-eslint — pre-existing, lint was already broken.
