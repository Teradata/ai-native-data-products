---
title: PostgreSQL Observability Implementation
anchor: observability
type: implementation
status: draft
version: 2.0
normative: true
implements: observability
platform: postgres
---

# PostgreSQL: Observability

Binding of [Observability](../../../../design/modules/observability.md). The design owns the contract; this binding adds platform mechanisms and enforcement limits.

[schema.sql](schema.sql) separates operational events, quality measurements, lineage definitions, flow executions, retention policy and validation evidence. `ChangeEventCapture` is supplied by the temporal writer for history changes; other producers must publish their own aggregate events. `AgentOutcomeCapture` permits AGENT to append outcomes, with no update or delete grant. `LineageCapture` separates active definitions from executions. `QualityScore` publishes measured quality and advisory validation confidence separately.

The native validator appends wire-schema 2.1 run, area and check records. Ordinary reader and agent roles cannot rewrite evidence. ADMIN and object owners are privileged maintainers, so append-only is an operational contract for them. No automatic audit trigger, retention scheduler, graph-native facet or external trust importer is claimed.

`OBS`, `VAL`, `BOUNDARY`, metadata and lifecycle checks cover the selected facets. See [validation](../../patterns/validation/README.md) for latest-per-area, authority and expiry semantics.
