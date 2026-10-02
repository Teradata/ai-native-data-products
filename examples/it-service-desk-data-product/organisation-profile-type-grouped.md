---
organisation: Contrasting example organisation
platform: teradata
platform_version: "20.00"
---

# Organisation Profile: contrasting example (Teradata)

A second organisation profile for the IT Service Desk example, deliberately unlike
[`organisation-profile.md`](organisation-profile.md) in every respect a profile controls:
placement (type-grouped rather than one container per module), object and column naming,
principals (one bound to an existing group), classification and protection, retention
bounds, environment isolation, and an adopted entity. Building the same
[design specification](design-output/design_specification.md) under both profiles is the
portability test of the [Platform Implementation Authoring Standard](../../design/core/IMPLEMENTATION_AUTHORING.md)
§8: the products must differ only where the profiles do.

```bash
python tooling/build/org_profile.py examples/it-service-desk-data-product/organisation-profile-type-grouped.md
```

---

## Section 1. Platform Declaration

```
Platform: -
  Container term:  DATABASE
  Principal term:  ROLE
  Namespace:       flat
  Max name length: 128
  Name characters: lower-case letters, digits and underscore
  Reserved words:  DBC, SYSLIB, SYSBAR, TDSTATS, TDWM
```

## Section 2. Container Model

Two containers per product, one for data and one for views, plus the organisation's
existing enterprise catalogue.

```
Containers: -
  data:       dp_{product_code|lower}_data
  views:      dp_{product_code|lower}_views
  governance: enterprise_catalogue
```

## Section 3. Naming Pattern

Everything is lower snake case. Base views carry `_cur` and consumer views take the bare
name, distinguished by container and suffix. The organisation's column standard names
audit and validity columns `_ts`, and its catalogue tooling expects the validation
relations in snake case.

```
Naming: -
  Objects:
    table: {entity|snake}
    base_view: {entity|snake}_cur
    consumer_view: {entity|snake}
  Attributes: {attribute}
  Standard names:
    created_dts: row_created_ts
    updated_dts: row_updated_ts
    valid_from_dts: valid_start_ts
    valid_to_dts: valid_end_ts
    ValidationRun: validation_run
    ValidationArea: validation_area
```

## Section 4. Object Placement Rules

```
Placement: -
  Rules:
    table: data
    base_view: views
    consumer_view: views
    procedure: data
    function: data
    DataProductRegistry: governance
```

## Section 5. Separation Policy

```
Separation: -
  Policy:        TYPE_GROUPED
  Object naming: name-discriminated
  Exceptions:    Base and consumer views share the views container; the _cur suffix distinguishes them, and consumer principals are granted only the unsuffixed views.
```

## Section 6. Derivation Function

```
Derivation: -
  Product code: ITSD
  Examples:
    - table domain Ticket History -> dp_itsd_data.ticket
    - base_view domain Ticket History -> dp_itsd_views.ticket_cur
    - consumer_view domain TicketFeatureSet History -> dp_itsd_views.ticket_feature_set
    - table semantic DataProductRegistry -> enterprise_catalogue.data_product_registry
    - table observability ValidationRun -> dp_itsd_data.validation_run
```

## Section 7. Access Model

The admin tier binds the organisation's existing data-steward group; the read and agent
tiers are created per product.

```
Principals: -
  ROLE_READ:   create grp_{product_code|lower}_reader
  ROLE_AGENT:  create svc_{product_code|lower}_agents
  ROLE_ADMIN:  existing dba_data_stewards
  Grant level: object
```

## Section 8. Validation Procedure

The platform binding generates the placement checks from this profile and runs them after
each deployment phase, halting on any failure.

## Classification

```
Classification: -
  Scheme:  Public, Internal, Sensitive
  Default: Internal
  Markers:
    pii: Sensitive
    pii-incidental: Internal
  Protection:
    Public: none
    Internal: none
    Sensitive: mask for ROLE_READ, ROLE_AGENT
```

## Retention

```
Retention: -
  Audit minimum: 1 years
  Audit maximum: 7 years
```

## Environments

Development, acceptance and production share one system; containers carry the phase.

```
Environments: -
  Phases:             dev, uat, prod
  Isolation:          container
  Container template: {container}_{environment}
```

## Adoption

The enterprise catalogue exists already. The IT Service Desk product reads customers from
the organisation's customer master rather than holding its own copy.

```
Adoption: -
  Containers:
    governance: enterprise_catalogue
  Entities:
    ITSD.Customer: crm.customer_master
```
