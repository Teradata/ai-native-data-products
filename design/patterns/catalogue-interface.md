---
title: Enterprise Catalogue Interface Pattern
anchor: catalogue-interface
type: pattern
status: draft
version: 1.0
normative: true
---

# Enterprise Catalogue Interface

## 1. Purpose

A data product describes itself across three modules: Semantic holds the entity, column and relationship catalogue, Memory holds the glossary and design decisions, Observability holds lineage and quality. An enterprise catalogue (Alation, Collibra, DataHub) needs a product-level summary of that, on a stable contract, with change history.

This pattern defines that contract. It answers four questions:

1. What products exist, and what state is each in?
2. Who do I contact about this product?
3. Which objects is a consumer meant to query?
4. What changed since I last synchronised?

The fourth question is why the product record is versioned rather than current-state. Without history you cannot tell a retired product from one that was never registered, and you cannot show when a product's contract changed.

## 2. Scope and Boundaries

**In scope.** Product-level identity, lifecycle state, ownership contacts, the set of consumer-facing interfaces, the containers each module is deployed in, and the change history of all of those.

**Out of scope.** Column-level business meaning, glossary terms, lineage edges and quality measurements. Those are owned by the Semantic, Memory and Observability modules and are exported from them per release. This pattern says where a catalogue finds them, not what they contain.

It also defines no transport. Whether the catalogue pulls from the governance container or a build pipeline pushes a rendered bundle is a site decision.

The registry holds product-level governance state that exists nowhere else — lifecycle, contacts, approved entrypoint — plus pointers to the modules that own the detail. It does not duplicate module content.

## 3. Capabilities

**Provides:** no new capability. This pattern composes existing ones.

**Requires:**

| Capability | Strength | Provider | Why |
|------------|----------|----------|-----|
| `CurrentStateFilter` | `[hard]` | `pattern:temporal-lifecycle-metadata` | The default read of every feed is the current version, by one predictable filter. |
| `PointInTimeReconstruction` | `[hard]` | `pattern:temporal-lifecycle-metadata` | Governance readers ask what was published on a past date, including after retirement. |
| `SoftDelete` | `[hard]` | `pattern:temporal-lifecycle-metadata` | Retirement has to be a readable event, not a missing row. |
| `RichMetadata` | `[hard]` | `self` / `platform` | Every published field carries a description. |
| `SemanticRegistration` | `[hard]` | `module:Semantic` | The interface feed is projected from the product's entity, view and primary-object catalogues. |
| `AccessView` | `[soft]` | `module:Domain` | Where the product exposes named consumer views, those are what the interface feed publishes. A product exposing only tables still works. |

## 4. Placement Independence

Sites place containers where their standards say, and name them what they like. So:

> **Nothing a catalogue needs may be derivable only from a container or object name.**

A catalogue that infers the consumer surface from a name suffix works only at sites that adopted that suffix. Every container a product occupies is declared as data, at the grain of (product, module, layer). A product whose Domain layer sits in one hierarchy and whose Semantic layer sits in another is described as accurately as one that took every default.

The registry is the only object a catalogue must be told the location of.

## 5. The Interface Contract

Five feeds. A conforming implementation provides all five; a catalogue consumes the ones it can use.

| Feed | Grain | Answers |
|---|---|---|
| Product | one row per product version | what exists, what state, who owns it |
| Lifecycle | one row per state or version transition | what changed and when |
| Interface | one row per consumer-facing object per product version | what a consumer may query |
| Container | one row per (product, module, layer) | where every part of the product is deployed |
| Detail pointer | one row per product version | where the column, glossary, lineage and quality detail is |

### 5.1 Product identity and contacts

```
Entity: DataProductRegistration          [kind: History]
  product_id: NaturalKey [required] [unique]  // stable identifier; never reused across products
  product_name: ShortText [required]          // human-readable name
  product_version: ShortText [required]       // the contract version this registration describes
  product_domain: ShortText [optional]        // business domain the catalogue files it under
  product_description: Text [optional]        // purpose, scope, intended consumers
  product_status: Enum{DRAFT|ACTIVE|DEPRECATED|RETIRED} [required]
  owner_team: ShortText [optional]            // owning team or steward function
  owner_name: ShortText [optional]            // accountable person, by name
  owner_email: ShortText [optional] [pii]     // accountable person, addressable
  technical_contact_name: ShortText [optional] // engineering contact, by name
  technical_contact_email: ShortText [optional] [pii]  // engineering contact, addressable
  approved_entrypoint: Text [optional]        // the approved first data-access surface
  approved_access_mode: Enum{VIEW|MCP_TOOL|SEMANTIC_QUERY} [optional]
  manifest: Json [optional]                   // machine-readable orientation manifest
  is_active: Flag [required]                  // discoverable to consumers

  Keys:
    natural: product_id

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement

  Requires capabilities:
    - CurrentStateFilter
    - PointInTimeReconstruction
    - SoftDelete
    - RichMetadata
```

