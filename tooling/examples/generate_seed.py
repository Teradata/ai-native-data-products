"""The seed data of the two examples that accompany the IT Service Desk, built from its own files.

IT Asset Configuration (CMDB) and Customer Service Agreements (CSA) share the service desk's
customers and tickets, so their data is generated from the service desk's `customers.csv` and
`tickets.csv`: every customer and ticket number they hold exists there, apart from the
disagreements planted on purpose (see each example's README). Unlike tooling/bindings/seed.py,
which writes structurally valid rows for any product, this writes realistic ones for these two.

Deterministic: a fixed seed, so a rerun writes the committed files byte for byte. The examples'
data is a frozen fixture; regenerate only between cycles, never mid-run.

usage: python tooling/examples/generate_seed.py
"""
import csv
import random
import re
from datetime import date, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ITSD = REPO / "examples" / "it-service-desk-data-product" / "data"
CMDB = REPO / "examples" / "it-asset-configuration-data-product" / "data"
CSA = REPO / "examples" / "customer-service-agreements-data-product" / "data"
rng = random.Random(20261028)


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


customers = read(ITSD / "customers.csv")
tickets = read(ITSD / "tickets.csv")
cust = {c["customer_id"]: c for c in customers}

# --------------------------------------------------------------------------- CMDB
ci_types = [
    ("CIT-HW", "End-user hardware", "Hardware", "", "Devices issued to customer staff"),
    ("CIT-INF", "Infrastructure", "Infrastructure", "", "Compute, storage and network that services run on"),
    ("CIT-APP", "Applications and services", "Software", "", "Business applications and platform services"),
    ("CIT-LAPTOP", "Laptop", "Hardware", "CIT-HW", "Portable computer issued to one person"),
    ("CIT-DESKTOP", "Desktop", "Hardware", "CIT-HW", "Fixed workstation"),
    ("CIT-MONITOR", "Monitor", "Hardware", "CIT-HW", "External display"),
    ("CIT-PHONE", "Mobile phone", "Hardware", "CIT-HW", "Managed mobile device"),
    ("CIT-HOST", "Physical host", "Infrastructure", "CIT-INF", "Physical server running virtual machines"),
    ("CIT-VM", "Virtual server", "Infrastructure", "CIT-INF", "Virtual machine running application workloads"),
    ("CIT-DB", "Database server", "Infrastructure", "CIT-INF", "Server running a database engine"),
    ("CIT-NET", "Network device", "Network", "CIT-INF", "Switch, router or firewall"),
    ("CIT-VPN", "VPN gateway", "Network", "CIT-INF", "Remote-access gateway"),
    ("CIT-BIZAPP", "Business application", "Software", "CIT-APP", "Application a customer runs its business on"),
    ("CIT-IDP", "Identity service", "Service", "CIT-APP", "Directory, single sign-on and MFA"),
    ("CIT-MAIL", "Email and messaging service", "Service", "CIT-APP", "Mail, chat and collaboration"),
    ("CIT-BI", "Reporting platform", "Software", "CIT-APP", "Reporting and BI tooling"),
    ("CIT-PORTAL", "Customer portal", "Software", "CIT-APP", "Externally facing web application"),
]
write(CMDB / "ci_types.csv", ["ci_type_code", "name", "ci_class", "parent_ci_type_code", "description"],
      [dict(zip(["ci_type_code", "name", "ci_class", "parent_ci_type_code", "description"], t)) for t in ci_types])

