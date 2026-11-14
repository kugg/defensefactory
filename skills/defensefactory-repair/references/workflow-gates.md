# Workflow gates and resumable ticket state

These gates convert recurring prose qualifications into portable ticket receipts.
They do not authenticate connector identities or choose product policy. Save every
input/output under the registered evidence root, attach the selected receipt, and
read it back before a dependent stage.

## Assessment eligibility before repair

An active assessment does not itself admit source mutation. After the exact
counterexample is reproduced, the applicable contract is versioned, every repair
decision is resolved, and repair scope is authorized, run
`assess-eligibility-receipt`. Its receipt binds the exact repository/revision,
assessment, counterexample, contract version and authorization reference.

Every repair `stage-scope` must carry that retrieved receipt as
`eligibility_receipt`. Scope preparation calls `repair-admission` and refuses a
missing, changed or stale subject. Do not recreate a receipt after editing; return
to assessment and issue a new one from current evidence.

## Structured owner decisions

Use `decision-request` with one question, at least two option/consequence pairs,
the exact subject and blocking stage. Publish it while open. Use `decision-record`
only after the owner chooses; retain the decision reference, decider, time and
scope. `decision-gate` returns `blocked` until the matching receipt is supplied,
then `resume`. Ticket prose such as “decision needed” is context, not gate state.

## CodeIntel coverage

Index identity, source querying, SCIP coverage and a security conclusion are
different facts. After retaining the exact-subject index receipt and actual query
observations, run `codeintel-coverage`. It emits exactly one disposition:

- `coverage_available`: positive occurrences, successful scoped query, retained
  source reads, and no declared coverage warning;
- `coverage_zero_occurrence`: exact index but zero SCIP occurrences;
- `coverage_partial`: exact index with unknown/limited occurrences, source reads,
  query success or quality warnings;
- `coverage_unavailable`: no exact active index.

For a `required` handoff, include the coverage receipt and the same disposition.
Anything except `coverage_available` is “semantic coverage unsupported.” It never
silently satisfies a semantic claim and never unpublishes evidence by default.
`codeintel-coverage-gate` requires the operator to preserve either
`scope: semantic_required` (blocked) or `scope: non_semantic` (publish with an
explicit limitation and no semantic-claim credit).

## Guarded capture and publication

The guarded capture entrypoint is the selected package's absolute
`scripts/stage-exec.py`. Invoke it directly in one shell tool call. Aliases,
wrappers, compound shell commands and uncaptured producers remain unguarded because
the audit cannot observe their inner process. `handoff-audit.py` reports the exact
unguarded event and whether the observed prefix or finalized whole attempt is
ready. The foreground runner records final problems and reason in
`invocation-result.json`.

`handoff-publication-gate` blocks incomplete publication. An operator may attach a
structured `publish_incomplete_evidence` override to preserve a failed attempt,
but the resulting receipt keeps `handoff_ready` and
`whole_attempt_claim_permitted` false. Prefix bundles therefore need the same
explicit incomplete-evidence override; they cannot claim whole-attempt readiness
until the runner finalizes the trace.

## Fresh-process evaluator comparison

`scripts/independent-eval.py --spec SPEC.json --output NEW_DIRECTORY` runs one
primary and one independently named evaluator adapter using direct argv, separate
working directories, clean home directories, a minimal environment, no shell and
no supplied chat history. Both receive the same frozen subject and obligation
contract. The comparison receipt reports agreement/divergence per obligation and
retains both outputs. Divergence blocks acceptance.

This demonstrates fresh process context only. It is not a protected sandbox,
authenticated organizational independence, or proof that an adapter ignored
external state. State those limits rather than upgrading agreement to independent
acceptance.

## Stalled findings

Run `stalled-findings` over the current ticket inventory. An exact-subject intake
receipt without an assessment/eligibility receipt is reported as
`stalled_after_intake` with `required_stage: assess`. A finding is excluded only by
a structured current `finding_park` receipt naming the finding, subject, reason,
decider, time and durable reference. A label or remembered intention is not a park
receipt.

## Cross-component deployment bindings

Define `defensefactory/deployment-contract/v1` with portable alignment point IDs,
source names and one rule: `all_equal`, `all_present`, or `allowed_values`. The
project adapter supplies actual observations plus durable protected evidence
references and capture digests. `deployment-contract` emits satisfied/violated/unknown per point while
omitting observed values from the shareable receipt. Raw protected observations
remain at their evidence references.

A release admission now requires a satisfied exact-subject
`deployment_binding`. Unknown is not a pass; violated or unknown points must be
corrected/captured before rollout. The factory defines the receipt shape, not an
application's component names, secrets, config paths or deployment topology.
