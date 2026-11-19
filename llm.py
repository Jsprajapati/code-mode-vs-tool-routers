"""Model backends.

ScriptedLLM    A deterministic 'ideal agent'. It always picks the right tool, writes correct code and never
               hallucinates -- so what it measures is only what the SURFACE costs and whether the surface
               even makes the right tools available. It CANNOT measure hallucination or wrong-tool picks.
AnthropicLLM   A real model through the Messages API (set ANTHROPIC_API_KEY). Same surfaces, same servers,
               same scenarios; correctness is judged by the same oracle. This is the one that tests the claims.
"""
import json
import os
import re

SYSTEM = ("You are an assistant with access to company tools (GitHub, Jira, Slack, CRM and more). "
          "Use the tools to complete the request exactly, then answer with only the JSON asked for.")


def _results_of(messages, raw=False):
    """tool_result contents of the latest user turn, in order, parsed if JSON."""
    last = messages[-1]["content"]
    out = []
    for b in last:
        if b.get("type") == "tool_result":
            c = b["content"]
            if raw:
                out.append(c)
                continue
            try:
                out.append(json.loads(c))
            except (TypeError, ValueError):
                out.append(c)
    return out


class ScriptedLLM:
    name = "scripted"
    max_turns = 14

    def __init__(self):
        self._runs = {}

    def _policy(self, strategy, scn):
        if strategy == "router":
            yield [("route_tools", {"request": scn.request})]
        elif strategy == "tool_search":
            yield [("search_tools", {"query": q}) for q in scn.search_queries]
        elif strategy == "code_mode_search":
            yield [("search_api", {"query": q}) for q in scn.search_queries]
        if strategy.startswith("code_mode"):
            out = yield [("execute_code", {"code": scn.program})]
            return out[0] if isinstance(out[0], str) else json.dumps(out[0])
        plan = scn.plan()
        calls = next(plan)
        while True:
            results = yield calls
            try:
                calls = plan.send(results)
            except StopIteration as e:
                return json.dumps(e.value, sort_keys=True)

    async def turn(self, strategy, scn, messages, tools):
        key = (strategy, scn.id)
        if len(messages) == 1:
            self._runs[key] = self._policy(strategy, scn)
            gen, first = self._runs[key], True
        else:
            gen, first = self._runs[key], False
        try:
            if first:
                calls = next(gen)
            else:
                calls = gen.send(_results_of(messages, raw=strategy.startswith("code_mode")))
        except StopIteration as e:
            return {"text": e.value or "", "calls": []}
        visible = {t["name"] for t in tools}
        missing = [n for n, _ in calls if n not in visible]
        if missing:  # the surface never offered the tool the plan needs -> ideal agent cannot proceed
            return {"text": "FAILED: tool(s) not available: %s" % ", ".join(sorted(set(missing))), "calls": []}
        return {"text": "", "calls": [{"id": "t%d_%d" % (len(messages), i), "name": n, "input": a} for i, (n, a) in enumerate(calls)]}


class AnthropicLLM:
    name = "anthropic"
    max_turns = 30

    def __init__(self, model=None):
        import anthropic
        self.client = anthropic.AsyncAnthropic()
        self.model = model or os.environ.get("DEMO_MODEL", "claude-haiku-5-5")

    async def turn(self, strategy, scn, messages, tools):
        resp = await self.client.messages.create(
            model=self.model, max_tokens=8000, system=SYSTEM, tools=tools, messages=messages)
        text, calls = "", []
        for b in resp.content:
            if b.type == "text":
                text += b.text
            elif b.type == "tool_use":
                calls.append({"id": b.id, "name": b.name, "input": b.input})
        return {"text": text, "calls": calls,
                "usage": {"input": resp.usage.input_tokens, "output": resp.usage.output_tokens}}

    async def complete(self, system, prompt):
        """Single-shot completion, used by the LLM router strategy (router_llm)."""
        resp = await self.client.messages.create(
            model=self.model, max_tokens=2000, system=system, messages=[{"role": "user", "content": prompt}])
        return "".join(b.text for b in resp.content if b.type == "text")


