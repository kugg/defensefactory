# Finish the selected task; defer only the work that depends on missing facts

Use this procedure for nonactive source findings, proposed holds, or impact claims
inherited from a reporter. Keep applicability, assessment completeness, repair
readiness, verification and lifecycle disposition separate.

## Bounded source completion

In an invoker-authorized `source_assessment`, an assessor may establish removal or
an already-fixed condition at the exact selected trial subject. That completes
the bounded task without attesting to every supported release or deployment.
`assess-eligibility` returns `disposition: stop_source`,
`source_assessment_complete: true`, and the per-target reasons. It does not grant
repair or lifecycle authority. Publish/read back the result and stop; do not turn
deferred lifecycle inventory into an assessment hold or ask for unrelated E2E
guidance for a component absent from the selected subject.

For removal, provide the existing per-target `git:{repo,before,after,path}` and a
hashed `applicability_observation` from the actual authorized assessor:

```json
{
  "kind":"applicability_observation", "target":"trial",
  "subject":{"revision":"FULL_CURRENT_COMMIT"},
  "performed_by":"ACTUAL_ASSESSOR", "reason":"removed",
  "rationale":"Original component is absent; bounded successor analysis below.",
  "source_reference":"captured-component-inspect-receipt",
  "replacement_review":{
    "revision":"FULL_CURRENT_COMMIT", "reference":"bounded-source-search-receipt",
    "searched_roots":["."],
    "rationale":"Explain entrypoints, renames, successors and deployment references inspected in this tree."
  }
}
```

`evidence-record` wraps the actual `{id,record}` in its canonical hash; it does
not author the analysis or attest to authority. `component-inspect` still checks
immutable Git objects, including renamed/copied blobs. A failed read/search is
not absence. Meaningfully changed successors require substantive review, not
just a successful helper call. For `already_fixed`, source/fix analysis and all
required security/positive/regression execution evidence remain mandatory.
Retirement still needs an actual owner/support-policy decision.

Unknown mandatory source targets hold. Mixed scopes retain each reason and
continue only the active subjects. Whole-ticket close/disqualify still requires
complete declared lifecycle scope, actual review bindings and authorized native
transition/readback. No new review actor or security-team approval is introduced.

## Before declaring a hold

Identify the exact decision that prevents the next action. A product behavior,
trust anchor, interoperability requirement, or conflict between declared
requirements may block repair. A missing fixture, semantic index, live runtime,
or lifecycle inventory usually blocks a narrower evidence or later-stage claim.
Missing facts can still block source understanding; explain the dependency rather
than treating every missing capability as either mandatory or irrelevant.

Before `assess-decisions`, retrieve the current ticket and persist a complete
authority review of its description, status, comments, documents, attachments
and relations. Mark a surface `empty` only when the connector confirms it; a
truncated or unavailable surface is not complete. Extract applicable owner
directions as authority records with a stable decision ID, exact reference,
owner, timestamp, retained directive and effect (`resolves`, `constrains`,
`authorizes` or `context_only`). When an owner changes a decision, retain both
records and identify the exact prior record in `supersedes`; unresolved
conflicting resolutions are rejected. Older receipts remain evidence, but a
newer opening does not erase a still-current owner decision.

Run `assess-decisions` with `{stage,authority_review,decisions}`. Each decision
carries `id`, `state`, `reference`, `blocks_stages`, actual `owner`, one concrete
`question`, and at least two `alternatives` with `choice` and `consequence`. A
resolved choice needs its actual `decision_reference`, retained `choice` and any
applied constraint references. An unresolved question must record
`no_applicable_resolution` and explain why the complete review does not answer
it. The helper refuses to reopen a decision whose reviewed owner record already
resolves the same ID, and refuses to omit a current constraint. It routes
explicit dependencies; it cannot judge whether prose was mapped to the correct
stable decision ID, prove a choice is necessary or authorize the answer.
Unresolved legacy repair decisions default to blocking repair, so old contracts
are not weakened. Only repair-stage blockers flow into repair-contract readiness;
later blockers remain visible in `deferred_decisions`.

