"""Department catalog for the collision evaluation.

Five departments (HR, Finance, IT, Legal, Facilities) each expose the SAME five tool families with
near-identical names and descriptions, but different meanings and different data:

    <dept>_list_requests   <dept>_get_request   <dept>_approve_request
    <dept>_search_records  <dept>_get_summary_report

"list requests" in HR means leave requests, in Finance expense/purchase approvals, in IT access and device
requests. The user's wording is what decides which department is meant, exactly like a real multi-team catalog.

Catalog sizes (build(size)):
    15   HR + Finance + IT, core families only (3 x 5)
    50   all five departments (25 core) + 25 department-specific extras
    150  the 50 above + remaining extras + generated decoy tools from unrelated services

Fixtures are seeded and independent of size, so the same question has the same answer at every size.
"""
import random

import catalog as C
from catalog import Catalog, P, Tool

rng = random.Random(11)

NAMES = ["Priya Raman", "Dev Kapoor", "Ananya Shah", "Marcus Lee", "Sofia Alvarez", "Tom Becker", "Hana Sato",
         "Omar Haddad", "Lena Fischer", "Raj Patel", "Chloe Martin", "Ivan Petrov", "Nora Quinn", "Jun Takeda"]
TEAM_OF = {n: ["Engineering", "Sales", "Support", "Finance", "Operations"][i % 5] for i, n in enumerate(NAMES)}
TODAY = C.TODAY


def _pick(weights):
    r, acc = rng.random(), 0.0
    for k, w in weights:
        acc += w
        if r <= acc:
            return k
    return weights[-1][0]


STATUS = [("pending", 0.38), ("approved", 0.47), ("rejected", 0.15)]

# ---- HR: leave / wfh / schedule requests
HR = {}
for i in range(1, 71):
    who = rng.choice(NAMES)
    HR["HR-%03d" % i] = {"id": "HR-%03d" % i, "requester": who, "team": TEAM_OF[who],
                         "type": rng.choice(["leave", "leave", "wfh", "schedule change"]), "status": _pick(STATUS),
                         "start": "2026-%02d-%02d" % (rng.randint(10, 12), rng.randint(1, 28))}

# ---- Finance: expense reimbursements and purchase approvals (amount only in get_request)
FIN = {}
for i in range(1, 151):
    who = rng.choice(NAMES)
    kind = _pick([("expense", 0.7), ("purchase", 0.3)])
    cat = rng.choice(["travel", "software", "meals", "hardware", "training"])
    FIN["FIN-%03d" % i] = {"id": "FIN-%03d" % i, "requester": who, "status": _pick(STATUS), "kind": kind,
                           "category": cat, "amount": rng.randint(40, 2600), "description": "%s %s request" % (cat, kind)}

# ---- IT: access and device requests
IT = {}
for i in range(1, 46):
    who = rng.choice(NAMES)
    IT["IT-%03d" % i] = {"id": "IT-%03d" % i, "requester": who, "type": rng.choice(["access", "access", "device"]),
                         "system": rng.choice(["Payments", "CRM", "Analytics", "VPN", "Laptop"]), "status": _pick(STATUS)}

# ---- Legal: contract reviews
LEG = {}
_CP = ["Orion Logistics", "Helix Labs", "Northwind", "Vega Systems", "Acme Holdings", "Orion Freight", "Zenith Corp"]
for i in range(1, 31):
    LEG["LEG-%03d" % i] = {"id": "LEG-%03d" % i, "requester": rng.choice(NAMES), "counterparty": rng.choice(_CP),
                           "title": "Master services agreement", "status": _pick(STATUS)}

# ---- Facilities: desk and room requests
FAC = {}
for i in range(1, 26):
    FAC["FAC-%03d" % i] = {"id": "FAC-%03d" % i, "requester": rng.choice(NAMES), "building": rng.choice(["HQ", "Annex", "Lab"]),
                           "status": _pick(STATUS), "type": rng.choice(["desk", "room"])}

