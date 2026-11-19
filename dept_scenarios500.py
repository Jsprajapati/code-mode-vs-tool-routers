"""Scenarios for the 500-tool catalog: router stress tests (R) and the situations where Code Mode claims to win (C).

R1  a request that spans every department (the router keeps only its top-3 departments)
R3  one needle tool among ~500 (reset a password)
C1  one tool returns a large ledger; the answer is two numbers            (claim: filter large results in code)
C2  the same fan-out at N = 5, 20, 50, 100, 200 open orders               (claim: gains grow with N; small jobs cost more)
C3  copy a long document unchanged into a note                            (claim: data need not pass through the model twice)
C4  start an async export, poll until ready, download                      (claim: loops and polling run in code)
C5  copy 120 customers with emails and phones from CRM to billing         (claim: sensitive data need not reach the model)
"""
import dept_catalog as D
from dept_scenarios import ALL as BASE_ALL
from dept_scenarios import Scenario, ids

# R1
_p = "Ivan Petrov"
r1 = sorted(r["id"] for st in D.STORES.values() for r in st.values() if r["status"] == "pending" and r["requester"] == _p)
R1 = Scenario("R1", "Router stress: all departments", "needs the list tool of every department; the router keeps only its top 3",
              "List every request from %s that is still pending, across all departments." % _p, "a sorted list of request ids", r1,
              {"%s_list_requests" % d for d in D.STORES}, min_size=50)

# R3
R3 = Scenario("R3", "Needle in 500 tools", "one specific tool among hundreds of look-alikes and decoys",
              "Reset the password for Jun Takeda.", '{"reset": true}', {"reset": True}, {"it_reset_password"},
              [("reset_password", "Jun Takeda")], min_size=50)

# C1
_fl = [r for r in D.LEDGER if r["status"] == "flagged"]
C1 = Scenario("C1", "Large result, small answer", "ledger of 1,200 rows returned by one tool; answer is two numbers",
              "Using the finance general ledger for 2026-09, how many lines have status flagged, and what is their total amount?",
              '{"count": <number>, "total": <number>}', {"count": len(_fl), "total": sum(r["amount"] for r in _fl)},
              {"finance_export_ledger"}, min_size=500)

# C2 at several N
_open = sorted((r for r in D.PO.values() if r["status"] == "open"), key=lambda r: r["id"])
C2 = []
for _n in (5, 20, 50, 100, 200):
    C2.append(Scenario("C2_%d" % _n, "Scaling, N=%d" % _n, "list open orders, then get_order for each of the first N; sum the amounts",
                       "What is the total amount of the first %d open procurement orders (lowest order ids)? Give a single integer." % _n,
                       "a single integer", sum(r["amount"] for r in _open[:_n]), {"procurement_list_orders", "procurement_get_order"}, min_size=500))

# C3
C3 = Scenario("C3", "Copy a long document", "2,400-word document read from one tool and written unchanged through another",
              "Copy the full text of document DOC-17 unchanged into a note on legal matter LEG-007, then tell me how many characters you copied.",
              '{"chars": <number>}', {"chars": len(D.DOC_TEXT)}, {"docs_get_document", "legal_create_note"},
              [("note", "LEG-007", D.DOC_SHA)], min_size=500)

# C4
C4 = Scenario("C4", "Poll until ready", "the export is pending for four status checks, then ready",
              "Start the IT audit export, wait until it is ready, then download it and tell me how many rows it has.",
              "a single integer", 317, {"it_start_export", "it_get_export_status", "it_download_export"}, min_size=500)

# C5
C5 = Scenario("C5", "Copy PII between systems", "120 customers with emails and phones; the model should not need to read them",
              "Copy all customers from the CRM export into the billing system, then tell me how many were imported.",
              '{"imported": <number>}', {"imported": len(D.CUSTOMERS)}, {"crm_export_customers", "billing_import_customers"},
              [("import", len(D.CUSTOMERS), D.CUST_SHA)], min_size=500, pii_marker="@pii.example")

NEW = [R1, R3, C1] + C2 + [C3, C4, C5]
ALL = BASE_ALL + NEW
