"""Run every strategy on every scenario against REAL MCP servers over HTTP.

    python3 bench.py                      # scripted ideal agent, 63-tool catalog
    python3 bench.py --llm anthropic      # real model (needs ANTHROPIC_API_KEY)
    python3 bench.py --sweep              # repeat at 63 / 150 / 300 tools
    python3 bench.py --only S4,S5 --strategies all_tools,code_mode

Metrics per (strategy, scenario):
  correct        final answer == oracle AND side effects (Jira issues, Slack posts) == oracle
  turns          model round trips
  peak_ctx       largest context sent in one turn (system + tool defs + messages), ~tokens
  cum_input      sum of context over all turns = input tokens billed with no caching, ~tokens
  out            ~tokens the model had to generate (tool calls / code / answer)
  mcp_calls      real tools/call requests that hit the MCP servers
Token counts are ~chars/4 estimates, applied identically to every strategy.
"""
import argparse
import asyncio
import json
import os
import subprocess
import sys
import time

import httpx

import scenarios as S
from llm import SYSTEM, AnthropicLLM, GeminiLLM, ScriptedLLM, extract_json
from mcp_hub import Hub, tok
from surfaces import SURFACES

HERE = os.path.dirname(os.path.abspath(__file__))
ORDER = ["all_tools", "router", "tool_search", "code_mode", "code_mode_search"]
LABEL = {"all_tools": "All tools (plain MCP)", "router": "Tool router", "tool_search": "Tool search (lazy)",
         "code_mode": "Code Mode (stubs)", "code_mode_search": "Code Mode (search+exec)"}


def start_server(port, pad, stateful=False):
    cmd = [sys.executable, os.path.join(HERE, "mcp_servers.py"), "--port", str(port), "--pad", str(pad)]
    if stateful:
        cmd.append("--stateful")
    p = subprocess.Popen(cmd, cwd=HERE)
    base = "http://127.0.0.1:%d" % port
    for _ in range(100):
        try:
            httpx.get(base + "/__state", timeout=1)
            return p, base
        except Exception:
            time.sleep(0.1)
    p.kill()
    raise RuntimeError("server did not start")


async def run_one(base, strategy, scn, llm):
    async with httpx.AsyncClient() as h:
        await h.post(base + "/__reset")
    async with Hub(base) as hub:
        surface = SURFACES[strategy](hub)
        messages = [{"role": "user", "content": scn.prompt}]
        m = {"real_in": 0, "real_out": 0, "turns": 0, "peak_ctx": 0, "cum_input": 0, "out": 0, "first_ctx": 0, "tool_def_tokens": 0,
             "router_in": 0, "router_out": 0, "tool_errors": 0, "cli_cost": 0.0}
        final, t0, last_out = "", time.time(), ""
        if hasattr(surface, "prepare"):  # phase-1/2 router: runs before the main model, its LLM call is billed too
            info = await surface.prepare(scn.request, llm)
            m["router_in"], m["router_out"] = info["router_in"], info["router_out"]
            m["router_chosen"] = info["router_chosen"]
        for _ in range(getattr(llm, "max_turns", 14)):
            tools = surface.visible_tools()
            tdefs = tok(json.dumps(tools))
            ctx = tok(SYSTEM) + tdefs + tok(json.dumps(messages))
            if m["turns"] == 0:
                m["first_ctx"], m["tool_def_tokens"] = ctx, tdefs
            m["turns"] += 1
            m["peak_ctx"] = max(m["peak_ctx"], ctx)
            m["cum_input"] += ctx
            resp = await llm.turn(strategy, scn, messages, tools)
            m["out"] += tok(resp["text"] + json.dumps(resp["calls"]))
            m["cli_cost"] += resp.get("cost", 0.0)
            if resp.get("usage"):
                m["real_in"] += resp["usage"]["input"]
                m["real_out"] += resp["usage"]["output"]
            if not resp["calls"]:
                final = resp["text"]
                break
            blocks = ([{"type": "text", "text": resp["text"]}] if resp["text"] else []) + \
                     [{"type": "tool_use", "id": c["id"], "name": c["name"], "input": c["input"]} for c in resp["calls"]]
            messages.append({"role": "assistant", "content": blocks})
            results = []
            for c in resp["calls"]:
                out = await surface.handle(c["name"], c["input"])
                last_out = out
                if str(out).startswith("ERROR") or "\nERROR:" in str(out):
                    m["tool_errors"] += 1
                results.append({"type": "tool_result", "tool_use_id": c["id"], "content": out})
            messages.append({"role": "user", "content": results})
        mcp_calls = hub.mcp_calls
        called = list(hub.called)
        result_tokens = hub.result_chars // 4
    async with httpx.AsyncClient() as h:
        st = (await h.get(base + "/__state")).json()
    actions = sorted(tuple(a) for a in st["actions"])
    expected_actions = sorted(tuple(a) for a in scn.expected_actions)
    answer = extract_json(final)
    ans_ok = answer == scn.expected_answer
    act_ok = actions == expected_actions
    note = ""
    if final.startswith("FAILED"):
        note = final
    elif not ans_ok:
        note = "wrong answer: model said %r; last tool output %r" % (final[:70], last_out[:90])
    elif not act_ok:
        note = "wrong side effects (%d vs %d expected)" % (len(actions), len(expected_actions))
    right = getattr(scn, "right_tools", None)
    m["wrong_calls"] = len([n for n in called if right is not None and n not in right])
    m["called"] = called
    marker = getattr(scn, "pii_marker", "")
    if marker:
        import re as _re
        seen = set(_re.findall(r"[\w.]+" + _re.escape(marker), json.dumps(messages)))
        m["pii_seen"] = len(seen)
    m["final"] = final[:300]
    m["cum_input"] += m["router_in"]
    m["out"] += m["router_out"]
    m.update(correct=ans_ok and act_ok, mcp_calls=mcp_calls, mcp_result_tokens=result_tokens,
             secs=round(time.time() - t0, 2), note=note)
    return m


