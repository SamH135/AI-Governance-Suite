"""Offline tests for the 2026-11-17 gateway fixes: CORSMiddleware must
be the LAST app.add_middleware call in gateway/main.py (Starlette makes
the last-added middleware outermost, so rate-limit 429s still get CORS
headers), and the websocket manager must keep its Redis task reference.
AST checks — the modules can't import outside the service env.
"""
import ast
import sys
from pathlib import Path

root_path = str(Path(__file__).resolve().parent.parent.parent)
if root_path not in sys.path:
    sys.path.insert(0, root_path)

GATEWAY_MAIN = Path(root_path) / "gateway" / "main.py"
WS_MANAGER = Path(root_path) / "gateway" / "src" / "websocket" / "manager.py"


def _is_create_task_call(node):
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "create_task"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "asyncio"
    )


def test_cors_middleware_added_last():
    tree = ast.parse(GATEWAY_MAIN.read_text(encoding="utf-8"))
    names = [
        node.args[0].id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_middleware"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "app"
        and node.args
        and isinstance(node.args[0], ast.Name)
    ]
    assert names, "no app.add_middleware calls found"
    assert names[-1] == "CORSMiddleware", names


def test_ws_manager_no_dropped_create_task():
    tree = ast.parse(WS_MANAGER.read_text(encoding="utf-8"))
    bare = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr) and _is_create_task_call(node.value)
    ]
    assert bare == [], f"bare asyncio.create_task at lines {bare}"


def test_ws_manager_stores_redis_task():
    tree = ast.parse(WS_MANAGER.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _is_create_task_call(node.value):
            for target in node.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                    and target.attr == "_redis_task"
                ):
                    return
    raise AssertionError("self._redis_task assignment not found")
