# IT Service Desk AI-Native Data Product: Reference Brief

**Product code:** `ITSD`  
**Full name:** `ITServiceDesk`

This document is the fixed input to the Design, Build, and Review starter prompts. Every
decision it records is pre-settled. Paste the relevant section into the matching starter as
your intake. Do not re-open settled decisions; where a decision departs from the standard's
advocated option, the reason is already recorded here and carries through to Memory.

---

## 1. Process & Workflow

### GitHub
- A private GitHub repository and PAT are supplied at the start of each conversation.
- All artefacts are written to the repository. No artefact lives only in the conversation.
- Commits use author `ITSD Design Agent <itsd@noreply>`, branch `main`.
- **Push cadence:**

| Event | Commit message |
|---|---|
| Design phase complete | `design: ITServiceDesk design brief and decisions log` |
| Build DDL generated (before execution) | `build: generate DDL for ITServiceDesk` |
| Phase 1+1.5 deployed (Memory, Semantic, roles, grants) | `build: Memory and Semantic deployed` |
| Phase 2+2.5 deployed (Domain, Observability, grants) | `build: Domain and Observability deployed` |
| Phase 3 deployed + validation run | `build: Search and Prediction deployed; validation passed` |
| Review complete | `review: trust map complete` |

### Teradata MCP Server
- Available throughout Build and Review conversations.
- Use for: DDL execution, SQL syntax testing, validation query runs, row counts.
- Do not use for file operations. Those go to GitHub.
- Before executing any CREATE, test the statement with a `SHOW TABLE` dry-run or `EXPLAIN`
  to catch syntax errors; commit SQL to the repository before executing.

### Repeatability
The repository contains `deploy.sh` and `teardown.sh`. Together they allow a complete
redeploy on an empty Teradata system without Claude involvement. Both are generated during
the Build phase and committed before any SQL is executed against the platform.

---

## 2. Repository Layout

```
itsd-data-product/
├── README.md
├── deploy.sh                        # Ordered deployment driver (bteq-based)
├── teardown.sh                      # Reverse-order teardown for repeat runs
├── .env.example                     # Template: TD_HOST, TD_USER, TD_PASS
├── data/
│   ├── categories.csv
│   ├── agents.csv
│   ├── customers.csv
│   └── tickets.csv
├── standards/
│   └── object_placement.md          # Conforming Object Placement Standard (this repo)
├── design/
│   ├── design_brief.md              # Platform-agnostic design (Design phase output)
│   └── decisions_log.md             # Every settled decision with option and reason
├── build/
│   ├── 00_databases_and_roles.sql
│   ├── 01_memory.sql
│   ├── 02_semantic.sql
│   ├── 03_access_phase1.sql
│   ├── 04_domain.sql
│   ├── 05_observability.sql
│   ├── 06_access_phase2.sql
│   ├── 07_search.sql
│   └── 08_prediction.sql
├── review/
│   └── trust_map.md
└── validation/
    └── validation.sql
```

### deploy.sh specification

```bash
#!/usr/bin/env bash
set -euo pipefail

: "${TD_HOST:?TD_HOST is not set}"
: "${TD_USER:?TD_USER is not set}"
: "${TD_PASS:?TD_PASS is not set}"

LOG="logs/deploy_$(date +%Y%m%d_%H%M%S).log"
mkdir -p logs

run_sql() {
  local file="$1"
  echo ">>> $file" | tee -a "$LOG"
  bteq <<EOF 2>&1 | tee -a "$LOG"
.LOGON ${TD_HOST}/${TD_USER},${TD_PASS};
.SET ERROROUT STDOUT;
.SET WIDTH 200;
.RUN FILE = ${file};
.IF ACTIVITYCOUNT > 0 THEN .ECHO OK;
.LOGOFF;
.QUIT 0;
EOF
}

run_sql "build/00_databases_and_roles.sql"
run_sql "build/01_memory.sql"
run_sql "build/02_semantic.sql"
run_sql "build/03_access_phase1.sql"
run_sql "build/04_domain.sql"
run_sql "build/05_observability.sql"
run_sql "build/06_access_phase2.sql"
run_sql "build/07_search.sql"
run_sql "build/08_prediction.sql"

echo "=== Deployment complete. Log: $LOG ==="
```

