---
organisation: IT Service Desk example organisation
platform: postgres
platform_version: "16"
---

# Organisation Profile: IT Service Desk example (PostgreSQL)

The same organisation as [`teradata.md`](teradata.md), building on PostgreSQL. A profile is
per platform, so the organisation keeps one for each; its classification and environments
are the same, while placement and names follow what PostgreSQL's schemas and identifier
rules suit. Every name is derived from the specification's `product_code`.

```bash
python tooling/build/org_profile.py examples/it-service-desk-data-product/profiles/postgres.md
```

---

## Section 1. Platform Declaration

PostgreSQL, where the container is a schema within the product's database.

```
Platform: -
  Container term:  SCHEMA
  Principal term:  ROLE
  Namespace:       flat
  Max name length: 63
  Name characters: lower-case letters, digits and underscore
  Reserved words:  pg_catalog, information_schema, public
```

## Section 2. Container Model

One schema per module and one access schema holding every consumer view.

```
Containers: -
  memory:        {product_code|lower}_{module}
  semantic:      {product_code|lower}_{module}
  domain:        {product_code|lower}_{module}
  observability: {product_code|lower}_{module}
  search:        {product_code|lower}_{module}
  prediction:    {product_code|lower}_{module}
  access:        {product_code|lower}_access
```

## Section 3. Naming Pattern

Lower snake case. A table and its consumer view share a name and are told apart by schema;
point-in-time functions carry `at_`, and similarity functions `similar_`. The discovery and
trust views keep their logical names in snake case.

```
Naming: -
  Objects:
    table: {entity|snake}
    consumer_view: {entity|snake}
    function: at_{entity|snake}
    function search: similar_{entity|snake}
  Attributes: {attribute}
  Standard names:
    ColumnCatalogue: column_catalogue
    DataProductManifest: data_product_manifest
    RelationshipPaths: relationship_paths
    LineageGraph: lineage_graph
    LineageRunLatest: lineage_run_latest
    TrustMap: trust_map
```

## Section 4. Object Placement Rules

```
Placement: -
  Rules:
    table: module
    consumer_view: access
    function: module
```

## Section 5. Separation Policy

```
Separation: -
  Policy:        STRICT_SEPARATION
  Object naming: container-discriminated
```

## Section 6. Derivation Function

```
Derivation: -
  Product code: ITSD
  Examples:
    - table domain Ticket History -> itsd_domain.ticket
    - consumer_view domain Ticket History -> itsd_access.ticket
    - table semantic EntityMetadata -> itsd_semantic.entity_metadata
    - consumer_view observability TrustMap -> itsd_access.trust_map
```

## Section 7. Access Model

```
Principals: -
  ROLE_READ:   create {product_code|lower}_role_read
  ROLE_AGENT:  create {product_code|lower}_role_agent
  ROLE_ADMIN:  create {product_code|lower}_role_admin
  Grant level: object
```

## Section 8. Validation Procedure

The binding generates the placement checks from this profile and runs them after each
deployment phase, halting on any failure.

## Classification

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
