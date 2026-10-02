---
organisation: IT Service Desk example organisation
platform: teradata
platform_version: "17.20"
---

# Organisation Profile: IT Service Desk example (Teradata)

The organisation profile the IT Service Desk example builds under, written to the
[Organisation Profile Standard](../../design/core/ORGANISATION_PROFILE.md). It replaces the
prose object-placement standard this example used to carry: the eight placement sections
below are that standard, with each rule stated in a block the build-context resolver
executes. Validate it with:

```bash
python tooling/build/org_profile.py examples/it-service-desk-data-product/organisation-profile.md
```

Nothing here is specific to the IT Service Desk product: every name is derived from the
specification's `product_code`, so another product built in this organisation gets its own
`<CODE>_*` databases and roles from the same profile.

---

## Section 1. Platform Declaration

Teradata, where the container is a `DATABASE` and the namespace is flat (`database.object`).
Names are alphanumeric and underscore only; system databases are reserved.

```
Platform: -
  Container term:  DATABASE
  Principal term:  ROLE
  Namespace:       flat
  Max name length: 30
  Name characters: letters, digits and underscore
  Reserved words:  DBC, SYSLIB, SYSBAR, TDSTATS, TDWM
```

## Section 2. Container Model

Child containers only: one database per module, plus a views-only access database and the
organisation's shared `governance` database, which holds the cross-product registry.
Environments are separate Teradata systems, so container names carry no environment marker.

```
Containers: -
  memory:        {product_code}_MEM
  semantic:      {product_code}_SEM
  domain:        {product_code}_DOM
  observability: {product_code}_OBS
  search:        {product_code}_SCH
  prediction:    {product_code}_PRD
  access:        {product_code}_ACC
  governance:    governance
```

## Section 3. Naming Pattern

Containers are `{product_code}_{module abbreviation}`. Objects take the entity name; a
versioned Domain entity's table carries `_History`, every governed view carries `_Current`,
and the consumer view takes the bare entity name. Attributes keep the specification's names. The
validation pattern's relations keep their logical snake-case names, which this
organisation's conformance tooling expects.

```
Naming: -
  Objects:
    table: {entity}
    table domain History: {entity}_History
    base_view: {entity}_Current
    consumer_view: {entity}
  Attributes: {attribute}
  Standard names:
    ValidationRun: validation_run
    ValidationArea: validation_area
```

## Section 4. Object Placement Rules

Tables, governed views and procedures sit in their module's database; every consumer view
sits in the access database; functions sit with Domain. The product's registry row lives
in the shared governance database because its purpose is cross-product discovery.

```
Placement: -
  Rules:
    table: module
    base_view: module
    consumer_view: access
    procedure: module
    function: domain
    DataProductRegistry: governance
```

## Section 5. Separation Policy

Strict separation: consumers are granted the access database only, so a grant there never
exposes a base table.

```
Separation: -
  Policy:        STRICT_SEPARATION
  Object naming: container-discriminated
  Exceptions:    Governed _Current views live in module databases as an internal tier; they are never granted to consumer principals.
```

## Section 6. Derivation Function

The resolver derives every container and object name from Sections 2 to 4. These worked
examples are re-derived on every check, so they cannot drift from the rules.

```
Derivation: -
  Product code: ITSD
  Examples:
    - table domain Ticket History -> ITSD_DOM.Ticket_History
    - base_view domain Ticket History -> ITSD_DOM.Ticket_Current
    - consumer_view domain Ticket History -> ITSD_ACC.Ticket
    - table search EntityEmbedding History -> ITSD_SCH.EntityEmbedding
    - table domain Category Reference -> ITSD_DOM.Category
    - table memory AgentSession -> ITSD_MEM.AgentSession
    - table semantic DataProductRegistry -> governance.DataProductRegistry
    - table observability ValidationRun -> ITSD_OBS.validation_run
```

## Section 7. Access Model

Role-based and granted at database level. Each tier is a role created for the product.
The grant matrix itself is the access-layer pattern's; the implied grants the access
database needs to compile its views are derived by the binding from the placement above.

```
Principals: -
  ROLE_READ:   create {product_code}_ROLE_READ
  ROLE_AGENT:  create {product_code}_ROLE_AGENT
  ROLE_ADMIN:  create {product_code}_ROLE_ADMIN
  Grant level: container
```

## Section 8. Validation Procedure

The platform binding generates the placement checks from this profile and runs them after
each deployment phase: every container exists; no table sits in the access database; no
consumer view sits in a module database; the implied grants are present; consumer
principals hold no rights on module databases. Any failure halts the deployment and is
reported, never corrected silently.

## Classification

Four classes. Personal data is Restricted. Incidental personal data in free text is
Confidential. No runtime masking is applied in this cycle: the risk is recorded in the
product's Memory for production hardening.

```
Classification: -
  Scheme:  Public, Internal, Confidential, Restricted
  Default: Internal
  Markers:
    pii: Restricted
    pii-incidental: Confidential
  Protection:
    Public: none
    Internal: none
    Confidential: none
    Restricted: none
```

## Environments

```
Environments: -
  Phases:    development, test, production
  Isolation: system
```

## Adoption

The shared governance database already exists; products register into it and never create
it.

```
Adoption: -
  Containers:
    governance: governance
```
