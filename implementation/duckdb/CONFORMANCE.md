<!-- design-lint: ignore-file (implementation evidence index, not a design document) -->

# DuckDB conformance evidence

The native [profile](checks.py) contains executable violation queries. `conformance.sql` is generated from the same definitions for CLI readers; the Python runner records every result including execution errors. Tests run against an actual persistent DuckDB engine, not a SQL translator. Generated SQL is checked for currency.

| Contract | Evidence / scope | Boundary |
|---|---|---|
| INV-DOMAIN-001..007 | META coverage, DOM-KEY, JOIN, temporal checks; current/as-of, key allocation and duplication mutation tests | Stable-key retention and writer authorization are host obligations. |
| INV-SEMANTIC-001..002 | Explicit object-level model, table/content allowlists and model review | No instance catalogue is generated. |
| INV-SEMANTIC-003..012 | SEM/REL checks, orientation/resource resolution, bidirectional access paths and name-only agent demo | Bootstrap registry and orientation are the only consumer conventions. |
| INV-SEMANTIC-013..015 | Metric/expression/dataset/synonym checks | One DuckDB dialect and one additive metric in the example. |
| INV-SEARCH-001..005 | SEARCH, JOIN, BOUNDARY, temporal checks; live join-back and reopened vector query tests | Toy embedding quality unassessed; VSS omitted. |
| INV-PRED-001..005 | PRED/JOIN/BOUNDARY checks, engineered-value tests and point-in-time cutoffs | SCD2 effective history only; retrospective feature correction rejected. Definitions live in Semantic, monitoring in Observability. |
| INV-OBS-001..006 | BOUNDARY, OBS, VAL checks; active-edge mutation and appended evidence tests | Host supplies events; no automatic trigger/audit guarantee. |
| INV-OBS-007..009 | Not applicable: graph-native/column-lineage facets not selected | Recorded in DD-OBSERVABILITY-003. |
| INV-MEMORY-001..006 | BOUNDARY, MEM-SCOPE, DOC checks; versioned compiler and cookbook execution | Semantic privacy enforcement external; no unrestricted runtime view. |
| TLM-01..05,18 | Inventory/profile/required-column/type checks and corpus prohibited-name lint | UTC-aware timestamp binding. |
| TLM-06..11,17 | NOT NULL/CHECK constraints, overlap/current/finite-event queries and mutation tests | No exclusion constraint is claimed; transactional writer prevents conflicts. |
| TLM-12 | Authored lineage lifecycle comment + metadata check | Sole is_active field; owner controls active→retired. |
| TLM-13..16 | Exact current-surface set comparison, comments and as-of tests; compiler review | All current views explicit; no inclusive-end idioms. |
| Replay, unchanged input, late changes, closure/insertion atomicity | Temporal writer behavioural tests | Conflicting same-boundary corrections rejected, not silently overwritten. |
| VAL-01..09,12,14..18 | VAL checks, shared fixture, failure/error/severity/append tests | Optional score/JSON fields are null in count-only native producer. |
| VAL-10..11,13 | Shared trust fixture, staleness/latest-area tests, designated producer and demo disclosure | Native 2.1 producer only; no external legacy importer. |
| Access Layer / INV-MASTER-004 | Logical tier registry, public-surface metadata and DD-ACCESS-001 | Native RBAC unsupported; external enforcement remains no-evidence. |
| Object placement / INV-MASTER-006 | PLACE/schema inventory, portable file paths and explicit naming declaration | Environment markers belong only to file location. |
| Physical storage / self-containment | Checkpoint, close/reopen, read-only tests; no external asset references in baseline | OS ACL/backup/remote storage validation external. |
| Documentation capture / INV-MASTER-002 | Per-module and pair minimums, required decisions, provenance fields, cookbook execution | No requirement is satisfied by an empty placeholder record. |

The map reports evidence strength, not deployment permission. A strong module entry means its **defined native checks** passed. Separate unknown entries disclose capabilities this fixture cannot prove. Adding a model field, view or check requires regeneration and review; changing the standards is not part of this implementation.
