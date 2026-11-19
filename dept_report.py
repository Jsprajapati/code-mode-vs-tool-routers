"""Aggregate the department-collision runs into tables.

    python3 dept_report.py results/results_dept_haiku.jsonl results/results_dept_haiku_typed.jsonl results/results_dept_haiku_full.jsonl > results/report_dept.md
"""
import json
import sys
from collections import defaultdict

import dept_scenarios as DS
import dept_scenarios500 as DS500

DEPTS = {sc.id: {t.split("_")[0] for t in sc.right_tools} for sc in DS.ALL + DS500.ALL}


def wrong_dept(r):
    """calls to a tool of a department the request is not about (the look-alike mistake)"""
    return len([n for n in r.get("called", []) if n.split("_")[0] not in DEPTS.get(r["scenario"], set())])

LABEL = {"all_tools": "All tools", "router": "Router (BM25)", "router_llm": "Router (BM25 + dept + LLM)",
         "tool_search": "Tool search", "code_mode": "Code Mode (stubs)", "code_mode_search": "Code Mode (search+exec)",
         "code_mode_typed": "Code Mode (stubs) + return types", "code_mode_search_typed": "Code Mode (search+exec) + return types",
         "code_mode_full": "Code Mode (stubs) + return types + param docs",
         "code_mode_search_full": "Code Mode (search+exec) + return types + param docs"}
ORDER = list(LABEL)


def load(paths):
    rows = []
    for p in paths:
        rows += [json.loads(l) for l in open(p) if l.strip()]
    return rows


def avg(xs):
    return sum(xs) / len(xs) if xs else 0


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def main(paths):
    rows = load(paths)
    models = sorted({r["model"] for r in rows})
    sizes = sorted({r["size"] for r in rows})
    print("# Department collision evaluation\n")
    print("%d runs. Tokens are chars/4 estimates; router_llm includes its own LLM call.\n" % len(rows))
    for m in models:
        print("## %s: overall by strategy and catalog size\n" % m)
        hdr = ["strategy"] + ["%d tools: correct" % s for s in sizes] + ["avg input tokens (all sizes)", "avg turns", "wrong-department calls", "tool errors"]
        tr = []
        for st in ORDER:
            sel = [r for r in rows if r["model"] == m and r["strategy"] == st]
            if not sel:
                continue
            cells = []
            for s in sizes:
                x = [r for r in sel if r["size"] == s]
                cells.append("%d/%d" % (sum(r["correct"] for r in x), len(x)) if x else "-")
            tr.append([LABEL[st]] + cells + ["{:,.0f}".format(avg([r["cum_input"] for r in sel])), "%.1f" % avg([r["turns"] for r in sel]),
                                              sum(wrong_dept(r) for r in sel), sum(r.get("tool_errors", 0) for r in sel)])
        print(table(hdr, tr) + "\n")
        for s in sizes:
            print("### %s, %d tools: correct per scenario (all repeats)\n" % (m, s))
            scs = sorted({r["scenario"] for r in rows if r["model"] == m and r["size"] == s})
            tr = []
            for st in ORDER:
                cells = []
                for sc in scs:
                    x = [r for r in rows if r["model"] == m and r["size"] == s and r["strategy"] == st and r["scenario"] == sc]
                    cells.append("%d/%d" % (sum(r["correct"] for r in x), len(x)) if x else "-")
                if any(c != "-" for c in cells):
                    tr.append([LABEL[st]] + cells)
            print(table(["strategy"] + scs, tr) + "\n")
        print("### %s: average total input tokens per run, by size\n" % m)
        tr = []
        for st in ORDER:
            cells = []
            for s in sizes:
                x = [r for r in rows if r["model"] == m and r["size"] == s and r["strategy"] == st]
                cells.append("{:,.0f}".format(avg([r["cum_input"] for r in x])) if x else "-")
            tr.append([LABEL[st]] + cells)
        print(table(["strategy"] + ["%d tools" % s for s in sizes], tr) + "\n")
        print("### %s: failures\n" % m)
        for r in rows:
            if r["model"] == m and not r["correct"]:
                print("- %d tools %s/%s rep%s: %s" % (r["size"], r["scenario"], r["strategy"], r["rep"], (r.get("note") or "")[:200]))
        print()


if __name__ == "__main__":
    main(sys.argv[1:])