### teardown.sh specification

Drop in reverse dependency order; handle missing objects gracefully via `.IF ERRORCODE`
guards. Drops: ITSD_PRD, ITSD_SCH, ITSD_ACC, ITSD_OBS, ITSD_DOM, ITSD_SEM, ITSD_MEM,
then roles ITSD_ROLE_ADMIN, ITSD_ROLE_AGENT, ITSD_ROLE_READ.

---

## 3. Design Phase

### 3a. Starter intake

Paste this block into the Design Starter prompt's **Intake** section.

---

**Business purpose:**  
Central data product for IT service desk operations. Supports SLA breach prediction on open
tickets, semantic discovery of similar past tickets and their resolutions, and quality
monitoring across the full ticket lifecycle. Serves both real-time triage (agent-driven) and
analytical review (manager and analyst-driven).

**Primary consumers:**
- AI agents: ticket triage, similar-ticket retrieval, multi-step investigation with session continuity
- Operations analysts: SLA performance and agent productivity reporting
- Service desk managers: quality monitoring, breach risk review
- Downstream ML pipelines: feature store consumption

**Top use cases:**
1. Predict SLA breach risk for an open ticket (given priority, customer tier, category,
   time-in-queue) so agents can proactively escalate before breach occurs
2. Find semantically similar past tickets and retrieve their resolution approaches
3. Monitor ticket data quality (completeness, referential integrity, satisfaction coverage)
   so the operations team has confidence in SLA reporting figures
4. Track agent and team SLA performance over time for manager review and coaching
5. Maintain AI agent session continuity across a multi-step ticket investigation

**Composition:** Full AI-Native Data Product: all six modules; Memory with both facets
(documentation + runtime).

**Data sources:** Four CSV files (categories, agents, customers, tickets). Batch ingestion
from file on initial load. No streaming source in this cycle.

**Approximate volumes:**

| Entity | Initial rows | Monthly growth | 3-year estimate |
|---|---|---|---|
| Ticket | 150 | 75 | ~2,850 |
| Agent | 12 | <1 | ~20 |
| Customer | 20 | 2 | ~90 |
| Category | 15 | 0 | ~15 |

**Sensitivity:**
- `agents.email` is `[pii]`
- `customers.contact_name` is `[pii]`
- `customers.contact_email` is `[pii]`
- Ticket `description` and `resolution_notes` may contain incidental PII in free text.
  Flag as a risk in Memory. No runtime masking in this build; noted for future production
  hardening.

**Entity model source:** Custom model; no applicable industry standard exists for generic
IT service desk data. Record in Semantic with rationale. Consider ITIL alignment for future
standardisation.

---

### 3b. Pre-settled design decisions

The design agent will raise these in the decision conversation. Respond with the answer
below; do not re-open. Every answer is recorded in `design/decisions_log.md`.

#### The seven catalogued decisions

