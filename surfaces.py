"""The five ways of putting the same MCP servers in front of a model.

A Surface decides (a) which tool definitions the model can see on each turn and
(b) what happens when it calls one. The servers, protocol and tools underneath are identical.

  all_tools          plain MCP: every definition from every server is in context
  router             a router sits in front; the model describes the request, the router returns
                     an ordered tool set, and only those definitions are enabled
  tool_search        lazy loading: the model searches for capabilities and loads what it finds
  code_mode          one tool, execute_code; the whole API is given as short typed stubs
  code_mode_search   server-side Code Mode form: search_api + execute_code (Cloudflare's shape)
"""
import json
import os

import sandbox
from mcp_hub import ToolError
from mcp_hub import tok
from retrieval import BM25, ToolRouter


TYPED = os.environ.get("DEMO_TYPED_STUBS", "") in ("1", "2")   # Code Mode stubs include return shapes (like a typed API)
PARAM_DOCS = os.environ.get("DEMO_TYPED_STUBS") == "2"          # ...and the parameter descriptions the plain tool definitions carry


def _stub(d, returns=None):
    props = d["input_schema"].get("properties", {})
    req = set(d["input_schema"].get("required", []))
    pytype = {"string": "str", "integer": "int", "boolean": "bool", "array": "list", "number": "float", "object": "dict"}
    args = ", ".join("%s%s: %s%s" % (k, "" if k in req else "?", pytype.get(v.get("type"), "any"),
                                     (" /*%s*/" % v["description"]) if PARAM_DOCS and v.get("description") else "") for k, v in props.items())
    first = d["description"].split(". ")[0].rstrip(".")
    ret = " -> %s" % returns if (TYPED and returns) else ""
    return "tools.%s(%s)%s  # %s" % (d["name"], args, ret, first)


CODE_HELP = ("Write Python that calls the API below via `tools.<name>(**kwargs)`; each call returns parsed JSON "
             "(dicts/lists). Use loops, filters and aggregation inside the code and print() ONLY the final result "
             "as JSON. No file or network access; json, math, re, statistics, datetime and collections can be imported. "
             "Only printed output comes back to you.")

SEARCH_API = {"name": "search_api", "description": "Search the available API by keywords; returns matching function stubs you can call from execute_code.",
              "input_schema": {"type": "object", "properties": {"query": {"type": "string", "description": "What you need to do"}}, "required": ["query"]}}
ROUTE = {"name": "route_tools", "description": "Describe the user's whole request; returns the ordered list of tools to use for it and enables them.",
         "input_schema": {"type": "object", "properties": {"request": {"type": "string", "description": "The user's request"}}, "required": ["request"]}}
SEARCH_TOOLS = {"name": "search_tools", "description": "Search for tools by capability. Matching tools are enabled for the following turns.",
                "input_schema": {"type": "object", "properties": {"query": {"type": "string", "description": "Capability you need"}}, "required": ["query"]}}


def _exec_def(description):
    return {"name": "execute_code", "description": description,
            "input_schema": {"type": "object", "properties": {"code": {"type": "string", "description": "Python source"}}, "required": ["code"]}}


class Surface:
    name = ""

    def __init__(self, hub):
        self.hub = hub
        self.defs = hub.defs
        self.extra = {}  # per-run counters

    def visible_tools(self):
        raise NotImplementedError

    async def handle(self, name, args):
        raise NotImplementedError

    def visible_names(self):
        return {t["name"] for t in self.visible_tools()}

    async def _mcp(self, name, args):
        if name not in self.visible_names():
            return "ERROR: tool '%s' is not available in this session" % name
        try:
            return await self.hub.call(name, args)
        except ToolError as e:
            return str(e)


class AllTools(Surface):
    name = "all_tools"

    def visible_tools(self):
        return list(self.defs.values())

    async def handle(self, name, args):
        return await self._mcp(name, args)


class Router(Surface):
    name = "router"
    K = 2  # tools returned per intent; bench.py --router-k overrides

    def __init__(self, hub):
        super().__init__(hub)
        self.router = ToolRouter(self.defs, k=self.K)
        self.enabled = []

    def visible_tools(self):
        return [ROUTE] + [self.defs[n] for n in self.enabled]

    async def handle(self, name, args):
        if name == "route_tools":
            r = self.router.route(args.get("request", ""))
            for n in r["tools"]:
                if n not in self.enabled:
                    self.enabled.append(n)
            return json.dumps({"use_in_order": [{"intent": p["intent"], "tools": p["tools"], "similar": p["similar"]}
                                                for p in r["plan"]]}, separators=(",", ":"))
        return await self._mcp(name, args)


