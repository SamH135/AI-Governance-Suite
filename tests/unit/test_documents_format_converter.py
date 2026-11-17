"""Offline tests for the wkhtmltopdf temp-file fix (2026-11-17):
_generate_pdf_with_wkhtmltopdf must use a private TemporaryDirectory
(no predictable /tmp/<base> paths) and clean it up on success AND on
wkhtmltopdf failure. No network, services, or wkhtmltopdf binary.
"""
import asyncio
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

root_path = str(Path(__file__).resolve().parent.parent.parent)
if root_path not in sys.path:
    sys.path.insert(0, root_path)

# markdown isn't installed in the local dev env; stub it so
# format_converter imports.
try:
    import markdown  # noqa: F401
except ImportError:
    sys.modules.setdefault("markdown", ModuleType("markdown"))

from services.documents.services.format_converter import (  # noqa: E402
    FormatConverter,
)
import services.documents.services.format_converter as fc_mod  # noqa: E402

FAKE_PDF = b"%PDF-1.4 fake-bytes"
CONTENT = {
    "metadata": {"template_name": "T"},
    "sections": {"summary": "hello"},
}
BASE = "attacker-controlled-name"


def _converter():
    return FormatConverter()


class _RunRecorder:
    """Fake subprocess.run that writes fake PDF bytes to the last cmd arg."""

    def __init__(self, fail=False):
        self.fail = fail
        self.cmds = []

    def __call__(self, cmd, **kwargs):
        self.cmds.append(list(cmd))
        if self.fail:
            raise subprocess.CalledProcessError(1, cmd)
        Path(cmd[-1]).write_bytes(FAKE_PDF)
        return SimpleNamespace(returncode=0)


def test_pdf_success_uses_private_tempdir_and_cleans_up(monkeypatch):
    run = _RunRecorder()
    monkeypatch.setattr(fc_mod.subprocess, "run", run)

    result = asyncio.run(
        _converter()._generate_pdf_with_wkhtmltopdf(CONTENT, BASE)
    )

    assert result["content"] == FAKE_PDF
    assert result["filename"] == f"{BASE}.pdf"
    assert result["format"] == "pdf"

    html_path, pdf_path = run.cmds[0][-2], run.cmds[0][-1]
    # no predictable /tmp/<base_filename> paths; fixed names in a private dir
    assert BASE not in os.path.basename(html_path)
    assert BASE not in os.path.basename(pdf_path)
    assert os.path.dirname(html_path) == os.path.dirname(pdf_path)
    # temp dir fully cleaned up afterwards
    assert not os.path.exists(html_path)
    assert not os.path.exists(pdf_path)
    assert not os.path.exists(os.path.dirname(html_path))


def test_pdf_failure_falls_back_to_html_and_cleans_up(monkeypatch):
    run = _RunRecorder(fail=True)
    monkeypatch.setattr(fc_mod.subprocess, "run", run)

    result = asyncio.run(
        _converter()._generate_pdf_with_wkhtmltopdf(CONTENT, BASE)
    )

    assert result["format"] == "html"
    assert result["filename"] == f"{BASE}.html"
    assert "<h1>T</h1>" in result["content"]

    html_path, pdf_path = run.cmds[0][-2], run.cmds[0][-1]
    # no leaked temp files/dir on the failure path
    assert not os.path.exists(html_path)
    assert not os.path.exists(pdf_path)
    assert not os.path.exists(os.path.dirname(html_path))
