"""Five real-world requests, each with a ground-truth answer computed straight from the fixtures.

Every scenario carries:
  request          what the user types (also what the router sees)
  search_queries   the short capability queries a model would write for tool search / search_api
  plan()           the sequence of tool calls an ideal agent makes (used by the scripted model)
  program          the Python an ideal agent writes in Code Mode
  expected_answer / expected_actions   oracle, computed independently of MCP
"""
import json
from dataclasses import dataclass, field

import catalog as C

CTX = "Context: today is %s; this week started %s. Jira project PAY, repo acme/payments, Slack #releases." % (C.TODAY, C.WEEK_START)


@dataclass
class Scenario:
    id: str
    title: str
    kind: str                 # what this scenario is meant to stress
    request: str
    answer_format: str
    search_queries: list
    plan: object              # generator function
    program: str
    expected_answer: object
    expected_actions: list = field(default_factory=list)

    @property
    def prompt(self):
        return "%s\n\n%s\n\nWhen finished, reply with only JSON: %s" % (CTX, self.request, self.answer_format)


def _jira_key(i):
    return i["key"]


# ---------------------------------------------------------------- S1
def _plan1():
    res = yield [("jira_search_issues", {"project": "PAY", "sprint": 42, "priority": "P1", "status_not": "Done"})]
    return sorted(i["key"] for i in res[0])


S1_ANSWER = sorted(k for k, i in C.ISSUES.items() if i["sprint"] == 42 and i["priority"] == "P1" and i["status"] != "Done")
S1 = Scenario(
    "S1", "Single lookup", "one intent, one tool, but 'issue search' exists in GitHub and Jira",
    "Which P1 issues in sprint 42 of the PAY project are not done yet?",
    'a sorted list of issue keys, e.g. ["PAY-101"]',
    ["search jira issues by sprint priority and status"], _plan1,
    'issues = tools.jira_search_issues(project="PAY", sprint=42, priority="P1", status_not="Done")\n'
    'print(json.dumps(sorted(i["key"] for i in issues)))',
    S1_ANSWER)


# ---------------------------------------------------------------- S2
def _plan2():
    res = yield [("slack_search_files", {"query": "Q3 roadmap", "from_user": "Priya"})]
    return res[0][0]["permalink"]


_f = sorted([f for f in C.FILES if "q3" in f["name"].lower() and "roadmap" in f["name"].lower() and "priya" in f["user"].lower()],
            key=lambda f: f["ts"], reverse=True)
S2 = Scenario(
    "S2", "Look-alike tools", "slack_search_files vs slack_search_messages vs docs_search vs email_search",
    "Find the Q3 roadmap file Priya shared in Slack and give me the link.",
    'the permalink as a JSON string',
    ["search files shared in slack by file name and sharer"], _plan2,
    'files = tools.slack_search_files(query="Q3 roadmap", from_user="Priya")\n'
    'print(json.dumps(files[0]["permalink"]))',
    _f[0]["permalink"])


# ---------------------------------------------------------------- S3
_merged = sorted(p["number"] for p in C.PRS if p["state"] == "merged" and p["merged_at"] and p["merged_at"] >= C.WEEK_START)
S3_TEXT = "Merged this week (%d): %s" % (len(_merged), ", ".join("#%d" % n for n in _merged))


def _plan3():
    res = yield [("github_list_pull_requests", {"repo": "acme/payments", "state": "merged", "since": C.WEEK_START})]
    nums = sorted(p["number"] for p in res[0])
    text = "Merged this week (%d): %s" % (len(nums), ", ".join("#%d" % n for n in nums))
    yield [("slack_post_message", {"channel": "#releases", "text": text})]
    return text


S3 = Scenario(
    "S3", "Multi-intent, ordered", "two intents in order: read from GitHub, then write to Slack",
    "Find the pull requests merged this week in acme/payments and post a one-line summary to #releases.",
    'the exact text you posted, as a JSON string',
    ["list merged pull requests in a repository since a date", "post a message to a slack channel"], _plan3,
    'prs = tools.github_list_pull_requests(repo="acme/payments", state="merged", since="%s")\n'
    'nums = sorted(p["number"] for p in prs)\n'
    'text = "Merged this week (%%d): %%s" %% (len(nums), ", ".join("#%%d" %% n for n in nums))\n'
    'tools.slack_post_message(channel="#releases", text=text)\n'
    'print(json.dumps(text))' % C.WEEK_START,
    S3_TEXT, [("slack_post_message", "#releases", S3_TEXT)])


# ---------------------------------------------------------------- S4
def _plan4():
    issues = (yield [("jira_search_issues", {"project": "PAY", "sprint": 42, "priority": "P1", "status_not": "Done"})])[0]
    prs = yield [("github_list_pull_requests", {"repo": "acme/payments", "state": "open", "query": i["key"]}) for i in issues]
    pairs = [(i["key"], p["number"]) for i, r in zip(issues, prs) for p in r]
    if not pairs:
        return []
    reviews = yield [("github_get_pr_reviews", {"repo": "acme/payments", "pull_number": n}) for _, n in pairs]
    return sorted(k for (k, n), rv in zip(pairs, reviews) if not any(x["state"] == "APPROVED" for x in rv))


