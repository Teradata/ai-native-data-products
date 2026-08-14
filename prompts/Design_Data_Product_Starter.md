# AI-Native Data Product: Design Starter

For designing a new data product, platform-agnostic.

> Install this repository as the `ai-native-data-product` skill. The agent reads `SKILL.md`,
> routes itself to [`roles/design.md`](../roles/design.md), and works from there. The
> procedure lives in that file, not here: this starter only gives you the intake to fill in.

---

## How to use

Copy the block below, fill the intake, and paste it into a new conversation.

---

## Starter

You are collaborating with a data architect to **design** the `[PRODUCT_NAME]` data product
using the AI-Native Data Product standards. Follow `roles/design.md`.

We are producing a **platform-agnostic design**: entities in logical types, the capabilities
the product requires, and the invariants it must satisfy. No platform SQL at this stage, that
is the builder's job. Apply the standards first; customise only where the business demands
it, and record every deviation as a design decision.

### Intake

- **Business purpose:** [what problem this solves]
- **Primary consumers:** [agents, apps, analysts, APIs?]
- **Top use cases:** [3-5 concrete cases]
- **Composition:** [Data Asset · Traditional Data Product · AI-Native · an extension onto an
  existing Domain · or "recommend one" and the agent will pick from the use cases]
- **Data sources:** [source systems]
- **Approximate volumes:** [row counts / growth for the main entities]
- **Sensitivity:** [any PII / regulated data to flag as `[pii]`]

Ask me for anything you need. Drive one module at a time; don't dump the whole design at
once. Put every catalogued decision to me rather than choosing for me.
