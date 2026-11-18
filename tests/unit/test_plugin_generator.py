"""Offline tests for the plugin scaffold generator.

Covers the admin trust boundary: plugin names become directory names,
so slug validation must reject traversal and overwrite attempts.
"""
import sys
from pathlib import Path

import pytest

root_path = str(Path(__file__).resolve().parent.parent.parent)
if root_path not in sys.path:
    sys.path.insert(0, root_path)

# structlog isn't installed in the local dev env; stub it like the
# other shared-service tests do for redis.
try:
    import structlog  # noqa: F401
except ImportError:
    from types import ModuleType
    stub = ModuleType("structlog")
    stub.get_logger = lambda *a, **k: type(
        "L", (), {"info": lambda *a, **k: None,
                  "warning": lambda *a, **k: None,
                  "error": lambda *a, **k: None}
    )()
    sys.modules.setdefault("structlog", stub)

from services.shared.exceptions import ValidationError  # noqa: E402
from services.compliance.services.plugin_generator_service import (  # noqa: E402
    PluginGenerator,
)


@pytest.fixture
def gen(tmp_path):
    return PluginGenerator(base_dir=str(tmp_path / "plugins" / "evaluators"))


def test_scaffold_writes_plugin_and_metadata(gen, tmp_path):
    assert gen.generate_plugin(
        plugin_name="bias_audit",
        framework_name="BIAS_AUDIT",
        description="Checks bias",
        author="Tester",
        test_cases=[{"name": "t1"}],
    ) is True
    d = tmp_path / "plugins" / "evaluators" / "bias_audit"
    plugin_py = (d / "plugin.py").read_text()
    meta = (d / "metadata.yaml").read_text()
    assert "bias_audit" in plugin_py
    assert "BIAS_AUDIT" in plugin_py
    assert "BiasAuditPlugin" in plugin_py
    assert "'name': 't1'" in plugin_py
    assert "name: bias_audit" in meta
    assert "config_schema:" in meta


def test_list_available_templates(gen):
    templates = gen.list_available_templates()
    assert templates == ["custom_evaluator"]


def test_generate_from_template_round_trip(gen, tmp_path):
    assert gen.generate_from_template(
        template_name="custom_evaluator",
        plugin_name="scaffolded",
        parameters={"framework_name": "FW", "description": "d"},
    ) is True
    assert (tmp_path / "plugins" / "evaluators" / "scaffolded").is_dir()


def test_generate_from_template_rejects_unknown(gen):
    with pytest.raises(ValidationError):
        gen.generate_from_template("nope", "ok_name", {})


@pytest.mark.parametrize("bad", ["../evil", "a/b", "a\\b", "dot.name",
                                 "has space", "1startswithdigit", ""])
def test_slug_rejects_unsafe_names(gen, bad):
    with pytest.raises(ValidationError):
        gen.generate_plugin(bad, "FW", "d")


def test_existing_dir_rejected(gen, tmp_path):
    gen.generate_plugin("taken", "FW", "d")
    with pytest.raises(ValidationError):
        gen.generate_plugin("taken", "FW", "d")
