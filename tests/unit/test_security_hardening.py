"""Offline tests for the 2026-11-14 security-hardening fixes: outbound-URL
validation, Jinja sandboxing, model-config ownership scoping,
and schema api_url validators. No network, keys, or services.
"""
import ast
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

root_path = str(Path(__file__).resolve().parent.parent.parent)
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from services.shared.url_safety import validate_outbound_url


# ---------- url_safety ----------

def test_https_public_literal_accepted():
    assert validate_outbound_url("https://93.184.216.34/v1/models") == "https://93.184.216.34/v1/models"


@pytest.mark.parametrize("url", [
    "http://93.184.216.34/",          # plain http rejected by default
    "https://127.0.0.1:11434/",       # loopback
    "https://10.0.0.5/",              # RFC1918
    "https://169.254.169.254/latest/meta-data",  # link-local (cloud metadata)
    "https://localhost:6379/",        # resolves to loopback
    "https://user:pass@93.184.216.34/",  # userinfo
    "ftp://93.184.216.34/",           # unsupported scheme
    "https://0.0.0.0/",               # unspecified
])
def test_unsafe_urls_rejected(url):
    with pytest.raises(ValueError):
        validate_outbound_url(url)


def test_private_opt_in_allows_http_and_private(monkeypatch):
    monkeypatch.setenv("ALLOW_PRIVATE_OUTBOUND_URLS", "true")
    assert validate_outbound_url("http://127.0.0.1:11434/")
    assert validate_outbound_url("http://10.0.0.5/")


def test_opt_in_still_rejects_userinfo(monkeypatch):
    monkeypatch.setenv("ALLOW_PRIVATE_OUTBOUND_URLS", "true")
    with pytest.raises(ValueError):
        validate_outbound_url("http://user:pw@127.0.0.1/")


# ---------- schema api_url validators ----------

def test_schema_rejects_private_api_url():
    from services.shared.schemas import AIModelConfigCreate, AIModelConfigUpdate
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        AIModelConfigCreate(name="x", provider="openai", model_id="gpt-4",
                            api_url="http://169.254.169.254/")
    with pytest.raises(ValidationError):
        AIModelConfigUpdate(api_url="http://localhost:6379/")


def test_schema_allows_none_and_public(monkeypatch):
    monkeypatch.delenv("ALLOW_PRIVATE_OUTBOUND_URLS", raising=False)
    from services.shared.schemas import AIModelConfigCreate, AIModelConfigUpdate

    assert AIModelConfigCreate(name="x", provider="openai", model_id="m").api_url is None
    assert AIModelConfigUpdate(api_url=None).api_url is None
    assert (AIModelConfigCreate(name="x", provider="custom", model_id="m",
                                api_url="https://93.184.216.34/v1")
            .api_url == "https://93.184.216.34/v1")


# ---------- Jinja sandbox ----------

def test_sandboxed_env_blocks_attribute_escape():
    from jinja2.sandbox import SandboxedEnvironment
    from jinja2.exceptions import SecurityError

    env = SandboxedEnvironment()
    with pytest.raises(SecurityError):
        env.from_string("{{ ''.__class__.__mro__ }}").render()


def test_document_services_use_sandboxed_env():
    docs = Path(root_path) / "services" / "documents" / "services"
    for name in ("template_processor.py", "document_service.py",
                 "industry_templates_service.py"):
        assert "SandboxedEnvironment" in (docs / name).read_text(encoding="utf-8"), name


# ---------- _resolve_model_config ownership scoping ----------

def _load_resolve_fn():
    """Execute the real _resolve_model_config body in a stub namespace.

    The router module can't be imported offline (service-only deps), so the
    function's AST is extracted and compiled — the code under test is the
    actual implementation, only its imports/dependencies are stubbed.
    """
    src = (Path(root_path) / "services" / "compliance" / "routers" / "systems.py").read_text(encoding="utf-8")
    node = next(n for n in ast.parse(src).body
                if isinstance(n, ast.AsyncFunctionDef) and n.name == "_resolve_model_config")
    ns: dict = {}
    exec(
        "from typing import Optional, Dict, Any\n"
        "from sqlalchemy.ext.asyncio import AsyncSession\n"
        "from sqlalchemy import select\n"
        "from services.shared.models import AIModelConfig, UserAPIKey\n",
        ns,
    )
    ns["logger"] = SimpleNamespace(warning=lambda *a, **k: None, error=lambda *a, **k: None)
    exec(compile(ast.Module(body=[node], type_ignores=[]), "systems.py", "exec"), ns)
    return ns["_resolve_model_config"]


class _Result:
    def __init__(self, row):
        self._row = row

    def scalar_one_or_none(self):
        return self._row


def _criteria(stmt):
    """{column_name: literal_value} from a select's equality where-clauses."""
    w = stmt.whereclause
    clauses = getattr(w, "clauses", [w])
    return {c.left.key: c.right.value for c in clauses}


class FakeDB:
    """AsyncSession stub that applies the query's where criteria to fake rows."""

    def __init__(self, configs=(), keys=()):
        self.configs = list(configs)
        self.keys = list(keys)
        self.queries = []

    async def execute(self, stmt):
        entity = stmt.column_descriptions[0]["entity"].__name__
        crit = _criteria(stmt)
        self.queries.append((entity, crit))
        rows = self.configs if entity == "AIModelConfig" else self.keys
        for row in rows:
            if all(getattr(row, k, None) == v for k, v in crit.items()):
                return _Result(row)
        return _Result(None)


def _config(config_id=1, created_by=99, api_url=None):
    return SimpleNamespace(
        config_id=config_id, name="cfg", provider="openai", model_id="gpt-4",
        api_key="sk-x", api_key_id=None, api_url=api_url,
        temperature=0.7, max_tokens=100, timeout=30, max_retries=3,
        retry_delay=1.0, provider_options={}, enabled=True,
        created_by=created_by,
    )


def test_resolve_denies_other_users_config(monkeypatch):
    monkeypatch.delenv("ALLOW_PRIVATE_OUTBOUND_URLS", raising=False)
    resolve = _load_resolve_fn()
    db = FakeDB(configs=[_config(config_id=1, created_by=99)])
    result = asyncio.run(resolve(db, 1, user_id=42))
    assert result is None
    # The denial must come from an ownership filter in the query itself
    entity, crit = db.queries[0]
    assert entity == "AIModelConfig"
    assert crit.get("created_by") == 42


def test_resolve_returns_own_config(monkeypatch):
    monkeypatch.delenv("ALLOW_PRIVATE_OUTBOUND_URLS", raising=False)
    resolve = _load_resolve_fn()
    db = FakeDB(configs=[_config(config_id=1, created_by=42)])
    result = asyncio.run(resolve(db, 1, user_id=42))
    assert result is not None
    assert result["config_id"] == 1


def test_resolve_rejects_config_with_private_api_url(monkeypatch):
    monkeypatch.delenv("ALLOW_PRIVATE_OUTBOUND_URLS", raising=False)
    resolve = _load_resolve_fn()
    db = FakeDB(configs=[_config(config_id=1, created_by=42,
                                 api_url="http://169.254.169.254/")])
    assert asyncio.run(resolve(db, 1, user_id=42)) is None
