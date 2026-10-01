---
title: Platform Implementation Authoring Standard
anchor: implementation-authoring
type: core
status: standard
version: 1.0
normative: true
---

# Platform Implementation Authoring Standard

## 1. Purpose and scope

Every new platform binding must express the design standards as reusable Jinja templates. A binding must support arbitrary conforming data products, rather than encode a completed example product. This is a repository authoring contract, not a product-level choice in the Advocated Standards catalogue.

The [Design Language](DESIGN_LANGUAGE.md) remains the authority for the design/implementation boundary. This document defines requirements that are independent of the target database; concrete syntax and physical choices belong under `implementation/{platform}/`.

The requirements apply to new platform directories and to implementation refactors adopting this contract. Existing Teradata implementation files remain unchanged under the narrowly scoped legacy exception in section 7.

## 2. Required binding structure

Each platform must provide:

- A `README.md` describing supported compositions, deployment order and limitations.
- A `PLATFORM_PROFILE.md` recording physical choices, supported engine versions and driver constraints.
- A `TEMPLATE_INPUTS.md` defining the template context and its validation rules.
- Module and pattern directories corresponding to the design contracts the platform supports. Each directory must map capabilities to bindings, logical types to physical representations, and invariants to executable checks or explicitly reported gaps.
- Reusable `.sql.j2` templates for applicable deployment, access, maintenance, discovery and validation operations. Ordering and dependencies must be documented.

Unsupported capabilities must be declared explicitly. Absence of a binding, a skipped check or an unexecuted engine test must never be reported as conformance. Support for a minimal composition does not imply support for all six modules.

## 3. Template and input contract

Jinja templates are the maintained source of platform SQL. Product-specific SQL must be rendered into a separate product output location, outside the standards and examples corpus. Renaming fixed product SQL to a template suffix does not satisfy this requirement.

The input contract must specify required and optional fields, allowed values, defaults, dependencies and failure behaviour. It must cover product identity, selected modules, object placement, entities, relationships, temporal profiles and any applicable access or model configuration. Product and organisation names, business entities, containers, roles and credentials must not be embedded in reusable templates. Standard-owned metadata structures and documented platform constants may be fixed.

Rendering must use Jinja `StrictUndefined` or an equivalent configuration that rejects missing required values. Optional values must have explicit documented defaults. Identifiers and literal values require appropriate platform-aware quoting; runtime query parameters must use the driver's value-binding mechanism where available. Credentials must remain outside committed input fixtures and generated example artefacts.

Templates must honour composition and dependency declarations. They must not silently create omitted modules or infer placement from a private naming convention. Authoring tools may validate and normalise inputs, select templates and order phases; they must not become an alternative store of platform SQL.

## 4. Packaging and examples

Reusable rendering, validation and test utilities belong under `tooling/`. Platform directories contain binding documentation, declarations and templates, not product-specific Python compilers or completed applications.

New platform examples must use the shared IT Service Desk brief and source data so implementations can be compared. Examples supply declarative product inputs, platform placement overlays and a walkthrough. They must not ship generated deployment SQL, populated databases or completed product pipelines. Organisation-specific accounts, repositories and operational conventions must not be prerequisites.

Test fixtures and test-only loaders belong with the tests. Any synthetic facts or model outputs must be labelled as test data and must not be represented as source evidence. The shared example does not limit the binding to IT Service Desk products.

## 5. Automated acceptance checks

Repository validation must discover platform directories directly under `implementation/`, independently of example presence or a manually maintained platform allowlist. A newly added platform must not escape validation by omitting its example, manifest or templates. Only explicitly recorded legacy exceptions may narrow a check.

| Required check | Acceptance evidence |
|---|---|
| Structure and coverage | Required documents exist; supported module and pattern contracts have template and check mappings; gaps are explicit. |
| Input validation | Missing required values, invalid names, unsupported values and incompatible compositions fail clearly. |
| Reusability | The same templates render IT Service Desk and an unrelated product with different entities, names and placement. Rendering assertions detect residual fixture identifiers and unresolved template expressions. |
| Composition | Declared minimal and larger compositions render with only their required dependencies. |
| Packaging | No generated product deployment files or product compilers occur in binding or example directories; permitted standard-owned declarations are distinguished from business fixtures. |
| Engine behaviour | Rendered artefacts execute on the declared engine/version; applicable temporal, metadata, discovery, access and invariant checks exercise actual behaviour. |
| Corpus integrity | Design lint, frontmatter, catalogue and skill-package validation remain clean. |

Static naming and file-extension checks alone cannot establish reuse. Review must assess whether the input contract and generated behaviour satisfy the design contracts. Engine tests must use disposable environments and report their tested versions. Skipped tests remain gaps, even when rendering and packaging checks pass.

## 6. Review and merge requirements

Pull requests adding or refactoring platform bindings must identify the supported compositions and engine versions, show both product rendering cases, and report validation results and remaining gaps.

The checks in section 5 must run in pull-request CI. Repository branch protection or an equivalent ruleset must make the relevant checks required before merge. A failed required check blocks acceptance; missing engine coverage must not be disguised as a successful required run. Changes to the checks and exception scope require review alongside the binding.

This document specifies the acceptance policy. It does not itself install CI workflows or configure remote branch protection. Until those mechanisms are implemented and required, maintainers must record the checks as manual evidence and describe enforcement as manual rather than automated. Local checks alone do not prevent a remote merge.

## 7. Legacy exception and migration

The existing `implementation/teradata/` binding and original Teradata IT Service Desk example are exempt from newly introduced packaging and template-contract checks that would require their refactoring. Existing validation still applies. This exception preserves their present layout and behaviour; it does not exempt another platform or justify copying legacy packaging into a new implementation.

Every exception must identify exact paths, affected checks, rationale and migration scope in reviewed repository documentation. Exceptions must not be inferred from a missing file, absent example, engine availability or directory age. No automatic exception applies to new platforms. A migration must preserve validated behaviour and explicitly state which requirements remain outstanding.

## 8. Authoring completion checklist

Before presenting a binding as ready to merge, its author must provide the input contract, reusable templates and coverage mappings; the shared example inputs and unrelated-product test; test results with honest gaps; and evidence that required merge checks are configured or explicitly still manual. The reviewer verifies the semantic design obligations in addition to the mechanical checks.
