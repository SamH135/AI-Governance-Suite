"""AST guard: no bare asyncio.create_task(...) expression statements.

Un-referenced tasks can be garbage-collected mid-run (SonarQube S7502),
silently killing background loops. Tasks must be stored or spawned via
services.shared.async_utils.spawn. Offline: parses source only.
"""
import ast
import sys
from pathlib import Path

root_path = str(Path(__file__).resolve().parent.parent.parent)
if root_path not in sys.path:
    sys.path.insert(0, root_path)

SCAN_DIRS = ("services", "gateway", "shared", "plugins")


def _is_bare_create_task(node):
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == "create_task"
        and isinstance(node.value.func.value, ast.Name)
        and node.value.func.value.id == "asyncio"
    )


def test_no_bare_asyncio_create_task():
    offenders = []
    for dirname in SCAN_DIRS:
        for py_file in Path(root_path, dirname).rglob("*.py"):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if _is_bare_create_task(node):
                    offenders.append(f"{py_file}:{node.lineno}")
    assert offenders == [], f"bare asyncio.create_task: {offenders}"