STORES = {"hr": HR, "finance": FIN, "it": IT, "legal": LEG, "facilities": FAC}

# Searchable "records" differ per department, and "Orion" appears in several on purpose.
RECORDS = {
    "hr": [{"id": "EMP-%03d" % i, "title": n} for i, n in enumerate(NAMES, 1)] + [{"id": "EMP-099", "title": "Orion Vale (contractor)"}],
    "finance": [{"id": "INV-%03d" % i, "title": "%s invoice %d" % (rng.choice(["Orion Supplies", "Helix Labs", "Northwind", "Vega Systems"]), i)}
                for i in range(1, 21)],
    "it": [{"id": "AST-%03d" % i, "title": "%s %s" % (rng.choice(["Orion", "Dell", "Lenovo", "Apple"]), rng.choice(["laptop", "monitor", "dock"]))}
           for i in range(1, 21)],
    "legal": [{"id": "MTR-%03d" % i, "title": "%s matter %d" % (rng.choice(_CP), i)} for i in range(1, 26)],
    "facilities": [{"id": "ROOM-%02d" % i, "title": "Room %s" % rng.choice(["Orion", "Atlas", "Nova", "Pegasus", "Lyra"])} for i in range(1, 16)],
}
REPORTS = {"hr": {"period": "2026-09", "headcount": 412, "open_roles": 17, "leave_days_taken": 640},
           "finance": {"period": "2026-09", "spend_usd": 1830400, "invoices_paid": 211, "open_invoices": 38},
           "it": {"period": "2026-09", "opened": 388, "closed": 361, "backlog": 27},
           "legal": {"period": "2026-09", "reviews_done": 22, "open_matters": 9},
           "facilities": {"period": "2026-09", "bookings": 1204, "work_orders": 64}}