| ID | Decision | Answer | Advocated? | Reason |
|---|---|---|---|---|
| DEC-TIMESTAMP-ZONE | Zone handling for all Timestamp attributes | `zone-aware`: store normalised to UTC; presentation conversion is a consumer concern | Yes | Source data is UTC; no single-zone assumption; ordering correctness required |
| DEC-TEMPORAL-PATTERN | History representation for versioned entities | `bi-temporal`: valid time + transaction time independently | Yes | Prediction module requires point-in-time correctness; ticket reclassifications and priority corrections occur and must not leak into training features |
| DEC-COLUMN-STRATEGY | Where audit, lineage, and quality attributes live | `offload`: none on the entity; all in Observability, presented via AccessView | Yes | Ticket history accumulates many changes per entity; quality trend matters for SLA reporting trust |
| DEC-SURROGATE-ALLOCATION | How entity Identifiers are kept stable | `keymap` for all History entities; `inline` for Category (Reference) | Partially: Category departs | Ticket, Agent, Customer are each referenced by other modules, so stability is required; Category is a Reference entity that does not version, so the keymap machinery is unnecessary |
| DEC-DELETE-STRATEGY | What happens when an entity instance is deleted | `soft-delete`: `is_deleted` set with `deleted_dts` recorded, as a new current version; the predecessor's `valid_to_dts` and `transaction_to_dts` close at that instant | Yes | SLA reporting and audit require deletion history; agent departures and customer offboarding are analytically significant events |
| DEC-QUALITY-STORAGE | Where quality assessments are held | `observability`: scores and per-rule results as a time series in Observability | Yes | Quality trend is how the team identifies deteriorating data before it affects SLA reporting |
| DEC-AUDIT-RETENTION | How long change events and deletion records are retained | `bounded`: 3-year uniform retention window | **No, a departure** | IT service desk ticket data carries no statutory retention obligation in this deployment context; 3-year window covers operational investigation needs and pattern analysis depth; revisit if compliance scope changes |

#### Module-specific decisions

**Domain: entity model**

| Entity | Kind | Declared temporal profile | Surrogate allocation | Keymap needed |
|---|---|---|---|---|
| Ticket | History | `SCD2_BITEMPORAL` | keymap | Yes, referenced by Search, Prediction, Observability |
| Agent | History | `SCD2_BITEMPORAL` | keymap | Yes, referenced by Ticket |
| Customer | History | `SCD2_BITEMPORAL` | keymap | Yes, referenced by Ticket |
| Category | Reference | `CURRENT_STATE` | inline | No, it holds present values only; see below |

Every keymap is `CURRENT_STATE`: one row per natural key, allocated once, never versioned.

**The validity columns are not restated here.** They come from the temporal pattern, as they do for any entity that applies it: `valid_from_dts` / `valid_to_dts` for business validity, `transaction_from_dts` / `transaction_to_dts` for the transaction-time axis that `bi-temporal` adds, `is_current`, `is_deleted` / `deleted_dts`, and the `created_dts` / `updated_dts` audit pair. Restating them in a brief is how a second spelling gets in.

**Category departs from the `Reference` default.** The default profile for a `Reference` entity is `SCD2_HISTORY`, because a code's label can be reworded and a past record should still decode against what its code meant then. Category takes `CURRENT_STATE` instead: this is a small internal taxonomy whose labels are not reworded in service, and no ticket needs to resolve a category name as at its creation date. Recorded as a design decision.

That profile declaration is what licenses `effective_date` / `expiration_date` on this entity for the period a category is available for assignment. TLM-04 permits those two names on a `CURRENT_STATE` entity and prohibits them everywhere else, and the permission turns on the *declared* profile, so the declaration must reach the Semantic entity metadata. An entity registered with no profile cannot claim the exception. They are a day-grain business lifecycle date here, not a validity pair.

Relationship entities:
- No explicit Relationship entity needed at this stage. The Ticket entity carries
  `assigned_agent_id`, `customer_id`, and `category_id` as direct references. These are
  point-in-time attributes of the ticket, not standalone associations.

**Search: entity model**

One entity, `EntityEmbedding`, as the Search module defines it. The two embeddings are **rows** discriminated by `source_attribute`, not two tables: the module models an embedding per (entity, source attribute, model), and splitting it per source would fork the similarity query and the currency flag along with it.

| `source_attribute` | Embedding source | Dimensions | Coverage |
|---|---|---|---|
| `subject_description` | `subject \|\| ' ' \|\| description` | 384 | Every ticket, since both attributes are mandatory |
| `resolution_notes` | `resolution_notes` | 384 | Resolved and closed tickets only; no row where `resolution_notes` is NULL |

`entity_kind` is `TICKET` for both. Absence is represented by the absence of a row, not by a row with a null vector: `embedding` is required, and a null vector is not a fact about an unresolved ticket.

