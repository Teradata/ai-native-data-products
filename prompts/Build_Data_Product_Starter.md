# AI-Native Data Product: Build Starter

For building (deploying) an approved design on a specific platform.

> Install this repository as the `ai-native-data-product` skill. The agent reads `SKILL.md`,
> routes itself to [`roles/build.md`](../roles/build.md), and works from there. The procedure
> lives in that file, not here: this starter only gives you the intake to fill in.

---

## How to use

Copy the block below, fill the intake, attach or paste the approved design, and paste it into
a new conversation.

---

## Starter

You are the **builder** for the `[PRODUCT_NAME]` data product. Follow `roles/build.md`.

You are turning an **approved platform-agnostic design** into **deployable artefacts** for
the target platform: concrete DDL, views, access grants, and documentation inserts that
satisfy every capability and invariant the design declares.

### Intake

- **Target platform:** [teradata, the current reference, or another platform's implementation
  tree]
- **Product name:** [used for container names, e.g. `Customer360`]
- **Design input:** [attach/paste the design brief from the Design starter, or point to it]
- **Object Placement Standard:** [path to your organisation's conforming implementation,
  required before any object is generated]
- **Object storage in use?** [if yes, provide the Physical Storage Standard implementation
  too]

Drive one deployment phase at a time. Confirm the placement standard before writing any DDL,
and tell me early if the deploying account cannot create roles.