class ToolSearch(Surface):
    name = "tool_search"

    def __init__(self, hub, limit=5):
        super().__init__(hub)
        self.index = BM25(self.defs)
        self.loaded = []
        self.limit = limit

    def visible_tools(self):
        return [SEARCH_TOOLS] + [self.defs[n] for n in self.loaded]

    async def handle(self, name, args):
        if name == "search_tools":
            hits = self.index.search(args.get("query", ""), self.limit)
            for n, _ in hits:
                if n not in self.loaded:
                    self.loaded.append(n)
            return json.dumps({"loaded": [n for n, _ in hits]}, separators=(",", ":"))
        return await self._mcp(name, args)


class CodeMode(Surface):
    name = "code_mode"

    def visible_tools(self):
        stubs = "\n".join(_stub(d, self.hub.returns.get(d["name"])) for d in self.defs.values())
        return [_exec_def(CODE_HELP + "\n\nAPI:\n" + stubs)]

    async def _bind(self, name, args):
        return await self.hub.call_json(name, args)

    async def handle(self, name, args):
        if name != "execute_code":
            return "ERROR: tool '%s' is not available in this session" % name
        res = await sandbox.run_code(args.get("code", ""), self._bind)
        self.extra["sandbox_calls"] = self.extra.get("sandbox_calls", 0) + res.get("tool_calls", 0)
        out = res.get("done", "")
        return out + (("\nERROR: " + res["error"]) if res.get("error") else "")


class CodeModeSearch(CodeMode):
    name = "code_mode_search"

    def __init__(self, hub, limit=5):
        super().__init__(hub)
        self.index = BM25(self.defs)
        self.limit = limit

    def visible_tools(self):
        return [SEARCH_API, _exec_def(CODE_HELP + "\n\nFunctions you find with search_api are available as tools.<name>(...).")]

    async def handle(self, name, args):
        if name == "search_api":
            hits = self.index.search(args.get("query", ""), self.limit)
            return "\n".join(_stub(self.defs[n], self.hub.returns.get(n)) for n, _ in hits) or "no matches"
        return await super().handle(name, args)


class HybridRouter(Surface):
    """Two-phase router that runs BEFORE the model sees anything (it is not a tool the model calls).

    Phase 1 (no LLM): BM25 over all tool definitions, then keep only tools from the best-matching departments
                      (a department = the MCP server a tool lives on) -> a shortlist.
    Phase 2 (one LLM call): the request plus the shortlist go to an LLM that returns the tools to use, in order.
    Only those tools are then enabled for the main model, which does the actual tool calling.
    The phase-2 call is counted as extra tokens (router_in / router_out)."""
    name = "router_llm"
    DEPTS, SHORTLIST = 3, 15

    def __init__(self, hub):
        super().__init__(hub)
        self.index = BM25(self.defs)
        self.enabled = []
        self.info = {}

    async def prepare(self, request, llm):
        hits = self.index.search(request, limit=len(self.defs))
        score = {}
        for n, s in hits:
            d = self.hub.server_of[n]
            score[d] = score.get(d, 0.0) + s
        keep = {d for d, _ in sorted(score.items(), key=lambda x: -x[1])[: self.DEPTS]}
        cand = [n for n, _ in hits if self.hub.server_of[n] in keep][: self.SHORTLIST]
        listing = [{"name": n, "department": self.hub.server_of[n], "description": self.defs[n]["description"]} for n in cand]
        from llm import ROUTER_SYSTEM, _loads_obj
        prompt = "REQUEST:\n%s\n\nCANDIDATE TOOLS (JSON):\n%s\n\nReturn the JSON array of tool names to use, in order." % (request, json.dumps(listing))
        text = await llm.complete(ROUTER_SYSTEM, prompt)
        names = _loads_obj(text) if text.strip().startswith("{") else None
        if names is None:
            try:
                a, b = text.find("["), text.rfind("]")
                names = json.loads(text[a:b + 1])
            except ValueError:
                names = None
        names = [n for n in (names or []) if n in cand]
        self.enabled = names or cand[:5]
        self.info = {"router_in": tok(ROUTER_SYSTEM) + tok(prompt), "router_out": tok(text), "router_candidates": cand,
                     "router_chosen": list(self.enabled), "router_fallback": not names}
        return self.info

    def visible_tools(self):
        return [self.defs[n] for n in self.enabled]

    async def handle(self, name, args):
        return await self._mcp(name, args)


SURFACES = {c.name: c for c in (AllTools, Router, HybridRouter, ToolSearch, CodeMode, CodeModeSearch)}
