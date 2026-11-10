# Stage execution and verifiable challenges

Apply this procedure to new attempts only. Preserve earlier packages, prompts,
receipts and failures. The orchestration skill routes work; load the actual stage
skill and its stage/evidence references before executing the case. An existing
candidate challenged with new tests belongs in verification, not a new repair
or a replay of old assessment receipts.

For capture completeness and handoff, use [state, capture and replay](handoff-state.md).
The runner registers an evidence root and event log. Use one direct canonical
helper invocation per tool call, without shell aliases, compound commands or
truncating pipelines. The final postflight audit is separate from worker claims.


## Manual kickoff before a fresh worker

For a fresh foreground worker, the operator/preparation conversation opens the
stage first: read the live ticket, prepare/publish scope, retrieve the actual
native comment, run `stage-start`, then attach the opening JSON to the ticket.
Retrieve/download that receipt and pass it to `opencode-trial.py --opening FILE`.
The runner validates its correspondence to the selected package and refuses to
spawn the worker without it. It retains the receipt as a captured input. This
is a deliberate manual bootstrap, not an unassisted agent preflight pass.
Publication/readback objects are caller-supplied, so this is not authentication,
protected authority or restriction of arbitrary host tools outside the runner.

The fresh worker retrieves that opening from the ticket and checks it against
the captured copy, actual subject, authorization and installed stage package.
Continue using it if still applicable; do not claim operator actions as your own
or replace it merely to use a different performer label. Record the operator and
worker separately under the actual shared host identity. If the subject, scope,
actor or package changes, obtain a new published opening before case work. In an
interactive preparation conversation, do only the kickoff first; no checkout or
product execution is needed to publish the invoker's known exact subject.

## One command without retyping receipt plumbing

Use `scripts/stage-exec.py` for ordinary host producers, including checkout,
setup, builds, supplementary suites and cleanup. It computes bindings from the
saved opening and writes a new capture directory:

```sh
python3 /path/to/skill/scripts/stage-exec.py --opening /ticket/opening.json --id checkout --cwd /workspace --output /new/capture -- git clone REPOSITORY repo
```

With `--challenge PLAN --variant baseline` (or a declared variant ID), evaluation
uses the plan's frozen argv/protocol/evaluator; no argv after `--` is necessary.
For different setup/build/runtime commands, add `--variant ACTUAL_VARIANT_ID`
(explicit `baseline` for the original), `--support --purpose REASON` and
a direct argv. Use `--protocol factory-jsonl-v1 --required-test NAME` plus
`--evaluators FROZEN_RELATIVE_PATH_DIGEST_MAP.json` for a predeclared runtime
adapter. Explicit nonsecret build overrides use `--env KEY=VALUE`. Never pass
secrets in captured argv/environment. The wrapper returns the producer's failure
code; an inconclusive assertion result also exits nonzero. It cannot prove adapter
correctness: forward or persist every child producer's stdout/stderr, check its
exit code, and retain those bytes along with named assertions. A root refusal
must have the expected guard diagnostic and valid positive/changed-control legs;
a generic startup error is not evidence of security enforcement.

For container or binary probes, record the source revision of the artifact
actually executed, its build receipt and image/binary identity. Binding a command
to the baseline opening does not make a mutant image a baseline artifact. Keep
that provenance in the runtime adapter/resources and adjudicate it explicitly.
When all legs emit the same generic error, retain the error as an observation;
do not assign a missing-CA, configuration or dependency cause without a diagnostic
or discriminating test. Report locally verified tools separately from missing
tools in an image. Measure durations from invocation timestamps rather than the
agent's estimated elapsed time.

Use `--source-repo` / `--produces NAME=NEW_FILE` for build bindings and
`--use-artifact NAME=BINDING_JSON` with `{artifact:NAME}` in the runtime argv.
Use `--assertions FILE` for predeclared child exit/diagnostic criteria. A generic
command receipt does not establish refusal merely because a wrapper prints a
child status. See the linked procedure for archived replay and comparison files.

## Short startup and stop checklist

Before any case checkout, edit, fixture generation, build, test, runtime probe or
index request: read the ticket and required skill resources, resolve subject
metadata, then publish/read back the narrow stage scope and save `stage-start`.
Only prerequisite reads, package inspection and creating scope/receipt metadata
belong before that opening. Open a discovery scope first if more investigation
is needed; do not prepare mutants or run a sanity test while composing preflight.
Keep the actual connector readback object and retrieval timestamp; never copy the
expected body into fields labeled as a native readback. A later opening cannot
repair earlier ordering violations.

Use the following four outcomes in the final receipt, separately from technical
check results: (1) scope precedes case execution, (2) all case commands have guarded
capture or named omissions, (3) actual host indexing actions/errors retained,
(4) both archive and external requirements independently retrieved from ticket.
An unperformed item is incomplete or violated, never implied by a green helper.

## Open the stage through the ticket