- Similarity metric: cosine (default for text embeddings)
- Approximate index: none at this volume; linear scan conformant; HNSW upgrade path noted
  in Memory for production scaling
- Similarity threshold for "similar ticket" queries: cosine ≥ 0.75 (conservative; tunable)

**Prediction: entity model**

Prediction target: `sla_breach_risk_score DECIMAL(5,4)`, a probability 0.0000–1.0000 that
the ticket will breach SLA before resolution. Binary classification model output stored as
continuous score for downstream agent decision-making.

Feature register:

| Feature | Source | Transformation | PIT-safe |
|---|---|---|---|
| f_priority_int | ticket.priority | P1=1, P2=2, P3=3, P4=4 | Yes |
| f_sla_hours | ticket.sla_hours | Direct | Yes |
| f_customer_tier_int | customer.tier (at ticket creation time) | Platinum=1, Gold=2, Silver=3, Bronze=4 | Yes, join at valid_time |
| f_agent_team_int | agent.team (at assignment time) | Infrastructure=1, Applications=2, Service Desk=3; NULL if unassigned | Yes |
| f_category_leaf_int | ticket.category_id | CAT-006=1 through CAT-015=10 | Yes |
| f_created_hour | `tickets.csv:created_at` | Hour of day 0–23 | Yes |
| f_created_dow | `tickets.csv:created_at` | Day of week 0=Mon, 6=Sun | Yes |
| f_response_hours | `tickets.csv:first_response_at` − `created_at` | NULL if not yet responded | Yes |
| f_subject_length | ticket.subject | Character count | Yes |
| f_is_escalated | ticket.escalated | 0 / 1 | Yes |

Column names in the Source column above are **source-file** columns as they appear in
`tickets.csv`, not product columns. On the way in they become the entity's own canonical
names; the feature columns themselves are the `f_*` names on the left.

Point-in-time correctness: features involving Agent and Customer tier use bi-temporal
join-back to recover attribute values as at the ticket's creation instant. Fields
unavailable at prediction time (resolution time, closure time, satisfaction score) are
excluded from the feature set.

Feature group entity: `TicketFeatureSet`, a wide-format `FeatureGroup` carrying the `f_*`
columns above, one per ticket, on the `SCD2_HISTORY` profile with `observation_dts` as the
point-in-time anchor.

Model output entity: `ModelPrediction`, as the Prediction module defines it. The SLA-breach
score is carried in its `prediction_value` (a probability, 0.0000–1.0000) with
`prediction_class` unused, `model_key = 'sla_breach'` and `prediction_dts` recording the
scoring instant. History of scores is retained by the profile's validity pair; one version
per scoring event. There is no separate `SLABreachScore` table: a product-named table for
one model's output is a private spelling of the module's own entity, and the agent-facing
query then differs per product for no gain.

**Observability: quality dimensions and weights**

| Dimension | Weight | Assesses |
|---|---|---|
| Completeness | 35% | Required attributes populated |
| Validity | 25% | Values in expected format/range |
| Consistency | 20% | Related attributes agree (e.g. resolution time is not before creation time) |
| Accuracy | 10% | Values match source (reduced weight, since there is a single source of truth) |
| Timeliness | 10% | Freshness of latest data |

Thresholds (per entity per dimension):
- Completeness: composite ≥ 0.90 = pass; 0.80–0.90 = warn; < 0.80 = fail
- Freshness: no new tickets in 24h = warn; >48h = fail
- Referential integrity: any orphaned FK = fail (zero tolerance)
- Satisfaction coverage: >10% of Closed tickets missing score = warn

Validation frequency: on each batch data load; on-demand via `validation/validation.sql`.

Lineage scope this cycle: source file → Domain ingest only. Search and Prediction lineage
noted as derived from Domain; full pipeline lineage at production maturity.

**Memory: documentation facet**

All six documentation entities deploy, as the Memory module defines them: `ModuleRegistry`,
`DesignDecision`, `BusinessGlossary`, `QueryCookbook`, `ImplementationNote`, `ChangeLog`.
Their columns come from the module and are not restated here.

