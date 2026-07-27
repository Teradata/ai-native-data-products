---
title: Advocated Standards: Decision Catalogue
anchor: advocated-standards
type: core
status: draft
version: 2.0
normative: true
---

# Advocated Standards: Decision Catalogue

## AI-Native Data Product Architecture: Foundational Reference

---

## 1. Purpose

This document catalogues the **decisions** (see the [Design Language](DESIGN_LANGUAGE.md)) that an AI-Native Data Product design must settle, and states the recommended answer for each.

These recommendations come from three decades of enterprise data management practice. They are strong defaults rather than mandates. A small controlled vocabulary and a hundred-million-row transaction history warrant different answers, and a standard that pretended otherwise would be ignored where it did not fit.

**What is normative here is the requirement to choose, not the choice.** A module or pattern must state which decisions its designers have to settle; a product's design must record what it settled them to. Taking the advocated option needs no justification; taking any other requires a recorded reason. A design that leaves an applicable decision unstated is not conformant.

### 1.1 Why this is a catalogue and not guidance

Advisory prose has no purchase on a design workflow. Nothing records which option a product took, and nothing checks that its implementation matches, so an agent reading the design cannot tell a deliberate departure from an oversight.

Expressing the same material as decisions fixes that. Each module names the decisions it obliges a designer to settle, the design skill puts those questions to the designer at design time, and the answer is recorded in the product's design where the linter and the reviewer can both find it. The recommendation carries exactly as much weight as before: what changes is that using it, or not using it, becomes visible and testable.

### 1.2 How a decision reaches a design

A module or pattern document lists, under **Designer Responsibilities**, the decisions its designers must settle: each with the option this standard recommends and the question that shifts the answer. Nothing there fixes a choice: a standard recommends, a product decides.

At design time the design skill reads those tables and works through them with the human designer, one question at a time, recording each answer in the product's own design. A choice that departs from the recommendation is recorded with its reason.

This is why the decisions live in the document body rather than a header: a header is metadata a reader skips, while Designer Responsibilities is exactly where someone doing the design is already looking.

### 1.3 Scope

This catalogue covers **logical** decisions: the shape of the data and where responsibility sits. It is deliberately silent on where objects are placed, how containers are named, and how access is granted: those are governed by the `object-placement` pattern, which prescribes structure where this document recommends practice. Physical-design decisions belong to each platform's profile.

---

## 2. `DEC-TEMPORAL-PATTERN`

```
Decision: DEC-TEMPORAL-PATTERN
  Question:   How is the history of a versioned entity represented?
  Applies to: every entity of kind History

  Option: bi-temporal                                  [advocated]
    Summary:      Two independent time dimensions: valid time (when the fact
                  was true in the world) and transaction time (when the database
                  recorded it).
    Implies:      pattern temporal-lifecycle-metadata, profile SCD2_BITEMPORAL;
                  capabilities CurrentStateFilter, PointInTimeReconstruction
    Acceptable when: always.

  Option: scd2
    Summary:      A single valid-time dimension. Simpler to load and query;
                  cannot express a correction to a previously recorded fact.
    Implies:      pattern temporal-lifecycle-metadata, profile SCD2_HISTORY;
                  capability CurrentStateFilter
    Acceptable when: late-arriving facts are rare, corrections are not required,
                  and no consumer needs to reconstruct what the database
                  believed at a past moment.
    Requires:     a recorded reason, and acknowledgement that point-in-time
                  reconstruction is limited to valid time.

  Option: current-state
    Summary:      No history. The entity holds only its present state.
    Implies:      pattern temporal-lifecycle-metadata, profile CURRENT_STATE
    Acceptable when: history has no analytical or regulatory value. Typically
                  staging, scratch, or derived sets rebuilt from source.
    Requires:     a recorded reason.
```

**Why bi-temporal is advocated.** The two dimensions answer different questions, and machine learning needs both. *What did we believe on the day the model scored?* is a transaction-time question; answering it with valid time alone silently leaks post-hoc corrections into training features, which is how a model comes to look accurate in backtest and fail in production. A single dimension also cannot represent a correction at all: restating a fact overwrites the record of having been wrong, and regulated explanations require that record.

The cost is real, two extra period pairs per row and a more careful load, which is why `scd2` remains a legitimate choice where corrections genuinely do not occur.