locations = [
    ("LOC-SYD-DC1", "Sydney datacentre 1", "Sydney", "Australia", "ANZ", "Datacentre"),
    ("LOC-MEL-DC2", "Melbourne datacentre 2", "Melbourne", "Australia", "ANZ", "Datacentre"),
    ("LOC-SGP-DC1", "Singapore datacentre 1", "Singapore", "Singapore", "APAC", "Datacentre"),
    ("LOC-CLOUD-AU", "Public cloud, Australia East", "Sydney", "Australia", "ANZ", "Cloud"),
    ("LOC-CLOUD-SG", "Public cloud, Southeast Asia", "Singapore", "Singapore", "APAC", "Cloud"),
    ("LOC-SYD-OFF", "Sydney customer offices", "Sydney", "Australia", "ANZ", "Office"),
    ("LOC-MEL-OFF", "Melbourne customer offices", "Melbourne", "Australia", "ANZ", "Office"),
    ("LOC-AKL-OFF", "Auckland customer offices", "Auckland", "New Zealand", "ANZ", "Office"),
    ("LOC-SGP-OFF", "Singapore customer offices", "Singapore", "Singapore", "APAC", "Office"),
    ("LOC-HKG-OFF", "Hong Kong customer offices", "Hong Kong", "Hong Kong", "APAC", "Office"),
    ("LOC-TYO-OFF", "Tokyo customer offices", "Tokyo", "Japan", "APAC", "Office"),
]
write(CMDB / "locations.csv", ["location_code", "name", "city", "country", "region", "location_type"],
      [dict(zip(["location_code", "name", "city", "country", "region", "location_type"], l)) for l in locations])

offices = {"ANZ": ["LOC-SYD-OFF", "LOC-MEL-OFF", "LOC-AKL-OFF"], "APAC": ["LOC-SGP-OFF", "LOC-HKG-OFF", "LOC-TYO-OFF"]}
dcs = {"ANZ": ["LOC-SYD-DC1", "LOC-MEL-DC2"], "APAC": ["LOC-SGP-DC1"]}
clouds = {"ANZ": "LOC-CLOUD-AU", "APAC": "LOC-CLOUD-SG"}
models = {
    "CIT-LAPTOP": [("Lenovo", "ThinkPad T14"), ("Dell", "Latitude 7440"), ("Apple", "MacBook Pro 14")],
    "CIT-DESKTOP": [("Dell", "OptiPlex 7010"), ("HP", "EliteDesk 800")],
    "CIT-MONITOR": [("Dell", "P2723DE"), ("LG", "27UP850")],
    "CIT-PHONE": [("Apple", "iPhone 14"), ("Samsung", "Galaxy S23")],
    "CIT-HOST": [("Dell", "PowerEdge R750"), ("HPE", "ProLiant DL380")],
    "CIT-VM": [("VMware", "vSphere VM")], "CIT-DB": [("Microsoft", "SQL Server 2019"), ("PostgreSQL", "PostgreSQL 14")],
    "CIT-NET": [("Cisco", "Catalyst 9300"), ("Fortinet", "FortiGate 100F")], "CIT-VPN": [("Palo Alto", "PA-3220")],
}
cost = {"CIT-LAPTOP": 2200, "CIT-DESKTOP": 1500, "CIT-MONITOR": 450, "CIT-PHONE": 1300, "CIT-HOST": 28000,
        "CIT-VM": 0, "CIT-DB": 12000, "CIT-NET": 9000, "CIT-VPN": 22000}
life = {"CIT-LAPTOP": 4, "CIT-DESKTOP": 5, "CIT-MONITOR": 6, "CIT-PHONE": 3, "CIT-HOST": 6, "CIT-DB": 5,
        "CIT-NET": 7, "CIT-VPN": 6}
teams = {"CIT-LAPTOP": "Service Desk", "CIT-DESKTOP": "Service Desk", "CIT-MONITOR": "Service Desk",
         "CIT-PHONE": "Service Desk", "CIT-HOST": "Infrastructure", "CIT-VM": "Infrastructure",
         "CIT-DB": "Infrastructure", "CIT-NET": "Infrastructure", "CIT-VPN": "Infrastructure",
         "CIT-BIZAPP": "Applications", "CIT-IDP": "Infrastructure", "CIT-MAIL": "Applications",
         "CIT-BI": "Applications", "CIT-PORTAL": "Applications"}

items, deps = [], []


