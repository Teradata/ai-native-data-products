---
title: Teradata Access Layer Pattern Implementation
anchor: access-layer
type: implementation
status: standard
version: 2.0
normative: true
implements: access-layer
platform: teradata
---

# Teradata: Access Layer Implementation

Teradata binding of [`design/patterns/access-layer.md`](../../../../design/patterns/access-layer.md). Creates the three product roles and grants them access as each module deploys. Read the pattern first for the role model, grant matrix, and two-phase timing.

## Files

| File | Purpose |
|------|---------|
| `access-layer.dcl.sql` | The Phase 1.5a implied grants, then `CREATE ROLE` for the three roles and the phased `GRANT` blocks (schema-neutral tags `{ProductName}_{Module}`). |
| `dd-access-001.sql` | The mandatory `DD-ACCESS-001` design-decision record inserted into the product's Memory documentation facet. |

## Bindings

| Pattern element | Teradata binding |
|-----------------|------------------|
| Role | `CREATE ROLE {ProductName}_ROLE_{TIER}` with a `COMMENT`. |
| Read | `GRANT SELECT ON {container} TO {role}`. |
| Write-back (append) | `GRANT INSERT ON {container} TO {role}` (Memory, Observability; `ROLE_AGENT` only). |
| Module access container | `{ProductName}_{Module}` (standard placement) or the `_V` view container under `STRICT_SEPARATION` (see [object-placement](../object-placement/)). |
| Implied grant (Phase 1.5a) | `GRANT SELECT ON {module_container} TO {access_container} WITH GRANT OPTION`. |

## Privilege split

The file divides at a privilege boundary, and the division is the point.

**Phase 1.5a needs no DBA.** The implied grants require only ownership of the source and target containers. They are what lets a view in the access container compile against a base table in a module container, so they belong at the end of Phase 1, as soon as the containers exist. Omitting them fails at view-compile time with `[5315] An owner referenced by user does not have SELECT WITH GRANT OPTION access`, which reads as a fault in the view rather than a missing grant two phases earlier.

**Everything from `CREATE ROLE` down needs DBA.** Confirm the privilege before generating the block:

```sql
SELECT * FROM DBC.AllRightsV WHERE UserName = USER AND AccessRight = 'CG';
```

Where the deploying account does not hold it, emit that block as a separate DBA-prerequisite artefact and continue: the schema and data are fully functional without roles, and the outstanding step stays visible rather than being swallowed by a failed block. Under co-located placement there is no separate access container, so Phase 1.5a is empty and the split costs nothing.

## Artefact location

In a data product's artefact tree the DCL lives at `00-access/{ProductName}_access_layer.dcl`, the `00-` prefix marking it as a prerequisite alongside the module directories. The roles are product artefacts created once; assigning users/service accounts to them is an operational event, not part of this artefact.
