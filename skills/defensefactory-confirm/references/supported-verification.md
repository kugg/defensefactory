# Supported setup, comparison and runtime paths

Use this procedure when a new verification experiment builds comparison artifacts,
runs runtime refusals, or must establish current CodeIntel coverage. It applies to
new packages/attempts; do not rewrite a frozen trial to satisfy it.

## Scope the real subjects first

The operator's `stage-scope` input can include:

```json
{
  "comparisons": [{
    "id": "control",
    "subject": {"repository": "selected repository", "revision": "full comparison commit"},
    "purpose": "Changed-control runtime comparison",
    "reference": "existing ticket scope/authorization"
  }],
  "codeintel_requirement": {
    "mode": "attempt_or_limitation",
    "reference": "governing exact-source verification requirement"
  }
}
```

These are fields in the existing scope input, not a complete invocation. They
become part of the published/read-back opening. Source approval comes from the
actual task/ticket; filling JSON does not create permission. If the source or
comparison set changes, publish a new opening before its commands. The invoker
and developers retain ordinary ownership of claims and policy.

Use `attempt_or_limitation` when the obligation is to try native discovery,
exact-subject index verification and scoped queries, while an honestly captured
unavailable or limited capability is an acceptable result. Use
`coverage_required` only when usable exact-source queries are themselves a gate;
it cannot be satisfied by a limitation. Use `not_required` only under an explicit
governing disposition. The legacy `required: true` form maps to strict
`coverage_required`; do not use it to mean “attempt required.” In the handoff
requirements, record `disposition: limited`, retained attempt event IDs and
nonempty `coverage_limitations` when tools exist but search/index/SCIP coverage
cannot support the claim. This qualifies the handoff record, not the missing
semantic coverage.

For baseline setup, `stage-exec.py --support --purpose ... -- DIRECT_ARGV` no
longer requires an unrelated mutation declaration. For a comparison build/use,
select `--comparison control`, then use the same `--source-repo --produces`
and `--use-artifact` paths as the candidate. This preserves the actual source
subject across build and runtime. Comparison IDs and challenge variants are
distinct; never relabel a base binary as a candidate or invent a variant merely
to get a command accepted.

Use the stage package path recorded in `opening.scope.package`. One direct
canonical helper invocation per tool call makes audit correspondence practical.
Run checkout/setup through it too; do not pipe producers into `tail`.

A helper refusal is a saved failure, not a reason to remove its binding:
`stage-exec` saves a new admission-failure receipt and requested assertions when
it can safely create a fresh output directory. Use a new directory for recovery.
Registered trial CLI calls to low-level `command-record` are rejected before
launch. Incomplete command criteria are rejected before side effects. Unknown
commands still appear in the audit; these helpers are not a sandbox and cannot
prevent arbitrary Python/host-tool bypass.

For partial source packages and paired publication, follow the executable
[fixture and handoff procedure](fixture-runtime-handoff.md). Fixtures retain a
distinct subject; scope-required runtime probes cannot be omitted from the audit.

## Prepare fixtures, then run the actual runtime producer

Do fixture generation, ownership/permission setup, image creation and readiness
as separately captured setup commands. Freeze project adapters and preserve their
bytes. For containers, a prepared bind mount/volume can supply configuration while
the runtime command directly executes the binary. Pin actual image identity in
the project recipe. Do not combine setup and the probe in `sh -c ...; echo $?`.
Do not delete `--assertions` after the inline shell guard rejects it.

Use `stage.py --describe runtime-plan`. Its input names the saved opening file,
ticket runtime reference and probes. Each probe specifies its ID, purpose,
artifact names, exact direct argv with `{artifact:NAME}` placeholders, and frozen
exit/diagnostic assertions. Add `comparison_id` when appropriate. For example,
the same sealed candidate can have one refusal probe and one legitimate probe.
A generic error needs discriminating positive/changed-control observations where
necessary; a recipe does not establish its own causal adequacy.

Create the declaration **before launching probes**, then:

```sh
python3 /selected/stage/scripts/stage-exec.py --opening OPENING --id PROBE_ID --cwd WORKING_DIRECTORY --output NEW_CAPTURE --runtime-plan DECLARATION --use-artifact NAME=BINDING
```

For an admitted comparison probe, also pass `--comparison ID`. The declaration
supplies argv and protocol; overrides/downgrades are refused. An expected exit 2
can satisfy a named assertion while retaining the actual producer status. Missing
artifact bindings, changed subjects, empty tests, timeouts and generic-command
substitutions cannot earn the declared runtime result.

`runtime-result` reads declaration/opening/execution **files**. Archive verification
checks the runtime context and actual specification; the whole inventory replays
declared probes. A preserved `--assertions` rejection followed by generic-command
fallback under the same check ID is flagged even without a runtime declaration.
These checks enforce correspondence within the helper path, not protected
acceptance or the honesty of an arbitrary project adapter.

## Retain exact local source objects