def add(name, type_code, location, customer="", criticality="Medium", environment="Production",
        status="Live", purchased=None):
    n = len(items) + 1
    key = f"CI-{n:05d}"
    make, model = rng.choice(models.get(type_code, [("", "")]))
    row = dict(configuration_item_id=key, name=name, ci_type_code=type_code, location_code=location,
               customer_id=customer, environment=environment, lifecycle_status=status, criticality=criticality,
               support_team=teams[type_code], manufacturer=make, model_name=model)
    if type_code in life:
        purchased = purchased or date(rng.randint(2019, 2025), rng.randint(1, 12), rng.randint(1, 28))
        row["purchase_date"] = purchased.isoformat()
        row["warranty_end_date"] = date(purchased.year + 3, purchased.month, purchased.day).isoformat()
        row["end_of_support_date"] = date(purchased.year + life[type_code], purchased.month, purchased.day).isoformat()
        row["purchase_cost"] = f"{cost[type_code] * rng.uniform(0.9, 1.15):.2f}" if cost[type_code] else ""
        row["serial_number"] = f"{make[:2].upper()}{rng.randint(10**7, 10**8 - 1)}"
        if row["end_of_support_date"] < "2026-07-01" and status == "Live" and rng.random() < 0.15:
            row["lifecycle_status"] = "Retired"
    row["last_discovered_at"] = (datetime(2026, 6, 24, 2, 0) + timedelta(minutes=n * 7)).isoformat()
    items.append(row)
    return key


def depend(source, target, kind, since):
    deps.append(dict(source_ci_id=source, target_ci_id=target, relationship_type=kind,
                     established_date=since))


# Shared provider platforms: every customer depends on these, so one failure crosses customers.
idp = add("Managed identity platform", "CIT-IDP", "LOC-CLOUD-AU", criticality="Critical")
mail = add("Managed email and collaboration", "CIT-MAIL", "LOC-CLOUD-AU", criticality="Critical")
shared = {}
for region in ("ANZ", "APAC"):
    for dc in dcs[region]:
        hosts = [add(f"Host cluster node {dc[4:7]}-{i}", "CIT-HOST", dc, criticality="High",
                     purchased=date(2019 + i, 3, 1)) for i in (1, 2)]
        core = add(f"Core switch {dc[4:7]}", "CIT-NET", dc, criticality="Critical", purchased=date(2018, 9, 1))
        for h in hosts:
            depend(h, core, "ConnectsThrough", "2020-01-01")
        shared[dc] = hosts
    vpn = add(f"Remote access gateway {region}", "CIT-VPN", dcs[region][0], criticality="Critical",
              purchased=date(2020, 2, 1) if region == "ANZ" else date(2021, 7, 1))
    shared[region + "-vpn"] = vpn

apps_by_customer = {}
devices_by_customer = {}
for c in customers:
    cid, region, tier = c["customer_id"], c["region"], c["tier"]
    since = c["contract_start_date"]
    office = rng.choice(offices[region])
    crit = {"Platinum": "Critical", "Gold": "High", "Silver": "Medium", "Bronze": "Low"}[tier]
    dc = rng.choice(dcs[region])
    apps = {}
    names = ["CRM", "ERP", "Customer portal", "Reporting"] if tier in ("Platinum", "Gold") else ["CRM", "Reporting"]
    db = add(f"{c['company_name']} database server", "CIT-DB", dc, cid, crit)
    depend(db, rng.choice(shared[dc]), "HostedOn", since)
    for app in names:
        type_code = {"CRM": "CIT-BIZAPP", "ERP": "CIT-BIZAPP", "Customer portal": "CIT-PORTAL",
                     "Reporting": "CIT-BI"}[app]
        a = add(f"{c['company_name']} {app}", type_code, clouds[region] if app == "Reporting" else dc, cid, crit)
        if app != "Reporting":
            vm = add(f"{c['company_name']} {app} application server", "CIT-VM", dc, cid, crit)
            depend(a, vm, "RunsOn", since)
            depend(vm, rng.choice(shared[dc]), "HostedOn", since)
            depend(a, db, "DependsOn", since)
        depend(a, idp, "DependsOn", since)
        apps[app] = a
    devices = []
    staff = {"Platinum": 6, "Gold": 5, "Silver": 4, "Bronze": 3}[tier]
    for i in range(staff):
        kind = "CIT-LAPTOP" if i % 3 != 2 else rng.choice(["CIT-DESKTOP", "CIT-PHONE", "CIT-MONITOR"])
        d = add(f"{c['company_name']} {dict((t[0], t[1]) for t in ci_types)[kind].lower()} {i + 1}", kind,
                office, cid, "Low")
        if kind in ("CIT-LAPTOP", "CIT-PHONE"):
            depend(d, shared[region + "-vpn"], "ConnectsThrough", since)
        devices.append(d)
    apps_by_customer[cid] = apps
    devices_by_customer[cid] = devices

