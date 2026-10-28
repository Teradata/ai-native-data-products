# Customer Service Agreements Data Product: Reference Brief

**Product code:** `CSA`  
**Full name:** `CustomerServiceAgreements`

This document is the fixed input to the Design, Build and Review starter prompts. Every
decision it records is pre-settled. Paste the relevant section into the matching starter as
your intake. Do not re-open settled decisions.

It is one of three example products that share one organisation and one set of customers.
The [IT Service Desk](../it-service-desk-data-product/ITSD_Reference_Brief.md) records tickets,
[IT Asset Configuration](../it-asset-configuration-data-product/CMDB_Reference_Brief.md) records
the items they were about, and this product records what each customer was promised and paid.
Each is designed, built and reviewed on its own; the places where they meet are recorded as
decisions, not solved.

---

## 1. Process

- Artefacts go to a product repository of the product's own, laid out as in section 2.
- Generate before you execute: render every phase and check, commit them, then deploy.
- The product is a single DuckDB database file. Access tiers are enforced outside the database,
  as the organisation profile's `duckdb` target states.

| Event | Commit message |
|---|---|
| Design phase complete | `design: CustomerServiceAgreements design specification` |
| Build rendered (before execution) | `build: render CustomerServiceAgreements for DuckDB` |
| Deployed, loaded and validated | `build: CustomerServiceAgreements deployed; validation passed` |
| Review complete | `review: trust map complete` |

---

## 2. Repository Layout

```
csa-data-product/
├── README.md
├── data/
│   ├── customers.csv
│   ├── contracts.csv
│   ├── service_level_terms.csv
│   └── service_credits.csv
├── standards/
│   ├── design.toml                  # Organisation profile: classification (from config/)
│   └── implementation.toml          # Organisation profile: placement, naming, roles, one target per platform
├── design/
│   └── design_specification.md      # Design phase output
├── build/                           # render.py output for target duckdb
└── review/
    └── trust_map.md
```

The organisation profile is the same one the IT Service Desk uses
([`config/`](../../config/)).

---

## 3. Design Phase

### 3a. Starter intake

---

**Business purpose:**  
The commercial record of every customer the provider serves: who they are, which contract they
are on, what service levels and service credits that contract promises per ticket priority,
and which credits have been paid. It is the system of record for a customer's tier.

**Primary consumers:**
- Account managers: renewal pipeline, contract terms
- Finance: contract value, credits paid
- Commercial analysts: renewal risk, credit exposure
- AI agents: "which contracts say X" over the contract text

**Top use cases:**
1. List contracts up for renewal, with their value and notice period
2. Score each active contract's risk of not renewing
3. Find contracts whose terms contain a given clause, or something like it
4. Report contract value and credits paid by tier, region and month
5. Trace a contract back through the contracts it renewed

**Composition:** Domain, Semantic, Search, Prediction, Observability, Memory (documentation
facet only). The AI-Native composition without the runtime facet.

**Data sources:** Four CSV files from the contract management and billing systems. Monthly
batch; the customer file carries one row per version from its `valid_from`.

**Approximate volumes:**

| Entity | Initial rows | Monthly growth | Horizon |
|---|---|---|---|
| Customer | 21 (23 versions) | 2 | 7 years |
| Contract | 48 | 2 | 7 years |
| ServiceLevelTerm | 184 | 8 | 7 years |
| ServiceCredit | 9 | 4 | 7 years |

**Sensitivity:** `customers.billing_contact_email` is `[pii]`. Contract terms are commercially
confidential but hold no personal data.

**Entity model source:** custom; Customer follows Schema.org's Organization where the fields
overlap.

**Other products:** the IT Service Desk product holds its own `Customer` with the same customer
numbers. This product is the system of record for tier. A credit's ticket is the service
desk's ticket number, held as that product's natural key (`TKT-nnnnn`).

---

### 3b. Pre-settled design decisions

#### The seven catalogued decisions

All seven take the advocated option.

| ID | Answer | Reason |
|---|---|---|
| DEC-TIMESTAMP-ZONE | `zone-aware` | Customers in five countries |
| DEC-TEMPORAL-PATTERN | `bi-temporal` | Tier changes and contract amendments are often agreed after the date they take effect; the renewal model must not see them before they were recorded |
| DEC-COLUMN-STRATEGY | `offload` | Advocated; nothing on the hot path needs audit inline |
| DEC-SURROGATE-ALLOCATION | `keymap` for Customer and Contract; `inline` for ServiceLevelTerm and ServiceCredit | Customers and contracts are referenced across modules; terms and credits are referenced by nothing |
| DEC-DELETE-STRATEGY | `soft-delete` | Advocated |
| DEC-QUALITY-STORAGE | `observability` | Advocated |
| DEC-AUDIT-RETENTION | `regulatory`: 2 years queryable, 7 years archived | Contracts and credit notes are financial records |

