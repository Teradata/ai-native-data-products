# Composite joins in the design specification: design

Status: approved in conversation 2026-10-14; implementation proceeds from this document.

## Purpose

The 2.0.0 metadata contract stores a relationship as a join group of ordered column pairs, but nothing in the
specification language could produce more than one pair. A reference attribute (`[-> Customer]`) carries one
source column and is paired with the first column of the target's identity; any further column of a composite
target identity was reported as a gap. This change lets a design author, and the standards themselves, state a
multi-column join, so the relationship catalogue, the path view and the reference checks see it.

The standard needs it: `ValidationArea` joins `ValidationRun` on `product_code`, `producer_id` and `run_id`, and no
relationship declared it. The resolver also never scanned standard-owned relations for references, so none of their
joins (`LineageRun` to `DataLineage`, `KeyColumn` to `KeyDefinition`, ...) were registered either.

## Decisions

| Decision | Choice |
|---|---|
| Where a composite join is written | On each source attribute, naming the target attribute it pairs with |
| Standard-owned relations | Their references become relationships too, and the standards declare their composite joins |

## Syntax (Design Specification Standard §3.4)

| Qualifier | Meaning |
|---|---|
| `[-> Target]` | Unchanged. This attribute is the whole join, paired with the target's identity (its surrogate, else its natural key) |
| `[-> Target.attribute]` | This attribute pairs with that attribute of the target |
| `[join: name]` | Names the join group, so an entity can hold two joins to the same target |

Attributes of one entity that name the same target form one join group, in declaration order; that order is the
pair order (`key_ordinal`). A group of one is a single-column join to a named target attribute.

The lint rejects a group when:

- a target attribute does not exist, or is named twice;
- the target attributes are not exactly one key of the target (its surrogate or its natural key);
- the two sides of a pair have different logical types (`Reference` and `Identifier` count as the same);
- the group uses a multi-target `A | B` reference.

A bare reference is always its own group, so a bare and a named join to the same target can sit side by side.

A join is mandatory only when every source attribute of the group is required.

## Resolver

The resolver builds one relationship per group, from the specification's entities and from the standard-owned
relations. A relationship's name is the source entity and the group's name (the `join:` name, else its first
attribute). A bare reference to a composite target still pairs the first column and reports the rest as a gap, so
existing specifications resolve as before.

## Standards

`design/patterns/validation.md` declares `ValidationArea` to `ValidationRun` with three pairs. Standard-owned relations
that already carry a bare `[->]` are registered without change.

## Bindings

Registration already writes one `RelationshipColumn` row per pair. The relationship reference check on all three
platforms joins on every pair, where it compared only the first target column.

## Visible effects

Every product's relationship catalogue and path view grow by the standards' internal relationships. Each product also
runs one reference check per new relationship. `COMPATIBILITY.md` drops the "composite joins can't be declared"
limitation and the migration note records that the catalogue grows.

## Testing

- Lint: accept and reject cases for each rule.
- Resolver: a small specification with a composite join resolves to one relationship with ordered pairs; a bare
  reference to a composite target still reports its gap.
- DuckDB engine: `ValidationArea` to `ValidationRun` has three ordered pairs, the path rows group them in one hop, and
  the reference check fails when one pair is broken.
- Postgres and Teradata render and pass the shared tests; neither is executed here.

## Out of scope

Rendering the `integrity` expression, composite multi-target references, generating alternate keys, and joins to
attributes that are not a key of the target.
