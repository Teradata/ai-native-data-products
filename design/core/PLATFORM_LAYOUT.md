---
title: Platform Layout Standard
anchor: platform-layout
type: core
status: draft
version: 1.0
normative: true
---

# Platform Layout Standard

## 1. Purpose

Products built to these standards are named differently, because the organisation profile lets each organisation choose its own names. That is deliberate, and it is safe only if nothing that reads a product has to guess what the names are. This standard makes the layout of a product something it states, not something a reader infers: which layers it has, which container and object serves each, and which platform conventions produced them.

It does three things:

- It names the **layer roles** every product has, in terms that hold on every platform (§3).
- It defines the **platform layout declaration**: a block each platform publishes in its platform profile, saying which layers are possible there and how its catalogue is read (§4).
- It defines the **product layout declaration**: the facts a product records in its Semantic module so that any evaluator, client or agent can resolve physical names from the product itself (§5), and the order in which they are resolved (§6).

It adds no new naming rule. Names remain the organisation's, derived by its [organisation profile](ORGANISATION_PROFILE.md). This standard governs how the result is recorded and read.

## 2. The three levels

| Level | Fixed by | Decides | Recorded in |
|---|---|---|---|
| **Standard** | This repository's design documents | What must exist, and the vocabulary of the metadata that describes it: Semantic and Memory relation and attribute names do not vary by product. | `design/` |
| **Platform layout** | The platform binding | What is possible on the platform: its container model, which layers are worth having, how its catalogue is read. | The `Layout:` block of the platform profile (§4) |
| **Product layout** | The build, from the organisation profile | The names this product actually has, and which object serves each layer. | The product's Semantic module (§5) |

Each level constrains the one below. The standard fixes what must exist, the platform layout fixes what is possible, and the product declares what it chose. A reader that needs a name asks the product, and the platform layout tells it what the answer can look like.

**Explicit bindings beat patterns.** An enumerated name in the product is authoritative and can be verified against the platform catalogue. A naming template, in an organisation profile or a generator, is an aid for producing names; no reader may use one to find a name it was not given.

## 3. Layer roles

A **layer role** is the platform-neutral name for the part a relational object plays in a product. There are exactly three, and each is a name for an object role the organisation profile already places and names ([Organisation Profile Standard](ORGANISATION_PROFILE.md) §5). This standard introduces no second vocabulary, so a layer role is always derived from an object role and never recorded separately.

| Layer role | Object role | What it is | Availability |
|---|---|---|---|
| `STORAGE` | `table` | The base table that holds an entity's rows. | Required on every platform. |
| `ACCESS` | `base_view` | An optional governed one-to-one view over a storage object, which insulates readers from the table. Not the [access-layer pattern](../patterns/access-layer.md), which grants read rights. | Declared per platform (`Access layer` in §4). |
| `CONSUMER` | `consumer_view` | The governed interface for agents and tools. | Required on every platform. |

Procedures and functions are not layers; they are placed and registered as objects of their own roles.

A module may expose more than one `CONSUMER` object for an entity. They differ by **audience** and by **access semantics**, both recorded on the object (§5):

| Property | Values | Meaning |
|---|---|---|
| `consumer_audience` | `AGENT`, `BI`, `ALL` | Who the object is intended for. Present only on `CONSUMER` objects. |
| `access_semantics` | `FULL_HISTORY`, `CURRENT_ONLY`, `POINT_IN_TIME` | The temporal contract of the object: the governed full-contract surface, the default current surface, or a surface that takes a point in time, as the [temporal pattern](../patterns/temporal-lifecycle-metadata.md) defines them. Absent for an entity that declares no history. |

`STAGING` and `MASKED` are not layer roles in this version. A platform needing them extends the vocabulary through a change to this standard, not through a local value.

## 4. The platform layout declaration

Every platform profile (`implementation/{platform}/PLATFORM_PROFILE.md`) carries a heading `Layout` and, under it, one `Layout:` block. The block is read by tooling (`tooling/build/platform_layout.py`), which also exports it as JSON for evaluators to load, so the prose profile and the machine-readable definition cannot drift apart.

