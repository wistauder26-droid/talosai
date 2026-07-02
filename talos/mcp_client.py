"""MCP-Anbindung: externe Tool-Server (Model Context Protocol).

Konfiguration in data/settings.json unter "mcp_servers":
  [{"name": "files", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/Users/me"]},
   {"name": "remote", "url": "https://example.com/mcp"}]

Alle Tools der verbundenen Server erscheinen für den Agenten als
mcp__<server>__<tool>. Verbindungen laufen in einem Hintergrund-Eventloop.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from contextlib import AsyncExitStack
from typing import Any

log = logging.getLogger("talos.mcp")

_manager: "MCPManager | None" = None
_manager_sig: str = ""


def get_manager(servers: list[dict]) -> "MCPManager | None":
    """Gecachter Manager; wird bei geänderter Konfiguration neu aufgebaut."""
    global _manager, _manager_sig
    if not servers:
        return None
    sig = json.dumps(servers, sort_keys=True)
    if _manager is None or sig != _manager_sig:
        _manager = MCPManager(servers)
        _manager_sig = sig
    return _manager


class MCPManager:
    def __init__(self, servers: list[dict]):
        self.tools: list[tuple[str, Any]] = []  # (server_name, mcp-Tool)
        self.sessions: dict[str, Any] = {}
        self.errors: dict[str, str] = {}
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True).start()
        try:
            asyncio.run_coroutine_threadsafe(
                self._connect_all(servers), self.loop
            ).result(timeout=60)
        except Exception as e:
            self.errors["__init__"] = str(e)

    async def _connect_all(self, servers: list[dict]) -> None:
        self._stack = AsyncExitStack()
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        for srv in servers:
            name = srv.get("name", "server")
            try:
                if srv.get("url"):
                    from mcp.client.streamable_http import streamablehttp_client
                    read, write, _ = await self._stack.enter_async_context(
                        streamablehttp_client(srv["url"])
                    )
                else:
                    params = StdioServerParameters(
                        command=srv["command"], args=srv.get("args", []),
                        env=srv.get("env"),
                    )
                    read, write = await self._stack.enter_async_context(stdio_client(params))
                session = await self._stack.enter_async_context(ClientSession(read, write))
                await asyncio.wait_for(session.initialize(), timeout=20)
                result = await session.list_tools()
                self.sessions[name] = session
                for tool in result.tools:
                    self.tools.append((name, tool))
                log.info("MCP '%s': %d Tools", name, len(result.tools))
            except Exception as e:
                self.errors[name] = f"{type(e).__name__}: {e}"
                log.warning("MCP '%s' nicht erreichbar: %s", name, e)

    def tool_defs(self) -> list[dict]:
        defs = []
        for srv, tool in self.tools:
            defs.append({
                "type": "function",
                "function": {
                    "name": f"mcp__{srv}__{tool.name}",
                    "description": (tool.description or "")[:1000],
                    "parameters": tool.inputSchema
                    or {"type": "object", "properties": {}},
                },
            })
        return defs

    def call(self, full_name: str, args: dict) -> str:
        try:
            _, srv, tool = full_name.split("__", 2)
        except ValueError:
            return f"Ungültiger MCP-Tool-Name: {full_name}"
        session = self.sessions.get(srv)
        if session is None:
            return f"MCP-Server '{srv}' nicht verbunden."
        try:
            result = asyncio.run_coroutine_threadsafe(
                session.call_tool(tool, args), self.loop
            ).result(timeout=120)
            parts = []
            for c in result.content:
                parts.append(getattr(c, "text", None) or str(c))
            return "\n".join(parts)[:8000] or "(leeres Ergebnis)"
        except Exception as e:
            return f"FEHLER (MCP {srv}): {type(e).__name__}: {e}"

    def status(self) -> dict:
        return {
            "servers": sorted({s for s, _ in self.tools}),
            "tools": len(self.tools),
            "errors": self.errors,
        }
