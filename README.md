# Code Mode vs tool routers vs all-tools loading

Runnable code and raw results for the article *Too Many Tools: From a Tool Router to Code Mode*.
It compares five ways to put MCP tools in front of a model, using real MCP servers (official Python SDK, Streamable HTTP),
fixture business data, and answers checked against an oracle computed straight from the fixtures.

No Cloudflare account is needed. Code Mode here is a pattern you can run yourself, not a product.

> **Warning: the sandbox is demo-grade.** `sandbox.py` runs model-written Python in a restricted subprocess. A restricted
> CPython namespace can be escaped, so this is **not a security boundary**. Never point it at real credentials or untrusted
> input. For anything real, use a container with no network, a micro-VM, or a V8 isolate. A hardened way to run the demos is in
> [Docker](#docker).

## Quick start

Python 3.10 or newer (tested on 3.13).

```bash
git clone <repo-url> && cd code-mode-vs-tool-routers
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

### 1. No model, no API key (about 10 seconds)

```bash
python3 examples/minimal_code_mode.py   # a 1,200-row ledger counted by a script: ~13.8K tokens of rows vs ~8 tokens of output
python3 bench.py                        # 5 strategies x 5 requests on a 63-tool catalog, scripted "ideal agent"
```

The scripted agent never makes a mistake of its own. It can only fail when a strategy hides a tool it needs, so this run shows
the *plumbing* (definition size, data passing through the model, turns, MCP calls), not model behaviour.

### 2. Real model through Claude Code (how the article's numbers were made)

Needs the [Claude Code](https://claude.com/claude-code) CLI signed in. Tool calling is emulated: the tool list goes into
the prompt as JSON and the model replies with one JSON object, the same protocol for every strategy.

```bash
# one request, plain MCP vs Code Mode, 500 tools
DEMO_TYPED_STUBS=2 python3 dept_bench.py --model haiku --suite x500 --sizes 500 \
  --reps 1 --only C1 --strategies all_tools,code_mode_search --out try.jsonl
python3 dept_report.py try.jsonl
```

Expected shape (one run on a fresh clone, see `examples/expected_output.txt`): both strategies correct, plain MCP at about 134K input tokens, Code Mode at about 1.8K.

### 3. Real model through the Anthropic API (untested by the author)

```bash
pip install anthropic
ANTHROPIC_API_KEY=... DEMO_TYPED_STUBS=2 python3 dept_bench.py --llm anthropic --model claude-haiku-5-5 \
  --suite x500 --sizes 500 --reps 1 --only C1 --strategies all_tools,code_mode_search --out try_api.jsonl
```

This uses native tool calling, so numbers will not match the CLI runs exactly. Check the model id against Anthropic's current list.

### Look at the servers yourself

```bash
python3 mcp_servers.py --port 9000 --dept 500     # 500-tool catalog at http://127.0.0.1:9000/mcp/<server>/
curl -s http://127.0.0.1:9000/__state
```

## The strategies

| name in code | what it is |
|---|---|
| `all_tools` | plain MCP, every definition in context on every turn |
| `router` | BM25 keyword search picks the tools the model sees |
| `router_llm` | hybrid: BM25 narrows to a few departments, one LLM call picks and orders tools; its tokens are counted |
| `tool_search` | the model searches for tools and loads what it finds |
| `code_mode` / `code_mode_search` | one `execute` tool with typed stubs, or the server-side `search` + `execute` shape. `DEMO_TYPED_STUBS=1` adds return types, `=2` adds parameter docs too |

## What the test contains

- **Base suite** (`dept_scenarios.py`): look-alike tools across five departments (HR, Finance, IT, Legal, Facilities) at 15, 50 and 150 tools.
- **500-tool suite** (`dept_scenarios500.py`): 18 requests, each run twice, including a 1,200-row ledger, chained lookups (5 to 200 items) and a PII export.
- A run counts as correct only if the final answer **and** the side effects (what was approved, reset, exported) match the oracle.
- Tokens are `chars/4` estimates applied the same way to every strategy. Compare ratios, not absolutes.

## Results shipped here

`results/*.jsonl` hold one JSON line per run, the raw data behind the article. Rebuild the tables with:

```bash
python3 dept_report.py results/results_dept500_haiku.jsonl results/results_dept500_all_tools.jsonl > results/report_dept500.md
python3 dept_report.py results/results_dept_haiku.jsonl results/results_dept_haiku_typed.jsonl results/results_dept_haiku_full.jsonl > results/report_dept.md
```

Headline at 500 tools, Claude Haiku, 36 runs per strategy (all-tools: 3 runs, all correct, 101K to 154K input tokens each):

| strategy | correct | avg input tokens | median |
|---|---|---|---|
| Code Mode (search + execute) | 36/36 | 2,365 | 1,840 |
| Router (hybrid) | 34/36 | 8,302 | 5,576 |
| Tool search | 33/36 | 9,145 | 6,463 |
| Router (BM25) | 29/36 | 19,247 | 5,933 |

## Limits of this test

- One model (Haiku), two runs per request, one fixture family. Small differences are noise; large ones are the signal.
- Tool calling is emulated through `claude -p`, not the native tool-use format.
- Code Mode can get this wrong: asked to approve every pending IT access request for the CRM system (scenario D3), it approved one extra request in most runs at 15, 50 and 150 tools. It was correct at 500 tools.
- Vendor and third-party numbers quoted in the article are theirs, not reproduced here.
- Sonnet and larger models were not run.

## Files

| file | role |
|---|---|
| `mcp_servers.py`, `catalog.py`, `dept_catalog.py` | the MCP servers and fixtures (63-tool and department catalogs) |
| `mcp_hub.py` | MCP client that connects to all servers |
| `surfaces.py` | the strategies |
| `retrieval.py` | BM25 and the router |
| `sandbox.py` | demo Code Mode sandbox: separate process, empty env, no file access, tools only through RPC to the host |
| `llm.py` | scripted agent, Claude CLI backend, Anthropic API backend, Gemini backend |
| `bench.py`, `scenarios.py` | runner and the 5-request suite |
| `dept_bench.py`, `dept_scenarios*.py`, `dept_report.py` | department suites, runner, report |
| `examples/minimal_code_mode.py` | smallest runnable loop |

## Docker

`docker/run.sh` builds the image and runs a demo with `--network none`, a read-only filesystem, all capabilities dropped,
1 GB of memory and a PID limit. The servers and sandbox only need loopback, so the model-free demos work with no network.
Real-model runs need network access to reach the model, so run those outside this isolation and accept the sandbox caveat above.

```bash
docker/run.sh                       # runs examples/minimal_code_mode.py
docker/run.sh python3 bench.py      # the scripted 5x5 comparison
```

## License

MIT. See [LICENSE](LICENSE).