# Deliberate quality findings: a Live item missing its support date, and a duplicated serial number.
for row in items:
    if row["ci_type_code"] == "CIT-LAPTOP" and row["lifecycle_status"] == "Live" and rng.random() < 0.06:
        row["end_of_support_date"] = ""
laptops = [r for r in items if r["ci_type_code"] == "CIT-LAPTOP"]
laptops[7]["serial_number"] = laptops[3]["serial_number"]

write(CMDB / "configuration_items.csv",
      ["configuration_item_id", "name", "ci_type_code", "location_code", "customer_id", "environment",
       "lifecycle_status", "criticality", "support_team", "manufacturer", "model_name", "serial_number",
       "purchase_date", "warranty_end_date", "end_of_support_date", "purchase_cost", "last_discovered_at"],
      items)
write(CMDB / "ci_relationships.csv", ["source_ci_id", "target_ci_id", "relationship_type", "established_date"],
      [d for d in deps if d])

# Which item each ticket affected, from its text and category.
by_key = {r["configuration_item_id"]: r for r in items}


def item_for(t):
    text = (t["subject"] + " " + t["description"]).lower()
    apps, devices = apps_by_customer[t["customer_id"]], devices_by_customer[t["customer_id"]]
    for word, app in (("crm", "CRM"), ("erp", "ERP"), ("portal", "Customer portal"), ("report", "Reporting"),
                      ("dashboard", "Reporting"), ("power bi", "Reporting")):
        if word in text and app in apps:
            return apps[app]
    cat = t["category_id"]
    region = cust[t["customer_id"]]["region"]
    if cat in ("CAT-011", "CAT-012") or re.search(r"\b(sso|mfa|password|login|account)\b", text):
        return idp
    if cat == "CAT-013" or "email" in text or "teams" in text:
        return mail
    if cat == "CAT-007" or "vpn" in text:
        return shared[region + "-vpn"]
    if cat in ("CAT-006", "CAT-014") or re.search(r"laptop|keyboard|monitor|printer|screen|battery", text):
        # Breached tickets lean to the oldest device: the signal the cross-product analysis looks for.
        ordered = sorted(devices, key=lambda k: by_key[k].get("purchase_date") or "9999")
        return ordered[0] if t["sla_breached"] == "True" else rng.choice(ordered)
    if cat in ("CAT-008", "CAT-009", "CAT-010"):
        return rng.choice(list(apps.values()))
    return None


links = []
for t in tickets:
    ci = item_for(t)
    if ci is None:
        continue
    created = datetime.fromisoformat(t["created_at"])
    links.append(dict(ticket_id=t["ticket_id"], configuration_item_id=ci, impact="Primary",
                      linked_at=(created + timedelta(minutes=rng.randint(5, 240))).isoformat()))
    if ci == idp and rng.random() < 0.3:  # an identity fault often also takes down a customer app
        apps = list(apps_by_customer[t["customer_id"]].values())
        links.append(dict(ticket_id=t["ticket_id"], configuration_item_id=rng.choice(apps), impact="Secondary",
                          linked_at=(created + timedelta(hours=rng.randint(2, 20))).isoformat()))