# --------------------------------------------------------------------- tool implementations
def _mk_list(dept, filters):
    store = STORES[dept]

    def fn(status=None, requester=None, limit=200, page=None, page_size=50, **kw):
        rows = [r for r in store.values()
                if (not status or r["status"] == status) and (not requester or requester.lower() in r["requester"].lower())
                and all(not v or str(r.get(k, "")).lower() == str(v).lower() for k, v in kw.items())]
        keep = {"hr": ["id", "requester", "team", "type", "status", "start"],
                "finance": ["id", "requester", "status", "kind", "category"],       # no amount: needs get_request
                "it": ["id", "requester", "type", "system", "status"],
                "legal": ["id", "requester", "counterparty", "status"],
                "facilities": ["id", "requester", "building", "type", "status"]}[dept]
        rows = [{k: r[k] for k in keep} for r in rows]
        if dept == "finance":
            pages = max(1, (len(rows) + page_size - 1) // page_size)
            p = page or 1
            return {"requests": rows[(p - 1) * page_size:p * page_size], "page": p, "total_pages": pages}
        return rows[:limit]
    return fn


def _mk_get(dept):
    def fn(request_id):
        if request_id not in STORES[dept]:
            raise ValueError("unknown %s request id %r" % (dept, request_id))
        return dict(STORES[dept][request_id])
    return fn


def _mk_approve(dept):
    def fn(request_id, comment=None):
        if request_id not in STORES[dept]:
            raise ValueError("unknown %s request id %r" % (dept, request_id))
        C.STATE.actions.append(("approve", request_id))
        return {"ok": True, "id": request_id, "status": "approved"}
    return fn


def _mk_search(dept):
    def fn(query, limit=20):
        q = query.lower()
        return [r for r in RECORDS[dept] if q in r["title"].lower()][:limit]
    return fn


def _mk_report(dept):
    def fn(period="2026-09"):
        if dept == "it":  # flaky upstream: the first call of every run fails, a retry succeeds
            n = C.STATE.counters.get("it_report", 0)
            C.STATE.counters["it_report"] = n + 1
            if n == 0:
                raise RuntimeError("503 upstream timeout while building the report; please retry")
        return dict(REPORTS[dept], period=period)
    return fn


_DESC = {
    "hr": ("employee requests (leave, working from home, schedule changes)", "Filter by status, requester or team.",
           "id, requester, team, type, status and start date"),
    "finance": ("finance requests (expense reimbursements and purchase approvals)", "Filter by status, requester, kind or category; paged.",
                "id, requester, status, kind and category (the amount is only on the single-request lookup)"),
    "it": ("IT requests (system access and device requests)", "Filter by status, requester, system or type.",
           "id, requester, type, system and status"),
    "legal": ("legal requests (contract reviews)", "Filter by status, requester or counterparty.",
              "id, requester, counterparty and status"),
    "facilities": ("facilities requests (desk and room requests)", "Filter by status, requester or building.",
                   "id, requester, building, type and status"),
}
_FILTER_PARAMS = {
    "hr": [P("team", "string", "Team name, e.g. Engineering")],
    "finance": [P("kind", "string", "expense or purchase"), P("category", "string", "travel, software, meals, hardware or training"),
                P("page", "integer", "Page number, starting at 1"), P("page_size", "integer", "Rows per page (default 50)")],
    "it": [P("system", "string", "System name, e.g. Payments"), P("type", "string", "access or device")],
    "legal": [P("counterparty", "string", "Counterparty name")],
    "facilities": [P("building", "string", "HQ, Annex or Lab"), P("type", "string", "desk or room")],
}
_RECORD_DESC = {"hr": "employee records", "finance": "vendor invoices", "it": "hardware assets", "legal": "legal matters",
                "facilities": "rooms and desks"}
_REPORT_DESC = {"hr": "headcount, open roles and leave days", "finance": "spend, invoices paid and open invoices",
                "it": "tickets opened, closed and backlog", "legal": "reviews done and open matters",
                "facilities": "bookings and work orders"}


_RET_LIST = {"hr": "list[{id, requester, team, type, status, start}]",
             "finance": "{requests: list[{id, requester, status, kind, category}], page: int, total_pages: int}",
             "it": "list[{id, requester, type, system, status}]",
             "legal": "list[{id, requester, counterparty, status}]",
             "facilities": "list[{id, requester, building, type, status}]"}
_RET_GET = {"hr": "{id, requester, team, type, status, start}",
            "finance": "{id, requester, status, kind, category, amount: int, description}",
            "it": "{id, requester, type, system, status}",
            "legal": "{id, requester, counterparty, title, status}",
            "facilities": "{id, requester, building, type, status}"}
_RET_REPORT = {"hr": "{period, headcount, open_roles, leave_days_taken}", "finance": "{period, spend_usd, invoices_paid, open_invoices}",
               "it": "{period, opened, closed, backlog}", "legal": "{period, reviews_done, open_matters}",
               "facilities": "{period, bookings, work_orders}"}


def core_tools(dept):
    noun, filt, fields = _DESC[dept]
    first = dept.title() if dept != "it" else "IT"
    return [
        Tool(dept, "%s_list_requests" % dept,
             "List %s. %s Returns %s." % (noun, filt, fields),
             [P("status", "string", "pending, approved or rejected"), P("requester", "string", "Requester name")] + _FILTER_PARAMS[dept],
             _mk_list(dept, None), returns=_RET_LIST[dept]),
        Tool(dept, "%s_get_request" % dept,
             "Get one %s request by id with its full details." % first,
             [P("request_id", "string", "The request id", True)], _mk_get(dept), returns=_RET_GET[dept]),
        Tool(dept, "%s_approve_request" % dept,
             "Approve a pending %s request by id." % first,
             [P("request_id", "string", "The request id", True), P("comment", "string", "Optional approval comment")], _mk_approve(dept), returns="{ok: bool, id, status}"),
        Tool(dept, "%s_search_records" % dept,
             "Search %s by text. Returns matching record ids and titles." % _RECORD_DESC[dept],
             [P("query", "string", "Text to search for", True), P("limit", "integer", "Maximum results")], _mk_search(dept), returns="list[{id, title}]"),
        Tool(dept, "%s_get_summary_report" % dept,
             "Get the monthly %s summary report: %s." % (first, _REPORT_DESC[dept]),
             [P("period", "string", "Month as YYYY-MM")], _mk_report(dept), returns=_RET_REPORT[dept]),
    ]


def _t(dept, name, desc, params=()):
    return Tool(dept, "%s_%s" % (dept, name), desc, list(params))


EXTRAS = [
    _t("hr", "get_employee", "Get an employee profile: manager, team, start date and location.", [P("name", "string", "Employee name", True)]),
    _t("hr", "list_employees", "List employees, optionally by team.", [P("team", "string", "Team name")]),
    _t("hr", "get_leave_balance", "Get the remaining leave balance for an employee.", [P("name", "string", "Employee name", True)]),
    _t("hr", "list_holidays", "List company holidays for a year.", [P("year", "integer", "Year")]),
    _t("hr", "create_job_opening", "Open a new job requisition.", [P("title", "string", "Job title", True), P("team", "string", "Hiring team")]),
    _t("hr", "get_org_chart", "Get the reporting tree below a manager.", [P("manager", "string", "Manager name", True)]),
    _t("finance", "get_budget", "Get the budget and spend to date for a cost centre.", [P("cost_centre", "string", "Cost centre code", True)]),
    _t("finance", "list_invoices", "List vendor invoices by status.", [P("status", "string", "open, paid or overdue")]),
    _t("finance", "get_invoice", "Get a single vendor invoice by id.", [P("invoice_id", "string", "Invoice id", True)]),
    _t("finance", "create_payment", "Schedule a payment to a vendor.", [P("vendor", "string", "Vendor name", True), P("amount", "number", "Amount in USD", True)]),
    _t("finance", "get_vendor", "Get vendor details and payment terms.", [P("vendor", "string", "Vendor name", True)]),
    _t("finance", "list_cost_centres", "List cost centres and owners.", []),
    _t("it", "list_assets", "List hardware assets by owner or type.", [P("owner", "string", "Owner name"), P("type", "string", "laptop, monitor or dock")]),
    _t("it", "get_asset", "Get a hardware asset by tag.", [P("tag", "string", "Asset tag", True)]),
    _t("it", "reset_password", "Reset a user's password and send a reset link.", [P("user", "string", "User name", True)]),
    _t("it", "list_incidents", "List open IT incidents by severity.", [P("severity", "string", "sev1, sev2 or sev3")]),
    _t("it", "get_incident", "Get an IT incident by id with its timeline.", [P("incident_id", "string", "Incident id", True)]),
    _t("it", "create_incident", "Open a new IT incident.", [P("title", "string", "Short title", True), P("severity", "string", "sev1, sev2 or sev3")]),
    _t("legal", "get_contract", "Get a contract by id with clauses and status.", [P("contract_id", "string", "Contract id", True)]),
    _t("legal", "list_contracts", "List contracts by counterparty or status.", [P("counterparty", "string", "Counterparty name")]),
    _t("legal", "get_counterparty", "Get counterparty details and risk rating.", [P("name", "string", "Counterparty name", True)]),
    _t("legal", "list_templates", "List contract templates.", []),
    _t("legal", "create_matter", "Open a new legal matter.", [P("title", "string", "Matter title", True)]),
    _t("facilities", "list_rooms", "List meeting rooms with capacity and floor.", [P("building", "string", "HQ, Annex or Lab")]),
    _t("facilities", "book_room", "Book a meeting room for a time slot.", [P("room", "string", "Room name", True), P("start", "string", "ISO start time", True)]),
    _t("facilities", "get_desk_map", "Get the desk map of a floor.", [P("building", "string", "Building", True), P("floor", "integer", "Floor number")]),
    _t("facilities", "list_maintenance", "List open maintenance tickets.", [P("building", "string", "Building")]),
    _t("facilities", "create_work_order", "Create a facilities work order.", [P("summary", "string", "What needs doing", True)]),
]


# ====================================================================================================
# Extra tools and fixtures that exist only in the 500-tool catalog (Code Mode strengths + router stress)
# ====================================================================================================
import hashlib

rng2 = random.Random(23)

# C1: one tool returns a large ledger; a request needs two numbers out of it
_VENDORS = ["Orion Supplies", "Helix Labs", "Northwind", "Vega Systems", "Acme Holdings", "Zenith Corp", "Lumen Co", "Apex Parts"]
LEDGER = [{"id": "L-%04d" % i, "vendor": rng2.choice(_VENDORS), "category": rng2.choice(["travel", "software", "meals", "hardware", "training"]),
           "amount": rng2.randint(5, 900), "status": None} for i in range(1, 1201)]
for _r in LEDGER:
    x = rng2.random()
    _r["status"] = "flagged" if x < 0.08 else ("void" if x < 0.14 else "posted")

# C3: a long document to copy unchanged into a legal note
_W = ("party agreement clause service term payment notice liability confidentiality data security audit renewal termination "
      "delivery warranty indemnity governing law jurisdiction schedule amendment obligation remedy breach cure period fee "
      "invoice interest dispute arbitration assignment waiver force majeure insurance compliance").split()
_words = []
for _i in range(2400):
    _words.append(rng2.choice(_W))
    if _i % 17 == 16:
        _words[-1] += "."
DOC_TEXT = " ".join(_words)
DOCS = {"DOC-17": {"id": "DOC-17", "title": "Master services agreement draft v3", "text": DOC_TEXT}}
DOC_SHA = hashlib.sha1(DOC_TEXT.encode()).hexdigest()[:12]

# C5: customers with PII that must be copied from CRM to billing
CUSTOMERS = []
for _i in range(1, 121):
    _n = rng2.choice(NAMES).split()
    CUSTOMERS.append({"id": "CUS-%03d" % _i, "name": "%s %s" % (_n[0], _n[1]), "email": "%s.%s%d@pii.example" % (_n[0].lower(), _n[1].lower(), _i),
                      "phone": "+91 9%09d" % rng2.randint(0, 999999999)})
CUST_SHA = hashlib.sha1("\n".join(sorted(c["email"] for c in CUSTOMERS)).encode()).hexdigest()[:12]

# C2: 300 procurement orders; list has no amount, get_order does
PO = {}
for _i in range(1, 301):
    PO["PO-%03d" % _i] = {"id": "PO-%03d" % _i, "vendor": rng2.choice(_VENDORS), "status": "open" if rng2.random() < 0.83 else "closed",
                          "amount": rng2.randint(100, 9000)}


def _fn_ledger(period="2026-09"):
    return {"period": period, "rows": LEDGER}


def _fn_get_doc(doc_id):
    if doc_id not in DOCS:
        raise ValueError("unknown document %r" % doc_id)
    return dict(DOCS[doc_id])


def _fn_note(matter_id, text):
    if not matter_id.startswith("LEG-"):
        raise ValueError("unknown legal matter %r" % matter_id)
    C.STATE.actions.append(("note", matter_id, hashlib.sha1(text.encode()).hexdigest()[:12]))
    return {"ok": True, "matter_id": matter_id, "chars": len(text)}


def _fn_start_export():
    C.STATE.counters["export_status"] = 0
    return {"job_id": "EXP-1"}


def _fn_export_status(job_id):
    n = C.STATE.counters.get("export_status", 0) + 1
    C.STATE.counters["export_status"] = n
    return {"job_id": job_id, "status": "ready" if n > 4 else "pending"}


def _fn_export_download(job_id):
    if C.STATE.counters.get("export_status", 0) <= 4:
        raise RuntimeError("export %s is not ready yet" % job_id)
    return {"job_id": job_id, "rows": 317}


def _fn_crm_export():
    return {"customers": CUSTOMERS}


def _fn_billing_import(records):
    if isinstance(records, str):
        import json as _j
        records = _j.loads(records)
    emails = sorted(r["email"] for r in records)
    C.STATE.actions.append(("import", len(records), hashlib.sha1("\n".join(emails).encode()).hexdigest()[:12]))
    return {"imported": len(records)}


def _fn_po_list(status=None, page=1, page_size=100):
    rows = [{"id": r["id"], "vendor": r["vendor"], "status": r["status"]} for r in PO.values() if not status or r["status"] == status]
    pages = max(1, (len(rows) + page_size - 1) // page_size)
    return {"orders": rows[(page - 1) * page_size:page * page_size], "page": page, "total_pages": pages}


def _fn_po_get(order_id):
    if order_id not in PO:
        raise ValueError("unknown order %r" % order_id)
    return dict(PO[order_id])


def _fn_reset_password(user):
    C.STATE.actions.append(("reset_password", user))
    return {"ok": True, "user": user, "link_sent": True}


for _t in EXTRAS:
    if _t.name == "it_reset_password":
        _t.fn = _fn_reset_password
        _t.returns = "{ok: bool, user, link_sent: bool}"

EXTRAS_500 = [
    Tool("finance", "finance_export_ledger", "Export the full general ledger for a month as rows (id, vendor, category, amount, status).",
         [P("period", "string", "Month as YYYY-MM")], _fn_ledger,
         returns="{period, rows: list[{id, vendor, category, amount: int, status}]}"),
    Tool("docs", "docs_get_document", "Get a document by id, including its full text.", [P("doc_id", "string", "Document id", True)], _fn_get_doc,
         returns="{id, title, text}"),
    Tool("legal", "legal_create_note", "Attach a note (free text) to a legal matter by id.",
         [P("matter_id", "string", "Matter id, e.g. LEG-007", True), P("text", "string", "Note text", True)], _fn_note,
         returns="{ok: bool, matter_id, chars: int}"),
    Tool("it", "it_start_export", "Start an asynchronous IT audit export job and return its job id.", [], _fn_start_export, returns="{job_id}"),
    Tool("it", "it_get_export_status", "Get the status of an IT audit export job: pending or ready.",
         [P("job_id", "string", "Job id", True)], _fn_export_status, returns="{job_id, status}"),
    Tool("it", "it_download_export", "Download a finished IT audit export job (fails if it is not ready).",
         [P("job_id", "string", "Job id", True)], _fn_export_download, returns="{job_id, rows: int}"),
    Tool("crm", "crm_export_customers", "Export all customers from the CRM with name, email and phone.", [], _fn_crm_export,
         returns="{customers: list[{id, name, email, phone}]}"),
    Tool("billing", "billing_import_customers", "Import a list of customer records into the billing system.",
         [P("records", "array", "Customer records as objects with id, name, email and phone", True)], _fn_billing_import, returns="{imported: int}"),
    Tool("procurement", "procurement_list_orders", "List procurement purchase orders. Filter by status; paged. Returns id, vendor and status (not the amount).",
         [P("status", "string", "open or closed"), P("page", "integer", "Page number, starting at 1"),
          P("page_size", "integer", "Rows per page (default 100)")], _fn_po_list,
         returns="{orders: list[{id, vendor, status}], page: int, total_pages: int}"),
    Tool("procurement", "procurement_get_order", "Get one procurement purchase order by id with its amount.",
         [P("order_id", "string", "Order id, e.g. PO-012", True)], _fn_po_get, returns="{id, vendor, status, amount: int}"),
]

SIZES = (15, 50, 150, 500)


def build(size):
    if size == 15:
        tools = [t for d in ("hr", "finance", "it") for t in core_tools(d)]
        return Catalog(tools)
    tools = [t for d in STORES for t in core_tools(d)]
    if size <= 50:
        tools += EXTRAS[: size - len(tools)]
        return Catalog(tools)
    tools += EXTRAS
    if size >= 500:
        tools += EXTRAS_500
    return Catalog(tools).padded(size)