A generated mutant commit that exists only in a temporary clone is not a portable
source locator. `stage.py --describe source-export` accepts a local repository,
a safe name-to-full-commit map and a NEW output directory. Export selected
candidate/variant commits before handoff. The helper creates an isolated temporary
bare repository, fetches only those local objects into named refs, verifies the
bundle, and saves preparation, command outcomes and dependency receipts. It does
not alter the original checkout/refs or contact a remote.

Keep failed exports and partial bytes. Attach the export receipt and its bundle,
not just generator code or commit strings. New mutation declarations make the
inventory check for their variant source exports; explicit `source_revisions`
can add other required objects. The receiver can restore the exact refs from the
downloaded Git bundle after the original clone is gone. This preserves source
reproduction; it does not make a build hermetic.

## Make skipped CodeIntel work visible

New handoff inventories (schema 2) require `codeintel` in the ticket-derived
handoff requirements. Connection discovery is distinct from actual source work.

For a required obligation:

```json
{
  "codeintel": {
    "disposition": "required",
    "reference": "governing ticket requirement",
    "reason": "Current-source evidence needed for this claim",
    "index_observation": "/evidence/index-observation.json",
    "query_event_ids": ["actual native part ID from this invocation"],
    "repository_argument": "actual tool repository argument key",
    "repository_value": "actual repository ID/value",
    "ref_argument": "actual tool branch/ref argument key",
    "coverage_receipt": "/evidence/codeintel-coverage.json",
    "coverage_disposition": "coverage_available",
    "coverage_limitations": ["actual warnings and lexical/semantic limits"]
  }
}
```

Do not copy these placeholder argument keys/values blindly: inspect the deployed
native schema. Event IDs are `part.id` from the private invocation stream;
only selected tool observations enter the shareable evidence, never reasoning.
The gate checks actual current native query events, explicit repository/ref
arguments and errors (including full truncated-response caches). A list-repos
event alone is not a source query. Skipped work, query errors, stale/mismatched
index identity or an attempted switch from a scope-required obligation to
`not_needed` remain incomplete.

After the index observation and actual queries, run `codeintel-coverage` with
the retained occurrence count, query outcome, source-read count and warnings.
Bind its receipt and exact disposition in the handoff requirement. Zero
occurrences is `coverage_zero_occurrence`, not a pass or a claim violation.
Unavailable and partial coverage are also explicit. For any unsupported state,
run `codeintel-coverage-gate`: a `semantic_required` decision remains blocked;
an owner-declared `non_semantic` scope may publish the evidence with limitation
but receives no semantic-claim credit. See [workflow gates](workflow-gates.md).

Create `codeintel-index-observation` from a **saved raw status** plus explicit JSON
Pointers selecting its manifests/fields; the raw bytes become a dependency and
are replayed on receipt. `repository_pointer` (default `/body/id`) binds the
actual backend repository ID to the query arguments, so a matching commit/ref
in another index cannot qualify it. The explicit-active-flag form is supported. For deployed
status schemas with `currentIndexManifests`, use:

```json
{
  "manifest_pointer": "/body/currentIndexManifests",
  "activation": {
    "mode": "activated_current",
    "usable_pointer": "/body/activeIndexUsable"
  }
}
```

This profile derives activation from the actual current collection, usability,
READY status, activation timestamp and absent supersession/failure. It never
inserts a caller's guessed `active:true`. Job state and SCIP quality remain
unevaluated by this identity receipt; read them from the actual status before
index scheduling or semantic reliance. Other schemas need a retained adapter
or remain unsupported. Reconcile jobs, refs and shared connection policy under
the existing host integration procedure before scheduling another index.

An `unavailable` disposition needs reason/reference plus actual
`attempt_event_ids` or saved `api_observations`; absence of tool use is not a
service failure. A `not_needed` disposition needs the actual governing scoped
decision, not an explanation invented after skipping the task. Neither can
satisfy a published scope that requires the work. These are same-host supplied
policy records, not authenticated authority.

A successful readiness check means the required index/query evidence exists.
It does **not** establish complete semantic coverage: SCIP occurrences, warnings,
unsupported dispatch, source readability and per-query limits remain separate.
Exact manifest identity or READY alone is insufficient.

## Finish with the whole inventory

Keep recovered historical bundles/members in working input storage, outside the
current execution evidence root. Copy selected dependencies through comparison/
observation records. Otherwise an audit can mistake old execution receipts for
new uncorrelated work.

Use `handoff-audit.py --requirements FILE --output NEW_GENERATION --bundle`.
A selected subset can retain transport verification but cannot replace this
whole-inventory pass or the finalized parent postflight/operator checkpoint.
If a service rejects an upload size, retain that native error and use a bounded
transport split with ordered native resource IDs, per-part and whole hashes,
a saved reassembly operation and external requirements. Verify downloaded
reassembled bytes. Do not infer a universal attachment size from another account.

Keep technical failures, capture adherence, coverage and handoff readiness
separate. A later observer supplement preserves missing bytes; it does not turn
a worker's bypass into compliant execution. Fresh-agent adherence needs another
frozen experiment; helper regressions alone do not demonstrate autonomy.