1. Read the current ticket and referenced inputs. Load the stage's `SKILL.md`,
   `stage-contract.md`, `claim-evidence.md`, and the stage execution reference.
   Run `stage.py --describe stage-scope` for the short input shape.
2. Run `stage-scope` with the actual package path, performer, exact base subject,
   case/attempt, existing authorization reference and bounded scope. This reads
   and hashes those stage resources and returns `scope_body`. Publish that body
   to the ticket through the native connector **before case commands/effects**.
3. Fetch the new comment separately. `stage-start` takes the preparation plus
   actual publication/readback objects (`id`, `body`, `createdAt`; readback also
   has `operation: retrieval` and actual `retrieved_at`). It refuses changed
   bodies, wrong resources and invalid temporal order. Save its output as a
   new receipt. Never backdate a missing scope publication.
4. Use `stage-command` for bounded product commands in this trial. Bind the
   saved opening through `stage_start_reference` and `stage_start_sha256`
   (canonical JSON identity, obtainable with `evidence-record`). Every command
   has direct `argv`, canonical absolute `cwd`/evaluator paths, timeout,
   actual subject, performer and declared output protocol. The helper validates
   these bindings **before spawning**. It snapshots the opening/declaration,
   exact command, evaluators and raw producer output. Use a new evidence
   directory per execution, including recovery and fixture changes.

Use native tool readbacks, not self-authored approvals. The helper cannot
authenticate a caller-supplied connector object, prove that a model comprehended
a skill, restrict arbitrary host tools, or establish independent acceptance.
Those remain declared demo qualifications. Bypassing it is a recorded protocol
failure, not a later opportunity to manufacture compliant execution receipts.

`command-record` remains the low-level capture primitive for legacy/adapters;
its success alone is not v6 stage admission. Existing `verify`/`challenge` engines
remain bounded clean-source evaluators; a standalone engine result cannot replace
the ticket opening, durable execution dependencies and published handoff.

Do not run a producer through `tail`, `head` or a formatter and report the
formatter's exit code. `stage-command` refuses shell `-c` wrappers. A needed
project script is an explicit reviewed/frozen adapter, and must propagate each
producer's status. Python scripts and other adapters can also hide failures;
the helper does not prove arbitrary adapter correctness. Use supported named
output parsing instead of rewriting Go JSON parsers that mistake package events
for test events. An empty required inventory or skip cannot pass.

## Declare mutations before executing the baseline

Use `mutation-plan` with an exact `baseline_subject` copied WHOLE from
`opening.scope.subject` (including repository and every binding key), direct `argv`, named
`execution` protocol, `evaluators` as relative-path/digest map, separate `controls`
paths and explicit `variants`. Each variant has `id`, exact derived `subject`
(commit or parent revision plus patch digest), `kind` (`security` or
`legitimate_behavior`) and a nonempty `expected_failures` test-name list drawn
from the frozen required inventory. There is no security-only global rule that
can accidentally exclude deny-all detection. Keep implementation out of the
evaluator manifest. Developers still own and edit canonical claims; hashes here
identify the executed receipts, not an external claims-approval mechanism.

Pass the saved declaration as `challenge` to `stage-command`, and bind its whole
receipt with `challenge_plan_reference`/`challenge_plan_sha256`. Baseline and
variants must use identical command/protocol and logical evaluator identities.
Their actual workspace paths may differ; use the corresponding canonical file
paths. A later fixture/evaluator/criterion change needs a new declaration and
new baseline; preserve all old attempts.

Run `mutation-result` on the declaration, variant ID and actual captured baseline
and mutant receipts. It requires a green baseline, an unchanged evaluator,
execution after declaration, all required terminal assertions, and a failure
among that variant's intended tests. Compile/startup errors, wrong subjects,
hash mismatches, skipped/empty output and unrelated failures are inconclusive,
never successful detection. A positive test must catch deny-all. The predicate
and causal attribution still need review; the helper does not prove test adequacy.

For declared mutant setup/build/runtime commands that differ from the mutation
evaluator, still use `stage-command` with the saved `challenge` declaration,
`challenge_plan_reference`/`challenge_plan_sha256`, `challenge_role: support`, and
an explicit `purpose`. This permits only subjects in the declaration and retains
both contexts. Use command-format capture for builds/setup, or a frozen named
probe adapter for runtime assertions. Support receipts never earn mutation-test
detection credit. The default `evaluation` role still enforces the exact declared
command/protocol/evaluator. Supplementary suites on the baseline also use
`stage-command`; do not fall back to unbound `command-record`. If a helper rejects
a legitimate command, preserve that failure and report the specific limitation
before selecting a documented supported path; do not bypass it silently.

For runtime refusal, freeze the adapter and its expected observations BEFORE
launching the probe, then have that adapter emit named assertions during execution.
Retain the adapter bytes in the execution evaluator manifest. `probe-assert` run
after inspecting raw observations is post-processing, not predeclared runtime
verification. A generic error is insufficient: include a valid positive
fixture and a changed-control comparison where needed. Check actual identities,
input ownership and executable permissions. Network isolation and environment
scope come from the case. Do not bake any application's config or container
profile into these skills. Pin build inputs, retain image/artifact identities,
and keep each fixture version/failure in a separate directory.

