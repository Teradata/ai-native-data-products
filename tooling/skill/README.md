# tooling/skill: skill package verification

This repository **is** the agent skill. `SKILL.md` at the root routes an agent to one of the
four files in `roles/`, and each role file routes on into `design/`, `implementation/` and
`tooling/` as the task needs. Nothing is generated, so nothing can drift from the corpus.

That removes most of what the old compiler-era verifier checked. Compilation was judgement
work: an agent compressed the standards into four skills, two runs never agreed, and the
verifier existed to prove the compression had not quietly dropped or paraphrased a rule.
With no compression there is no loss to detect.

What remains worth gating is narrower and sharper.

## Run it

```bash
python tooling/skill/verify_skill.py
```

Exit code is `0` when the package conforms, `1` when it does not, and `2` when there is no
`SKILL.md` to check, so a missing skill is not mistaken for a pass.

```bash
python tooling/skill/verify_skill.py --root /path/to/checkout
```

## What it checks

| Rule | Fails when… |
|------|-------------|
| `skill-frontmatter` | the frontmatter block is absent or malformed, the name is not `ai-native-data-product`, or there is no description. |
| `skill-description` | the description is too short, or never names one of the four roles. The description is what decides whether the skill loads at all; a role it does not mention will under-trigger. |
| `too-long` | `SKILL.md` exceeds 120 lines, or a role file exceeds 150. These are the only context the package spends unconditionally: `SKILL.md` on every invocation, one role file per session. Everything else is read on demand and costs nothing until it is. |
| `role-missing` | a role named in `SKILL.md` has no file in `roles/`. |
| `dangling-route` | a backticked path in `SKILL.md` or a role file does not exist in the repository. |
| `dangling-section` | a `file.md §N` citation lands on a section that file does not have. |

## Why `dangling-route` is the one that earns its keep

The failure mode of a routed skill is a pointer to nothing. An agent told to read a file that
is not there either guesses or stops, and both look like a standards defect rather than a
packaging one.

The compiled packages shipped exactly this. `skills/review.zip` contained `SKILL.md` and
`checks/` and nothing else, while its `SKILL.md` instructed the agent to run
`tooling/validation/design_lint.py` against `design/`. Neither shipped. That was structural
rather than a bad run: a compiled skill is a *rendering* of the repository, so every pointer
back to the repository dangles by construction.

Reading the corpus directly removes the cause. This check makes sure a later edit does not
reintroduce it by moving or renaming a file the routing names.

Placeholders are expanded before checking, so `implementation/{platform}/modules/{module}/`
is tested against every platform and module the corpus defines. A path passes if at least one
expansion exists, because a route may legitimately cover an area that not every module
implements.

## Keep frontmatter values on one line

`SKILL.md`'s frontmatter is flat: `name` and `description`, one line each, however long the
description gets.

This is stricter than YAML, deliberately. `design_lint.parse_frontmatter` is a lenient
stdlib-only subset parser, and the installer uses a real YAML loader, so the two disagree
about reflowed values. Unindented, a wrapped line ends the scalar and the loader rejects the
whole block. Indented, the loader folds it correctly but the corpus tooling does not, and the
description is silently truncated everywhere the repo reads it.

Both forms are reported, because a value that survives one parser and not the other is worse
than one that fails both. This is not hypothetical: the first published `SKILL.md` had a
reflowed description, verified clean, and failed to install.

## What it cannot check

- **That the routing sends the agent somewhere useful.** A path can exist and still be the
  wrong file for the role.
- **That a role file's procedure is correct.** It verifies the pointers, not the advice.
- **That the corpus is well formed.** That is `tooling/validation/design_lint.py`, which is
  run separately and against `design/`, not against the skill.
- **That a real YAML loader accepts the frontmatter.** The rule above approximates one
  without taking a dependency; PyYAML is not in the standard library and this tool is
  stdlib-only, like the tools it sits beside.

The test suite includes a case asserting that this repository passes, so a corpus change that
breaks a route fails the build rather than reaching an agent.