write(CMDB / "ticket_item_links.csv", ["ticket_id", "configuration_item_id", "impact", "linked_at"], links)

# --------------------------------------------------------------------------- CSA
industries = {"Financial": "Financial services", "Logistics": "Transport and logistics", "Healthcare": "Healthcare",
              "Energy": "Energy and utilities", "Retail": "Retail", "Manufacturing": "Manufacturing",
              "Consulting": "Professional services", "Engineering": "Engineering", "Analytics": "Professional services",
              "Property": "Property", "Insurance": "Financial services", "Pharmaceuticals": "Healthcare",
              "Media": "Media", "Tech": "Technology", "Hotels": "Hospitality", "Freight": "Transport and logistics",
              "Accounting": "Professional services", "Recruitment": "Professional services",
              "Construction": "Construction", "Agri": "Agriculture"}
countries = {"ANZ": ["Australia", "Australia", "New Zealand"], "APAC": ["Singapore", "Hong Kong", "Japan"]}
managers = ["Account team East", "Account team South", "Account team Asia"]
csa_customers = []
for c in customers:
    words = c["company_name"].split()
    industry = next((v for k, v in industries.items() if k in c["company_name"]), "Professional services")
    legal = c["company_name"] + (" Ltd" if c["customer_id"] == "CUST-001" else " Pty Ltd" if c["region"] == "ANZ" else " Pte Ltd")
    since = c["contract_start_date"]
    if c["customer_id"] == "CUST-012":
        since = "2021-05-01"  # disagrees with the service desk's 2021-05-10: which product is right?
    base = dict(customer_id=c["customer_id"], legal_name=legal, trading_name=c["company_name"], industry=industry,
                tier=c["tier"], region=c["region"], billing_country=rng.choice(countries[c["region"]]),
                billing_contact_email=f"accounts@{c['contact_email'].split('@')[1]}",
                account_manager=managers[0 if c["region"] == "ANZ" and int(c["customer_id"][-2:]) % 2 else 1 if c["region"] == "ANZ" else 2],
                customer_since=since, valid_from=since)
    csa_customers.append(base)
    if c["customer_id"] == "CUST-007":  # upgraded in April; the service desk still says Gold
        csa_customers.append(dict(base, tier="Platinum", valid_from="2026-04-01"))
    if c["customer_id"] == "CUST-016":  # downgraded in May; the service desk still says Silver
        csa_customers.append(dict(base, tier="Bronze", valid_from="2026-05-01"))
# A customer the service desk has never seen: signed in June, no tickets yet.
csa_customers.append(dict(customer_id="CUST-021", legal_name="Northwind Utilities Pty Ltd",
                          trading_name="Northwind Utilities", industry="Energy and utilities", tier="Gold",
                          region="ANZ", billing_country="Australia", billing_contact_email="accounts@northwind.com.au",
                          account_manager="Account team East", customer_since="2026-06-15", valid_from="2026-06-15"))
write(CSA / "customers.csv", ["customer_id", "legal_name", "trading_name", "industry", "tier", "region",
                              "billing_country", "billing_contact_email", "account_manager", "customer_since",
                              "valid_from"], csa_customers)

