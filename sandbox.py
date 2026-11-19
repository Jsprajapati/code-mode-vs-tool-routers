"""Code Mode execution sandbox (demo-grade).

The model's code runs in a separate Python process that:
  * starts with `-I` (isolated mode) and an empty environment,
  * has no `open`, no `eval`, and may import only a few pure modules (json, math, re, statistics, datetime, collections, ...),
  * can reach the outside world ONLY through `tools.<name>(**kwargs)`, which is an RPC
    to the host over the pipe; the host performs the real MCP call and holds all credentials,
  * returns only what the code `print()`s.

This mirrors the *shape* of Cloudflare's Dynamic Workers design (bindings instead of network,
host keeps tokens, only console output comes back). It is NOT a security boundary: a restricted
CPython namespace can be escaped. Production systems use V8 isolates, gVisor or Firecracker.
"""
import asyncio
import json
import os
import sys

try:  # POSIX only; on Windows the sandbox runs without CPU/memory rlimits
    import resource
except ImportError:  # pragma: no cover
    resource = None

BOOT = r'''
import sys, json, builtins

_out = []

def _rpc(name, args):
    sys.stdout.write(json.dumps({"call": name, "args": args}) + "\n")
    sys.stdout.flush()
    msg = json.loads(sys.stdin.readline())
    if "error" in msg:
        raise RuntimeError(msg["error"])
    return msg["result"]

class _Tools:
    def __getattr__(self, name):
        def call(**kw):
            return _rpc(name, kw)
        return call

def _print(*a, sep=" ", end="\n"):
    _out.append(sep.join(str(x) for x in a) + end)

_names = ("abs all any bool dict enumerate filter float int isinstance len list map max min range "
          "reversed round set sorted str sum tuple zip Exception ValueError KeyError TypeError RuntimeError").split()
SAFE = {n: getattr(builtins, n) for n in _names}
SAFE["print"] = _print

_ALLOWED = {"json", "math", "re", "statistics", "datetime", "collections", "itertools", "functools"}
_real_import = builtins.__import__

def _imp(name, globals=None, locals=None, fromlist=(), level=0):
    if name.split(".")[0] not in _ALLOWED:
        raise ImportError("import of %r is not allowed in the sandbox" % name)
    return _real_import(name, globals, locals, fromlist, level)

SAFE["__import__"] = _imp

code = json.loads(sys.stdin.readline())["code"]
g = {"__builtins__": SAFE, "tools": _Tools(), "json": json}
try:
    exec(compile(code, "<model-code>", "exec"), g)
    res = {"done": "".join(_out)}
except BaseException as e:
    res = {"done": "".join(_out), "error": type(e).__name__ + ": " + str(e)}
sys.stdout.write(json.dumps(res) + "\n")
sys.stdout.flush()
'''


def _limits():
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    resource.setrlimit(resource.RLIMIT_AS, (1 << 30, 1 << 30))


def _child_env():
    # Empty environment so the code sees no secrets. Windows cannot start Python without SYSTEMROOT.
    return {"SYSTEMROOT": os.environ["SYSTEMROOT"]} if os.name == "nt" and "SYSTEMROOT" in os.environ else {}


async def run_code(code, call_tool, timeout=120):
    """Run `code`; `call_tool(name, args)` is an async function that performs the real MCP call."""
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-I", "-c", BOOT,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        env=_child_env(), preexec_fn=_limits if resource else None, limit=1 << 26)
    proc.stdin.write((json.dumps({"code": code}) + "\n").encode())
    await proc.stdin.drain()
    calls = 0

    async def loop():
        nonlocal calls
        while True:
            line = await proc.stdout.readline()
            if not line:
                err = (await proc.stderr.read()).decode()[-300:]
                return {"done": "", "error": "sandbox exited: " + err}
            msg = json.loads(line)
            if "call" in msg:
                calls += 1
                try:
                    reply = {"result": await call_tool(msg["call"], msg["args"])}
                except Exception as e:
                    reply = {"error": "%s: %s" % (type(e).__name__, e)}
                proc.stdin.write((json.dumps(reply) + "\n").encode())
                await proc.stdin.drain()
            else:
                return msg

    try:
        res = await asyncio.wait_for(loop(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        res = {"done": "", "error": "timeout"}
    finally:
        if proc.returncode is None:
            proc.kill()
        await proc.wait()
    res["tool_calls"] = calls
    return res
