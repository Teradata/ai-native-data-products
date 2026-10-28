# IT Asset Configuration Data Product: Reference Brief

**Product code:** `CMDB`  
**Full name:** `ITAssetConfiguration`

This document is the fixed input to the Design, Build and Review starter prompts. Every
decision it records is pre-settled. Paste the relevant section into the matching starter as
your intake. Do not re-open settled decisions; where a decision departs from the standard's
advocated option, the reason is already recorded here and carries through to Memory.

It is one of three example products that share one organisation and one set of customers.
The [IT Service Desk](../it-service-desk-data-product/ITSD_Reference_Brief.md) records tickets,
this product records the items those tickets were about, and
[Customer Service Agreements](../customer-service-agreements-data-product/CSA_Reference_Brief.md)
records what each customer was promised. Each is designed, built and reviewed on its own; the
places where they meet are recorded as decisions, not solved.

---

## 1. Process

- Artefacts go to a product repository of the product's own, laid out as in section 2. No
  artefact lives only in the conversation.
- Generate before you execute: render every phase and check, commit them, then deploy.
- The build runs with a PostgreSQL connection the build role can create schemas and roles
  through. Use it for DDL execution, check runs and row counts.

| Event | Commit message |
|---|---|
| Design phase complete | `design: ITAssetConfiguration design specification` |
| Build rendered (before execution) | `build: render ITAssetConfiguration for PostgreSQL` |
| Deployed, loaded and validated | `build: ITAssetConfiguration deployed; validation passed` |
| Review complete | `review: trust map complete` |

---

## 2. Repository Layout

```
cmdb-data-product/
├── README.md
├── data/
│   ├── ci_types.csv
│   ├── locations.csv
│   ├── configuration_items.csv
│   ├── ci_relationships.csv
│   └── ticket_item_links.csv
├── standards/
│   ├── design.toml                  # Organisation profile: classification (from config/)
│   └── implementation.toml          # Organisation profile: placement, naming, roles, one target per platform
├── design/
│   └── design_specification.md      # Design phase output
├── build/                           # render.py output for target postgres: phases, deploy.sql, manifest.json
└── review/
    └── trust_map.md
```

The organisation profile is the same one the IT Service Desk uses
([`config/`](../../config/)): one organisation, three products.

---

## 3. Design Phase

### 3a. Starter intake

Paste this block into the Design Starter prompt's **Intake** section.

---

**Business purpose:**  
The register of every configuration item the service provider manages: customers' devices,
business applications and the servers they run on, and the shared platforms (identity, email,
host clusters, network) that many customers depend on at once. It answers what an item is,
where it is, who owns it, when it falls out of support, what depends on it, and which service
desk tickets it was involved in.

**Primary consumers:**
- Infrastructure engineers: impact analysis before a change and during an outage
- Asset managers: refresh planning, end-of-support exposure, asset cost
- Service desk agents and AI agents: the item behind a ticket, and what else it affects
- Analysts: asset age and criticality joined to ticket outcomes

**Top use cases:**
1. List everything that depends, directly or transitively, on an item (its blast radius)
2. Find the items past or near end of support, by customer and criticality
3. Report asset cost and counts by type, location and customer
4. Find the items a ticket affected, and the tickets an item was involved in
5. Monitor register quality: missing support dates, duplicate serial numbers, dangling
   dependencies

**Composition:** Traditional Data Product: Domain, Semantic, Observability, Memory
(documentation facet only). No Search, no Prediction, no runtime Memory.

**Data sources:** Five CSV files from the configuration management tool's nightly export.
Batch ingestion; no streaming source in this cycle.

**Approximate volumes:**

| Entity | Initial rows | Monthly growth | Horizon |
|---|---|---|---|
| ConfigurationItem | 235 | 15 | 5 years |
| ItemDependency | 300 | 20 | 5 years |
| AffectedItem | 161 | 80 | 5 years |
| ItemType | 17 | <1 | 5 years |
| Location | 11 | <1 | 5 years |

**Sensitivity:** none. Devices are recorded against the customer that owns them, not the person
using them; the register holds no personal data.

**Entity model source:** custom, using ITIL's vocabulary (configuration item, CI type,
relationship). ITIL publishes no data model and vendor CMDB schemas are proprietary.

**Other products:** an item's owning customer and a ticket's number belong to the IT Service
Desk product. Hold them as that product's natural keys (`CUST-nnn`, `TKT-nnnnn`); do not copy
its entities.

---

### 3b. Pre-settled design decisions

#### The seven catalogued decisions

