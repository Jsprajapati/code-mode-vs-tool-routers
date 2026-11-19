"""Department collision evaluation with a real model (Claude through the headless CLI).

    python3 dept_bench.py --model haiku --sizes 15,50,150 --reps 2 --workers 6 --out results_dept_haiku.jsonl
    ANTHROPIC_API_KEY=... python3 dept_bench.py --llm anthropic --model claude-haiku-5-5 --suite x500 --sizes 500 --reps 1

One JSON line per run is appended to --out, so a long run can be stopped and resumed (finished runs are skipped).
Each worker owns its own MCP server process (side effects are recorded per process), so runs never interfere.
"""
import argparse
import asyncio
import json
import os
import subprocess
import sys
import time

import httpx

import dept_scenarios as DS
import dept_scenarios500 as DS500
from bench import run_one
from llm import AnthropicLLM, ClaudeCLI
from surfaces import SURFACES

HERE = os.path.dirname(os.path.abspath(__file__))
ORDER = ["all_tools", "router", "router_llm", "tool_search", "code_mode", "code_mode_search"]


def start_server(port, size):
    p = subprocess.Popen([sys.executable, os.path.join(HERE, "mcp_servers.py"), "--port", str(port), "--dept", str(size)], cwd=HERE)
    base = "http://127.0.0.1:%d" % port
    for _ in range(150):
        try:
            httpx.get(base + "/__state", timeout=1)
            return p, base
        except Exception:
            time.sleep(0.1)
    p.kill()
    raise RuntimeError("server did not start")


def key(r):
    return "%s|%s|%s|%s|%s" % (r["model"], r["size"], r["strategy"], r["scenario"], r["rep"])


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", default="cli", choices=["cli", "anthropic"],
                    help="cli = headless Claude Code (`claude -p`, how the article's numbers were made); anthropic = Messages API with a key")
    ap.add_argument("--model", default="haiku")
    ap.add_argument("--sizes", default="15,50,150")
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--port", type=int, default=8900)
    ap.add_argument("--only", default="")
    ap.add_argument("--strategies", default=",".join(ORDER))
    ap.add_argument("--router-k", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--suite", default="base", choices=["base", "x500"])
    ap.add_argument("--tag", default="", help="suffix added to the strategy name in the records (e.g. _typed)")
    ap.add_argument("--out", default="results_dept.jsonl")
    a = ap.parse_args()
    SURFACES["router"].K = a.router_k
    pool = DS500.ALL if a.suite == "x500" else DS.ALL
    scs = [s for s in pool if not a.only or s.id in a.only.split(",")]
    strategies = a.strategies.split(",")
    out = os.path.join(HERE, a.out)
    done = set()
    if os.path.exists(out):
        done = {key(json.loads(l)) for l in open(out) if l.strip()}
    cwd = os.environ.setdefault("DEMO_CLI_CWD", os.path.join(HERE, ".cli_cwd"))
    os.makedirs(cwd, exist_ok=True)
    lock = asyncio.Lock()
    for size in [int(x) for x in a.sizes.split(",")]:
        jobs = [(sc, st, rep) for rep in range(a.reps) for sc in scs for st in strategies if sc.min_size <= size and
                 "%s|%s|%s|%s|%s" % (a.model, size, st, sc.id, rep) not in done]
        if not jobs:
            continue
        print("== size %d: %d runs, %d workers ==" % (size, len(jobs), a.workers), flush=True)
        procs = [start_server(a.port + i, size) for i in range(a.workers)]
        q = asyncio.Queue()
        for j in jobs:
            q.put_nowait(j)
        t0 = time.time()

        async def worker(i):
            base = procs[i][1]
            llm = ClaudeCLI(a.model, cwd) if a.llm == "cli" else AnthropicLLM(a.model)
            while True:
                try:
                    sc, st, rep = q.get_nowait()
                except asyncio.QueueEmpty:
                    return
                t1 = time.time()
                try:
                    r = await asyncio.wait_for(run_one(base, st, sc, llm), a.timeout)
                except Exception as e:  # a crashed or timed-out run is a failed run, recorded as such
                    r = {"correct": False, "turns": 0, "note": "EXC %s: %s" % (type(e).__name__, str(e)[:150]), "cum_input": 0,
                         "peak_ctx": 0, "out": 0, "mcp_calls": 0, "wrong_calls": 0, "tool_errors": 0, "router_in": 0, "router_out": 0}
                r.update(model=a.model, size=size, strategy=st + a.tag, scenario=sc.id, rep=rep, wall=round(time.time() - t1, 1))
                async with lock:
                    with open(out, "a") as f:
                        f.write(json.dumps(r) + "\n")
                    print("[%4ds] %s %s/%s r%d -> %s turns=%s wrong=%s %s" % (time.time() - t0, a.model, sc.id, st, rep,
                          "OK " if r["correct"] else "NO ", r.get("turns"), r.get("wrong_calls"), (r.get("note") or "")[:90]), flush=True)

        try:
            await asyncio.gather(*[worker(i) for i in range(a.workers)])
        finally:
            for p, _ in procs:
                p.kill()
                p.wait()


if __name__ == "__main__":
    asyncio.run(main())
