---
title: PostgreSQL Validation Implementation
anchor: validation
type: implementation
status: draft
version: 2.0
normative: true
implements: validation
platform: postgres
---

# PostgreSQL: Validation

Binding of [Validation](../../../../design/patterns/validation.md). The design owns the contract; this binding adds platform mechanisms and enforcement limits.

[checks.py](../../checks.py) defines executable violation queries; [conformance.sql](conformance.sql) reports counts for SQL clients. Zero rows means the check passed. [validate.py](../../validate.py) executes the profile and appends wire-schema 2.1 evidence, retaining SQL execution errors as ERROR records. Each query uses a savepoint so one error does not abort all later checks. Evidence publication is atomic.

[views.sql](views.sql) resolves the designated producer, newest evidence per area, conservative fallback when no authority is designated, and expired evidence as unknown. Missing evidence is no-evidence/unknown, never success. Trust is advisory and does not gate database access. The example uses a seven-day freshness policy; optional scores remain null.

The profile covers this declared fixture, not arbitrary products. Strong means its defined checks passed; unassessed authentication operations, physical storage and semantic embedding quality are explicitly separate unknown areas. `VAL` checks verify wire vocabularies, parentage, counts and area accounting. Tests cover append behavior, SQL errors, expiry and build rollback. See [CONFORMANCE.md](../../CONFORMANCE.md) for limits.
