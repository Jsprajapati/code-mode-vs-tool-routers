"""Smallest runnable Code Mode loop. No model, no server, no API key.

A "model" (here a hardcoded script) counts flagged ledger rows. Compare what passes through the model's context in
plain tool calling (every row) with Code Mode (only the printed answer).

    python3 examples/minimal_code_mode.py

Demo-grade sandbox: see sandbox.py. It is NOT a security boundary.
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import sandbox  # noqa: E402

ROWS = [{"id": i, "amount": 100 + (i * 37) % 900, "flagged": i % 7 == 0} for i in range(1200)]


async def call_tool(name, args):
    """The host side. Real systems put allow-lists, rate limits, logging and approvals here."""
    if name == "export_ledger":
        return ROWS
    raise ValueError("tool not allowed: %s" % name)


# What the model would write after reading a typed stub such as:
#   export_ledger() -> list[{id:int, amount:int, flagged:bool}]
MODEL_SCRIPT = """
rows = tools.export_ledger()
flagged = [r for r in rows if r["flagged"]]
print(json.dumps({"flagged": len(flagged), "total": sum(r["amount"] for r in flagged)}))
"""


def tokens(text):
    return len(text) // 4  # same chars/4 estimate the benchmark uses


async def main():
    plain = tokens(json.dumps(ROWS))
    res = await sandbox.run_code(MODEL_SCRIPT, call_tool)
    print("sandbox output :", res["done"].strip(), "| error:", res.get("error"), "| tool calls:", res["tool_calls"])
    print("plain tool calling would put ~%d tokens of rows through the model" % plain)
    print("Code Mode puts ~%d tokens of output through the model" % tokens(res["done"]))
    expected = {"flagged": sum(r["flagged"] for r in ROWS), "total": sum(r["amount"] for r in ROWS if r["flagged"])}
    assert json.loads(res["done"]) == expected, "script result differs from direct computation"
    print("matches a direct computation:", expected)


if __name__ == "__main__":
    asyncio.run(main())