Every decision in this brief produces one `DesignDecision` record. A departure carries its
reason verbatim in `rationale`, and the alternatives considered in
`alternatives_considered`; that is what makes the departure auditable inside the product
rather than only in this file.

`INV-MEMORY-006` sets the floor per deployed module (at least three design decisions,
three glossary terms, and one query recipe) so the capture protocol runs for every module
in the composition, not only the ones with something interesting to say.

**Memory: runtime facet**

All five runtime entities deploy: `AgentSession`, `AgentInteraction`, `LearnedStrategy`,
`UserPreference`, `DiscoveredPattern`. Their columns come from the module.

Ticket investigation state maps onto them rather than onto a bespoke session table.
`AgentSession` carries the session's own lifecycle (`session_start_dts`,
`session_end_dts`, goal, status) and `session_context_json` holds the working state: the
ticket under investigation, the analysis step reached, the last search issued. The tickets
retrieved by a search are recorded on `AgentInteraction` as a **count**
(`query_result_count`) and a table-level reference, never as a list of ticket ids:
`INV-MEMORY-001` keeps runtime references at table level, and a JSON array of retrieved
ticket ids is exactly the instance-key column it prohibits.

Session TTL: 24 hours of inactivity, computed from `session_start_dts` and the latest
`interaction_dts` rather than stored as an expiry column. Expired sessions are closed by
setting `session_end_dts` and `session_status = 'ABANDONED'`; rows are retained for 7 days
then purged.

**Semantic: registration scope**

The catalogue entities are the module's own: `EntityMetadata`, `ColumnMetadata`,
`NamingStandard`, `TableRelationship`, `DataProductMap`, `PrimaryObject`. The product-level
`DataProductRegistry` row lives in the shared `governance` container, not in `ITSD_SEM`,
since its purpose is cross-product discovery.

Every entity across every module registers at deploy time, and each registration states its
`temporal_pattern`. The profile declaration is what lets a validator resolve an entity's
temporal behaviour from metadata instead of guessing from its name, and it is what licenses
Category's `effective_date` / `expiration_date`. The relationship catalogue covers all FK
relationships in Domain. Entity and column metadata are sourced from `COMMENT ON
TABLE/COLUMN` values via `DBC.TablesV` and `DBC.ColumnsV`.

**Access layer: role definitions**

The three roles the access-layer pattern defines, no more:

| Role | Consumers | Reads | Write-back |
|---|---|---|---|
| `ITSD_ROLE_READ` | Operations analysts, service desk managers, BI, ad-hoc users | `ITSD_ACC`, `ITSD_SEM` | None |
| `ITSD_ROLE_AGENT` | AI agents and automated tools | `ITSD_ACC`, `ITSD_SEM` | Append to `ITSD_MEM` and `ITSD_OBS` |
| `ITSD_ROLE_ADMIN` | Product owner, data steward | All `ITSD_*` | Full |

Consumer-facing views live in `ITSD_ACC` only. End users are granted roles, never direct
database access. Everything a consumer needs from Observability, Search and Prediction is
reached through a view in `ITSD_ACC`, so the read set does not widen per module as the
composition grows.

Role comments carry **one short sentence naming the consumers** and never what the role can
reach: a comment enumerating the grant boundary publishes it to everyone who can query the
catalogue, and the grant matrix plus `DD-ACCESS-001` already record it.

Agent write-back is append-only, and it reaches Memory's runtime entities and
Observability's usage and quality events. It is not a general write on `ITSD_MEM`: the
documentation facet is written at deploy time by the capture protocol, not by an agent at
runtime.

---

## 4. Build Phase

### 4a. Starter intake

Paste this block into the Build Starter prompt's **Intake** section.

---

**Target platform:** Teradata Vantage 17.20  
**Product name:** `ITServiceDesk`  
**Design input:** `design/design_brief.md` in the repository  
**Object Placement Standard:** `standards/object_placement.md` in this repository. Read
it in full before generating any object  
**Object storage in use?** No

