# AGENTS.md — services/documents/

> Inherits `/AGENTS.md`. Root Security Rules always apply and cannot be overridden here.

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
- 2026-11-11 — AGENTS.md created (baseline).