**Selection.** Point-in-time correctness for model features, or common late-arriving facts, or corrections, or a regulatory audit trail → `bi-temporal`. None of those, and simplicity is worth more → `scd2`. No analytical value in history at all → `current-state`.

The column contract for each option, and the profile each entity declares, are defined by the `temporal-lifecycle-metadata` pattern. This decision selects among them; it does not restate them.

---

## 3. `DEC-COLUMN-STRATEGY`

```
Decision: DEC-COLUMN-STRATEGY
  Question:   Where do an entity's audit, lineage, and quality attributes live?
  Applies to: every entity of kind History or Record

  Option: offload                                      [advocated]
    Summary:      The entity carries no audit, lineage, or quality attributes.
                  They live once in Observability and are reached by joining on
                  the entity reference.
    Implies:      capabilities ChangeEventCapture, LineageCapture, QualityScore
                  required [soft] from module:observability; AccessView to
                  present the joined result
    Acceptable when: always.

  Option: reference
    Summary:      The entity carries a small number of references to the
                  Observability records, trading a few narrow attributes for a
                  more direct join.
    Implies:      as offload, plus Reference attributes on the entity
    Acceptable when: a measured access path needs the directness and the entity
                  is not large enough for the extra attributes to matter.
    Requires:     a recorded reason naming the access path.

  Option: inline
    Summary:      Audit, lineage, and quality attributes are carried on the
                  entity itself.
    Implies:      no Observability requirement for these concerns
    Acceptable when: the entity is small and low-volume, or the composition
                  genuinely has no Observability module.
    Requires:     a recorded reason, and acceptance that quality and audit
                  history is limited to the latest state.
```

**Why offload is advocated.** Audit, lineage, and quality are *properties of a change*, not properties of an entity: one entity accumulates many of each over its life. Carrying them inline forces a one-to-one shape onto one-to-many data, which has two consequences: only the most recent value survives, and every row of the entity pays for attributes that are null on most of them. Offloading stores each fact once, keeps the full series, and leaves the entity to hold what it actually is.

The objection is that a join is now required. That objection is answered by `AccessView` rather than by duplication: consumers read a view that presents the joined result as one surface, so the normalisation stays out of the way of the people reading the data.

**Selection.** Volume is the discriminator. A small reference set can afford `inline` and gains simplicity; a large history cannot, and the advantage of `offload` grows with row count. Between the two, `reference` is the compromise. Adopt it against a measured access path rather than a predicted one.

---

## 4. `DEC-SURROGATE-ALLOCATION`

```
Decision: DEC-SURROGATE-ALLOCATION
  Question:   How is an entity's Identifier allocated so that it stays stable
              across every version of the same real-world thing?
  Applies to: every entity whose Identifier is referenced by another entity

  Option: keymap                                       [advocated]
    Summary:      A dedicated Keymap entity allocates the Identifier for a
                  natural key once; every version of the entity reuses it.
    Implies:      entity kind Keymap; capability SurrogateKeyAllocation
    Acceptable when: always.

  Option: external-allocator
    Summary:      An existing organisational mechanism: a central sequence
                  service, a key management framework, a shared identifier
                  registry that allocates the Identifier.
    Implies:      capability SurrogateKeyAllocation required from external
    Acceptable when: the organisation already operates such a mechanism and it
                  guarantees stability across versions.
    Requires:     a recorded reason naming the mechanism.

  Option: inline
    Summary:      The Identifier is allocated by the entity itself as rows are
                  written.
    Implies:      capability SurrogateKeyAllocation provided by self
    Acceptable when: no other entity holds a reference to this entity's
                  Identifier: reference sets and detail entities that are
                  never themselves referenced.
    Requires:     a recorded reason confirming nothing references it.

  Option: natural-key
    Summary:      The business identifier is used directly as the surrogate.
    Implies:      capability NaturalKeyLookup; no separate Identifier
    Acceptable when: the natural key is genuinely immutable, single-valued, and
                  the business strongly prefers it.
    Requires:     a recorded reason, and acceptance that a change to the natural
                  key becomes a breaking change to every referencing entity.
```

**Why keymap is advocated.** In a versioned entity, many rows describe the same real-world thing. If the identifier is minted as rows are written, each version receives a different one, and a reference held elsewhere becomes ambiguous: it cannot say *which* version it meant, and it breaks the moment a new version arrives. Allocating the identifier separately, keyed on the natural key, makes it a property of the thing rather than of the row.