---

### 4b. Physical design standard (Teradata 17.20)

These are the physical design choices for this product. Apply them during Build; record any
deviation as a design decision in Memory.

**Primary index strategy**

Physical table names are the platform binding's, derived at build time; the entity names
are the design's. Where the two differ the binding wins, and this table names the entity.

| Entity | PI type | PI columns |
|---|---|---|
| `*_Keymap` tables | UPI | `(entity_key)` |
| History entities (Ticket, Agent, Customer) | NUPI | `(entity_id, transaction_from_dts)` |
| Category | UPI | `(category_id)` |
| EntityEmbedding | NUPI | `(entity_id, source_attribute)` |
| TicketFeatureSet | UPI | `(entity_id)` |
| ModelPrediction | NUPI | `(entity_id, prediction_dts)` |
| DataQualityMetric | NUPI | `(table_name, measured_dts)` |
| ChangeEvent | UPI | `(change_event_id)` |
| DataLineage | UPI | `(lineage_id)` |
| LineageRun | UPI | `(lineage_run_id)` |
| DesignDecision | UPI | `(decision_key)` |
| AgentSession | UPI | `(session_id)` |
| Semantic catalogue entities | UPI | the entity's own surrogate |

`EntityEmbedding` is NUPI on `(entity_id, source_attribute)` rather than UPI on the entity:
a ticket carries two embeddings, so the entity id alone is not unique.

**Partitioning**

| Entity | Partition expression |
|---|---|
| Ticket (history) | `RANGE_N(transaction_from_dts BETWEEN TIMESTAMP '2026-01-01 00:00:00+00:00' AND TIMESTAMP '2029-12-31 23:59:59+00:00' EACH INTERVAL '1' MONTH)` |
| DataQualityMetric | `RANGE_N(measured_dts BETWEEN TIMESTAMP '2026-01-01 00:00:00+00:00' AND TIMESTAMP '2029-12-31 23:59:59+00:00' EACH INTERVAL '1' DAY)` |
| ChangeEvent | `RANGE_N(change_dts BETWEEN TIMESTAMP '2026-01-01 00:00:00+00:00' AND TIMESTAMP '2029-12-31 23:59:59+00:00' EACH INTERVAL '1' DAY)` |
| All others | No partitioning |

**Temporal column conventions (Teradata)**

- Type: `TIMESTAMP(6) WITH TIME ZONE`
- Open-end sentinel: `TIMESTAMP '9999-12-31 23:59:59.999999+00:00'`
- Zone: always `+00:00` in stored literals
- Flags: `BYTEINT NOT NULL DEFAULT 0 CHECK (col IN (0, 1))`
- Consumer views: `LOCKING ROW FOR ACCESS` on all views

**Statistics: minimum collection set**

Collect after initial data load, before first query.

| Entity | Columns |
|---|---|
| Ticket | `(ticket_id, transaction_from_dts)`, `(ticket_key)`, `(status)`, `(priority)`, `(customer_id)`, `(category_id)`, `(is_current)` |
| Agent | `(agent_id, transaction_from_dts)`, `(agent_key)`, `(is_current)`, `(team)` |
| Customer | `(customer_id, transaction_from_dts)`, `(customer_key)`, `(tier)`, `(is_current)` |
| Category | `(category_id)`, `(category_code)`, `(parent_category_id)` |
| TicketFeatureSet | `(entity_id)`, `(f_priority_int)`, `(f_customer_tier_int)` |
| ModelPrediction | `(entity_id)`, `(prediction_dts)` |

**Deployment sequence**

Execute in this exact order. Each file is idempotent: objects are dropped (with error
handling) before creation.

