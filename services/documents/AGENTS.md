# AGENTS.md — services/documents/

> Inherits `/AGENTS.md`. Root Security Rules always apply and cannot be overridden here.
> Maintenance: keep it short — update the sections and add a dated Change Log line when this area's behavior, interfaces or conventions change; delete entries that stop being true.

## Purpose
Generates compliance documents/reports from templates, with approval workflows, version tracking, and notifications.

## Layout
- `main.py` — routers: `/documents`, `/templates`, `/workflow`, `/industry-templates`
- `services/document_service.py` — core generation; `template_processor.py` — template rendering
- `services/format_converter.py` — PDF/DOCX/HTML conversion (reportlab, weasyprint, docxtpl, pandoc)
- `services/industry_templates_service.py` + `services/templates/*.html` + `templates/registry.json` (fintech, healthcare, regulatory, technology)
- `services/workflow_service.py` (approvals/escalation), `change_tracking_service.py` (versions), `notification_service.py` (email/webhook/SMS)

## Interfaces
- Container `document-service`, host port **8003** → 8000. Build context is the repo root.
- Depends on: PostgreSQL (`document_templates`, `generated_documents`, `document_versions`, `workflow_*`), MinIO (object storage), pandoc binary for some conversions.

## Rules
- A new industry template is an `.html` file in `services/templates/` **plus** an entry in `registry.json`. Both are required.
- Generated reports are audit evidence. Include test provenance (models, thresholds, dates) and never embed raw API keys or unredacted PII.
- Notifications have real-world side effects. Don't trigger real sends from tests.

## Verification
- No unit tests exist for this service. A template or generation change needs a `tests/unit/test_documents_*.py` that renders with fixture data and asserts the required sections are present.
- Manual: generate a document from the UI (`/documents/generator`) and open the output.

## Decisions & Known Issues
- `/plan.md` Phase 4 adds a framework coverage matrix (OWASP/ATLAS/NIST/EU AI Act) to generated reports here.

## Change Log
- 2026-11-17 — `workflow_service.py`: escalation monitor spawned via `services.shared.async_utils.spawn` (no bare `create_task`; guard test `tests/unit/test_no_bare_create_task.py`).
- 2026-11-11 — AGENTS.md created (baseline).
- 2026-11-14 — Security hardening: all three Jinja environments (`template_processor`, `document_service`, `industry_templates_service`) use `jinja2.sandbox.SandboxedEnvironment`; template routes already required `require_admin`. Webhook URLs in `notification_service._send_webhook` are validated via `services.shared.url_safety` before sending. Floors bumped: `jinja2>=3.1.6`, `weasyprint>=61.2`.
- 2026-11-17 — `format_converter._generate_pdf_with_wkhtmltopdf`: predictable `/tmp/<base>.{html,pdf}` paths replaced by `tempfile.TemporaryDirectory()` with fixed `doc.html`/`doc.pdf` names inside (python:S5443); temp files now cleaned up on wkhtmltopdf failure too, not just success. Returned `filename` still `<base>.pdf`; HTML fallback on `CalledProcessError` unchanged.
- 2026-11-18 — `format_converter`: blocking `subprocess.run`/`open()` inside async methods moved off the event loop via `asyncio.to_thread` (`initialize`, `_generate_pdf_with_wkhtmltopdf` → sync `_render_pdf_wkhtmltopdf`). Sonar S7493/S7487.
- 2026-11-18 — Report HTML templates: `<html>` → `<html lang="en">` on all 14 industry templates (Web:S5254).
