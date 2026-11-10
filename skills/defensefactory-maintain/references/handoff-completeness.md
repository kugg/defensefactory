# Complete evidence and phase-specific assessment

For new v6 attempts, first follow [stage admission and capture](trial-controls.md). Use the guarded execution path and retained receipt dependencies; legacy helper success does not establish stage admission.

This revision applies only to new experiments. Keep ongoing and completed trials
on their frozen packages, inputs, receipts and native ticket state.

## Resolve the originating Git namespace

A product import can contain the same files without containing the snapshot's
Git history. A failed lookup in the product repository is not proof that the
reported ref cannot be recovered. Follow the ticket's source manifest, import
provenance and project resources to the original namespace. Do not guess a full
SHA, scan arbitrary home directories or change an immutable baseline.

`source-resolve` accepts either its existing single `repo`/`ref` input or a bounded
`repositories` array. Each entry has `id`, provisioned `repo` path, ticket/resource
`reference`, and optional namespace-relative `dependency_paths`. Example:

```json
{"ref":"reported-short-ref","repositories":[
  {"id":"product-import","repo":"/provided/product","reference":"ticket:product-mapping"},
  {"id":"original-snapshot","repo":"/provided/snapshot","reference":"ticket:import-source-manifest"}
]}
```

The helper checks only these supplied namespaces, retains every attempted
resolution and returns the verified full commit with its origin. Different
commit matches are ambiguous, never first-match wins. Missing objects stay
unavailable in the searched namespaces; fetching remains a separately authorized
and captured operation. Do not replace the declared trial subject with an
unrelated newer revision merely because it is easier to resolve.

## Source assessment is not deployment-wide disposition

Use `policy.assessment_scopes[case].purpose: source_assessment` for an authorized
bounded source investigation, with an actual scope `reference` and explicit
`trial_target` subjects. Complete supported-release/deployed-artifact inventory
is not required to investigate those subjects. Reported and comparison revisions
are background observations unless actually declared trial targets. Do not invent
an `unknown supported release` placeholder to make the gate hold.

The source-only gate reports `source_assessment_permitted` separately from
`repair_permitted` (always false here), `terminal_disposition_blockers`, deferred
lifecycle targets and background observations. Unknown required trial subjects
still block that source scope. Source-only evaluation can finish a nonactive source task with `stop_source`, retaining `lifecycle_disposition: deferred`. It cannot close/disqualify a
ticket; lifecycle disposition still needs its actual complete scope and evidence
for every required release/artifact. No unsupported target is silently dropped
from a lifecycle decision.

Use the [assessment resolution procedure](assessment-resolution.md) to route stage-specific blockers and prepare actionable owner alternatives. Keep real repair decisions in `packet.repair_decisions` as named `id`, `state`,
and actual authority/reference records. Unresolved trust/session/provisioning or
fairness requirements remain `repair_contract_blockers` and carry into assessment
readiness. Ask for those concrete decisions rather than demanding a production
inventory for a source-only candidate. Permission to assess never grants repair,
deployment or closure authority.

## Bundle the bytes needed to replay the evidence

`command-record` now retains its exact `specification.json` and copies frozen
evaluator inputs into the attempt's private evidence directory before launch.
Later workspace edits cannot silently replace those snapshots. Review/redact
sources, logs and specifications before sharing; use credential references rather
than secret values. Preserve failures as failures, with their actual subjects.

Use `bundle-prepare` with `{plan, destination}`. The plan contains `case`, `attempt`,
exact `subject` and explicit required `resources` (`id`, `path`, `kind`, optional
expected `sha256`). Kind `execution_receipt` causes automatic inclusion and checking
of its captured raw log, command specification and every declared evaluator file.
Legacy execution receipts need an explicit `specification_path` and exact matching
evaluator bytes. Never infer missing code from a hash or publish changed code as
the historical evaluator. Add all other required source retrieval manifests,
guidance, adapters, models and decision receipts as explicit resources too.

Preparation fails before writing the output archive if any mandatory dependency
is missing or changed. It creates a deterministic, private, no-overwrite archive
with `bundle-manifest.json` and returns an external `requirements` pointer. Retain
that pointer in the ticket with the archive identity; a bundle must not define
its own unchallenged completeness criteria. Only explicit plan resources and
captured execution dependencies are read; no repository/credential discovery or
native upload is performed by preparation.

After publication, freshly retrieve/download and run `bundle-verify` with
`{downloaded_file, requirements}`, or pass `bundle_requirements` to
`publication-verify`. These checks validate actual member bytes, target/attempt,
raw log/specification correspondence and evaluator sources. Archive links,
traversal, duplicate members, missing dependencies and changed bytes are rejected
without extracting to disk. A recomputed outer archive hash cannot hide a missing
or changed evaluator. The next worker maps retained paths into a new workspace,
retrieves exact source/dependencies from the declared resources and records any
replay as a new execution.

`publication-verify` reports `transport_verified`/`bytes_verified` independently
of `bundle_complete` and `evidence_handoff_ready`. Without declared requirements,
matching download bytes cannot produce complete-handoff readiness. Even a complete
bundle reports `stage_readiness: not_evaluated`; scope, authority, assessment and
verification obligations remain separate gates. Structural completeness is not
proof that an isolated sandbox replay or independent acceptance occurred.

When bundling both trial and reported/comparison executions, each
`execution_receipt` resource may declare its own exact `subject` object. Omission
means the bundle's trial subject. Use the complete captured subject (including
path/component fields), not just a matching commit. Historical evidence stays
explicitly historical; never edit an execution receipt to make its subject fit
the trial. Returned external requirements bind each execution separately.