clauses = {
    "coverage": ["Support is provided 24 hours a day, 7 days a week, for P1 and P2 incidents.",
                 "Support is provided during business hours, 8am to 6pm local time, Monday to Friday.",
                 "P1 incidents are covered 24 hours a day; all other priorities during business hours."],
    "credits": ["Service credits are capped at 10% of the monthly service fee.",
                "Service credits are capped at 20% of the monthly service fee.",
                "Service credits are uncapped and accrue for every breached incident."],
    "termination": ["Either party may terminate for convenience on the notice period stated.",
                    "Termination for convenience is not permitted during the initial term.",
                    "The customer may terminate if service credits exceed the cap in three consecutive months."],
    "data": ["Customer data is stored and processed only in Australia.",
             "Customer data may be processed in any region the provider operates.",
             "Customer data is stored in the customer's home region and backed up to a second region."],
    "price": ["Fees increase annually by CPI.", "Fees are fixed for the term.",
              "Fees increase annually by CPI plus 2%."],
}
resolution = {"Platinum": (1, 2, 4, 8, 24, 72), "Gold": (2, 4, 4, 8, 24, 72), "Silver": (4, 8, 12, 24, 48, 96),
              "Bronze": (8, 24, 24, 72, 72, 120)}
credit_pct = {"Platinum": (10, 5, 2, 0), "Gold": (5, 3, 1, 0), "Silver": (2, 1, 0.5, 0), "Bronze": (0, 0, 0, 0)}
annual = {"Platinum": (480000, 900000), "Gold": (180000, 420000), "Silver": (60000, 160000), "Bronze": (20000, 55000)}
contracts, terms = [], []


def tier_on(cid, day):
    versions = sorted((r for r in csa_customers if r["customer_id"] == cid), key=lambda r: r["valid_from"])
    return [r for r in versions if r["valid_from"] <= day][-1]["tier"] if any(r["valid_from"] <= day for r in versions) else versions[0]["tier"]


for c in [r for r in csa_customers if r["valid_from"] == r["customer_since"]]:
    cid = c["customer_id"]
    start = date.fromisoformat(c["customer_since"])
    previous = ""
    years = 3 if c["tier"] in ("Platinum", "Gold") else 2
    while start <= date(2026, 6, 30):
        end = date(start.year + years, start.month, start.day) - timedelta(days=1)
        n = len(contracts) + 1
        key = f"CTR-{n:04d}"
        status = "Active" if end >= date(2026, 7, 1) else "Renewed"
        tier = tier_on(cid, start.isoformat())
        lo, hi = annual[tier]
        auto = rng.random() < 0.55
        text = " ".join(rng.choice(clauses[k]) for k in ("coverage", "credits", "termination", "data", "price"))
        contracts.append(dict(contract_id=key, customer_id=cid, renewal_of_contract_id=previous,
                              contract_type="Managed service" if tier != "Bronze" else "Support only",
                              start_date=start.isoformat(), end_date=end.isoformat(), status=status,
                              annual_value=f"{rng.uniform(lo, hi):.2f}", currency="AUD",
                              auto_renew=str(auto), notice_period_days=rng.choice([30, 60, 90]),
                              signed_at=(datetime.combine(start, datetime.min.time()) - timedelta(days=rng.randint(10, 45), hours=-rng.randint(9, 17))).isoformat(),
                              terms_text=text))
        p1r, p1x, p2r, p2x, p3x, p4x = resolution[tier]
        for priority, resp, res, pct in (("P1", p1r, p1x, credit_pct[tier][0]), ("P2", p2r, p2x, credit_pct[tier][1]),
                                         ("P3", 8 if tier != "Bronze" else 24, p3x, credit_pct[tier][2]),
                                         ("P4", 24 if tier != "Bronze" else 48, p4x, credit_pct[tier][3])):
            terms.append(dict(contract_id=key, priority=priority, response_hours=resp, resolution_hours=res,
                              credit_percent=f"{pct:.2f}"))
        previous = key
        start = end + timedelta(days=1)
# Two endings, so the renewal model has negative examples: one project that lapsed, one terminated early.
for cid, kind, start, end, status in (("CUST-008", "Project", "2023-02-01", "2024-01-31", "Expired"),
                                      ("CUST-014", "Project", "2024-03-01", "2025-02-28", "Terminated")):
    n = len(contracts) + 1
    contracts.append(dict(contract_id=f"CTR-{n:04d}", customer_id=cid, renewal_of_contract_id="", contract_type=kind,
                          start_date=start, end_date=end, status=status, annual_value=f"{rng.uniform(40000, 90000):.2f}",
                          currency="AUD", auto_renew="False", notice_period_days=30,
                          signed_at=f"{start}T10:00:00", terms_text=" ".join(rng.choice(clauses[k]) for k in ("coverage", "termination", "price"))))