The stability requirement is what matters; the keymap is one way to meet it. An organisation with an established allocator should use it: `external-allocator` exists precisely so that meeting the requirement does not mean discarding working infrastructure.

**Selection.** The discriminating question is a single one: *does any other entity hold a reference to this entity's Identifier?* If yes, stability is required and `inline` is unsound. If no, `inline` is sufficient and the keymap is unnecessary machinery.

**Scope note.** Regardless of which option is chosen, a reference between entities always points at the stable Identifier and never at a particular version.

---

## 5. `DEC-DELETE-STRATEGY`

```
Decision: DEC-DELETE-STRATEGY
  Question:   What happens when an entity instance is deleted?
  Applies to: every entity of kind History or Reference

  Option: soft-delete                                  [advocated]
    Summary:      The instance is marked deleted. It stops satisfying
                  CurrentStateFilter, remains reachable by
                  PointInTimeReconstruction, and the deletion is itself an
                  observable event.
    Implies:      capability SoftDelete; a deleted-flag attribute; pattern
                  temporal-lifecycle-metadata
    Acceptable when: always.

  Option: hard-delete
    Summary:      The instance is destroyed. No history of it survives.
    Implies:      no SoftDelete capability
    Acceptable when: no regulatory audit obligation applies, no model feature
                  depends on deletion status, no analysis examines deletion
                  patterns, and the data genuinely has no future value.
                  Typically staging or test data.
    Requires:     a recorded reason, and confirmation that no reference to the
                  instance survives elsewhere.
```

**Why soft delete is advocated.** Deletion is information. *Which customers left, and when* is a question the business asks; *was this instance present when the model scored* is a question an explanation requires; and an accidental deletion that destroyed its own evidence cannot be reversed. A destructive delete answers all three with silence.

Soft deletion also keeps referential reasoning honest. A reference to a destroyed instance dangles; a reference to a soft-deleted one still resolves, and the consumer can see that the target is no longer current rather than encountering an absence it cannot interpret.

**Selection.** When in doubt, `soft-delete`: it is the safe default and the reversible one. `hard-delete` needs *all four* of its conditions to hold simultaneously, which in practice restricts it to data that was never intended to persist.

---

## 6. `DEC-TIMESTAMP-ZONE`

```
Decision: DEC-TIMESTAMP-ZONE
  Question:   Are the entity's Timestamp attributes zone-aware?
  Applies to: every entity carrying a Timestamp attribute

  Option: zone-aware                                   [advocated]
    Summary:      Every Timestamp fixes an instant. Values are stored
                  normalised to UTC; presentation in a local zone is a consumer
                  concern.
    Implies:      logical type Timestamp as defined; pattern
                  temporal-lifecycle-metadata
    Acceptable when: always.

  Option: zone-naive
    Summary:      Timestamps record a wall-clock reading with no zone. The zone
                  is an assumption held outside the data.
    Implies:      the assumed zone must be recorded as entity metadata
    Acceptable when: the data is genuinely single-zone and will remain so, a
                  regulation mandates a specific local zone, or a legacy
                  interface requires it.
    Requires:     a recorded reason **and** the assumed zone recorded in
                  metadata, so a consumer can interpret the value correctly.
```

**Why zone-aware is advocated.** A wall-clock reading without a zone is not a point in time: it is a point in time *plus an assumption held somewhere else*. As long as the assumption is universal and remembered, nothing goes wrong. Neither condition survives contact with a second region, a daylight-saving boundary, or a consumer who was not told.

The failure is quiet, which is what makes it serious: comparisons across zone-naive values silently produce wrong orderings and wrong durations rather than errors, and the result looks plausible. Ordering is exactly what temporal data is for.

**Practice under the advocated option.** Store normalised to UTC. Convert to a local zone for presentation, at the edge, never in storage. Write zone-explicit literals in queries and comparisons.

**Selection.** Choose `zone-naive` only when one of its three conditions genuinely holds: and record the assumed zone when doing so. An unrecorded assumption is the failure mode this decision exists to prevent.

---

## 7. `DEC-QUALITY-STORAGE`

```
Decision: DEC-QUALITY-STORAGE
  Question:   Where is an entity's data-quality assessment held?
  Applies to: every entity for which quality is assessed

  Option: observability                                [advocated]
    Summary:      Quality scores and their per-rule results live in
                  Observability as a time series, presented through a view.
    Implies:      capability QualityScore required [soft] from
                  module:observability; AccessView over the joined result
    Acceptable when: always.

  Option: inline
    Summary:      The latest score is carried as an attribute of the entity.
    Implies:      a Decimal attribute on the entity; no quality history
    Acceptable when: the entity is small, only the latest score is ever needed,
                  and no consumer examines quality trend or per-rule detail.
    Requires:     a recorded reason.
```

