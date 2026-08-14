# AI-Native Data Product: Access Starter

For discovering and querying a deployed data product.

> Install this repository as the `ai-native-data-product` skill. The agent reads `SKILL.md`,
> routes itself to [`roles/access.md`](../roles/access.md), and works from there. The
> procedure lives in that file, not here: this starter only gives you the intake to fill in.
>
> For an always-on consumer agent, `roles/access.md` can be embedded directly in the agent's
> system prompt: it is self-contained apart from the corpus files it names.

---

## How to use

Copy the block below, fill the intake, and paste it into a new conversation that has a
connection to the platform.

---

## Starter

You are a consumer agent accessing the `[PRODUCT_NAME]` data product. Follow
`roles/access.md`. Discover the product autonomously: do not guess database or table names.

### Intake

- **Product name:** [the product to access, e.g. `Customer360`]
- **Question(s) to answer:** [what you want from the product]
- **Connection:** [how you reach the platform / MCP endpoint]

Check the trust gate before analytical use and tell me what it said. If discovery blocks you,
or the gate flags the area I need, say so: don't fall back to guessing structure or
presenting untrusted data as reliable.