class GeminiLLM:
    """Google Gemini through the plain REST API (free tier works). Needs GEMINI_API_KEY (or GOOGLE_API_KEY).

    DEMO_MODEL picks the model (default gemini-2.5-flash; use one your AI Studio lists as free).
    DEMO_MIN_INTERVAL = minimum seconds between calls, to stay under free-tier requests-per-minute (default 4).
    Free-tier limits can still stop a run; the client retries on 429/503 with backoff.
    """
    name = "gemini"
    max_turns = 30

    def __init__(self, model=None):
        import httpx
        self.key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not self.key:
            raise SystemExit("Set GEMINI_API_KEY (get a free key at https://aistudio.google.com/apikey)")
        self.model = model or os.environ.get("DEMO_MODEL", "gemini-2.5-flash")
        self._client = lambda: httpx.AsyncClient(timeout=httpx.Timeout(180, connect=30))
        self.http = self._client()
        self.min_interval = float(os.environ.get("DEMO_MIN_INTERVAL", "4"))
        self._last = 0.0
        self._raw = {}   # tool_use id -> the model's original functionCall part (keeps thought signatures)
        self._names = {}  # tool_use id -> function name
        self._n = 0

    @staticmethod
    def _schema(sch):
        """JSON Schema -> the OpenAPI subset Gemini accepts."""
        t = sch.get("type", "string")
        if t == "object" and not sch.get("properties"):
            return {"type": "STRING", "description": (sch.get("description", "") + " (pass a JSON object as a string)").strip()}
        out = {"type": {"string": "STRING", "integer": "INTEGER", "number": "NUMBER", "boolean": "BOOLEAN",
                        "array": "ARRAY", "object": "OBJECT"}.get(t, "STRING")}
        if sch.get("description"):
            out["description"] = sch["description"]
        if t == "array":
            out["items"] = GeminiLLM._schema(sch.get("items") or {"type": "string"})
        if t == "object":
            out["properties"] = {k: GeminiLLM._schema(v) for k, v in sch["properties"].items()}
            if sch.get("required"):
                out["required"] = list(sch["required"])
        return out

    def _decl(self, t):
        d = {"name": t["name"], "description": t["description"]}
        props = t["input_schema"].get("properties") or {}
        if props:
            d["parameters"] = self._schema({"type": "object", "properties": props,
                                            "required": t["input_schema"].get("required", [])})
        return d

    def _contents(self, messages):
        out = []
        for m in messages:
            if isinstance(m["content"], str):
                out.append({"role": "user", "parts": [{"text": m["content"]}]})
                continue
            parts = []
            for b in m["content"]:
                if b["type"] == "text":
                    parts.append({"text": b["text"]})
                elif b["type"] == "tool_use":
                    parts.append(self._raw.get(b["id"]) or {"functionCall": {"name": b["name"], "args": b["input"]}})
                elif b["type"] == "tool_result":
                    parts.append({"functionResponse": {"name": self._names.get(b["tool_use_id"], "tool"),
                                                       "response": {"result": b["content"]}}})
            out.append({"role": "model" if m["role"] == "assistant" else "user", "parts": parts})
        return out

    async def _post(self, body):
        import asyncio
        import time

        import httpx
        url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % self.model
        for attempt in range(7):
            wait = self.min_interval - (time.time() - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.time()
            try:
                r = await self.http.post(url, json=body, headers={"x-goog-api-key": self.key})
            except httpx.TransportError as e:  # dropped connection, reset, timeout: retry on a fresh connection
                wait_s = 5 * (attempt + 1)
                print("  [gemini] network error (%s); new connection, retry in %ds" % (type(e).__name__, wait_s), flush=True)
                await self.http.aclose()
                self.http = self._client()
                await asyncio.sleep(wait_s)
                continue
            if r.status_code in (429, 500, 503):
                print("  [gemini] HTTP %d (rate limit or busy); waiting before retry" % r.status_code, flush=True)
                delay = min(60, 5 * 2 ** attempt)
                m = re.search(r'"retryDelay":\s*"(\d+(?:\.\d+)?)s"', r.text)
                if m:
                    delay = min(90, float(m.group(1)) + 1)
                await asyncio.sleep(delay)
                continue
            if r.status_code != 200:
                raise RuntimeError("Gemini HTTP %d: %s" % (r.status_code, r.text[:300]))
            self._last = time.time()
            return r.json()
        raise RuntimeError("Gemini: still rate-limited after retries (free-tier quota?)")

    async def turn(self, strategy, scn, messages, tools):
        body = {"systemInstruction": {"parts": [{"text": SYSTEM}]},
                "contents": self._contents(messages),
                "generationConfig": {"temperature": 0}}
        if tools:
            body["tools"] = [{"functionDeclarations": [self._decl(t) for t in tools]}]
        data = await self._post(body)
        cand = (data.get("candidates") or [{}])[0]
        text, calls = "", []
        for part in (cand.get("content") or {}).get("parts", []):
            if "functionCall" in part:
                self._n += 1
                cid = "g%d" % self._n
                fc = part["functionCall"]
                self._raw[cid] = part
                self._names[cid] = fc["name"]
                calls.append({"id": cid, "name": fc["name"], "input": fc.get("args") or {}})
            elif part.get("text") and not part.get("thought"):
                text += part["text"]
        u = data.get("usageMetadata", {})
        return {"text": text, "calls": calls,
                "usage": {"input": u.get("promptTokenCount", 0), "output": u.get("candidatesTokenCount", 0)}}


CLI_SYSTEM = ("You are an assistant that completes tasks by calling tools. You only see the conversation given to you. "
              "Reply with EXACTLY ONE JSON object and nothing else (no markdown, no commentary). Either "
              '{"tool_calls":[{"name":"<tool name>","input":{...}}, ...]} to call one or more tools (independent calls may be '
              'batched in one reply), or {"final":"<your final answer>"} when the task is complete. The final answer must be '
              "exactly in the format the task asks for. Only call tools that appear in the tool list.")
ROUTER_SYSTEM = ("You are a tool router. Given a user request and a shortlist of candidate tools, choose the tools needed to "
                 "complete the request and return them in the order they should be used. Prefer the tool from the department "
                 "the request is about. Include any tool needed for a step the user left unsaid (for example a lookup that must "
                 "come before an action). Reply with ONLY a JSON array of tool names.")


def _loads_obj(text):
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t)
    except ValueError:
        pass
    a, b = t.find("{"), t.rfind("}")
    if a != -1 and b > a:
        try:
            return json.loads(t[a:b + 1])
        except ValueError:
            return None
    return None


