"""A real MCP client hub: connects to every server over Streamable HTTP with the official SDK."""
import contextlib
import json

import httpx
from mcp import ClientSession

try:  # SDK renamed this helper in newer releases
    from mcp.client.streamable_http import streamable_http_client as _http
except ImportError:  # pragma: no cover
    from mcp.client.streamable_http import streamablehttp_client as _http


def tok(s):
    """Token estimate: ~4 characters per token. Consistent across strategies; not a tokenizer."""
    return (len(s) + 3) // 4


class ToolError(Exception):
    pass


class Hub:
    def __init__(self, base="http://127.0.0.1:8808"):
        self.base = base
        self.defs = {}         # name -> Anthropic-format tool definition
        self.server_of = {}    # name -> server name
        self.returns = {}      # name -> return shape string from the tool's meta (None if the server gives none)
        self.sessions = {}
        self.mcp_calls = 0
        self.called = []       # names of every tool actually called on the servers
        self.result_chars = 0
        self._stack = contextlib.AsyncExitStack()

    async def __aenter__(self):
        async with httpx.AsyncClient() as h:
            servers = (await h.get(self.base + "/__state")).json()["servers"]
        for s in servers:
            streams = await self._stack.enter_async_context(_http("%s/mcp/%s" % (self.base, s)))
            sess = await self._stack.enter_async_context(ClientSession(streams[0], streams[1]))
            await sess.initialize()
            self.sessions[s] = sess
            for t in (await sess.list_tools()).tools:
                self.defs[t.name] = {"name": t.name, "description": t.description or "",
                                     "input_schema": t.input_schema}
                self.server_of[t.name] = s
                self.returns[t.name] = (t.meta or {}).get("returns")
        return self

    async def __aexit__(self, *exc):
        await self._stack.aclose()

    async def call(self, name, args):
        """Real MCP tools/call. Returns the raw text the server sent back."""
        if name not in self.server_of:
            raise ToolError("unknown tool: %s" % name)
        self.called.append(name)
        res = await self.sessions[self.server_of[name]].call_tool(name, args)
        text = "".join(c.text for c in res.content if getattr(c, "type", "") == "text")
        self.mcp_calls += 1
        self.result_chars += len(text)
        if res.is_error or text.startswith("ERROR:"):
            raise ToolError(text)
        return text

    async def call_json(self, name, args):
        text = await self.call(name, args)
        try:
            return json.loads(text)
        except ValueError:
            return text