write(CSA / "contracts.csv", ["contract_id", "customer_id", "renewal_of_contract_id", "contract_type", "start_date",
                              "end_date", "status", "annual_value", "currency", "auto_renew", "notice_period_days",
                              "signed_at", "terms_text"], contracts)
write(CSA / "service_level_terms.csv", ["contract_id", "priority", "response_hours", "resolution_hours",
                                        "credit_percent"], terms)

# Credits: issued for most finished tickets that exceeded their contract's resolution time (the contract's
# own hours, not the service desk's flat SLA, so the two products disagree on what breached); some are
# never issued (credits owed), one is a goodwill credit for a ticket neither product counts as breached,
# and one names a ticket the service desk does not have.
credits = []
for t in sorted(tickets, key=lambda t: t["created_at"]):
    finished = t["resolved_at"] or t["closed_at"]
    if not finished:
        continue
    day = t["created_at"][:10]
    contract = next((k for k in contracts if k["customer_id"] == t["customer_id"] and k["contract_type"] != "Project"
                     and k["start_date"] <= day <= k["end_date"]), None)
    term = next((x for x in terms if contract and x["contract_id"] == contract["contract_id"]
                 and x["priority"] == t["priority"]), None)
    elapsed = (datetime.fromisoformat(finished) - datetime.fromisoformat(t["created_at"])).total_seconds() / 3600
    if not term or float(term["credit_percent"]) == 0 or elapsed <= term["resolution_hours"] or rng.random() < 0.25:
        continue
    issued = datetime.fromisoformat(finished).replace(day=1) + timedelta(days=rng.randint(33, 40))
    credits.append(dict(contract_id=contract["contract_id"], ticket_id=t["ticket_id"],
                        service_month=day[:8] + "01",
                        credit_amount=f"{float(contract['annual_value']) / 12 * float(term['credit_percent']) / 100:.2f}",
                        issued_at=issued.replace(hour=9, minute=0, second=0).isoformat(),
                        reason=f"{t['priority']} incident exceeded the contracted resolution time"))
credited = {r["ticket_id"] for r in credits}
goodwill = next(t for t in tickets if t["sla_breached"] == "False" and t["status"] == "Closed"
                and cust[t["customer_id"]]["tier"] == "Platinum" and t["ticket_id"] not in credited)
gw_contract = next(k for k in contracts if k["customer_id"] == goodwill["customer_id"] and k["status"] == "Active")
credits.append(dict(contract_id=gw_contract["contract_id"], ticket_id=goodwill["ticket_id"],
                    service_month=goodwill["created_at"][:8] + "01", credit_amount="2500.00",
                    issued_at=(datetime.fromisoformat(goodwill["created_at"][:10]).replace(day=1) + timedelta(days=36, hours=9)).isoformat(),
                    reason="Goodwill credit agreed by the account manager"))
credits.append(dict(contract_id=gw_contract["contract_id"], ticket_id="TKT-00999", service_month="2026-05-01",
                    credit_amount="1800.00", issued_at="2026-06-06T09:00:00",
                    reason="P2 incident exceeded the contracted resolution time"))
credits.sort(key=lambda r: r["issued_at"])
for i, r in enumerate(credits, 1):
    r["service_credit_id"] = f"SC-{i:04d}"
write(CSA / "service_credits.csv", ["service_credit_id", "contract_id", "ticket_id", "service_month", "credit_amount",
                                    "issued_at", "reason"], credits)

print(len(items), "items;", len([d for d in deps if d]), "dependencies;", len(links), "ticket links")
print(len(csa_customers), "customer versions;", len(contracts), "contracts;", len(terms), "terms;", len(credits), "credits")
