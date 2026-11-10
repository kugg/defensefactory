# Prepare a fixture, prove the runtime, hand off both files

Use this path when runtime guidance exists but the supplied helper is partial,
its sources differ from the candidate, or a prior worker exported only a subset.
Do not make a new user-approval blocker out of preparation already authorized by
the task. The helpers are same-host correspondence checks, not enforcement of
arbitrary tool use or independent acceptance.

## Recover current scope

After a continuation or compaction, run the actual stage package's
`scripts/trial-status.py`. It prints the current invocation paths, frozen scope,
required probes, canonical helper directory and measured elapsed time. Then fetch
current ticket resources and the latest approval/input checkpoints. A compaction
summary that repeats an older hold is historical context; the local status file
also does not establish the latest ticket state. Preserve earlier outcomes and
use new capture/download generations. Invocation elapsed time is not cumulative
attempt time; continuations must retain the original budget.

## Assemble an adequate, separate fixture

Before tests, inspect the guidance, actual entry points/imports, evaluator names,
configuration, toolchain and image requirements. A source-only selection is not
necessarily a buildable project. Missing dependencies may be recoverable from
approved public source; inspect that option before asking the owner to supply a
new private package. Preserve candidate and fixture identities separately.

Use `prepare-fixture.py --plan PLAN.json --output NEW_DIRECTORY` to assemble
already-approved local tar archives offline. The current opening comes from
`DEFENSEFACTORY_STAGE_OPENING` (or `--opening`). All input selection is explicit;
this helper performs no clone, download, image build, VM or container action.
Prepare Git archives and any source exports with guarded support commands first.
For example, the plan shape is:

```json
{
  "id": "local-call-fixture",
  "reference": "actual ticket fixture/input decision",
  "inputs": [
    {
      "id": "public-base",
      "path": "/case/inputs/base.tar",
      "sha256": "actual archive SHA-256",
      "reference": "repository and full source commit",
      "mappings": [{"from": "", "to": ""}]
    },
    {
      "id": "approved-overlay",
      "path": "/case/inputs/selected-helper.tar.gz",
      "sha256": "actual approved archive SHA-256",
      "reference": "native attachment ID and approval checkpoint",
      "mappings": [{"from": "integration", "to": ""}],
      "replace": ["path/of/explicitly/replaced/file"]
    }
  ],
  "required_paths": ["build-manifest", "adapter", "imported/dependency", "test-definition"]
}
```

Replace every illustrative value with discovered case inputs. Mappings select
subtrees, and `replace` lists exact existing file paths; undeclared/unused
replacements, path traversal, links/devices and empty selections are refused.
`required_paths` must cover the actual adapter/build/test prerequisites, not just
files already present. It is a declared adequacy check, not an automatic dependency
resolver. The helper retains input copies, plan, opening and a replayable manifest
on success, and failed preparation evidence on refusal. It refuses to overwrite.
Mappings filter the assembled tree, not the preserved input archives. The complete
input archive bytes become handoff dependencies; confirm their sharing scope and
inspect them before publication, even when only a subtree is mapped.

A successful result creates `tree/` and `fixture.json`. Capture offline fixture
checks with `stage-exec.py --support --fixture FIXTURE.json ... -- DIRECT_ARGV`,
with cwd inside that tree. Such receipts use a **fixture snapshot subject**,
not the candidate subject. Fixture files must remain unchanged during checks;
put caches/output/state outside the frozen tree (e.g. Python `-B`). Changed
fixtures need a new preparation generation. These checks cannot supply candidate
artifact production, comparison or runtime proof. Inspect fixtures for secrets
and project-specific network/ownership requirements before sharing or execution.

Image/tool absence is an observed readiness condition. Capture actual inventory,
then decide whether authorized preparation can resolve it within budget. Pin the
actual prepared image identities and retain build recipes/logs. Do not require the
user to provision images by default. Source assembly, image readiness and actual
call adequacy are separate. Additional private-source export, host changes or
real-provider calls still require their own applicable authority.

Keep a ticket direction table: required journey, synthetic-local versus external
legs, candidate/fixture identity, input prerequisites, checks actually run and
outcome. A mocked provider marker proves only that mock. Authorization for local
synthetic media/account journeys does not authorize real-provider or office
calls; a restriction on real calls does not prohibit the synthetic equivalents.
Continue independent candidate probes while a broader journey remains incomplete.

