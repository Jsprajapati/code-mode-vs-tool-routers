"""Mock MCP servers: 63 tools across 7 servers, backed by deterministic fixtures.

Only the tools used by the demo use cases have real behaviour; the rest are
realistic-looking decoys (they exist so the catalog has a believable size and
believable look-alike tools). Nothing here talks to a network.
"""
import json
import random

TODAY = "2026-10-24"
WEEK_START = "2026-10-19"


class _State:
    """Records side effects so every strategy can be checked against an oracle."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.actions = []
        self.next_issue = 180
        self.executed = []  # (tool, args) in execution order
        self.counters = {}  # per-run counters (used by the flaky-tool scenario)


STATE = _State()

_PY = {"string": "str", "integer": "int", "boolean": "bool", "array": "list", "number": "float"}


class Tool:
    def __init__(self, server, name, description, params, fn=None, returns=None):
        self.returns = returns  # return shape as a short type string, exposed to clients in the tool's meta
        self.server = server
        self.name = name
        self.description = description
        self.params = params  # [(name, json_type, description, required)]
        self.fn = fn or (lambda **kw: {"ok": True, "note": "decoy tool, unused by the demo scenarios"})

    def definition(self):
        props = {p[0]: {"type": p[1], "description": p[2]} for p in self.params}
        req = [p[0] for p in self.params if p[3]]
        schema = {"type": "object", "properties": props}
        if req:
            schema["required"] = req
        d = {"name": self.name, "description": self.description, "inputSchema": schema}
        if self.returns:
            d["_meta"] = {"returns": self.returns}
        return d

    def stub(self):
        args = ", ".join(
            "%s%s: %s" % (p[0], "" if p[3] else "?", _PY.get(p[1], "any")) for p in self.params
        )
        first = self.description.split(". ")[0].rstrip(".")
        return "%s(%s)  # %s" % (self.name, args, first)


class Catalog:
    def __init__(self, tools):
        self.tools = {t.name: t for t in tools}

    def names(self):
        return list(self.tools)

    def call(self, name, args):
        t = self.tools[name]
        required = {p[0] for p in t.params if p[3]}
        allowed = {p[0] for p in t.params}
        missing = required - set(args)
        extra = set(args) - allowed
        if missing or extra:
            raise TypeError("%s: missing %s, unexpected %s" % (name, sorted(missing), sorted(extra)))
        STATE.executed.append((name, args))
        return t.fn(**args)

    def padded(self, n):
        """Return a catalog padded with synthetic decoy tools up to n tools."""
        extra = _decoys(max(0, n - len(self.tools)))
        return Catalog(list(self.tools.values()) + extra)


def P(name, typ, desc, req=False):
    return (name, typ, desc, req)


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------
rng = random.Random(7)

USERS = [
    ("Priya Raman", "priya.r"), ("Dev Kapoor", "dev.k"), ("Ananya Shah", "ananya.s"),
    ("Marcus Lee", "marcus.l"), ("Sofia Alvarez", "sofia.a"), ("Tom Becker", "tom.b"),
    ("Hana Sato", "hana.s"), ("Omar Haddad", "omar.h"), ("Lena Fischer", "lena.f"),
    ("Raj Patel", "raj.p"), ("Chloe Martin", "chloe.m"), ("Ivan Petrov", "ivan.p"),
]

_BITS = [
    "Refactors the ledger rounding path to use banker's rounding.",
    "Adds idempotency keys to the refund endpoint.",
    "Moves currency conversion behind a feature flag.",
    "Retries webhook delivery with exponential backoff.",
    "Fixes a race between invoice finalisation and payment capture.",
    "Backfills missing tax region on legacy customers.",
    "Tightens validation on the payout schedule payload.",
    "Replaces the cron-based settlement job with a queue consumer.",
    "Adds structured logging around card network timeouts.",
    "Drops the unused v1 receipts table after the migration window.",
]
_SUMMARIES = [
    "Fix rounding drift in invoice totals", "Add idempotency to refunds", "Webhook retries drop events",
    "Settlement job misses weekend batches", "Tax region missing for legacy accounts",
    "Payout schedule validation too loose", "Card network timeout not logged",
    "Currency conversion rounds twice", "Receipts export is slow for large accounts",
    "Dispute evidence upload fails over 10MB", "Add audit trail to plan changes",
    "Proration wrong on mid-cycle downgrade", "Duplicate charge on retry after 3DS",
    "Reconciliation report off by one day", "Add SEPA mandate status to API",
]

ISSUES = {}
for n in range(100, 180):
    key = "PAY-%d" % n
    name, handle = rng.choice(USERS)
    ISSUES[key] = {
        "key": key,
        "summary": rng.choice(_SUMMARIES),
        "description": " ".join(rng.sample(_BITS, 3)),
        "status": rng.choice(["To Do", "In Progress", "In Review", "Done", "Blocked"]),
        "priority": rng.choices(["P1", "P2", "P3"], weights=[15, 45, 40])[0],
        "assignee": {"name": name, "handle": handle},
        "sprint": rng.choice([41, 42, 43]),
        "labels": rng.sample(["payments", "ledger", "api", "tech-debt", "customer", "security"], 2),
        "created": "2026-%02d-%02d" % (rng.choice([9, 10]), rng.randint(1, 28)),
        "comments": [
            {"author": rng.choice(USERS)[1], "body": rng.choice(_BITS)} for _ in range(rng.randint(1, 3))
        ],
    }


def _is_target(i):
    return i["priority"] == "P1" and i["sprint"] == 42 and i["status"] != "Done"


TARGET_KEYS = [k for k, i in ISSUES.items() if _is_target(i)]
while len(TARGET_KEYS) > 6:
    ISSUES[TARGET_KEYS.pop()]["priority"] = "P2"
_i = 0
_keys = list(ISSUES)
while len(TARGET_KEYS) < 6:
    k = _keys[_i]
    _i += 1
    if not _is_target(ISSUES[k]):
        ISSUES[k].update(priority="P1", sprint=42, status="In Progress")
        TARGET_KEYS.append(k)

_non_target = [k for k in _keys if k not in TARGET_KEYS]
PRS = []
REVIEWS = {}
_num = [1200]


def _pr(key, state, merged_at, created_at):
    num = _num[0]
    _num[0] += 1
    author = rng.choice(USERS)[1]
    PRS.append({
        "number": num,
        "title": "%s: %s" % (key, ISSUES[key]["summary"]),
        "state": state,
        "author": author,
        "labels": rng.sample(["payments", "ledger", "api", "hotfix", "refactor"], 2),
        "body": " ".join(rng.sample(_BITS, 2)) + " Closes %s." % key,
        "created_at": created_at,
        "merged_at": merged_at,
        "additions": rng.randint(5, 600),
        "deletions": rng.randint(0, 300),
        "changed_files": rng.randint(1, 25),
        "html_url": "https://github.com/acme/payments/pull/%d" % num,
        "requested_reviewers": rng.sample([u[1] for u in USERS], 2),
    })
    return num


def _rand_reviews():
    return [
        {"user": rng.choice(USERS)[1], "state": rng.choice(["APPROVED", "COMMENTED", "CHANGES_REQUESTED"]),
         "submitted_at": "2026-10-%02d" % rng.randint(1, 23), "body": rng.choice(_BITS)}
        for _ in range(rng.randint(0, 3))
    ]


for key in rng.sample(_non_target, 14):  # merged this week
    d = "2026-10-%02d" % rng.randint(19, 23)
    n = _pr(key, "merged", d, "2026-10-%02d" % rng.randint(10, 18))
    REVIEWS[n] = _rand_reviews()

_scenario = [
    ("APPROVED", "COMMENTED"), ("CHANGES_REQUESTED",), ("APPROVED",), (),
]
for key, states in zip(TARGET_KEYS[:4], _scenario):  # open PRs on target issues
    n = _pr(key, "open", None, "2026-10-%02d" % rng.randint(15, 22))
    REVIEWS[n] = [
        {"user": rng.choice(USERS)[1], "state": s, "submitted_at": "2026-10-22", "body": rng.choice(_BITS)}
        for s in states
    ]

for _ in range(22):  # background noise
    key = rng.choice(_non_target)
    kind = rng.choice(["merged_old", "open", "closed"])
    if kind == "merged_old":
        n = _pr(key, "merged", "2026-%02d-%02d" % (rng.choice([9, 10]), rng.randint(1, 17) if True else 1),
                "2026-09-%02d" % rng.randint(1, 28))
    elif kind == "open":
        n = _pr(key, "open", None, "2026-10-%02d" % rng.randint(1, 23))
    else:
        n = _pr(key, "closed", None, "2026-09-%02d" % rng.randint(1, 28))
    REVIEWS[n] = _rand_reviews()
PRS.sort(key=lambda p: -p["number"])

# Slack ------------------------------------------------------------------
CHANNELS = ["#general", "#releases", "#product", "#eng", "#payments-oncall", "#random"]
_MSG_BITS = [
    "deploy is green, rolling to 25%", "can someone review my PR when they get a minute",
    "standup notes are in the doc", "heads up: maintenance window tonight",
    "who owns the settlement job again?", "reminder: roadmap review on Thursday",
    "lunch at 1?", "the dashboards look off after the migration", "thanks, merging now",
    "anyone seen this error before?",
]
MESSAGES = []
FILES = []
for i in range(120):
    name, handle = rng.choice(USERS)
    MESSAGES.append({
        "id": "m%03d" % i, "channel": rng.choice(CHANNELS), "user": name, "handle": handle,
        "text": rng.choice(_MSG_BITS), "ts": "2026-10-%02d" % rng.randint(1, 23),
        "permalink": "https://acme.slack.com/archives/msg/m%03d" % i,
    })
MESSAGES.append({
    "id": "m900", "channel": "#product", "user": "Priya Raman", "handle": "priya.r",
    "text": "sharing the Q3 roadmap for review, comments by Friday", "ts": "2026-10-09",
    "permalink": "https://acme.slack.com/archives/msg/m900",
})
MESSAGES.append({
    "id": "m901", "channel": "#eng", "user": "Dev Kapoor", "handle": "dev.k",
    "text": "the Q3 roadmap has a payments item we should talk about", "ts": "2026-10-10",
    "permalink": "https://acme.slack.com/archives/msg/m901",
})
for fid, (fname, user, handle, ch, ts) in enumerate([
    ("Q3-roadmap-v4.pdf", "Priya Raman", "priya.r", "#product", "2026-10-09"),
    ("Q2-roadmap.pdf", "Priya Raman", "priya.r", "#product", "2026-07-02"),
    ("Q3-roadmap-draft.pdf", "Dev Kapoor", "dev.k", "#eng", "2026-09-28"),
    ("settlement-runbook.pdf", "Omar Haddad", "omar.h", "#payments-oncall", "2026-10-03"),
    ("incident-2026-10-01.pdf", "Lena Fischer", "lena.f", "#eng", "2026-10-02"),
]):
    FILES.append({"id": "F%03d" % fid, "name": fname, "user": user, "handle": handle, "channel": ch,
                  "ts": ts, "permalink": "https://acme.slack.com/files/%s/F%03d/%s" % (handle, fid, fname)})

# CRM --------------------------------------------------------------------
CUSTOMERS = []
SPEND = {}
TICKETS = {}
_company = ["Northwind", "Contoso", "Globex", "Initech", "Umbrella", "Hooli", "Stark", "Wayne", "Acme", "Vandelay"]
_suffix = ["Labs", "Retail", "Logistics", "Health", "Media", "Energy", "Foods", "Systems"]
_months = ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"]
for n in range(1, 121):
    cid = "CUST-%03d" % n
    CUSTOMERS.append({
        "id": cid, "name": "%s %s %d" % (rng.choice(_company), rng.choice(_suffix), n),
        "segment": rng.choice(["SMB", "Mid-market", "Enterprise"]),
        "region": rng.choice(["NA", "EMEA", "APAC", "LATAM"]),
        "owner": rng.choice(USERS)[1], "plan": rng.choice(["Starter", "Growth", "Scale"]),
        "mrr_usd": rng.randint(800, 40000), "health_score": rng.randint(30, 99),
        "created": "202%d-%02d-%02d" % (rng.randint(2, 6), rng.randint(1, 12), rng.randint(1, 28)),
        "notes": rng.choice(["Renewal in Q1.", "Champion left the company.", "Expanding to EMEA.",
                             "Asked about SEPA support.", "Escalated billing dispute last quarter."]),
    })
    v = [rng.randint(3000, 60000)]
    for _ in range(5):
        v.append(max(100, int(v[-1] * rng.uniform(0.88, 1.12))))
    SPEND[cid] = [{"month": m, "spend_usd": x} for m, x in zip(_months, v)]
    TICKETS[cid] = [
        {"id": "T-%d%02d" % (n, j), "subject": rng.choice(_SUMMARIES), "status": "open",
         "priority": rng.choice(["low", "normal", "high"]), "created": "2026-10-%02d" % rng.randint(1, 23),
         "assignee": rng.choice(USERS)[1]}
        for j in range(rng.randint(0, 6))
    ]
for idx, cid in enumerate(rng.sample([c["id"] for c in CUSTOMERS], 10)):  # force some decliners
    top = SPEND[cid][2]["spend_usd"]
    last4 = [int(top * f) for f in (1.0, 0.85, 0.7, 0.5)]
    for j, x in enumerate(last4):
        SPEND[cid][2 + j]["spend_usd"] = x
    if idx < 5:
        TICKETS[cid] = [
            {"id": "T-%s%02d" % (cid[-3:], j), "subject": rng.choice(_SUMMARIES), "status": "open",
             "priority": "high", "created": "2026-10-%02d" % rng.randint(1, 23), "assignee": "dev.k"}
            for j in range(rng.randint(4, 6))
        ]


# --------------------------------------------------------------------------
# Tool implementations (only the ones the scenarios use)
# --------------------------------------------------------------------------
def _gh_list_prs(repo, state="all", since=None, query=None, per_page=30):
    if repo != "acme/payments":
        return []
    out = []
    for p in PRS:
        if state != "all" and p["state"] != state:
            continue
        if since:
            when = p["merged_at"] if state == "merged" else p["created_at"]
            if not when or when < since:
                continue
        if query and query.lower() not in p["title"].lower():
            continue
        out.append(p)
    return out[:per_page]


def _gh_pr_reviews(repo, pull_number):
    return REVIEWS.get(pull_number, [])


def _jira_search(project, sprint=None, priority=None, status=None, status_not=None, text=None, max_results=50):
    out = []
    for i in ISSUES.values():
        if sprint is not None and i["sprint"] != sprint:
            continue
        if priority and i["priority"] != priority:
            continue
        if status and i["status"] != status:
            continue
        if status_not and i["status"] == status_not:
            continue
        if text and text.lower() not in (i["summary"] + i["description"]).lower():
            continue
        out.append({k: i[k] for k in ("key", "summary", "status", "priority", "assignee", "sprint", "labels")})
    return out[:max_results]


def _jira_get(key):
    return ISSUES.get(key, {"error": "issue not found: %s" % key})


def _jira_create(project, summary, issue_type, priority, description=None):
    key = "PAY-%d" % STATE.next_issue
    STATE.next_issue += 1
    STATE.actions.append(("jira_create_issue", json.dumps(
        {"project": project, "summary": summary, "issue_type": issue_type, "priority": priority}, sort_keys=True)))
    return {"key": key, "url": "https://acme.atlassian.net/browse/" + key}


def _slack_post(channel, text):
    STATE.actions.append(("slack_post_message", channel, text))
    return {"ok": True, "channel": channel, "ts": "1761290000.000100"}


def _norm(s):
    return s.lower().replace("-", " ").replace("_", " ").replace(".", " ")


def _slack_search_files(query, from_user=None, channel=None, count=20):
    toks = _norm(query).split()
    out = []
    for f in FILES:
        if not all(t in _norm(f["name"]) for t in toks):
            continue
        if from_user and from_user.lower() not in (f["user"] + f["handle"]).lower():
            continue
        if channel and f["channel"] != channel:
            continue
        out.append({k: f[k] for k in ("id", "name", "user", "channel", "permalink", "ts")})
    out.sort(key=lambda f: f["ts"], reverse=True)
    return out[:count]


def _slack_search_messages(query, from_user=None, in_channel=None, count=20):
    toks = _norm(query).split()
    out = []
    for m in MESSAGES:
        if not all(t in _norm(m["text"]) for t in toks):
            continue
        if from_user and from_user.lower() not in (m["user"] + m["handle"]).lower():
            continue
        if in_channel and m["channel"] != in_channel:
            continue
        out.append({k: m[k] for k in ("id", "channel", "user", "text", "ts", "permalink")})
    out.sort(key=lambda m: m["ts"], reverse=True)
    return out[:count]


def _crm_list(page=1, page_size=50):
    total_pages = -(-len(CUSTOMERS) // page_size)
    start = (page - 1) * page_size
    return {"customers": CUSTOMERS[start:start + page_size], "page": page, "total_pages": total_pages,
            "total": len(CUSTOMERS)}


def _crm_spend(customer_id, months=6):
    return {"customer_id": customer_id, "currency": "USD", "months": SPEND[customer_id][-months:]}


def _crm_tickets(customer_id, status="open"):
    return [t for t in TICKETS.get(customer_id, []) if t["status"] == status]


# --------------------------------------------------------------------------
# The catalog
# --------------------------------------------------------------------------
def build_catalog():
    T = []
    add = lambda *a, **k: T.append(Tool(*a, **k))

    # ---- GitHub (12)
    add("github", "github_list_pull_requests",
        "List pull requests for a repository. Supports filtering by state (open, closed, merged, all), by a date lower bound "
        "(merge date for merged PRs, creation date otherwise) and by a title substring. Returns newest first, including title, "
        "author, labels, body and requested reviewers.",
        [P("repo", "string", "Repository in owner/name form, e.g. acme/payments", True),
         P("state", "string", "One of open, closed, merged or all (default all)"),
         P("since", "string", "ISO date; only PRs on or after this date"),
         P("query", "string", "Substring to match against the PR title"),
         P("per_page", "integer", "Results per page, max 100 (default 30)")], _gh_list_prs)
    add("github", "github_get_pull_request",
        "Get a single pull request by number, including its description, diff statistics, mergeability and linked issues.",
        [P("repo", "string", "Repository in owner/name form", True), P("pull_number", "integer", "Pull request number", True)])
    add("github", "github_get_pr_reviews",
        "List the reviews submitted on a pull request. Each review has the reviewer, a state (APPROVED, COMMENTED, "
        "CHANGES_REQUESTED, DISMISSED) and an optional body.",
        [P("repo", "string", "Repository in owner/name form", True), P("pull_number", "integer", "Pull request number", True)],
        _gh_pr_reviews)
    add("github", "github_search_issues",
        "Search issues and pull requests across GitHub repositories using GitHub search syntax. Returns matching issues with "
        "state, labels, assignees and comment counts.",
        [P("q", "string", "Search query using GitHub search syntax", True), P("per_page", "integer", "Results per page")])
    add("github", "github_create_issue",
        "Create a new issue in a GitHub repository with a title, optional body, labels and assignees.",
        [P("repo", "string", "Repository in owner/name form", True), P("title", "string", "Issue title", True),
         P("body", "string", "Issue body in Markdown"), P("labels", "array", "Labels to apply"), P("assignees", "array", "Logins to assign")])
    add("github", "github_list_commits",
        "List commits on a branch of a repository, optionally filtered by author, path or date range.",
        [P("repo", "string", "Repository in owner/name form", True), P("sha", "string", "Branch name or commit SHA"),
         P("author", "string", "Filter by author login"), P("since", "string", "ISO date lower bound")])
    add("github", "github_list_workflow_runs",
        "List GitHub Actions workflow runs for a repository with status, conclusion, branch and duration.",
        [P("repo", "string", "Repository in owner/name form", True), P("status", "string", "queued, in_progress or completed"),
         P("branch", "string", "Filter by branch")])
    add("github", "github_get_file_contents",
        "Read a file or list a directory at a given path and ref in a repository.",
        [P("repo", "string", "Repository in owner/name form", True), P("path", "string", "Path within the repository", True),
         P("ref", "string", "Branch, tag or commit SHA")])
    add("github", "github_create_pull_request",
        "Open a pull request from a head branch into a base branch with a title and description.",
        [P("repo", "string", "Repository in owner/name form", True), P("head", "string", "Head branch", True),
         P("base", "string", "Base branch", True), P("title", "string", "Pull request title", True), P("body", "string", "Description")])
    add("github", "github_merge_pull_request",
        "Merge a pull request using the merge, squash or rebase method once checks pass.",
        [P("repo", "string", "Repository in owner/name form", True), P("pull_number", "integer", "Pull request number", True),
         P("merge_method", "string", "merge, squash or rebase")])
    add("github", "github_list_branches",
        "List branches in a repository, including whether each branch is protected.",
        [P("repo", "string", "Repository in owner/name form", True)])
    add("github", "github_add_issue_comment",
        "Add a comment to an issue or pull request conversation.",
        [P("repo", "string", "Repository in owner/name form", True), P("issue_number", "integer", "Issue or PR number", True),
         P("body", "string", "Comment body in Markdown", True)])

    # ---- Jira (11)
    add("jira", "jira_search_issues",
        "Search Jira issues in a project by sprint, priority, status or free text. Returns summary-level fields (key, summary, "
        "status, priority, assignee, sprint, labels); use jira_get_issue for the full record.",
        [P("project", "string", "Project key, e.g. PAY", True), P("sprint", "integer", "Sprint number"),
         P("priority", "string", "P1, P2 or P3"), P("status", "string", "Only issues in this status"),
         P("status_not", "string", "Exclude issues in this status"), P("text", "string", "Free-text match on summary and description"),
         P("max_results", "integer", "Maximum results (default 50)")], _jira_search)
    add("jira", "jira_get_issue",
        "Get a Jira issue by key with its full description, status, priority, assignee, sprint, labels and comments.",
        [P("key", "string", "Issue key, e.g. PAY-123", True)], _jira_get)
    add("jira", "jira_create_issue",
        "Create a Jira issue in a project with a summary, type, priority and optional description.",
        [P("project", "string", "Project key, e.g. PAY", True), P("summary", "string", "Issue summary", True),
         P("issue_type", "string", "Bug, Task or Story", True), P("priority", "string", "Highest, High, Medium or Low", True),
         P("description", "string", "Issue description")], _jira_create)
    add("jira", "jira_update_issue",
        "Update fields on an existing Jira issue such as summary, description, labels or priority.",
        [P("key", "string", "Issue key", True), P("fields", "object", "Fields to update", True)])
    add("jira", "jira_transition_issue",
        "Move a Jira issue to another workflow status, for example from In Progress to In Review.",
        [P("key", "string", "Issue key", True), P("status", "string", "Target status", True)])
    add("jira", "jira_add_comment",
        "Add a comment to a Jira issue.",
        [P("key", "string", "Issue key", True), P("body", "string", "Comment text", True)])
    add("jira", "jira_list_projects",
        "List Jira projects visible to the current user with keys, names and leads.", [])
    add("jira", "jira_list_sprints",
        "List sprints for a Jira board with state and start and end dates.",
        [P("board_id", "integer", "Board id", True), P("state", "string", "active, closed or future")])
    add("jira", "jira_get_sprint",
        "Get one sprint with its goal, dates and the issues it contains.",
        [P("sprint_id", "integer", "Sprint id", True)])
    add("jira", "jira_assign_issue",
        "Assign a Jira issue to a user or clear the assignee.",
        [P("key", "string", "Issue key", True), P("assignee", "string", "User handle, or empty to unassign")])
    add("jira", "jira_get_issue_links",
        "List issues linked to a Jira issue (blocks, is blocked by, relates to, duplicates).",
        [P("key", "string", "Issue key", True)])

    # ---- Slack (10)
    add("slack", "slack_post_message",
        "Post a message to a Slack channel or send a direct message by passing @handle as the channel.",
        [P("channel", "string", "Channel name like #releases, or @handle for a direct message", True),
         P("text", "string", "Message text", True)], _slack_post)
    add("slack", "slack_search_messages",
        "Search Slack message text across channels the user can see. Optionally restrict to a channel or sender. "
        "Returns matching messages with channel, author, timestamp and permalink.",
        [P("query", "string", "Words that must appear in the message", True), P("from_user", "string", "Name or handle of the sender"),
         P("in_channel", "string", "Restrict to a channel, e.g. #product"), P("count", "integer", "Maximum results")],
        _slack_search_messages)
    add("slack", "slack_search_files",
        "Search files shared in Slack by file name. Optionally restrict to the person who shared it or a channel. "
        "Returns the file name, sharer, channel, timestamp and permalink.",
        [P("query", "string", "Words that must appear in the file name", True), P("from_user", "string", "Name or handle of the sharer"),
         P("channel", "string", "Restrict to a channel"), P("count", "integer", "Maximum results")], _slack_search_files)
    add("slack", "slack_list_channels",
        "List public channels in the workspace with topic and member counts.",
        [P("limit", "integer", "Maximum channels to return")])
    add("slack", "slack_get_channel_history",
        "Fetch recent messages from a channel in reverse chronological order.",
        [P("channel", "string", "Channel name", True), P("limit", "integer", "Number of messages")])
    add("slack", "slack_get_thread_replies",
        "Fetch all replies in a message thread.",
        [P("channel", "string", "Channel name", True), P("thread_ts", "string", "Timestamp of the parent message", True)])
    add("slack", "slack_add_reaction",
        "Add an emoji reaction to a message.",
        [P("channel", "string", "Channel name", True), P("timestamp", "string", "Message timestamp", True),
         P("emoji", "string", "Emoji name without colons", True)])
    add("slack", "slack_get_user_profile",
        "Get a user's profile including title, timezone and status.",
        [P("handle", "string", "User handle", True)])
    add("slack", "slack_list_users",
        "List workspace members with handles, display names and activity status.",
        [P("limit", "integer", "Maximum users to return")])
    add("slack", "slack_upload_file",
        "Upload a file to a channel with an optional comment.",
        [P("channel", "string", "Channel name", True), P("filename", "string", "File name", True), P("content", "string", "File content", True)])

    # ---- Calendar (7)
    add("calendar", "calendar_list_events",
        "List calendar events in a time range with attendees, location and conferencing links.",
        [P("calendar_id", "string", "Calendar id", True), P("time_min", "string", "ISO start"), P("time_max", "string", "ISO end")])
    add("calendar", "calendar_get_event", "Get one calendar event with full details.",
        [P("calendar_id", "string", "Calendar id", True), P("event_id", "string", "Event id", True)])
    add("calendar", "calendar_create_event",
        "Create a calendar event with attendees and an optional video link.",
        [P("calendar_id", "string", "Calendar id", True), P("title", "string", "Event title", True),
         P("start", "string", "ISO start", True), P("end", "string", "ISO end", True), P("attendees", "array", "Attendee emails")])
    add("calendar", "calendar_update_event", "Change the time, title or attendees of an event.",
        [P("calendar_id", "string", "Calendar id", True), P("event_id", "string", "Event id", True), P("fields", "object", "Fields to change", True)])
    add("calendar", "calendar_delete_event", "Delete a calendar event and notify attendees.",
        [P("calendar_id", "string", "Calendar id", True), P("event_id", "string", "Event id", True)])
    add("calendar", "calendar_find_free_slots",
        "Find time slots when all listed people are free within a window.",
        [P("attendees", "array", "Attendee emails", True), P("duration_minutes", "integer", "Meeting length", True),
         P("window_start", "string", "ISO start"), P("window_end", "string", "ISO end")])
    add("calendar", "calendar_list_calendars", "List calendars the user can read or write.", [])

    # ---- CRM (9)
    add("crm", "crm_list_customers",
        "List customer accounts, one page at a time, with segment, region, owner, plan, MRR, health score and notes.",
        [P("page", "integer", "Page number starting at 1"), P("page_size", "integer", "Customers per page, max 100")], _crm_list)
    add("crm", "crm_get_customer", "Get one customer account by id.",
        [P("customer_id", "string", "Customer id, e.g. CUST-001", True)])
    add("crm", "crm_search_customers", "Search customers by name, segment or region.",
        [P("query", "string", "Search text", True), P("segment", "string", "SMB, Mid-market or Enterprise")])
    add("crm", "crm_get_monthly_spend",
        "Get a customer's monthly spend in USD for the most recent months, oldest first.",
        [P("customer_id", "string", "Customer id", True), P("months", "integer", "Number of months (default 6)")], _crm_spend)
    add("crm", "crm_list_support_tickets",
        "List support tickets for a customer filtered by status, with subject, priority, creation date and assignee.",
        [P("customer_id", "string", "Customer id", True), P("status", "string", "open or closed (default open)")], _crm_tickets)
    add("crm", "crm_create_note", "Attach a note to a customer account.",
        [P("customer_id", "string", "Customer id", True), P("body", "string", "Note text", True)])
    add("crm", "crm_update_customer", "Update fields on a customer account such as owner, plan or notes.",
        [P("customer_id", "string", "Customer id", True), P("fields", "object", "Fields to change", True)])
    add("crm", "crm_list_deals", "List open deals with stage, amount and expected close date.",
        [P("stage", "string", "Filter by stage"), P("owner", "string", "Filter by owner handle")])
    add("crm", "crm_get_deal", "Get one deal with its history and contacts.",
        [P("deal_id", "string", "Deal id", True)])

    # ---- Docs (8)
    add("docs", "docs_search",
        "Search documents in the company knowledge base by title and body text.",
        [P("query", "string", "Search text", True), P("folder", "string", "Restrict to a folder")])
    add("docs", "docs_get_document", "Read a document by id including its content as Markdown.",
        [P("doc_id", "string", "Document id", True)])
    add("docs", "docs_create_document", "Create a document in a folder.",
        [P("title", "string", "Title", True), P("content", "string", "Markdown content", True), P("folder", "string", "Folder")])
    add("docs", "docs_update_document", "Replace or append to a document's content.",
        [P("doc_id", "string", "Document id", True), P("content", "string", "New Markdown content", True)])
    add("docs", "docs_list_folders", "List folders in the knowledge base.", [P("parent", "string", "Parent folder")])
    add("docs", "docs_share_document", "Share a document with people or a group.",
        [P("doc_id", "string", "Document id", True), P("with", "array", "Emails or group names", True), P("role", "string", "viewer, commenter or editor")])
    add("docs", "docs_get_comments", "List comment threads on a document.", [P("doc_id", "string", "Document id", True)])
    add("docs", "docs_export_pdf", "Export a document as a PDF and return a download link.", [P("doc_id", "string", "Document id", True)])

    # ---- Email (6)
    add("email", "email_send", "Send an email to one or more recipients.",
        [P("to", "array", "Recipient addresses", True), P("subject", "string", "Subject", True), P("body", "string", "Body", True)])
    add("email", "email_search", "Search the mailbox by sender, subject or text.",
        [P("query", "string", "Search text or operators", True), P("max_results", "integer", "Maximum results")])
    add("email", "email_get_message", "Read one email with headers and body.", [P("message_id", "string", "Message id", True)])
    add("email", "email_create_draft", "Create a draft email without sending it.",
        [P("to", "array", "Recipients", True), P("subject", "string", "Subject", True), P("body", "string", "Body", True)])
    add("email", "email_list_labels", "List mailbox labels.", [])
    add("email", "email_reply", "Reply to an email thread.",
        [P("message_id", "string", "Message id", True), P("body", "string", "Reply text", True)])

    return Catalog(T)


# --------------------------------------------------------------------------
# Decoy generator for the catalog-size sweep
# --------------------------------------------------------------------------
_SERVICES = {
    "zendesk": ["tickets", "macros", "agents"], "salesforce": ["leads", "opportunities", "accounts"],
    "hubspot": ["contacts", "companies", "deals"], "stripe": ["charges", "invoices", "payouts"],
    "sentry": ["issues", "releases", "alerts"], "datadog": ["monitors", "dashboards", "incidents"],
    "pagerduty": ["incidents", "schedules", "services"], "linear": ["issues", "cycles", "projects"],
    "asana": ["tasks", "projects", "sections"], "figma": ["files", "comments", "components"],
    "snowflake": ["queries", "warehouses", "tables"], "bigquery": ["datasets", "jobs", "tables"],
    "twilio": ["messages", "calls", "numbers"], "shopify": ["orders", "products", "customers"],
    "okta": ["users", "groups", "apps"], "workday": ["workers", "requisitions", "absences"],
    "docusign": ["envelopes", "templates", "recipients"], "intercom": ["conversations", "contacts", "articles"],
    "mixpanel": ["events", "funnels", "cohorts"], "confluence": ["pages", "spaces", "comments"],
    "gitlab": ["merge_requests", "pipelines", "projects"], "bitbucket": ["pull_requests", "repositories", "branches"],
    "grafana": ["panels", "alerts", "datasources"], "segment": ["sources", "destinations", "tracking_plans"],
}
_VERBS = [("list", "Lists"), ("get", "Gets one of the"), ("create", "Creates a new item among the"),
          ("update", "Updates one of the"), ("search", "Searches the")]


def _decoys(n):
    out = []
    for svc, nouns in _SERVICES.items():
        for noun in nouns:
            for verb, vtext in _VERBS:
                if len(out) >= n:
                    return out
                name = "%s_%s_%s" % (svc, verb, noun)
                desc = ("%s %s in %s. Supports filtering by status and date range and returns JSON with ids, "
                        "owners and timestamps. Use pagination for large result sets." % (vtext, noun.replace("_", " "), svc.title()))
                out.append(Tool(svc, name, desc,
                                [P("query", "string", "Filter text"), P("limit", "integer", "Maximum results"),
                                 P("cursor", "string", "Pagination cursor")]))
    while len(out) < n:  # more than we have templates for: numbered variants
        i = len(out)
        out.append(Tool("misc", "misc_service_%d_action" % i, "Performs action %d in an internal service. Returns JSON." % i,
                        [P("query", "string", "Filter text")]))
    return out
