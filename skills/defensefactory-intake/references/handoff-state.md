# State, capture and replay across a handoff

A local file is not automatically ticket evidence. The next stage must be able
to recover the input bytes, operation, outcome and limitations through the
ticket's resource graph. Conversation memory and the producer's home directory
are not required inputs to that stage.

## What lives where

| Data | Local working copy | Durable handoff |
| --- | --- | --- |
| Canonical component claims and controls | Source checkout | Immutable repository/ref, control paths and introduction refs in the ticket |
| Exact source, toolchain/configuration and build inputs | Working checkout; project adapters | Pinned source references plus saved manifests/adapters and limitations |
| Producer execution | `evidence/CAPTURE/`: preparation, specification, raw output, timestamps, status, evaluator/context copies | Every capture, including failures and partial preparations, in the indexed attachment graph |
| Built/consumed binary | Sealed `artifacts/NAME/payload` and binding receipt | Payload, source observation, actual build receipt/spec/log and use binding |
| Connector response | Native client may cache it outside the case | Exact or explicitly redacted snapshot; original digest, selectors and dependencies |
| Comparison or review decision | Input copies plus comparison recipe/result; concise decision with evidence references | Same files, not only a Boolean or narrative conclusion |
| Invocation trace | Raw `agent.jsonl`, including private reasoning, stays private | Selected tool observations, cache snapshots, prefix identity and postflight audit; never private reasoning text |
| Credential or signed transfer URL | Provisioned environment/private native metadata | Credential reference/name only; fresh connector lookup for expiring access |

The ticket owns stage state, resource IDs, decisions and next action. Its
attachments carry machine-readable files. Disk copies are scratch/evidence
preparation; a receipt naming a local path alone is not a portable handoff.

## Layout and capture

The foreground runner supplies `DEFENSEFACTORY_EVIDENCE_ROOT` and
`DEFENSEFACTORY_EVENT_LOG`, plus separate `DEFENSEFACTORY_HANDOFF_ROOT` and
`DEFENSEFACTORY_PUBLICATION_ROOT`. Put all current producer evidence under the
evidence root. Frozen invocation inputs are copied there automatically.
`stage-exec.py` and `codeintel-api.py` enforce it when supplied. Keep working
checkouts/extracted historical inputs separately; copy selected frozen inputs
into current receipts. Preserve historical bundles as immutable input assets.
Do not scan a credential directory as an evidence root.

Use one direct helper command per shell tool call, with its canonical installed
script path. Avoid `cd && ...`, command aliases, pipes and status-printing shell
wrappers. The audit conservatively marks compound/unknown commands unreviewed;
it does not assume a wrapper mentioned somewhere captures every producer.
Native file editing and connector calls have separate saved tool observations.

```text
working/                     source and disposable project setup
invocation/evidence/          producer captures, input/decision files, artifact bindings
invocation/handoffs/g001/     frozen inventory, selected tool/cache snapshots, archive, requirements
private-capabilities/         native signed upload metadata, credentials excluded from sharing
invocation/publication/      transfer/readback/comparison receipts for the published assets
invocation/postflight/        final audit written by the runner AFTER the worker exits
```

## Save comparisons before relying on them

```sh
python3 /selected/skill/scripts/evidence-compare.py --id opening-bytes --left /case/expected.json --right /case/downloaded.json --output /case/evidence/opening-comparison
```

This snapshots both inputs, saves a recipe and outcome, and preserves mismatch
or invalid-input results. For JSON use `--mode json` and optional distinct JSON
Pointers `--left-pointer /publication/body --right-pointer /body`. To repeat it:

```sh
python3 /selected/skill/scripts/evidence-compare.py --replay /copied/comparison/comparison.json --output /new/replay
```

Input snapshots stay relative to the receipt for relocation. Bundle verification
also replays comparisons directly from archived bytes. A printed `True`, hash
list or model assertion alone is not a saved comparison. A console result may
exist in the private session log while its inputs/recipe remain outside the
ticket. Do not say that result was never on disk; identify the missing layer.

For an interpretation rather than file equality, save a concise decision,
specific supporting resource IDs/anchors, assumptions and uncertainty. Declare
`evidence_dependencies` with `name/path/sha256/bytes/kind` on machine records, or
use `saved_observation()` to snapshot supplied bytes and dependencies. Keep
private working memory out of evidence. No helper can observe every internal
comparison: without a saved result and inputs, the claim remains unsupported.

## Bind artifacts and test the actual child

