"""Lexical retrieval over tool definitions (BM25) + the tool router built on it.

Used by two strategies:
  * ToolRouter  - sits in front of the servers, sees the raw user request, splits it into
                  intents, returns an ordered set of tools (what the hackathon router did).
  * Tool search - the model writes a short capability query itself and gets the top matches back
                  (the shape of Anthropic's Tool Search Tool / Claude Code's lazy loading).

Retrieval is deliberately simple and deterministic so the experiment is reproducible. A production
router would use embeddings and/or a small LLM; the failure modes are the same in kind.
"""
import math
import re
from collections import Counter

STOP = set("a an the of to for in on and or with by from is are be this that it at as me my you your".split())


def _stem(w):
    for suf in ("ing", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            w = w[: -len(suf)]
            break
    return w[:-1] if w.endswith("e") and len(w) > 3 else w


def tokens(text):
    text = re.sub(r"[_\-./]", " ", text.lower())
    return [_stem(w) for w in re.findall(r"[a-z0-9]+", text) if w not in STOP]


def tool_text(d):
    props = d["input_schema"].get("properties", {})
    pt = " ".join("%s %s" % (k, v.get("description", "")) for k, v in props.items())
    return "%s %s %s %s" % (d["name"], d["name"], d["description"], pt)  # name counted twice


class BM25:
    def __init__(self, defs, k1=1.5, b=0.75):
        self.names = list(defs)
        self.docs = {n: Counter(tokens(tool_text(defs[n]))) for n in self.names}
        self.len = {n: sum(c.values()) for n, c in self.docs.items()}
        self.avg = sum(self.len.values()) / max(1, len(self.len))
        df = Counter()
        for c in self.docs.values():
            df.update(c.keys())
        N = len(self.names)
        self.idf = {t: math.log(1 + (N - n + 0.5) / (n + 0.5)) for t, n in df.items()}
        self.k1, self.b = k1, b

    def search(self, query, limit=5):
        q = tokens(query)
        scored = []
        for n in self.names:
            tf, L, s = self.docs[n], self.len[n], 0.0
            for t in q:
                if t in tf:
                    f = tf[t]
                    s += self.idf.get(t, 0) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * L / self.avg))
            if s > 0:
                scored.append((n, s))
        scored.sort(key=lambda x: -x[1])
        return scored[:limit]


class ToolRouter:
    SPLIT = re.compile(r"\s*(?:,\s*then\b|\band then\b|\bthen\b|;|\band\b)\s*", re.I)

    def __init__(self, defs, k=2, ambiguity=0.80, floor=0.35):
        self.index = BM25(defs)
        self.k, self.ambiguity, self.floor = k, ambiguity, floor

    def split_intents(self, request):
        parts = [p.strip(" .") for p in self.SPLIT.split(request) if p and p.strip(" .")]
        return parts or [request]

    def route(self, request):
        plan, ordered, seen = [], [], set()
        for intent in self.split_intents(request):
            hits = self.index.search(intent, limit=self.k + 3)
            if not hits:
                plan.append({"intent": intent, "tools": [], "similar": []})
                continue
            top = hits[0][1]
            chosen = [n for n, s in hits[: self.k] if s >= self.floor * top]
            # similar-tool handling: near-ties beyond k are returned together and flagged
            similar = [n for n, s in hits[self.k:] if s >= self.ambiguity * top]
            for n in chosen + similar:
                if n not in seen:
                    seen.add(n)
                    ordered.append(n)
            plan.append({"intent": intent, "tools": chosen, "similar": similar})
        return {"plan": plan, "tools": ordered}
