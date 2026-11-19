"""Seven requests for the department collision evaluation. Oracles are computed straight from the fixtures.

right_tools = the only tools a correct run needs. Any call to another tool counts as a wrong call, which is how the
'picked the look-alike from the wrong department' failure is measured.
"""
from collections import defaultdict
from dataclasses import dataclass, field

import dept_catalog as D

CTX = "Context: today is %s. Departments: HR, Finance, IT, Legal, Facilities." % D.TODAY


@dataclass
class Scenario:
    id: str
    title: str
    kind: str
    request: str
    answer_format: str
    expected_answer: object
    right_tools: set
    expected_actions: list = field(default_factory=list)
    min_size: int = 0          # smallest catalog that contains the departments this request needs
    pii_marker: str = ""       # if set, count how many distinct strings with this marker reach the model

    @property
    def prompt(self):
        return "%s\n\n%s\n\nWhen finished, reply with only JSON: %s" % (CTX, self.request, self.answer_format)


def ids(rows):
    return sorted(r["id"] for r in rows)


# D1  collision, cue in the wording (HR list_requests among five *_list_requests)
d1 = ids(r for r in D.HR.values() if r["status"] == "pending" and r["team"] == "Engineering")
D1 = Scenario("D1", "Collision: HR requests", "five *_list_requests tools; 'time-off / work-from-home' says HR",
              "Which time-off, work-from-home or schedule-change requests from the Engineering team are still pending?",
              'a sorted list of request ids', d1, {"hr_list_requests"})

# D2  collision, cue is a concept (purchase approvals -> Finance), filters + a paged list
d2 = ids(r for r in D.FIN.values() if r["status"] == "pending" and r["kind"] == "purchase")
D2 = Scenario("D2", "Collision: Finance purchases", "'purchase approvals' means Finance, and its list is paged",
              "Which purchase approvals are still waiting for a decision?",
              'a sorted list of request ids', d2, {"finance_list_requests"})

# D3  two departments, ordered, with a write
d3a = ids(r for r in D.IT.values() if r["status"] == "pending" and r["type"] == "access" and r["system"] == "CRM")
d3b = len([r for r in D.HR.values() if r["status"] == "pending"])
D3 = Scenario("D3", "Two departments, ordered, write", "list IT -> approve each -> count in HR; approve exists in every department",
              "Approve every pending IT access request for the CRM system, then tell me how many HR requests are still pending "
              "(all types).",
              'an object {"approved": <sorted list of the request ids you approved>, "hr_pending": <number>}',
              {"approved": d3a, "hr_pending": d3b}, {"it_list_requests", "it_approve_request", "hr_list_requests"},
              [("approve", i) for i in d3a])

# D4  bulk fan-out: list (2 pages) -> get_request for every pending item -> group and sum
tot = defaultdict(int)
for r in D.FIN.values():
    if r["status"] == "pending":
        tot[r["requester"]] += r["amount"]
d4 = sorted(n for n, v in tot.items() if v > 6000)
D4 = Scenario("D4", "Bulk fan-out", "56 pending finance requests; the amount is only on get_request, so 56 lookups; tiny answer",
              "Which requesters have more than $6,000 in total across their pending finance requests? Give their names.",
              'a sorted list of names', d4, {"finance_list_requests", "finance_get_request"})

# D5  arithmetic over fetched records
hw = [r["amount"] for r in D.FIN.values() if r["status"] == "approved" and r["category"] == "hardware"]
d5 = round(sum(hw) / len(hw))
D5 = Scenario("D5", "Aggregation with arithmetic", "16 lookups then an average; the model must compute or code it",
              "What is the average amount of the approved Finance requests in the hardware category (both expense and purchase kinds), "
              "rounded to the nearest whole dollar?",
              'a single integer', d5, {"finance_list_requests", "finance_get_request"})

# D6  flaky upstream: the first report call fails
D6 = Scenario("D6", "Flaky tool", "the first IT report call returns a 503-style error; a retry works",
              "How many IT tickets were closed in September 2026, according to the IT monthly summary report?",
              'a single integer', D.REPORTS["it"]["closed"], {"it_get_summary_report"})

# D7  same tool name family (search_records) in all five departments; only Legal is right
d7 = ids(r for r in D.RECORDS["legal"] if "orion" in r["title"].lower())
D7 = Scenario("D7", "Collision: search_records", "five *_search_records tools return different things; the request names legal matters",
              "Search the legal matters for 'Orion' and give me the matter ids.",
              'a sorted list of ids', d7, {"legal_search_records"}, min_size=50)

ALL = [D1, D2, D3, D4, D5, D6, D7]

if __name__ == "__main__":
    for s in ALL:
        print(s.id, s.title, "->", s.expected_answer, s.expected_actions[:3])
