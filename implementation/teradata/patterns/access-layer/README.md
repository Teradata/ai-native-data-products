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
| Role | `CREATE ROLE {ProductName}_ROLE_{TIER}` plus a `COMMENT ON ROLE` of **one short sentence naming the role's consumers**. Never the containers it reaches or the rights it holds (see below). |
| Read | `GRANT SELECT ON {container} TO {role}`. |
| Write-back (append) | `GRANT INSERT ON {container} TO {role}` (Memory, Observability; `ROLE_AGENT` only). |
| Module access container | `{ProductName}_{Module}` (standard placement) or the `_V` view container under `STRICT_SEPARATION` (see [object-placement](../object-placement/)). |
| Implied grant (Phase 1.5a) | `GRANT SELECT ON {module_container} TO {access_container} WITH GRANT OPTION`. |

## What a role comment says

One sentence, naming who the role is for:

```sql
COMMENT ON ROLE {ProductName}_ROLE_AGENT IS
    '{ProductName} data product - AI agent and automated tool role.';
```

Not what it can reach. The comment previously ran to three lines listing the containers, the write-back rights, and the reason `ROLE_AGENT` is separate, and it failed two ways at once.

It was **rejected on deployment** with `[5550] Comment string is longer than permitted`, the 255-character limit that applies to every `COMMENT ON` in Teradata (see [PLATFORM_PROFILE](../../PLATFORM_PROFILE.md)). Because `CREATE ROLE` runs first in the same block, the roles were created and left undescribed. A deployment that does not read the failure looks like it worked.

More importantly it **published the permission boundary**. `DBC` role comments are readable by principals who cannot read the grants themselves, so enumerating the grant model in one hands out a map of the access design to anyone who can query the catalogue. The grant matrix in the [pattern](../../../../design/patterns/access-layer.md) is the authoritative statement of who reaches what, and `DD-ACCESS-001` already records why the boundary sits where it does, inside the product. The comment was a third copy of both, and the only one exposed this widely.

The product name is the sole variable part, so the rendered length is predictable: keep the descriptor to a handful of words and a long product name still fits.

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