def table(rows, headers):
    w = [max(len(str(r[i])) for r in [headers] + rows) for i in range(len(headers))]
    line = lambda r: "  ".join(str(c).rjust(w[i]) if i else str(c).ljust(w[i]) for i, c in enumerate(r))
    return "\n".join([line(headers), "  ".join("-" * x for x in w)] + [line(r) for r in rows])


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", default="scripted", choices=["scripted", "anthropic", "gemini"])
    ap.add_argument("--port", type=int, default=8808)
    ap.add_argument("--pad", type=int, default=0)
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--router-k", type=int, default=2)
    ap.add_argument("--only", default="")
    ap.add_argument("--strategies", default=",".join(ORDER))
    ap.add_argument("--out", default="results.json")
    a = ap.parse_args()
    SURFACES["router"].K = a.router_k
    scs = [s for s in S.ALL if not a.only or s.id in a.only.split(",")]
    strategies = a.strategies.split(",")
    pads = [0, 150, 300] if a.sweep else [a.pad]
    allres = {}
    for pad in pads:
        proc, base = start_server(a.port, pad)
        try:
            llm = {"scripted": ScriptedLLM, "anthropic": AnthropicLLM, "gemini": GeminiLLM}[a.llm]()
            res = {}
            for sc in scs:
                for st in strategies:
                    if a.llm != "scripted":
                        print("running %s / %s ..." % (sc.id, st), flush=True)
                    res[(sc.id, st)] = await run_one(base, st, sc, llm)
            state = httpx.get(base + "/__state").json()
            n_tools = sum(state["servers"].values())
        finally:
            proc.kill()
            proc.wait()
        allres[n_tools] = res
        print("\n##### catalog: %d tools across %d MCP servers | model: %s #####" % (n_tools, len(state["servers"]), llm.name))
        if not a.sweep:
            for sc in scs:
                print("\n%s  %s  [%s]\n  %s" % (sc.id, sc.title, sc.kind, sc.request))
                rows = []
                for st in strategies:
                    r = res[(sc.id, st)]
                    rows.append([LABEL[st], "yes" if r["correct"] else "NO", r["turns"], r["mcp_calls"], r["peak_ctx"],
                                 r["cum_input"], r["out"], r["note"]])
                print(table(rows, ["strategy", "correct", "turns", "mcp_calls", "peak_ctx", "cum_input", "out", "note"]))
        print("\nTOTALS over %d scenarios" % len(scs))
        rows = []
        for st in strategies:
            rs = [res[(sc.id, st)] for sc in scs]
            rows.append([LABEL[st], "%d/%d" % (sum(r["correct"] for r in rs), len(rs)), rs[0]["tool_def_tokens"],
                         sum(r["cum_input"] for r in rs), max(r["peak_ctx"] for r in rs), sum(r["turns"] for r in rs),
                         sum(r["out"] for r in rs)])
        print(table(rows, ["strategy", "correct", "tool_defs/turn1", "cum_input", "peak_ctx", "turns", "out"]))
        if a.llm != "scripted":
            print("\nProvider-reported token usage (real, from the API):")
            rows = []
            for st in strategies:
                rs = [res[(sc.id, st)] for sc in scs]
                rows.append([LABEL[st], sum(r["real_in"] for r in rs), sum(r["real_out"] for r in rs)])
            print(table(rows, ["strategy", "input_tokens", "output_tokens"]))
    with open(os.path.join(HERE, a.out), "w") as f:
        json.dump({str(n): {"%s|%s" % k: v for k, v in r.items()} for n, r in allres.items()}, f, indent=1)


if __name__ == "__main__":
    asyncio.run(main())