## Discover named tests before declaring them

For Go, freeze the actual evaluator file map, then use a guarded support command
with `--protocol go-list-json --evaluators MANIFEST -- go test -json -list . ./...`.
This captures discovery names; it grants **zero executed-test coverage**. Keep
build/discovery failures instead of guessing a plausible test name.

Run the selected tests with `--protocol go-test-json --discovered-tests
DISCOVERY_CAPTURE/execution.json --evaluators SAME_MANIFEST --required-test
PACKAGE::TestName ... -- go test -count=1 -json ...`. The helper rejects names not
observed by discovery, a different subject/evaluator inventory, or failed discovery
before launching the producer. Freeze new/changed evaluators and repeat discovery
in a new generation. Other frameworks need their actual discovery mechanism and
an explicit retained adapter; do not label a generic zero exit as named coverage.

## Require actual candidate runtime evidence

Before execution, publish a scope with `runtime_requirement` when runtime checks
are required:

```json
{
  "required": true,
  "reference": "governing ticket runtime requirements",
  "probes": [
    {"id": "refusal", "artifacts": ["program"], "assertions": ["refused"]},
    {"id": "legitimate", "artifacts": ["program"], "assertions": ["accepted"]}
  ]
}
```

These are obligation names, not a complete scope or runtime plan. Select meaningful
checks from the ticket. Add `comparison_id` for probes of an admitted comparison.
The audit derives required probe coverage directly from the published opening,
even if the worker omits its runtime plan or supplies empty handoff requirements.
A runtime plan must retain these artifact/assertion identities. Unit/fixture tests,
a dry-run or a printed exit cannot discharge them. Incomplete runtime obligations
can be exported, but do not earn whole-handoff readiness.

When a reviewed fixture supplies the runtime driver, freeze its driver/import
files with `--evaluators` and use the product runtime plan and sealed product
artifact. Do not use `--fixture` to relabel that runtime as a harness-only check.
Keep driver source identity and stubbed legs explicit; an artifact argument alone
does not prove the driver exercised it correctly.

Use [supported verification](supported-verification.md) for exact candidate and
comparison builds, `--source-repo`, `--produces`, `runtime-plan`, direct child
assertions and `--use-artifact`. Preserve the actual payload and build/use graph.
Test legitimate behavior and relevant changed/negative controls. Missing broad
call coverage is not evidence that a bounded candidate refusal probe is impossible.

## Export and retrieve the machine handoff

Save ticket-derived `evidence/handoff-requirements.json`, including actual CodeIntel
index-observation and native query event IDs, then run one canonical
`handoff-audit.py --workspace WORK --output NEW_HANDOFF_GENERATION --bundle`
command. The helper reads the registered requirements by default. Inspect the
returned readiness and problems; failed audits still preserve evidence.

It returns `bundle`, `external_requirements` and their identities. `bundle-prepare`
also always writes `ARCHIVE.requirements.json` and returns
`external_requirements_file` / `external_requirements_sha256`. Publish that exact
machine file separately from the archive. A prose summary, a hand-written JSON
requirements report, or the bundle's own internal manifest is not this file.

Use native attachment tools and `ticket-transfer.py` with actual native event IDs;
do not retype signed URLs/headers. Retain separate upload receipts and finalize
each native attachment. Fetch both attachment IDs again. With the two native
`get_attachment` part IDs, run:

```sh
python3 /actual/stage/scripts/verify-handoff.py --prepared /case/handoffs/g001/bundle-prepared.json --bundle-event ACTUAL_BUNDLE_PART_ID --requirements-event ACTUAL_REQUIREMENTS_PART_ID --output /case/publication/readback-g001
```

The helper reads the current private event stream, downloads distinct files from
native metadata, checks expected digests and exact machine requirements, verifies
transitive members and records the result. No retries, redirects or destination
reuse. HTTP/error bodies remain failed generations. Refresh native metadata and
choose a new directory for recovery. These receipts retain the exact downloaded
inputs and can replay from archived bytes. Signed capabilities and private
reasoning stay outside shareable roots.

The final parent postflight still qualifies the worker prefix. Bundle integrity,
whole-attempt handoff readiness and runtime acceptance are different results. An
observer supplement can preserve missing evidence without turning the original
worker failure into compliance. Publish the actual diagnostics, next operator
action, work not performed and measured times; preserve the old trial unchanged.
