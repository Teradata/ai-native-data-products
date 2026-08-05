<!-- design-lint: ignore-file (documents the SQL tokens the linter matches) -->

# tooling/validation: design linter

`design_lint.py` enforces the [Design Language](../../design/core/DESIGN_LANGUAGE.md) across both hierarchies. It is the executable form of the **No-Platform-SQL Rule**, the **frontmatter schema**, and the **decision rules**. Stdlib-only, Python 3.8+.

> **This checks the standards, not a product.** Its rules are corpus rules: module spines, the capability and decision catalogues, frontmatter identity. Pointing it at a product's design brief reports things that are true of a standards document and meaningless for a product artefact. The linter for a product design written *against* these standards is [`brief_lint`](../evals/), and it checks what a designer actually needs checked: unsettled decisions, unmet hard requirements, unacknowledged invariants, and platform SQL in a brief.

## Run it

Lint both hierarchies:

```bash
python tooling/validation/design_lint.py design implementation
```

Lint specific files or folders:

```bash
python tooling/validation/design_lint.py design/modules/domain.md design/patterns
```

Exit code is `0` when clean, `1` when any violation is found. Wire it into CI so a platform-SQL leak, a malformed frontmatter block, or a dangling cross-reference fails the build.

The no-platform-SQL rules apply to `design/` only: concrete SQL is exactly what `implementation/` exists to hold. The frontmatter and corpus rules apply to every design document in both trees.

## Use it in module unit tests

When validating a worked module, import the checks so a test can assert its design document is clean:

```python
from design_lint import lint_text
assert lint_text("design/modules/domain.md", text) == []
```

## What it checks

| Rule | Fails when… |
|------|-------------|
| `sql-fence` | a code block is tagged ` ```sql ` (or `tsql`, `plsql`, `psql`, `mysql`, `sqlite`). |
| `sql-statement` | a line inside any code block starts with `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `CREATE`, `ALTER`, `DROP`, `TRUNCATE`, `GRANT`, `REVOKE`, or `WITH`. |
| `vendor-token` | a platform data type or vendor token appears anywhere: `VARCHAR`, `BIGINT`, `BYTEINT`, `SMALLINT`, `TINYINT`, `DECIMAL(…)`, `NUMERIC(…)`, `FLOAT32`, `TIMESTAMP(…)`, `PRIMARY INDEX`, `GENERATED ALWAYS AS IDENTITY`, `NOT NULL`, `DEFAULT <value>`, `COMMENT ON`, `::VECTOR`, any `TD_*` function. |
| `unknown-type` | an attribute inside an `Entity:` pseudo-block uses a type not in the logical vocabulary (the Design Language's Logical Type Vocabulary). |
| `invariant-id` | an invariant id does not match `INV-<MODULE>-<NNN>` (the Design Language's Invariants section). |

### Frontmatter and corpus rules

| Rule | Fails when… |
|------|-------------|
| `frontmatter-missing` | a design document has no frontmatter block. |
| `frontmatter-key` | a required key is absent, an unrecognised key is present (substance belongs in the body), or an implementation omits `implements` / `platform`. |
| `frontmatter-enum` | `type`, `status`, or `normative` carries a value outside its vocabulary. |
| `anchor-mismatch` | `anchor` disagrees with the document's location. |
| `unknown-capability` | a capability named in a body Provides / Requires table is not in the catalogue. |
| `unknown-anchor` | an `implements` or `supersedes` anchor resolves to no document. |
| `unknown-decision` | a decision named in a Decisions-to-settle table is not in the catalogue. |
| `invalid-choice` | a recommended option is not one of that decision's options. |
| `unjustified-choice` | a standard recommends other than the advocated option without saying why. |
| `undeclared-decision` | a module describes a `History` entity without asking the designer to settle how it versions and deletes. |
| `module-spine` | a `type: module` document is missing one of the canonical spine sections. Presence and naming are checked, never order or numbering, and a module may add its own sections anywhere; a subtitle after an em dash still matches (`Entity Model. Runtime Facet`). |
| `glossary-order` | a glossary entry is out of alphabetical order. |
| `glossary-entry` | a bold run opens a glossary line without the `, ` separator, almost always a cross-reference that wrapped onto the left margin, where it reads as a phantom definition. |

Both catalogues, and the per-document graph, are **read from the documents themselves**: found by anchor rather than by filename, and from body tables rather than headers. Adding a capability, a decision, or a whole module needs no change to the linter.

The rule is designed to catch real entanglement without flagging ordinary English: the words *table*, *view*, *date*, *index*, and *default* are fine in prose. Only high-precision tokens that never appear outside SQL are matched.

## Escape hatch

A core/meta document that must legitimately name SQL (the Design Language itself, this README) opts out in its frontmatter:

```yaml
lint: ignore-file
lint_reason: why this document must name SQL
```

That waiver covers the **content** rules only. The document has frontmatter (it declared the waiver there), so it is still held to it, and still contributes its anchor and catalogues to the corpus.

A document with **no** frontmatter at all uses the legacy directive on its first line:

```
<!-- design-lint: ignore-file (reason) -->
```

This one is a full opt-out, identity rules included. It has to be: the directive must open the file, which is exactly where a frontmatter block would have to start, so a document cannot carry both. Waiving only the content rules would leave it failing `frontmatter-missing` with no way to opt out of it.

Pick by whether the document has an identity to declare. A supporting note or a scratch file takes the directive; anything that belongs to the corpus takes the frontmatter key.

Module and pattern documents must never use either: they are exactly the content the rule keeps clean.

## Tests

```bash
python -m unittest discover -s tooling/validation/tests
```