Build with `stage-exec.py --source-repo /checkout --produces gateway=/new/binary`
and the selected exact subject. The helper checks Git HEAD/clean inputs before
and after, copies the output bytes, and binds them to the actual build receipt.
This is observed provenance, not a hermetic compiler proof; declare toolchain,
ignored inputs and external dependency limitations separately.

Consume with `--use-artifact gateway=/capture/artifacts/gateway/binding.json` and
the literal argument `{artifact:gateway}` (also usable in a Docker bind mount).
The helper expands that sealed payload path, verifies its bytes/source, checks
the actual argv uses it, and rejects a base/mutant binary labeled as a candidate.
Comparison/variant artifacts need their own admitted subject/declaration; do not
change the source label to satisfy the helper. Artifact hashes live in receipts.

On the receiving host, use `restore-artifact.py --bundle DOWNLOADED_ARCHIVE
--requirements DOWNLOADED_EXTERNAL_REQUIREMENTS --name ARTIFACT_NAME --output
NEW_EVIDENCE_DIRECTORY`. It verifies the archive, restores bytes and executable
mode, and writes `binding-reference.json` for `--use-artifact`. The reference
retains the immutable direct-build origin archive/requirements; old receipts are not rewritten
to invent a new build. Repeated handoffs flatten the reference back to that build
instead of continually nesting stage history. No original host paths are needed. Nested origin archives
are bounded; create a fresh direct artifact bundle when that bound is reached.

For refusal/success tests, freeze an assertions JSON list, for example
`[{"name":"root-refused","exit_code":2,"stdout_contains":["expected refusal"]}]`,
then pass `--assertions FILE`. This uses `process-assertions-v1` and checks the
actual producer exit and diagnostics. Expected nonzero can pass the assertion
while retaining the true child exit. Inline container `sh -c ...; echo $?`
cannot earn runtime assertion credit. Separate setup from the direct runtime
producer, or select and freeze a reviewed adapter. Adapter adequacy remains a
review obligation; formatting events cannot prove an arbitrary adapter honest.

## Freeze and publish a whole snapshot

Store ticket-derived `handoff-requirements.json` under the evidence root:

```json
{
  "scope_reference": "actual ticket contract/decision reference",
  "comparison_ids": ["opening-bytes"],
  "assertion_checks": {"runtime-refusal": ["root-refused"]},
  "artifact_subjects": {"gateway": {"repository": "selected repository", "revision": "full selected revision"}}
}
```

Select required checks from the real stage scope; empty inventories grant no
test coverage. Save a reason for obligations outside scope. Then run the actual
installed `handoff-audit.py` with `--requirements FILE --workspace WORKING_DIRECTORY
--output /outside-evidence/handoffs/g001 --bundle`. The runner's environment
supplies root/events/opening; other hosts must supply actual compatible records.

The helper inventories all registered files, retains native response caches,
flags unreviewed/missing captures and missing comparisons/assertions/artifacts,
and prepares both archive and external requirements. Dependency closure includes
non-execution records, not only test logs. Changed roots require a NEW generation.
Failed audits still preserve bytes; do not retry them until green or hide them.
Old subset bundles retain transport verification but cannot claim whole-handoff
readiness.

Publish archive and external requirements as distinct native resources. Use
`ticket-transfer.py --metadata NATIVE_RESPONSE.json --upload-file FILE --receipt
NEW.json`, then finalize the native attachment. For retrieval, use the refreshed
native attachment response with `--download-file NEW --expected-sha256 FULL_DIGEST`.
The helper reads exact native metadata; signed URLs/headers stay out of argv and
receipts. It preserves partial failures, performs no automatic retry/redirect,
and grants no publication authority. Keep signed metadata outside shared roots.
For OpenCode, `--metadata PRIVATE_EVENT_LOG --event-id ACTUAL_NATIVE_PART_ID`
extracts the completed native result directly; no model needs to retype the URL
or signed headers. Plain native JSON and single-text MCP envelopes are supported.
Verify downloaded bytes and transitive members; retain the comparisons/results.

`snapshot_handoff_ready` describes the observed prefix only. A still-running
worker cannot certify its later actions. The runner writes a **finalized**
postflight inventory after exit, covering producer, handoff and publication
directories. The manual operator publishes that audit and a
final checkpoint linking the assets/readback results before a dependent stage
claims whole-attempt readiness. Publication receipts are a separate final graph;
an archive cannot contain evidence of its own future publication. A false
postflight result qualifies the worker report without rewriting it.

These are same-host correspondence and replay checks, not authenticated event
logs, enforced isolation or independent acceptance. Undeclared roots, unknown
tool formats and private memory remain coverage limits. Review common automatic
redactions for project-specific secrets before sharing. Keep raw private traces
and credential capabilities local, with their limitations explicit.