### 4.1 `Layout:`

| Field | Required | Type | Value |
|---|---|---|---|
| `Container term` | yes | text | The platform's word for the unit a module's objects live in. |
| `Qualification` | yes | text | How a fully qualified object name is formed, naming its levels in order. |
| `Grant boundary` | yes | text | The unit access is granted on. |
| `Access layer` | yes | enum | `required`, `recommended`, `optional` or `not-applicable`: whether the `ACCESS` layer is worth having on this platform. |
| `Access rationale` | yes | text | Why, in a sentence. |
| `Consumer container` | yes | enum | `separate` or `may-share`: whether `CONSUMER` objects must sit in a different container from `STORAGE` objects, or may share it. |
| `Catalogue source` | yes | terms | The system catalogue relations an evaluator reads to verify a binding exists. |
| `Dialect` | yes | text | The SQL dialect the binding emits, for reading generated statements. |
| `Physical checks` | yes | terms | The platform-specific physical evidence checks a profile pack supplies, or `none`. |

`Access layer` states what the platform makes valuable. It does not relax the organisation profile: while the Organisation Profile Standard requires a `base_view` role on every platform, every binding still emits the layer, and the declaration governs how an evaluator reads its absence (§7), not whether a build may omit it.

## 5. The product layout declaration

A product declares its layout in Semantic metadata the build already writes, extended by four attributes. The build records them from the build context. A designer never supplies one.

| Fact | Where it is recorded | Notes |
|---|---|---|
| Platform | `DataProductRegistry.platform_profile` | The platform anchor: a directory under `implementation/`. |
| Standard version | `DataProductRegistry.standard_version` | The `version` of the Master Design the product was built against. |
| Container of each module's objects, by object role | `DataProductMap` | One row per module and object type, as today. This is the module's layer-to-container declaration. |
| Storage binding of an entity | `EntityMetadata.container_name`, `table_name` | The `STORAGE` binding. |
| Access and consumer bindings of an entity | `AccessObject` | One row per object, with `object_type` giving the layer role (§3). |
| Audience of a consumer object | `AccessObject.consumer_audience` | `CONSUMER` objects only. |
| Temporal contract of a consumer or access object | `AccessObject.access_semantics` | As §3. |

The attributes are defined in the [Semantic module](../modules/semantic.md). They sit on the registry because platform and standard version are facts about the product, not about each of its modules.

`EntityMetadata.view_name` remains the denormalised pointer to the entity's primary consumer object. It is derived from the `CONSUMER` binding whose `access_semantics` is `CURRENT_ONLY`, falling back to the primary `AccessObject` row where the entity declares no history.

**Verifiability.** Every binding names an object that exists. A reader can confirm that by querying the platform's catalogue (`Catalogue source`, §4). A binding that names a missing object is a defect in the product, reported by the validation pattern.

## 6. Discovery and resolution

A reader needs exactly one starting point: the product's Semantic container.

**Finding the Semantic container.** In order:

1. The organisation's catalogue, per the [catalogue-interface pattern](../patterns/catalogue-interface.md), which points at the product's discovery entry point.
2. An explicit pointer supplied by the caller, for a product not yet in the catalogue.

A reader never derives the Semantic container from a naming convention. Where the catalogue itself lives is configuration held by the evaluator for the estate, not by the product.

**Resolving a name.** Once the Semantic container is found, a name resolves from the first source in this table that supplies it:

| Priority | Source | Use |
|---|---|---|
| 1 | The evaluator's invocation | A one-off run or a test. |
| 2 | The evaluator's configuration for the product | An override while a product is migrating, so it can be assessed before its metadata is corrected. |
| 3 | The product's layout declaration (§5) | The authoritative, long-term home. |
| 4 | The derivation the organisation profile and platform binding make for the product | A product that has not declared a layout. |

An override at priority 1 or 2 is local to the evaluator and is never written into the product.

