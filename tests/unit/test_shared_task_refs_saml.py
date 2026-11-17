"""Offline tests for the 2026-11-17 shared fixes: SAML fail-closed
(unsigned assertions are no longer trusted), async_utils.spawn keeps
background-task refs, and the websocket Redis handler re-raises
CancelledError. No network, keys, or services.
"""
import ast
import asyncio
import base64
import sys
from pathlib import Path
from types import ModuleType

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

from services.shared.async_utils import _tasks, spawn  # noqa: E402
from services.shared.exceptions import AuthenticationError  # noqa: E402
from services.shared.sso_manager import SSOManager  # noqa: E402

SAML_WITH_EMAIL = base64.b64encode(
    b'<samlp:Response><saml:Assertion>'
    b'<saml:Attribute Name="email">'
    b'<saml:AttributeValue>attacker@evil.com</saml:AttributeValue>'
    b"</saml:Attribute></saml:Assertion></samlp:Response>"
).decode()


def test_saml_callback_fail_closed_with_response():
    mgr = SSOManager()
    with pytest.raises(AuthenticationError, match="disabled"):
        asyncio.run(
            mgr._handle_saml_callback({}, {"SAMLResponse": SAML_WITH_EMAIL})
        )


def test_saml_callback_fail_closed_missing_response():
    mgr = SSOManager()
    with pytest.raises(AuthenticationError, match="Missing SAML response"):
        asyncio.run(mgr._handle_saml_callback({}, {}))


def test_spawn_holds_reference_while_running():
    async def check():
        async def job():
            await asyncio.sleep(0.01)

        task = spawn(job())
        assert task in _tasks
        await task
        # done_callback is scheduled with call_soon; let it run
        await asyncio.sleep(0)
        assert task not in _tasks

    asyncio.run(check())


def test_spawn_returns_task():
    async def check():
        task = spawn(asyncio.sleep(0))
        assert isinstance(task, asyncio.Task)
        await task

    asyncio.run(check())


def test_ws_redis_handler_cancelled_error_reraises():
    src = (
        Path(root_path) / "services" / "shared" / "websocket_service.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef)
        and n.name == "_redis_message_handler"
    )
    handlers = [
        n
        for n in ast.walk(fn)
        if isinstance(n, ast.ExceptHandler)
        and "CancelledError" in ast.dump(n.type)
    ]
    assert len(handlers) == 1
    assert any(
        isinstance(n, ast.Raise) and n.exc is None
        for n in ast.walk(handlers[0])
    )