**Why observability is advocated.** A quality score is a measurement taken at a moment, and its value lies in the series: *is this entity getting better or worse, and which rule started failing?* An attribute on the entity holds one number and answers neither. It also discards the per-rule detail that makes a score actionable: an agent told only that quality is `0.72` knows that something is wrong but not what, and cannot judge whether the failure matters for its purpose.

This is the same argument as `DEC-COLUMN-STRATEGY`, applied to one specific concern, and the same answer applies to the join objection: present the result through a view.

**The rule categories.** A `QualityScore` decomposes into five standard categories, so that scores are comparable between entities and between products:

| Category | Assesses | Indicative weight |
|---|---|---|
| Completeness | Required attributes are populated | 30% |
| Validity | Values conform to format and range | 25% |
| Consistency | Related attributes agree with each other | 20% |
| Accuracy | Values agree with an authoritative source | 15% |
| Timeliness | Data is fresh enough for its purpose | 10% |

Weights are indicative and may be tuned per product; the categories are not, since comparability depends on them. The composite is expressed on a `0.00`-`1.00` scale.

---

## 8. `DEC-AUDIT-RETENTION`

```
Decision: DEC-AUDIT-RETENTION
  Question:   How long are change events and deletion records retained?
  Applies to: the observability module, per product

  Option: regulatory                                   [advocated]
    Summary:      Retention tiered by obligation: recent change history
                  immediately queryable, older history retained but archived,
                  deletion records held longest, and high-risk entities held
                  indefinitely.
    Implies:      capability ChangeEventCapture; INV-OBS-004
    Acceptable when: always.

  Option: bounded
    Summary:      A single uniform retention window for all audit data.
    Implies:      capability ChangeEventCapture
    Acceptable when: no regulatory obligation applies to any entity in the
                  product.
    Requires:     a recorded reason, and confirmation that no entity carries a
                  retention obligation.
```

**Why tiered retention is advocated.** Audit data does not have one purpose. Recent change history serves active investigation and needs to be queryable now; older history serves regulatory obligation and needs to survive, not to be fast; deletion records serve accountability regimes that outlive the data they describe. A single window either over-retains what is merely operational or under-retains what is legally required: and the second failure is discovered only when it matters.

**Indicative periods.** These are the recommended starting points; the governing obligation always wins where it differs.

| Audit data | Retention | Driven by |
|---|---|---|
| Recent change history | 2 years, immediately queryable | Active investigation |
| Older change history | 7 years, archived | Regulatory compliance |
| Deletion records | 10 years, archived | Accountability regimes |
| High-risk entities | Indefinite | Fraud and financial-crime obligations |

Retention of definitional lineage is governed separately by `INV-OBS-004`: definitions live as long as the product, while execution records follow the event-retention window.

---

## 9. Applying the catalogue

This catalogue holds the options and the reasoning in one place. Each module names, under Designer Responsibilities, which of them its designers must settle. A product's design records the answers.

Three properties follow, and they are the reason this material is expressed as decisions rather than advice:

- **A designer is asked rather than left to guess.** The questions arrive during design, from the skill, instead of sitting in a document someone was supposed to have read.
- **A reviewer can distinguish a deliberate departure from an oversight**, because the former carries a reason and the latter is missing an answer the linter expected.
- **Recommendations can change without invalidating existing products**: a product that recorded `scd2` with a reason remains conformant when the advocated option is restated, because it recorded that it was choosing.

---

## Change log

| Version | Change |
|---|---|
| 2.0 | Restructured from advisory prose into a decision catalogue expressed in the design language. Physical-design guidance moved to the Teradata platform profile; access-layer and object-placement material moved to their patterns; temporal column contracts moved to the temporal-lifecycle-metadata pattern. |
| 1.6 | Added the access-layer section, deferring placement and naming to the Object Placement Standard. |
| 1.5 | Established platform neutrality; Teradata physical design identified as a platform profile. |
| 1.4 | Surrogate key strategy rewritten to address instability in versioned entities. |
| 1.0-1.3 | Initial advocated standards and naming alignment. |
