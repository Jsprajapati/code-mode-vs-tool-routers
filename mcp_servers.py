"""Real MCP servers over Streamable HTTP (official `mcp` Python SDK).

One process hosts every server from catalog.py on its own path:
    http://127.0.0.1:8808/mcp/github, /mcp/jira, /mcp/slack, ...
Extra endpoints for the harness (not part of MCP):
    GET  /__state   -> {"executed": [...], "actions": [...], "requests": {...}}
    POST /__reset   -> clears recorded side effects

Run:  python3 mcp_servers.py [--port 8808] [--pad 0] [--stateful]
  --stateful  uses Mcp-Session-Id sessions held in this process's memory
              (the pre-2026-07-28 default model). Default is stateless HTTP.
  --pad N     pads the catalog with synthetic decoy tools up to N tools in total.
"""
import argparse
import contextlib
import json
from collections import Counter

import uvicorn
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

import catalog as C

REQUESTS = Counter()


def make_server(name, tools):
    async def on_list_tools(ctx, params):
        return types.ListToolsResult(tools=[types.Tool(**t.definition()) for t in tools])

    async def on_call_tool(ctx, params):
        REQUESTS[name] += 1
        try:
            result = C.CATALOG.call(params.name, params.arguments or {})
            return types.CallToolResult(content=[types.TextContent(type="text", text=json.dumps(result, separators=(",", ":")))])
        except Exception as e:  # surface as a tool error, like a real server would
            return types.CallToolResult(content=[types.TextContent(type="text", text="ERROR: %s" % e)], isError=True)

    return Server(name, on_list_tools=on_list_tools, on_call_tool=on_call_tool)


def build_app(pad=0, stateless=True, dept=0):
    if dept:  # department collision catalog (dept_catalog.py) at the given size
        import dept_catalog
        cat = dept_catalog.build(dept)
    else:
        cat = C.build_catalog()
        if pad:
            cat = cat.padded(pad)
    C.CATALOG = cat
    groups = {}
    for t in cat.tools.values():
        groups.setdefault(t.server, []).append(t)

    managers, mounts = {}, []
    for sname, tools in groups.items():
        mgr = StreamableHTTPSessionManager(app=make_server(sname, tools), stateless=stateless, json_response=True)
        managers[sname] = mgr

        async def handler(scope, receive, send, _m=mgr):
            await _m.handle_request(scope, receive, send)

        mounts.append(Mount("/mcp/%s" % sname, app=handler))

    async def state(request):
        return JSONResponse({"executed": C.STATE.executed, "actions": C.STATE.actions,
                             "requests": dict(REQUESTS), "servers": {k: len(v) for k, v in groups.items()}})

    async def reset(request):
        C.STATE.reset()
        REQUESTS.clear()
        return JSONResponse({"ok": True})

    @contextlib.asynccontextmanager
    async def lifespan(app):
        async with contextlib.AsyncExitStack() as stack:
            for m in managers.values():
                await stack.enter_async_context(m.run())
            yield

    return Starlette(routes=[Route("/__state", state), Route("/__reset", reset, methods=["POST"])] + mounts,
                     lifespan=lifespan)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8808)
    ap.add_argument("--pad", type=int, default=0)
    ap.add_argument("--stateful", action="store_true")
    ap.add_argument("--dept", type=int, default=0, help="serve the department collision catalog with this many tools (15, 50, 150)")
    a = ap.parse_args()
    uvicorn.run(build_app(a.pad, stateless=not a.stateful, dept=a.dept), host="127.0.0.1", port=a.port, log_level="warning")
