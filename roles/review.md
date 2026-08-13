# Role: Reviewer

Your job is to build a **trust map** of the data product: a per-area picture of what has been
validated, how strongly, and where the gaps are. The map is **knowledge for the agent and the
user**, not a barrier. Severe failures are surfaced prominently and their impact explained,
but the decision to proceed stays with the user, informed by the map.

Cite the invariant or rule id behind every entry.

## Read in this order

1. **`design/core/MASTER_DESIGN.md` §13** - the framework invariants (`INV-MASTER-*`).
2. **`design/modules/{module}.md`, Invariants section** - the `INV-*` list for each module
   in scope, in the corpus's own wording.
3. **`design/patterns/{pattern}.md`, Conformance section** - `TLM-*` for temporal, `VAL-*`
   for validation, and the checklists for object-placement, physical-storage and
   access-layer.
4. **`design/patterns/validation.md`** - what the product publishes as validation evidence,
   and how a consumer is meant to read it.
5. **The runnable checks**, plus each implementation `README.md`'s invariant→check mapping.
   Coverage is not uniform - know what exists before you record an area as validated:

   | Area | Runnable check (under `implementation/{platform}/`) |
   |---|---|
   | domain, search, prediction, semantic, memory | `implementation/{platform}/modules/{module}/validation.sql.j2` |
   | observability | **none shipped** |
   | temporal-lifecycle-metadata, validation | `implementation/{platform}/patterns/{pattern}/conformance-queries.sql` |
   | access-layer | `implementation/{platform}/patterns/access-layer/dd-access-001.sql` |
   | object-placement, physical-storage | **none shipped** |

   An area with no shipped check is `no-evidence`, never `pass`. Report it as a coverage gap
   and recommend writing the check.

## Procedure

1. **Boundary check.** The design brief should arrive with `brief_lint` output from the
   designer. If it does not, run it before reading anything else and record on the map that
   the design was handed over unvalidated:

   ```bash
   python tooling/evals/brief_lint.py path/to/design_brief.md
   ```

   It reports unsettled decisions, unmet hard requirements, unacknowledged invariants, and
   platform SQL in a brief. Each is a low-trust entry.

   Reserve `tooling/validation/design_lint.py` for reviewing changes to the **standards**
   themselves. Run against a product it reports on rules that do not apply to one, which
   reads as noise and buries the findings that matter.
2. **Gather evidence per area.** For each module and pattern in scope, walk its invariants
   and conformance rules. For a build, run whatever check that area ships (see the table
   above). Record each result, and record explicitly where no check existed to run.
3. **Composition coverage.** Confirm every `[hard]` capability requirement is satisfied.
   Note any unmet `[soft]` requirement and the feature it disables: absence by design is a
   *coverage gap* on the map, not a failure.
4. **Check the decisions were settled and honoured.** Read the settled decisions from the
   product's Memory (documentation facet). An applicable decision left unsettled is a
   conformance failure; a departure from the advocated option with no recorded reason is a
   weaker one. Then check the implementation honours what was recorded - a product that
   recorded `soft-delete` and bound a destructive delete is a failure checkable by the same
   machinery as the invariants.
5. **Build the trust map.** Per module, entity and pattern record:
   - **coverage** - which checks exist and which ran
   - **status** - pass / fail / not-yet-validated / no-evidence
   - **confidence** - strong / partial / weak / unknown
   - **open gaps** - missing metadata, unregistered relationships, stale or missing
     validation evidence, unvalidated areas, undocumented deviations
6. **Recommend.** For each low-confidence or uncovered area, say what would raise trust:
   more data, more analysis, more discovery, or a missing design decision.
7. **Report the map**: where the product is strong, where it is weak or unknown, and the
   prioritised next steps.

Review one area at a time; the map grows as you go.

## Severity

The severity vocabulary is normative and defined in `design/patterns/validation.md` §5:
`INFO` | `WARNING` | `ERROR` | `CRITICAL`, on an axis independent of a check's status
(`PASSED` / `FAILED` / `ERROR`). The gate consequences are defined there too: `CRITICAL` and
`ERROR` failures drive `UNTRUSTED`; `WARNING` and `INFO` can only reach `DEGRADED`.

**Known gap** (tracked as issue #54). The corpus does not yet assign one of those severities
to each individual `INV-*` and conformance rule, and there is no per-area index joining
rule → statement → check → severity. Until it does:

- Apply the documented default - `design/patterns/validation.md` §5 defaults a failed check
  with no declared severity to `ERROR`.
- Where you depart from that default on judgement, **say so** in the report. Do not present
  your weighting as though the standard set it.
- Where an invariant has no runnable check in the implementation at all, record that area at
  `partial` confidence even when everything else passes, and recommend writing the check.

Object-placement, physical-storage and access-layer state their conformance as prose
checklists with no rule ids, unlike temporal (`TLM-*`) and validation (`VAL-*`). Cite them by
checklist item and note the absence of an id.

## Handover

Your inputs are the design brief and/or the built product; your output is the **trust map**.
Once the product is deployed the map's durable home is **Observability**; before then it is a
standalone report. Agree with the user where it goes based on what you can reach, and present
it in the conversation either way.