## Exact CodeIntel subject before semantic reliance

Read the [host integration contract](codeintel-host-api.md) for transport/auth and
version-specific workspace routes. Use configured/documented clients before
guessing HTTP paths. Native MCP availability alone does not imply API absence.

Scope every repository query explicitly. Recover the actual indexing capability
from the host; requesting a ref is work for the factory, not a new owner decision.
Do not settle for the base index merely because the candidate is absent locally.

- Inspect repository status/job and branch policy first. Reconcile an active job
  before requesting another (a second request can return 409).
- Expose the exact commit via a branch/tag selected by that connection's policy,
  and ensure its managed/shallow Git checkout contains that ref. Check other repos
  sharing the connection before a policy change. Prefer an isolated connection or
  mapping when shared policy cannot be changed within authorized scope. Preserve
  stores, old trials and indexes; do not silently replace their targets.
- Request indexing by the selected ref, poll within the declared budget, and
  retain request/status/error receipts. `?ref=<SHA>` alone may not pin the planner.
- `codeintel-index-subject` checks the explicit repository request scope plus full
  active manifest branch/commit identity. Feed actual status entries normalized
  by the host adapter, preserving original response bytes. `active: true` must
  reflect current active status, not be invented from READY. Match a full commit;
  query that branch explicitly afterward and retain revision/locations/warnings.
- Separately inspect SCIP occurrences, quality issues, source reads and the
  query-specific coverage. Scope-only zero counters do not prove an empty index.
  A known base caller inventory plus a diff is a bounded inference, never complete
  candidate semantic coverage. If indexing remains unavailable after a bounded
  investigation, report that limitation and continue independent local checks.

If MCP exposes no indexing tool, inspect the configured service's host API or
its provisioned client/help. Retain actual status/branch-policy requests, errors,
ref availability and any bounded index request/poll. Failure to discover that
capability is a factory gap; a failed candidate query alone does not prove the
backend cannot index. Do not populate `job_active`, policy or checkout-absence
claims from assumptions. Stop after the declared investigation budget, report
what was actually attempted, and continue independent checks without semantic
coverage credit.

The helper performs identity checks only; no generic script changes connection
policies, launches index jobs or assumes a particular CodeIntel API version.

## Complete the handoff, not just the upload

Use `bundle-prepare` rather than hand-written `tar`. Declare every required
execution and failure/fixture diagnostic as explicit resources. A captured
`execution_receipt` automatically brings its raw log, exact specification,
evaluator bytes, stage opening and mutation declaration. Mixed baseline/candidate/
mutant executions require their exact `resource.subject`; never relabel them.
Finished failed/inconclusive runs are `execution_receipt` resources too. Do not
relabel them as diagnostics: that drops their transitive logs, specifications and
adapters from verification. Reconcile the finished captures under this attempt
against the declared execution inventory before upload; a complete chosen subset
is not preservation of every failure. Incomplete startup/preparation records are
retained as diagnostics, not claimed finished executions. Missing logs remain missing even if later commands pass.

Save `bundle-prepare.requirements` as its own JSON resource before publication.
Attach the bundle **and that external requirements resource**; keep two distinct
native resource IDs. Fetch and download both through the ticket, and run
`bundle-verify` using the downloaded requirements file, not the local preparation
object. Retain both native readbacks, byte identities and actual verifier output.
Finish this in the worker attempt before claiming ticket-only handoff. If either
publication/download fails, record the failure and incomplete handoff; do not
leave it for an observer to reconstruct or backdate the missing resource. Check `bundle_complete` and
`evidence_handoff_ready`, not only a hash match or a process exit. A directory-only
or manifest-free legacy archive is retained as partial evidence; do not rewrite
it into an allegedly original compliant receipt. Stage readiness, semantic
coverage and lifecycle acceptance stay separate from structural completeness.

## Next foreground runner

The bundled `scripts/opencode-trial.py` prepares a new private invocation using
explicit prompt/project/skills/destination paths. `--run` starts one fresh
`opencode-otel run --auto --format json --thinking --model MODEL` after installed
skill links and captured package identities match. Select an explicitly provisioned
model with `--model` or `OPENCODE_MODEL`;
there is no bundled model/provider default. Supply `--launcher`/`OPENCODE_OTEL`
or install the optional `opencode-otel` wrapper on PATH. The wrapper and its
OTel collector configuration are host capabilities, not included services.
No credentials are embedded or skill installation performed. This
runner does not resume/retry/reset tickets. It retains actual producer/runner
status, errors, raw reasoning events and usage. A zero process status is never
factory acceptance. Verify actual provider/model from session/OTel events. If
reasoning events are absent, preserve an explicit private session export rather
than claiming the provider produced none. Review/redact before sharing logs.