def _s4_expected():
    out = []
    for k in S1_ANSWER:
        for p in C.PRS:
            if p["state"] == "open" and k in p["title"]:
                if not any(r["state"] == "APPROVED" for r in C.REVIEWS.get(p["number"], [])):
                    out.append(k)
    return sorted(out)


S4 = Scenario(
    "S4", "Fan-out chain", "list -> N lookups -> N more lookups; intermediate data is large, only a few rows matter",
    "For each P1 issue in sprint 42 of PAY that is not done, check whether its open pull request in acme/payments has an "
    "approval. List the issue keys whose open PR has NO approval.",
    'a sorted list of issue keys',
    ["search jira issues by sprint priority and status", "list pull requests in a repository filtered by title", "get reviews on a pull request"], _plan4,
    'issues = tools.jira_search_issues(project="PAY", sprint=42, priority="P1", status_not="Done")\n'
    'out = []\n'
    'for i in issues:\n'
    '    for p in tools.github_list_pull_requests(repo="acme/payments", state="open", query=i["key"]):\n'
    '        rv = tools.github_get_pr_reviews(repo="acme/payments", pull_number=p["number"])\n'
    '        if not any(x["state"] == "APPROVED" for x in rv):\n'
    '            out.append(i["key"])\n'
    'print(json.dumps(sorted(out)))',
    _s4_expected())


# ---------------------------------------------------------------- S5
def _declining(months):
    return all(months[i] > months[i + 1] for i in range(len(months) - 1))


def _plan5():
    first = (yield [("crm_list_customers", {"page": 1, "page_size": 50})])[0]
    custs = list(first["customers"])
    if first["total_pages"] > 1:
        more = yield [("crm_list_customers", {"page": p, "page_size": 50}) for p in range(2, first["total_pages"] + 1)]
        for pg in more:
            custs += pg["customers"]
    spends = yield [("crm_get_monthly_spend", {"customer_id": c["id"], "months": 4}) for c in custs]
    decl = [c for c, s in zip(custs, spends) if _declining([m["spend_usd"] for m in s["months"]])]
    if not decl:
        return []
    tix = yield [("crm_list_support_tickets", {"customer_id": c["id"]}) for c in decl]
    hit = [c for c, t in zip(decl, tix) if len(t) > 3]
    if hit:
        yield [("jira_create_issue", {"project": "PAY", "summary": "Churn risk: " + c["name"], "issue_type": "Task", "priority": "High"})
               for c in hit]
    return sorted(c["id"] for c in hit)


_hit5 = [c for c in C.CUSTOMERS
         if _declining([m["spend_usd"] for m in C.SPEND[c["id"]][-4:]])
         and len([t for t in C.TICKETS.get(c["id"], []) if t["status"] == "open"]) > 3]
S5 = Scenario(
    "S5", "Aggregation over many records", "120 customers, 3 pages, a per-customer lookup, then writes",
    "Find customers whose monthly spend fell three months in a row (strictly decreasing over the last four months) and who "
    "have more than 3 open support tickets. For each, create a High-priority Task in Jira project PAY titled "
    "'Churn risk: <customer name>'. Give me the customer ids.",
    'a sorted list of customer ids',
    ["list customers", "get monthly spend for a customer", "list support tickets for a customer", "create a jira issue"], _plan5,
    'pg = tools.crm_list_customers(page=1, page_size=50)\n'
    'custs = list(pg["customers"])\n'
    'for p in range(2, pg["total_pages"] + 1):\n'
    '    custs += tools.crm_list_customers(page=p, page_size=50)["customers"]\n'
    'hit = []\n'
    'for c in custs:\n'
    '    m = [x["spend_usd"] for x in tools.crm_get_monthly_spend(customer_id=c["id"], months=4)["months"]]\n'
    '    if all(m[i] > m[i + 1] for i in range(len(m) - 1)):\n'
    '        if len(tools.crm_list_support_tickets(customer_id=c["id"])) > 3:\n'
    '            hit.append(c)\n'
    'for c in hit:\n'
    '    tools.jira_create_issue(project="PAY", summary="Churn risk: " + c["name"], issue_type="Task", priority="High")\n'
    'print(json.dumps(sorted(c["id"] for c in hit)))',
    sorted(c["id"] for c in _hit5),
    sorted(("jira_create_issue", json.dumps({"project": "PAY", "summary": "Churn risk: " + c["name"], "issue_type": "Task",
                                            "priority": "High"}, sort_keys=True)) for c in _hit5))

ALL = [S1, S2, S3, S4, S5]