**A contact is a person and an address.** `owner_team` names the accountable function; it is not an answer to "who do I ask about this". Conformance requires a reachable address on any product published as active. Both contact pairs are optional in the model, and an absent contact stays absent — an implementation does not substitute the build user or the team name.

**The registration is versioned.** At product level the transition is the fact a governance reader wants: when the product became active, when it deprecated, which version added the field they are asking about. Other catalogue entities in the corpus declare `CURRENT_STATE` because an agent generating a query wants today's meaning only; here the audience is different.

`product_status` is a value of the current version. A product reaching `DEPRECATED` closes the version that was `ACTIVE` and opens a successor. Retirement is a logical deletion, which under the temporal pattern is itself a new current version — so a retired product is still readable at any earlier instant.

### 5.2 Consumer interfaces

```
Entity: DataProductInterface              [kind: History]
  product_id: Reference [required] [-> DataProductRegistration]
  interface_name: ShortText [required]      // the object as a consumer names it
  container_name: ShortText [required]      // exact deployed container; used verbatim
  object_name: ShortText [required]         // exact deployed object; never derived
  object_kind: Enum{TABLE|VIEW|MACRO|PROCEDURE|FUNCTION} [required]
  interface_layer: Code [optional]          // layer of the container the object sits in
  exposure_type: Code [optional]            // what kind of exposure it is, from the module's view catalogue
  module_name: Code [optional]              // owning module
  interface_purpose: Text [optional]        // what this surface is for
  is_primary: Flag [required]               // the recommended surface for its entity
  is_consumer_facing: Flag [required]       // a consumer may query it
  is_active: Flag [required]

  Keys:
    natural: product_id, container_name, object_name

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement

  Requires capabilities:
    - CurrentStateFilter
    - RichMetadata
    - AccessView
```

The interface feed is a projection. The authority for which objects a consumer may query is the Semantic module's view and primary-object catalogues, maintained by the product as part of its own deployment. The feed exists so a catalogue gets the same list across every product without connecting to each product's Semantic container, and so an object withdrawn between versions stays visible as withdrawn. `INV-CATALOGUE-006` checks the projection against its source in both directions.

`is_consumer_facing` is recorded from the product's access declaration. It is not inferred from the container's name or the object's suffix.

### 5.3 Containers

```
Entity: DataProductContainer              [kind: History]
  product_id: Reference [required] [-> DataProductRegistration]
  module_name: Code [required]              // DOMAIN, SEMANTIC, MEMORY, OBSERVABILITY, SEARCH, PREDICTION, or site-defined
  layer_code: Code [required]               // which layer: base, view, access, business, staging
  container_name: ShortText [required]      // exact deployed container
  is_active: Flag [required]

  Keys:
    natural: product_id, module_name, layer_code

  Applies patterns:
    - temporal-lifecycle-metadata
    - object-placement

  Requires capabilities:
    - CurrentStateFilter
    - RichMetadata
```

One row per container the product occupies, at any depth of hierarchy, under any naming. A site that adds a module, or splits one module across three layers, adds rows rather than columns. This is what makes a product deployed outside the default hierarchy fully describable.

`layer_code` draws on a vocabulary shared across products, so a catalogue can ask which container holds a product's consumer surface and get the same answer at every site. `container_name` is whatever the site deployed, and nothing reads meaning out of it. An object's layer is a property of the container it sits in, declared once here.

### 5.4 Change visibility

A catalogue synchronises by reading the versions that opened after a given instant. Three properties make that work, all inherited from the temporal pattern: a transition closes the predecessor and opens a successor in one unit of work; replaying the same input opens nothing; and a logical deletion is a version, so a retirement is an event to read rather than an absence to detect.

The product-level feeds do not carry column-level or definition-level change. The Semantic catalogues that hold those declare `CURRENT_STATE` and record today's meaning only. A change to a column's business definition reaches a catalogue as a version-stamped snapshot difference: the registration's `product_version` moves, the release renders a complete detail export for that version, and the catalogue holds both. A site needing definition-level history inside the database is choosing `DEC-TEMPORAL-PATTERN` differently for its Semantic module and must record that choice; the interface contract is the same either way, since it reads the export.

### 5.5 Detail pointers

Per registration, a location for each body of detail a catalogue may navigate to: contract, semantic model, glossary, query cookbook, lineage, quality report and access policy. A pointer is set by whoever governs that surface, and re-registration never overwrites it. A build knows where its own artefacts are but not which of them a site has published, so an automated registration that cleared an operator's pointer would destroy the only value in the field.

## 6. Semantic Model Export