**An undeclared layout.** When priority 3 supplies nothing because the product has not recorded `platform_profile` and `standard_version`, or has no layer bindings, the evaluator resolves at priority 4, reports the issue code `LAYOUT_NOT_DECLARED`, and proposes the declaration it inferred as a repair candidate ([validation pattern](../patterns/validation.md)). The absence is a gap in the product's metadata, not a defect in its design.

## 7. Evaluator rules

An evaluator is anything that judges or reads a product: the trust engine, an orientation client, an agent. Evaluators work in two parts, and only the second is platform-specific.

- **Portable core checks** work on layer roles and bindings, whatever the platform.
- **A platform pack** supplies the catalogue reader, the dialect and the physical checks (`Physical checks`, §4) for one platform.

The rules:

1. A check asks for a role, such as "the `CONSUMER` binding of this entity", never for a suffix, prefix or pattern in a name.
2. A check that depends on a layer the product does not have is **excluded**, not failed, when the platform layout declares that layer `optional` or `not-applicable`, or `recommended` and the product declares none. An exclusion states its reason.
3. Exclusions are reported. A reader must be able to tell a check that passed from a check that does not apply here.
4. A check that depends on a layer the platform layout declares `required` fails when the product has no binding for it.
5. Physical checks of a profile pack run only against the platform they were written for.

Excluded checks are not counted in the area's expected checks, so exclusion neither lowers coverage nor raises confidence. How an exclusion is published through the validation result contract is outside this version; until it is defined, a producer states exclusions in its report.

## 8. Compatibility and adoption

Nothing here breaks an existing product. The four attributes are optional on deployed products, and a product without them resolves at priority 4 (§6) exactly as it did before.

The same declaration supports brownfield adoption. An existing estate declares how it is already named, through the organisation profile's `Adoption:` block, and is evaluated in place. It needs no renaming programme.

A later version of the Master Design may make the declaration mandatory. A product without one then scores a Semantic gap in place of resolving at priority 4.

## 9. DD-LAYOUT-001

When the Semantic module is deployed, the build records `DD-LAYOUT-001` in the product's Memory documentation facet, per the Memory capture protocol. Its category is `NAMING`. It records which platform the product was built for, which standard version, which organisation profile placed and named it, and that readers resolve the product's objects from its declared bindings and not from their names. Like `DD-DISCOVERY-001`, it explains a choice the deployed metadata cannot explain about itself.

## 10. Invariants

- `INV-LAYOUT-001`: every platform profile declares exactly one `Layout:` block that satisfies §4.1.
- `INV-LAYOUT-002`: a layer role is derived from an object role by the mapping in §3; no product records a layer role the mapping does not produce.
- `INV-LAYOUT-003`: a product built to this standard records its `platform_profile` and `standard_version` in its registry, and the build supplies both.
- `INV-LAYOUT-004`: a reader resolves a product's objects by layer role and declared binding, never from a suffix, prefix or pattern in a name.
- `INV-LAYOUT-005`: names resolve in the order of §6; an override is never written into the product; an undeclared layout is reported as `LAYOUT_NOT_DECLARED` and never silently defaulted.
- `INV-LAYOUT-006`: every declared binding names an object that exists on the platform.
- `INV-LAYOUT-007`: a check excluded for a layer the product does not have is reported with its reason and is not counted as expected.

## 11. Relationship to other standards

- **[Organisation Profile Standard](ORGANISATION_PROFILE.md)**: owns placement and naming; this standard owns how the result is declared and read.
- **[Semantic module](../modules/semantic.md)**: owns the metadata that carries the declaration (§5).
- **[Validation pattern](../patterns/validation.md)**: owns the issue code, the repair candidate and the result contract an evaluator publishes into (§6, §7).
- **[Object-placement pattern](../patterns/object-placement.md)**: owns container placement and separation; the layer roles name the objects it places.
- **[Platform Implementation Authoring Standard](IMPLEMENTATION_AUTHORING.md)**: requires each binding to carry the `Layout:` block and to register the product layout.
