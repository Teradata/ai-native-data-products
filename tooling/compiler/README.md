# tooling/compiler: skill package verification

Compiling the standards into role skills is judgement work. The [Skill Conversion Prompt](../../prompts/Skill_Conversion_Prompt.md) asks an agent to compress `design/` and `implementation/` into four skills, deciding what becomes a decision table, what stays prose, and what moves into an on-demand file. Two runs will not produce identical output, and a deterministic script would do that compression badly.

What *is* deterministic is whether the result kept everything it was required to keep. `verify_skills.py` makes the prompt's "Verify before finishing" checklist executable.

## Run it

```bash
python tooling/compiler/verify_skills.py
```

Checks `./skills` by default. Exit code is `0` when the package conforms, `1` when it does not, and `2` when there is nothing to check, so a forgotten compilation is not mistaken for a pass.

```bash
python tooling/compiler/verify_skills.py --skills /path/to/skills --platform teradata
```

## What it checks

| Rule | Fails when… |
|------|-------------|
| `missing-skill` | a role has no `SKILL.md`. |
| `missing-file` | an on-demand file is absent for a module or pattern the corpus puts in scope. |
| `skill-too-long` | `SKILL.md` exceeds 150 lines. It is read on every invocation, so detail belongs in an on-demand file. |
| `skill-frontmatter` | the name is not `ai-native-dp-{role}`, or there is no description telling an agent when to load it. |
| `duplicates-skill` | an on-demand file repeats five or more consecutive substantial lines from `SKILL.md`, spending the context the split was meant to save. |
| `missing-decision` | a decision a module raises appears nowhere in the design skill, so it can never be put to a designer. |
| `missing-invariant` | an invariant a module or the master design declares is absent from the review skill. |
| `missing-conformance-rule` | a `TLM-*` or `VAL-*` rule a pattern defines is absent from the review skill. |
| `paraphrased-platform-sql` | no distinctive line of an implementation artifact survives verbatim in the build skill. |
| `access-discovery`, `access-trust-gate` | the access skill does not lead with product-first discovery, or does not mention the pre-use gate. |
| *(all `design_lint` rules)* | platform SQL leaked into the design skill. |

**Everything expected is read from the repository.** Module and pattern anchors from `design/`, decisions from the Decisions-to-settle tables, invariants from each module's Invariants section plus the master design's framework invariants, conformance rules from the patterns, platform artifacts from `implementation/{platform}/`. Add a module and the verifier expects it in the skills without being edited.

## How verbatim preservation is checked

The prompt says platform SQL must be preserved exactly, never compressed. Checking that by object name does not work: the names are themselves templated, so `CREATE TABLE {{ database }}.{{ entity }}_H` yields nothing to match on.

Instead each artifact is fingerprinted on its longest un-templated lines, and at least one must survive verbatim into the build skill. A compiler that rewrote the SQL in its own words fails; one that carried it across passes.

## What it cannot check

Worth being explicit, because a green result is easy to over-read:

- **Every claim traces to a repo source.** A skill can be structurally complete and still assert something the standards do not say.
- **The compression is good.** This verifies that nothing required was lost, not that what remains is well written, well routed, or usable.
- **The mappings are correct.** It sees that the build skill carries capability-to-binding and invariant-to-check mappings, not that they map the right things to each other.

Those stay a human read. The verifier's job is to make that read shorter by taking the mechanical part off it.
