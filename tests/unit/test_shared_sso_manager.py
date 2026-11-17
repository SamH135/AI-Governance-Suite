"""Offline tests for the SSO OIDC userinfo fix (2026-11-17):
_handle_oauth_callback must always fetch claims from the userinfo
endpoint with the bearer access_token and must never decode the
unverified id_token. No network, keys, or services.
"""
import asyncio
import base64
import json
import sys
from pathlib import Path
from types import ModuleType

import jwt
import pytest

root_path = str(Path(__file__).resolve().parent.parent.parent)
if root_path not in sys.path:
    sys.path.insert(0, root_path)

# redis isn't installed in the local dev env; stub it so
# services.shared.redis_client (imported by sso_manager) loads.
try:
    import redis.asyncio  # noqa: F401
except ImportError:
    for _name in ("redis", "redis.asyncio"):
        sys.modules.setdefault(_name, ModuleType(_name))
    sys.modules["redis"].asyncio = sys.modules["redis.asyncio"]

from services.shared.exceptions import AuthenticationError  # noqa: E402
from services.shared.sso_manager import SSOManager  # noqa: E402

CONFIG = {
    "client_id": "cid",
    "client_secret": "cs",
    "token_endpoint": "https://idp.example.com/token",
    "userinfo_endpoint": "https://idp.example.com/userinfo",
}
CALLBACK = {"code": "auth-code", "redirect_uri": "https://app.example.com/cb"}


def _unsigned_jwt(payload):
    def b64(obj):
        return base64.urlsafe_b64encode(
            json.dumps(obj).encode()).rstrip(b"=").decode()

    return f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64(payload)}."


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class FakeHttpClient:
    def __init__(
        self, token_payload, userinfo_status=200, userinfo_payload=None
    ):
        self._token_payload = token_payload
        self._userinfo_status = userinfo_status
        self._userinfo_payload = userinfo_payload or {}
        self.userinfo_headers = None

    async def post(self, url, data=None):
        return _Response(200, self._token_payload)

    async def get(self, url, headers=None):
        self.userinfo_headers = headers
        return _Response(self._userinfo_status, self._userinfo_payload)


def _manager(client):
    mgr = SSOManager()
    mgr.http_client = client
    mgr.initialized = True
    return mgr


def test_forged_id_token_ignored_userinfo_claims_win():
    forged = _unsigned_jwt({"email": "attacker@evil.com"})
    # the token really is attacker-controlled: the old code decoded it
    claims = jwt.decode(forged, options={"verify_signature": False})
    assert claims["email"] == "attacker@evil.com"

    client = FakeHttpClient(
        token_payload={"access_token": "tok123", "id_token": forged},
        userinfo_payload={
            "email": "real@corp.com",
            "name": "Real User",
            "given_name": "Real",
            "family_name": "User",
            "groups": ["eng"],
        },
    )
    mgr = _manager(client)
    result = asyncio.run(mgr._handle_oauth_callback(CONFIG, CALLBACK))

    assert result["email"] == "real@corp.com"
    assert result["first_name"] == "Real"
    assert result["groups"] == ["eng"]
    assert client.userinfo_headers["Authorization"] == "Bearer tok123"


def test_missing_access_token_raises():
    client = FakeHttpClient(
        token_payload={
            "id_token": _unsigned_jwt({"email": "attacker@evil.com"})
        }
    )
    mgr = _manager(client)
    with pytest.raises(AuthenticationError, match="access token"):
        asyncio.run(mgr._handle_oauth_callback(CONFIG, CALLBACK))


def test_userinfo_non_200_raises():
    client = FakeHttpClient(
        token_payload={"access_token": "tok123"}, userinfo_status=500
    )
    mgr = _manager(client)
    with pytest.raises(AuthenticationError, match="user info"):
        asyncio.run(mgr._handle_oauth_callback(CONFIG, CALLBACK))