| ID | Decision | Answer | Advocated? | Reason |
|---|---|---|---|---|
| DEC-TIMESTAMP-ZONE | Zone handling | `zone-aware` | Yes | Items sit in several countries; discovery reports UTC |
| DEC-TEMPORAL-PATTERN | History representation | `scd2` | **No, a departure** | No model reads this product's history, so no feature needs transaction time; corrections are rare and made as new versions; business validity alone answers "what was this item's state on a date", which is the question asset and impact analysis asks |
| DEC-COLUMN-STRATEGY | Where audit, lineage and quality live | `offload` | Yes | Items change nightly through discovery; the history would bloat the entity |
| DEC-SURROGATE-ALLOCATION | Keeping identifiers stable | `keymap` for ConfigurationItem; `inline` for ItemType and Location | Partially: the two Reference entities depart | Items are referenced by dependencies and ticket links; type and site codes are never re-keyed |
| DEC-DELETE-STRATEGY | Deletion | `soft-delete` | Yes | A decommissioned item must still explain the tickets and dependencies it had |
| DEC-QUALITY-STORAGE | Quality assessments | `observability` | Yes | Register quality is tracked as a trend |
| DEC-AUDIT-RETENTION | Retention of change and deletion records | `regulatory`: 2 years queryable, 7 years archived | Yes | The register supports the fixed-asset register, kept seven years |

#### Module-specific decisions

**Domain: entity model**

| Entity | Kind | Declared profile | Allocation | Notes |
|---|---|---|---|---|
| ConfigurationItem | History | `SCD2_HISTORY` | keymap | Natural key is the register's item number, `CI-nnnnn` |
| ItemType | Reference | `SCD2_HISTORY` | inline | Two-level taxonomy, code `CIT-*` |
| Location | Reference | `SCD2_HISTORY` | inline | Datacentres, cloud regions, offices; code `LOC-*` |
| ItemDependency | Relationship | `ASSOCIATION_SCD2` | inline | Identity: dependent item, supporting item, dependency type |
| AffectedItem | Relationship | `ASSOCIATION_SCD2` | inline | Identity: item and the service desk's ticket number |

`ItemDependency` holds two references to `ConfigurationItem`, so each names its own join:
`dependent` and `supporting`. Dependency types are `DependsOn`, `RunsOn`, `HostedOn` and
`ConnectsThrough`.

**Semantic:** the orientation entrypoint is the access layer, by view. Metrics: live items,
asset cost, critical item share, current dependencies.

**Observability: quality dimensions and weights**

| Dimension | Weight |
|---|---|
| Completeness | 30% |
| Validity | 20% |
| Consistency | 30% |
| Accuracy | 10% |
| Timeliness | 10% |

Thresholds:
- End-of-support date present on live hardware: pass ≥ 0.95, warn ≥ 0.85
- Location present: pass ≥ 0.95, warn ≥ 0.90
- Warranty end not before purchase; no item depending on itself: pass at 1.0
- Duplicate current serial numbers, dangling references: any one fails
- Freshness, on the date discovery last saw an item: warn after 2 days, fail after 7

Validation runs on each load and daily. Lineage covers source files into Domain.

**Memory:** documentation facet only; every decision above produces a `DesignDecision`, and
`INV-MEMORY-006` sets the floor per module.

**Access layer:** the three standard tiers. With no runtime facet, the agent tier writes only
Observability's usage and quality events.

---

## 4. Build Phase

### 4a. Starter intake

---

**Target platform:** PostgreSQL 16  
**Product name:** `ITAssetConfiguration`  
**Design input:** `design/design_specification.md` in the repository  
**Organisation profile:** `standards/design.toml` and `standards/implementation.toml` (target
`postgres`). Resolve them with the design specification into the build context before
generating any object  
**Object storage in use?** No

---

### 4b. Physical design

Physical choices are the PostgreSQL binding's and the organisation profile's; this brief adds
none. Schemas, object names and roles come from the `postgres` target. Record any deviation as
a design decision in Memory.

After deployment, load the five source files, then run the build manifest's checks with
`tooling/bindings/validate.py` and confirm they pass before the final commit.

---

## 5. Review Phase

### 5a. Starter intake

---

**What to review:** Both design and build  
**Artefacts:** `design/design_specification.md`, `build/` and the live product on PostgreSQL  
**Composition:** Traditional Data Product (Domain, Semantic, Observability, Memory
documentation)

---

### 5b. Review instructions

Gather evidence from the deployed product: Semantic for registration completeness, Memory for
the recorded decisions (all seven catalogued decisions, including the `DEC-TEMPORAL-PATTERN`
departure with its reason), Observability for the validation run and trust map, and the
platform catalogue for metadata coverage (`INV-DOMAIN-001`).

Use the trust-map format of the IT Service Desk brief, section 5b, in the published vocabulary
of `design/patterns/validation.md` §4. Module review order: Memory, Semantic, Domain,
Observability.

**On the deliberate departure:** `DEC-TEMPORAL-PATTERN` is `scd2` rather than `bi-temporal`.
The reviewer confirms the reason is in Memory and notes it as a deliberate deviation.

**On the absent modules:** Search, Prediction and the runtime facet are absent by design
(`DD-DOMAIN-006`, `DD-MEM-001`). Record each as a coverage gap by design, not a failure.

**On the references to other products:** `customer_key` and `AffectedItem.ticket_key` cannot
be checked inside this product (`DD-OBS-002`). Record them as an open gap with that reason.

**Output:** `review/trust_map.md`.

---

## 6. Consistency note

This brief is the fixed reference across design cycles. Do not change any answer between runs;
the only variable is the content of the design, build and review skills. If a revised standard
adds a decision not in this brief, answer it with the advocated option and record it in the
design specification.
