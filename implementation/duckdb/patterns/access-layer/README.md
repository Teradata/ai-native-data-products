---
title: DuckDB Access Layer Implementation
anchor: access-layer
type: implementation
status: standard
version: 2.0
normative: true
implements: access-layer
platform: duckdb
---

# DuckDB access boundary

Binding of [access-layer](../../../../design/patterns/access-layer.md). `semantic.role_policy` represents customer360_ROLE_READ, customer360_ROLE_AGENT and customer360_ROLE_ADMIN, with audience-only descriptions. **These are logical tiers, not DuckDB roles.** No SQL GRANT/REVOKE statements are emitted.

**Provides:**

| Capability | Binding |
|---|---|
| `AccessView` | Explicit projections registered as PASSTHROUGH or COMPOSITE objects. |

The host must implement the authoritative design grant matrix: READ gets public module surfaces; AGENT additionally gets authorized append operations for Memory and Observability; ADMIN maintains the product. No agent writes Domain or Semantic. Publish Memory/Semantic interfaces after infrastructure deployment, then Domain/Observability, then enhancements. There are no implied engine grants needed before view compilation. Role provisioning is an external deployment artefact, explicitly unvalidated in this example.

Opening a file read-only prevents database mutation. It does **not** hide base tables, runtime memory, PII, or host filesystem capabilities. Schema separation and naming are not authorization. Direct CLI/JDBC users of the synthetic file can inspect everything. See DuckDB's [security model](https://duckdb.org/docs/current/operations_manual/securing_duckdb/overview).

Runtime entities require scope_level and scope_identifier and have no public views or agent-consumable registry rows. A production service must derive scope from authenticated identity, apply it to every runtime read/write, redact literal business results, and expose bounded append operations rather than an arbitrary SQL channel. If no such service exists, keep real private runtime in a separate file with OS/container controls; a second schema does not suffice. The shipped synthetic runtime does not constitute a privacy-enforcing service.

`DD-ACCESS-001` and `DD-MEMORY-002` record this boundary inside the product. SQL checks prove interface registration and scope presence. The `access-layer` trust entry remains no-evidence/unknown for external enforcement. File permissions and host identity mapping must be tested by the deployment owner; this repository does not pretend SQL can prove them.