The five feeds tell a catalogue what products exist and which objects to register as assets. A catalogue that masters semantic models needs more than that: the business entities, their attributes, how they join, and the measures defined over them. That material is in the product's Semantic module, and it reaches a catalogue as an export rather than through a feed, because it is version-scoped and because the consuming format is the catalogue's, not ours.

**Two artefacts per product version.**

| Artefact | Carries | Built from |
|---|---|---|
| Semantic model | datasets, fields, relationships, metrics, synonyms | the product's Semantic catalogue |
| Product descriptor | identity, version, status, contacts, output objects, detail pointers | the product and interface feeds |

Both are emitted at release, stamped with the product version current at that instant, and complete: an export states the whole model as at its version rather than a delta. A catalogue applying a delta cannot tell an omission from a deletion, and it already has the previous export to difference against if it wants one.

**Nothing in an export is inferred.** Every dataset, field, relationship, metric and contact is a declared row. Where the Semantic catalogue has no metric, the export has no metric; where a product records no owner, the descriptor's contact is absent. An emitter that filled a gap with a plausible value would put a definition into a governance catalogue that nobody in the business ever agreed to.

**Relationship direction is normalised on the way out.** Interchange formats generally express a relationship in one direction, from the entity holding the reference to the entity referenced. A relationship catalogue that records direction as the designer entered it therefore needs normalising at emit time, not at registration time: the catalogue's own record stays as declared, and the emitter inverts where the declared cardinality says the reference runs the other way. A many-to-many relationship has no single-direction expression at all; an emitter reports it rather than guessing, and the fix is to register the bridging entity that the relationship implies.

**The export is generated, never hand-maintained.** A semantic model kept by hand alongside the catalogue it describes is a second source of truth, and the two disagree within a release or two. The same holds in the other direction: where a catalogue enriches a model and offers to write it back, the product decides which fields it accepts, and a field the product considers its own is not overwritten by a round trip.

## 7. Invariants

- `INV-CATALOGUE-001`: every registration carries a lifecycle state from the declared state vocabulary.
- `INV-CATALOGUE-002`: at most one version of a given product is current at any instant.
- `INV-CATALOGUE-003`: a product's state and version history is reconstructable for any past instant, including after retirement.
- `INV-CATALOGUE-004`: a retired product is recorded as logically deleted and carries the instant of its retirement; no registration is physically removed.
- `INV-CATALOGUE-005`: every container a product occupies is declared as data; no consumer of the interface derives a container or object name from a naming convention.
- `INV-CATALOGUE-006`: every consumer-facing interface in the interface feed resolves to a live object declared by the product's own Semantic catalogue, and every object that catalogue declares consumer-facing appears in the feed.
- `INV-CATALOGUE-007`: a product published as active carries a reachable contact address.
- `INV-CATALOGUE-008`: a detail pointer set by a governance operator survives re-registration of the product by an automated build.
- `INV-CATALOGUE-009`: re-registering an unchanged product version opens no new version.
- `INV-CATALOGUE-010`: no field in any feed is populated with a value the source could not supply; an absent fact is absent, not inferred.
- `INV-CATALOGUE-011`: every dataset, field, relationship and metric in a semantic model export is registered in the product's Semantic catalogue; the export adds nothing the catalogue does not hold.
- `INV-CATALOGUE-012`: every export is stamped with the product version current at the instant it was produced, and states the complete model as at that version rather than a difference from an earlier one.
- `INV-CATALOGUE-013`: a relationship that cannot be expressed in the target format's direction or cardinality is reported by the emitter and omitted; it is never emitted in an altered form.

## 8. Designer Responsibilities

| Decision | Recommended | Settle it by asking |
|---|---|---|
| `DEC-TEMPORAL-PATTERN` | `scd2` | Does a governance audience need to know when the product's state or contract changed, or only what it is now? Retirement decides it: an audience asking what was live last quarter cannot be served from current state. `scd2` is recommended over the advocated `bi-temporal` because a registration is a governance declaration, true from the instant it is declared, so valid time and transaction time coincide and the second pair carries no information. A site that corrects registrations retrospectively should take `bi-temporal`. |
| `DEC-DELETE-STRATEGY` | `soft-delete` | Is a retired product still subject to audit, to an access review, or to a question about a report someone ran last year? |

A designer also settles: the state vocabulary, if the four advocated states do not fit the site's governance process; the layer vocabulary used by the container feed; whether the interface feed is projected at release time or read live; and which single contact a catalogue requiring exactly one should be given.

## 9. Implementation

A platform binding provides: the versioned product, interface and container entities; the transition operations for each lifecycle event; the query surfaces a catalogue reads; the resolution query returning a product's consumer-facing objects and contacts from metadata alone; and conformance checks for the invariants above. The Teradata binding is `implementation/teradata/patterns/catalogue-interface/`.