#### Module-specific decisions

**Domain: entity model**

| Entity | Kind | Declared profile | Allocation | Notes |
|---|---|---|---|---|
| Customer | History | `SCD2_BITEMPORAL` | keymap | Natural key `CUST-nnn`, shared with the service desk |
| Contract | History | `SCD2_BITEMPORAL` | keymap | Natural key `CTR-nnnn`; `renewal_of_contract_id` references the contract it renewed |
| ServiceLevelTerm | History | `SCD2_BITEMPORAL` | inline | One per contract and priority: response hours, resolution hours, credit percent |
| ServiceCredit | Record | `EVENT_APPEND_ONLY` | inline | A credit note, never amended; natural key `SC-nnnn` |

**Search:** one embedding per contract of its `terms_text`, 384 dimensions,
`bge-small-en-v1.5`, cosine, exact scan, similarity threshold 0.70, refreshed on load. Absence
is no row.

**Prediction:** target, the probability that an active contract is not renewed at the end of
its term. Feature group `ContractFeatureSet`, wide, refreshed monthly, anchored on
`observation_dts`:

| Feature | Source | Transformation |
|---|---|---|
| f_contract_type_int | contract type | Managed service=1, Support only=2, Project=3 |
| f_customer_tier_int | customer tier, as at observation | Platinum=1 to Bronze=4 |
| f_term_days | start and end date | Days between |
| f_notice_period_days | notice period | Direct (contractual) |
| f_auto_renew | auto-renew flag | Direct (contractual) |
| f_credits_365d | service credits | Sum of credit amounts issued in the last 365 days |
| f_credit_count_90d | service credits | Count issued in the last 90 days |
| f_days_since_credit | service credits | Days since the last credit; absent if none |

The service desk's breach history is not a feature in this cycle: no derivation reaches another
product. Scores go to the Prediction module's `ModelPrediction` with `model_key = 'renewal_risk'`.

**Observability: quality dimensions and weights**

| Dimension | Weight |
|---|---|
| Completeness | 25% |
| Validity | 30% |
| Consistency | 25% |
| Accuracy | 10% |
| Timeliness | 10% |

Thresholds: billing contact present ≥ 0.95 pass, ≥ 0.80 warn; end date not before start,
positive values, resolution hours not below response hours at 1.0; dangling references fail on
any; freshness on credits issued, warn after 35 days, fail after 62. Validation runs on each
load and monthly.

**Memory:** documentation facet only.

**Access layer:** the three standard tiers; the agent tier writes only Observability's usage
and quality events.

---

## 4. Build Phase

### 4a. Starter intake

---

**Target platform:** DuckDB 1.4 or later  
**Product name:** `CustomerServiceAgreements`  
**Design input:** `design/design_specification.md` in the repository  
**Organisation profile:** `standards/design.toml` and `standards/implementation.toml` (target
`duckdb`)  
**Object storage in use?** No

---

### 4b. Physical design

Physical choices are the DuckDB binding's and the organisation profile's; this brief adds none.
The product is one database file; read access is read-only access to that file.

After deployment, load the four source files, generate the contract embeddings with the
declared model, then run the build manifest's checks with `tooling/bindings/validate.py`.

---

## 5. Review Phase

### 5a. Starter intake

---

**What to review:** Both design and build  
**Artefacts:** `design/design_specification.md`, `build/` and the DuckDB database file  
**Composition:** Domain, Semantic, Search, Prediction, Observability, Memory documentation

---

### 5b. Review instructions

Gather evidence from the database file: Semantic for registration completeness, Memory for the
recorded decisions, Observability for the validation run and trust map, and the catalogue for
metadata coverage.

Use the trust-map format of the IT Service Desk brief, section 5b. Module review order:
Memory, Semantic, Domain, Observability, Search, Prediction.

**On the absent runtime facet:** absent by design (`DD-MEM-001`); a coverage gap, not a
failure.

**On the references to other products:** `ServiceCredit.ticket_key` cannot be checked inside
this product (`DD-OBS-002`), and its `Customer` disagrees with the service desk's for some
customers (`DD-DOMAIN-005`). Record both as open gaps with those reasons.

**Output:** `review/trust_map.md`.

---

## 6. Consistency note

This brief is the fixed reference across design cycles. Do not change any answer between runs;
the only variable is the content of the design, build and review skills.
