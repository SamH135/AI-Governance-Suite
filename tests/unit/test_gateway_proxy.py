"""Gateway proxy tests — the first TestClient tests for gateway/.

Runs inside the gateway container in CI (the repo is mounted at /repo
there) and locally from the repo root. Exercises the path-preserving
proxy and the service-status passthrough without network or services.
"""
import os
import sys
from pathlib import Path

import pytest

root_path = str(Path(__file__).resolve().parent.parent.parent)
for p in (root_path, str(Path(root_path) / "gateway")):
    if p not in sys.path:
        sys.path.insert(0, p)

# Dummy value for config import only — never a real credential.
os.environ.setdefault("JWT_SECRET", "ci-test-dummy-secret")
os.environ.setdefault("API_KEY_ENCRYPTION_KEY", "ci-test-dummy-key")

pytestmark = pytest.mark.skipif(
    not Path(root_path, "gateway", "main.py").exists(),
    reason="gateway source not present in this environment",
)

try:
    import main
except Exception as exc:  # noqa: BLE001
    pytest.skip(
        f"gateway app not importable here: {exc}", allow_module_level=True
    )
if "gateway" not in Path(getattr(main, "__file__", "")).parts:
    pytest.skip("resolved `main` is not the gateway app",
                allow_module_level=True)

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


class _FakeHttpClient:
    """Minimal async stand-in for the gateway's global httpx client."""

    def __init__(self, response):
        self._response = response
        self.calls = []

    async def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self._response


def _client(monkeypatch, response):
    fake = _FakeHttpClient(response)
    monkeypatch.setattr(main, "http_client", fake)
    main.app.dependency_overrides[main.get_current_user] = (
        lambda: {"user_id": 1, "role": "admin"}
    )
    # base_url host must satisfy TrustedHostMiddleware's allowlist.
    return TestClient(main.app, base_url="http://localhost"), fake


def test_proxy_forwards_path_and_injects_identity_headers(monkeypatch):
    resp = httpx.Response(200, json={"ok": True})
    client, fake = _client(monkeypatch, resp)

    r = client.get("/api/prompts/categories")

    assert r.status_code == 200
    assert r.json() == {"ok": True}
    method, url, kwargs = fake.calls[0]
    assert method == "GET"
    assert url.endswith("/categories")
    assert kwargs["headers"]["X-User-ID"] == "1"
    assert kwargs["headers"]["X-User-Role"] == "admin"


def test_proxy_preserves_service_status_and_detail(monkeypatch):
    resp = httpx.Response(404, json={"detail": "no such prompt"})
    client, _ = _client(monkeypatch, resp)

    r = client.get("/api/prompts/prompts/missing")

    # The service's 404 must reach the caller, not be masked as 500.
    assert r.status_code == 404
    assert r.json()["detail"] == "no such prompt"


def test_proxy_returns_500_only_for_unreachable_service(monkeypatch):
    class _BrokenClient(_FakeHttpClient):
        async def request(self, method, url, **kwargs):
            raise httpx.ConnectError("refused")

    monkeypatch.setattr(main, "http_client", _BrokenClient(None))
    main.app.dependency_overrides[main.get_current_user] = (
        lambda: {"user_id": 1, "role": "admin"}
    )
    client = TestClient(main.app, base_url="http://localhost")

    r = client.get("/api/prompts/categories")
    assert r.status_code == 500