Do independent work before stopping: source map, bounded tests, concrete options,
recommended choice with rationale where supportable, and planned success/failure
checks. Ask the owner only for non-inferable product decisions. A direction that
names the governing system, safety criterion or selected alternative is a
decision; do not downgrade it into context and ask the owner to choose again. A
direction that assigns routine design work to the factory is not a request for
the owner to design the implementation. Use existing developer-owned requirements
to select routine implementation details; do not invent an external security
approval requirement. Reuse an actual shared owner decision across related
tickets by reference, without fabricating or rewriting it.

An accepted design residual is not automatically a defect. Explain which
requirement the code violates, or record a policy/risk question rather than
labeling the residual a demonstrated security failure. Do not silently accept
risk or invent new requirements to close a ticket.

## Review the reporter's causal chain

Preserve the original assertion separately from the assessment. For each claimed
effect record its originating `report_reference`, assessed statement, `effect`,
assessment (`reporter_only`, `source_supported`, `observed`, `conditional`,
`unsupported`, `unresolved`), and direct support or rationale. `depends_on` names
other assertion IDs for conditional chains. Match the exposure graph's sensitive
edges to these assessed conclusions, including uncertainty and prerequisites.

`assess-impact` accepts `{assertions}`; `assess` also requires
`finding.impact_assertions`. Evidence entries bind `reference`, `assertion_id`,
`effect` and `basis` (`source` or `execution`). Supported effects need direct,
same-effect evidence; observations need execution evidence. Conditional/rejected
effects need a rationale and cannot support a confirmed escalation. Cycles are
rejected. The helper checks correspondence, not the semantics of arbitrary text;
review whether the referenced evidence actually establishes the stated effect.

A process crash does not establish code execution. Root execution increases the
potential consequence of a separately exploitable flaw; it is not a privilege
escalation primitive for an attacker already requiring root. A challenge/response
exchange does not establish recovery of the plaintext password. More generally,
each new effect or attacker capability needs evidence or an explicit assumption.

## Cheap input discovery and usage evidence

Run `stage.py --describe OPERATION` for small examples of `assess-observe`,
`assess-eligibility`, `evidence-record`, `assess-decisions`, `assess-impact`,
`command-record`, `bundle-prepare`, `publication-verify`, or `session-usage`.
This prints an example without execution or a receipt. Replace placeholders
with recovered facts; templates cannot supply authorization. Use `format: command`
with a reason/success criterion for source inspections and installations; do not
mislabel them as named tests. Prefer these examples to reading entire modules.

Check native CodeIntel tool exposure once per new session. Availability in another
conversation is not proof of availability here. Use the repository identity
returned by discovery and the managed source mapping, not a guessed short name or
arbitrary checkout. Preserve returned revision/scope/coverage and raw failures.
If native tools are absent, record that limitation and a concrete host action;
continue independent source work unless the missing evidence is required for the
specific next claim. Do not relabel REST/bridge fallback as native MCP or keep
retrying a stable configuration failure. This package cannot attach tools to the
host's registry or fix a server's managed-storage policy.

An index may expose a named branch alias even when querying its raw commit SHA
is rejected. Resolve the service's indexed ref and verify its full commit before
scoping queries; do not change the desired subject to make a query succeed.
A scope-only status response with zero matched terms does not prove an empty
index. Preserve source-slice, storage, search and graph-layer failures separately
from successful discovery and revision binding.

The operator can run `session-usage` with `{path,session_id}` on a captured
OpenCode JSONL log after an invocation finishes. It counts unique finish events
for that session only and reports provider counters separately from verified
billing. A reported cost of zero is not a verified free run. Do not sum
overlapping reasoning/output/cache fields into a fabricated charged total. The
worker may lack its own log path; the operator can publish a later supplemental
receipt without modifying the original stage evidence.

Fresh context applies between trials. A single agent may retain context across
stages within one attempt. Recover case state from the ticket, and do not infer
conversation continuity from the ticket's historical receipts.
