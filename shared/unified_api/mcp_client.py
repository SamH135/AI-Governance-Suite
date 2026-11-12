"""MCP client layer — connects to Model Context Protocol servers over stdio
and exposes their tools through the platform's generic manifest format.

Hand-rolled newline-delimited JSON-RPC 2.0 on purpose: every version of the
official ``mcp`` SDK requires ``anyio>=4.5``, which conflicts with this
stack's ``fastapi 0.104.x`` (``anyio<4``). stdio covers local/test servers.

shortcut: no HTTP/SSE transport — add streamable-HTTP support if/when the
platform needs to probe remote MCP servers.
"""

import json
import logging
import os
import queue
import subprocess
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PROTOCOL_VERSION = "2025-06-18"


class MCPToolset:
    """Sync client for one MCP server subprocess.

    Usage::

        ts = MCPToolset().connect(command="python", args=["server.py"])
        manifests = ts.tools()          # [{name, description, parameters}]
        text = ts.call("echo", {"text": "hi"})
        ts.close()
    """

    def __init__(self, call_timeout: float = 60.0):
        self.call_timeout = call_timeout
        self._proc: Optional[subprocess.Popen] = None
        self._write_lock = threading.Lock()
        self._next_id = 0
        self._inbox: "queue.Queue[Dict[str, Any]]" = queue.Queue()

    def connect(
        self,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        url: Optional[str] = None,
        timeout: float = 30.0,
    ) -> "MCPToolset":
        """Spawn the server and complete the MCP initialize handshake."""
        if url:
            raise NotImplementedError("HTTP transport not supported; use stdio command+args")
        if not command:
            raise ValueError("MCPToolset.connect requires command (stdio) or url")

        proc_env = dict(os.environ)
        if env:
            proc_env.update(env)
        self._proc = subprocess.Popen(
            [command, *(args or [])],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            env=proc_env,
        )
        # select() doesn't work on pipes on Windows; a daemon reader thread
        # demultiplexes responses vs server-initiated notifications.
        threading.Thread(target=self._reader, daemon=True).start()

        self._rpc(
            "initialize",
            {
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "ai-governance-suite", "version": "1.0"},
            },
            timeout=timeout,
        )
        self._notify("notifications/initialized")
        logger.info("MCP toolset connected: %s %s", command, " ".join(args or []))
        return self

    def tools(self) -> List[Dict[str, Any]]:
        """List server tools as generic manifests for ModelRequest.tools."""
        result = self._rpc("tools/list")
        return [
            {
                "name": t.get("name"),
                "description": t.get("description", ""),
                "parameters": t.get("inputSchema") or {"type": "object", "properties": {}},
            }
            for t in result.get("tools", [])
        ]

    def call(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> str:
        """Invoke a server tool; returns concatenated text content."""
        result = self._rpc("tools/call", {"name": name, "arguments": arguments or {}}, self.call_timeout)
        parts = [c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"]
        return "\n".join(p for p in parts if p) or json.dumps(result)

    def close(self) -> None:
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                self._proc.kill()
            self._proc = None

    def _reader(self) -> None:
        for line in self._proc.stdout:
            try:
                self._inbox.put(json.loads(line))
            except json.JSONDecodeError:
                continue

    def _send(self, payload: Dict[str, Any]) -> None:
        with self._write_lock:
            self._proc.stdin.write(json.dumps(payload) + "\n")
            self._proc.stdin.flush()

    def _notify(self, method: str) -> None:
        self._send({"jsonrpc": "2.0", "method": method})

    def _rpc(self, method: str, params: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None) -> Dict[str, Any]:
        self._next_id += 1
        req_id = self._next_id
        request: Dict[str, Any] = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params is not None:
            request["params"] = params
        self._send(request)

        deadline = timeout or self.call_timeout
        try:
            while True:
                msg = self._inbox.get(timeout=deadline)
                if msg.get("id") != req_id:
                    continue  # notification or unrelated response
                if "error" in msg:
                    err = msg["error"]
                    raise RuntimeError(f"MCP '{method}' failed: {err.get('message', err)}")
                return msg.get("result", {})
        except queue.Empty:
            if self._proc.poll() is not None:
                raise RuntimeError(f"MCP server exited during '{method}'")
            raise TimeoutError(f"MCP call '{method}' timed out after {deadline}s")

    def __enter__(self) -> "MCPToolset":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