def _parse_invoke(text):
    """Claude sometimes answers in its native XML tool format (<invoke name=...><parameter name=...>) instead of our JSON.
    The intent is unambiguous, so recover it rather than count a formatting slip as a capability failure."""
    calls = []
    for name, body in re.findall(r'<invoke name="([^"]+)">(.*?)</invoke>', text, re.S):
        args = {}
        for k, v in re.findall(r'<parameter name="([^"]+)">(.*?)</parameter>', body, re.S):
            try:
                args[k] = json.loads(v)
            except ValueError:
                args[k] = v
        calls.append({"name": name, "input": args})
    return {"tool_calls": calls} if calls else None


class ClaudeCLI:
    """Real Claude models (Haiku, Sonnet, ...) through the headless Claude Code CLI: `claude -p`, no API key.

    Tool calling is EMULATED: the tool list goes into the prompt as JSON and the model replies with one JSON object
    (tool_calls or final). Every strategy gets the same protocol, so comparisons between strategies are fair, but this is
    not the native tool-use format. Tokens are counted with the same chars/4 estimate as every other backend (the CLI's own
    usage includes ~13K tokens of fixed overhead that would swamp the comparison); the CLI's reported cost is kept separately.
    """
    max_turns = 20

    def __init__(self, model="haiku", cwd=None):
        self.model = model
        self.name = "claude-" + model
        self.cwd = cwd or os.environ.get("DEMO_CLI_CWD") or "/tmp"
        self.cost = 0.0
        self._n = 0
        self.cli_calls = 0

    async def _run(self, system, prompt, timeout=300):
        import asyncio
        cmd = ["claude", "-p", "--model", self.model, "--tools", "", "--system-prompt", system, "--no-session-persistence",
               "--strict-mcp-config", "--disable-slash-commands", "--no-chrome", "--output-format", "json"]
        last = ""
        for attempt in range(5):
            env = dict(os.environ, CLAUDE_CODE_ENABLE_CFC="0")  # no browser tools: the model must see only the emulated tools
            proc = await asyncio.create_subprocess_exec(*cmd, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                                                        stderr=asyncio.subprocess.PIPE, cwd=self.cwd, env=env)
            try:
                out, err = await asyncio.wait_for(proc.communicate(prompt.encode()), timeout)
            except asyncio.TimeoutError:
                proc.kill()
                last = "timeout"
                await asyncio.sleep(3)
                continue
            self.cli_calls += 1
            try:
                d = json.loads(out.decode() or "{}")
            except ValueError:
                d = {}
            if proc.returncode == 0 and d.get("result") is not None and not d.get("is_error"):
                self.cost += d.get("total_cost_usd") or 0.0
                return d["result"], (d.get("total_cost_usd") or 0.0)
            last = (d.get("result") or err.decode() or out.decode())[:200]
            print("  [claude-cli] attempt %d failed (%s); retrying" % (attempt + 1, last.replace("\n", " ")[:120]), flush=True)
            await asyncio.sleep(5 * (attempt + 1))
        raise RuntimeError("claude CLI failed after retries: %s" % last)

    async def complete(self, system, prompt):
        text, cost = await self._run(system, prompt)
        return text

    @staticmethod
    def _render(messages):
        names, parts = {}, []
        for m in messages:
            if isinstance(m["content"], str):
                parts.append("[USER]\n" + m["content"])
                continue
            if m["role"] == "assistant":
                calls = []
                for b in m["content"]:
                    if b["type"] == "tool_use":
                        names[b["id"]] = b["name"]
                        calls.append({"name": b["name"], "input": b["input"]})
                    elif b["type"] == "text" and b["text"]:
                        parts.append("[ASSISTANT]\n" + b["text"])
                if calls:
                    parts.append("[ASSISTANT TOOL CALLS]\n" + json.dumps({"tool_calls": calls}))
            else:
                res = ["%s -> %s" % (names.get(b["tool_use_id"], "tool"), b["content"]) for b in m["content"] if b["type"] == "tool_result"]
                parts.append("[TOOL RESULTS, in the same order as the calls]\n" + "\n".join(res))
        return "\n\n".join(parts)

    async def turn(self, strategy, scn, messages, tools):
        prompt = ("TOOLS (JSON):\n" + json.dumps(tools) + "\n\nCONVERSATION:\n" + self._render(messages) +
                  "\n\nReply now with your next single JSON object.")
        text, cost = await self._run(CLI_SYSTEM, prompt)
        obj = _loads_obj(text)
        if not isinstance(obj, dict) or not ("tool_calls" in obj or "final" in obj):
            obj = _parse_invoke(text)
        if not isinstance(obj, dict) or not ("tool_calls" in obj or "final" in obj):
            text2, cost2 = await self._run(CLI_SYSTEM, prompt + "\n\nYour previous reply was not a single valid JSON object "
                                           'of the form {"tool_calls":[...]} or {"final":"..."}. Reply again with exactly that.')
            cost += cost2
            obj = _loads_obj(text2) or _parse_invoke(text2)
            if not isinstance(obj, dict) or not ("tool_calls" in obj or "final" in obj):
                return {"text": text2 or text, "calls": [], "cost": cost}
        calls = []
        for c in obj.get("tool_calls") or []:
            if isinstance(c, dict) and c.get("name"):
                self._n += 1
                inp = c.get("input")
                calls.append({"id": "c%d" % self._n, "name": c["name"], "input": inp if isinstance(inp, dict) else {}})
        if calls:
            return {"text": "", "calls": calls, "cost": cost}
        fin = obj.get("final", "")
        return {"text": fin if isinstance(fin, str) else json.dumps(fin), "calls": [], "cost": cost}


def extract_json(text):
    """Pull the last JSON value out of a model's final text."""
    text = text.strip()
    try:
        return json.loads(text)
    except ValueError:
        pass
    m = re.search(r"(\[.*\]|\{.*\}|\".*\")\s*```?\s*$", text, re.S) or re.search(r"(\[.*\]|\{.*\}|\".*\")", text, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except ValueError:
            return None
    return None