| File | Contents |
|---|---|
| `00_databases_and_roles.sql` | CREATE DATABASE for each module; CREATE ROLE for each access role |
| `01_memory.sql` | Six documentation entities + five runtime entities; COMMENT ON all objects |
| `02_semantic.sql` | EntityMetadata, ColumnMetadata, NamingStandard, TableRelationship, DataProductMap, PrimaryObject; COMMENT ON all |
| `03_access_phase1.sql` | Implied grants for `ITSD_ACC`; the three roles with their one-sentence comments; GRANT SELECT on ITSD_SEM to all three; agent append on ITSD_MEM runtime |
| `04_domain.sql` | Keymap tables; History tables; Reference table (Category); Current views; seed data inserts; COMMENT ON all |
| `05_observability.sql` | ChangeEvent, DataQualityMetric, DataLineage, LineageRun, ModelPerformance, AgentOutcome; COMMENT ON all; initial validation run |
| `06_access_phase2.sql` | Extend grants to ITSD_DOM, ITSD_OBS |
| `07_search.sql` | EntityEmbedding; COMMENT ON all; embedding population placeholder for both source_attribute values |
| `08_prediction.sql` | TicketFeatureSet (FeatureGroup), ModelPrediction; COMMENT ON all; feature population from Domain |

After `08_prediction.sql`: run `validation/validation.sql` via MCP and confirm all checks
pass before the final push.

---

## 5. Review Phase

### 5a. Starter intake

Paste this block into the Review Starter prompt's **Intake** section.

---

**What to review:** Both design and build  
**Artefacts:** `design/design_brief.md` and `build/*.sql` in the repository; live deployed
product accessible via the Teradata MCP Server  
**Composition:** Full AI-Native (all six modules)

---

### 5b. Review instructions

**Evidence gathering:** read from the deployed product via MCP:
- Semantic tables for entity registration completeness
- Memory for recorded design decisions (verify all 7 catalogued decisions are present,
  including the DEC-AUDIT-RETENTION departure with its recorded reason)
- Observability for quality snapshot and validation event results
- `DBC.TablesV` and `DBC.ColumnsV` for metadata coverage (INV-DOMAIN-001)

**Trust map format:**

```markdown
## Trust Map: ITServiceDesk

Reviewed: [date]  
Reviewer: [identity]  
Evidence sources: design brief, build SQL, live Teradata product (MCP)

### [Module Name]
| Area | Coverage | Status | Confidence | Open Gaps | Recommended Action |
|---|---|---|---|---|---|
| [scope, e.g. MODULE:domain or ENTITY:domain.Ticket] | [checks ran / checks expected] | pass/fail/partial/not-validated/no-evidence | strong/partial/weak/unknown | [prose] | [what would raise trust] |
```

The vocabulary is the published one (`design/patterns/validation.md` §4), so the review's map is
the same artefact a validator later publishes as `validation_area` rows. Cite the invariant or rule
id behind each entry in the gaps column.

**Severity:**

| Severity | Definition |
|---|---|
| CRITICAL | Invariant violated; results are wrong or data is leaked; surface prominently with consequence |
| ERROR | Agent autonomy or trust contract broken; dependent capability is unusable |
| WARNING | Quality or discoverability degraded; product remains usable |

**Module review order:** Memory, Semantic, Domain, Observability, Search, Prediction.
Conclude with a summary: overall confidence rating, CRITICAL/ERROR items requiring action,
WARNING items, open gaps, and prioritised next-step recommendations.

**On the deliberate departure:** DEC-AUDIT-RETENTION uses `bounded` rather than
`regulatory`. This is a recorded, intentional departure with a stated reason. The reviewer
confirms the reason is present in Memory and notes it as a deliberate deviation, not an
oversight.

**Output:** `review/trust_map.md`, committed with message `review: trust map complete`.

---

## 6. Consistency note

This brief is the fixed reference across multiple design cycles. When testing a revised
version of the design standards:

- Do not change any answer in this brief between runs.
- The only variable between runs is the content of the design, build, and review skills.
- Comparison between runs is meaningful only if the intake and decisions are identical.
- If a revised standard adds a new decision not in this brief, answer it with the
  standard's advocated option and record it in the decisions log; do not leave it open.
