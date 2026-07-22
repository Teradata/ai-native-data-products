# Teradata — Access Layer Implementation

Teradata binding of [`design/patterns/access-layer.md`](../../../../design/patterns/access-layer.md).
Creates the three product roles and grants them access as each module deploys. Read the pattern
first for the role model, grant matrix, and two-phase timing.

## Files

| File | Purpose |
|------|---------|
| `access-layer.dcl.sql` | `CREATE ROLE` for the three roles and the phased `GRANT` blocks (schema-neutral tags `{ProductName}_{Module}`). |
| `dd-access-001.sql` | The mandatory `DD-ACCESS-001` design-decision record inserted into the product's Memory documentation facet. |

## Bindings

| Pattern element | Teradata binding |
|-----------------|------------------|
| Role | `CREATE ROLE {ProductName}_ROLE_{TIER}` with a `COMMENT`. |
| Read | `GRANT SELECT ON {container} TO {role}`. |
| Write-back (append) | `GRANT INSERT ON {container} TO {role}` (Memory, Observability; `ROLE_AGENT` only). |
| Module access container | `{ProductName}_{Module}` (standard placement) or the `_V` view container under `STRICT_SEPARATION` (see [object-placement](../object-placement/)). |

## Artefact location

In a data product's artefact tree the DCL lives at `00-access/{ProductName}_access_layer.dcl`, the
`00-` prefix marking it as a prerequisite alongside the module directories. How the two phases are
executed (one pass or two) is left to the deploying team. The roles are product artefacts created
once; assigning users/service accounts to them is an operational event, not part of this artefact.
