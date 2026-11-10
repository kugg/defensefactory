# Defense Factory

Manually invoked skills for ticket-driven security remediation. The ticket holds
the current requirements, decisions, receipts and next action. Developers own
component claims and their controls under normal repository policy.

This is an **experimental, manually operated workflow**. It does not provide
enforced agent isolation, independent acceptance or demonstrated reliable
end-to-end autonomy. Human review is required. No scheduler, CI, branch
protection, credential store or production deployment is installed.

## Install for OpenCode

Use Python 3.12+ and an installed OpenCode executable. Git is needed for source
operations; the bundled synthetic evaluation also needs Go 1.22+. Project
toolchains and test environments come from the ticket.

```sh
git clone https://github.com/kugg/defensefactory.git
cd defensefactory
python3 scripts/install-factory.py
```

The installer asks for the preferred provisioned `provider/model`, Linear
project, complete Linear/CodeIntel MCP URLs, a separate optional indexing API URL,
credential environment-variable name/header, transport, GitHub repository hint, launcher
and local paths. It never asks for or stores credential values. Authenticate
providers and native MCP connections separately. An OTel wrapper/collector is an
optional host capability; selecting a wrapper does not provision telemetry.

The optional CodeIntel tools-only stdio bridge supports POST-only deployments;
direct remote transport is also available. Workspace keys normally use
`X-Api-Key`; an explicitly selected Authorization header uses Bearer. New native
entries are named `factory_linear` and `factory_codeintel`. See the
[transport and host API contract](skills/defensefactory/references/codeintel-host-api.md).

It copies a versioned release and creates skill links plus an external host
profile. Identical reinstallation is a no-op. Explicit `--update` backs up changed
settings and replaces only its own managed links; old releases remain. For an
existing manually installed or frozen factory, choose a separate directory ending
in `skills/` to preserve it. Global OpenCode JSON/JSONC is not rewritten.

Unattended setup accepts `--yes --model PROVIDER/MODEL --linear-project PROJECT`
and the options shown by `--help`. See the complete
[installation procedure](skills/defensefactory/references/installation.md).

## Start a manual trial

1. In a preparation conversation, load the relevant stage skill and fetch the
   live ticket. Prepare, publish and separately read back its narrow stage scope
   before any product checkout or execution. Create `stage-start`, attach the
   opening receipt to the ticket, and retrieve it. The operator reviews this
   bootstrap; do not describe it as unassisted worker preflight.
2. Start a fresh worker using the installed `scripts/opencode-trial.py`, supplying
   `--config`, `--opening`, `--prompt`, `--project`, a new `--destination`, and
   `--run`. It refuses to spawn without the opening, snapshots consumed inputs,
   requests the selected model with `--thinking`, and retains status/usage.
3. The worker fetches the ticket and opening afresh, verifies correspondence,
   then uses `scripts/stage-exec.py` for direct producers. Stop at the authorized
   boundary: a draft PR or a justified disposition is a useful trial outcome.
4. The runner writes a finalized postflight audit after exit. The manual operator
   publishes its qualification and final resource/readback checkpoint before the
   next stage relies on the worker's result. A live worker snapshot covers only
   its observed prefix.

Follow [manual kickoff and execution](skills/defensefactory/references/trial-controls.md).
Caller-supplied connector records are checked for correspondence and ordering;
the helpers do not authenticate those records or restrict arbitrary host tools.
A passing process or bundle check does not grant acceptance or closure.

See [where state and evidence live](skills/defensefactory/references/handoff-state.md)
for local working files, client caches, ticket attachments and transient context.
The new helpers save/replay comparison inputs and recipes, bind artifacts to actual
build receipts, assert child exits, and inventory every registered evidence file.
Archive verification closes non-execution dependencies as well as execution logs.
Unwrapped/compound shell commands remain visible as incomplete capture; no OS
sandbox prevents bypass.

Use the [supported verification paths](skills/defensefactory/references/supported-verification.md)
for baseline setup, admitted comparison subjects, frozen direct runtime probes,
local source export and actual CodeIntel evidence. Registered-trial CLI legacy
capture cannot substitute for stage admission. A successful helper test does
not demonstrate a fresh agent will follow these paths.

For partial source packages, use the [fixture/runtime/readback path](skills/defensefactory/references/fixture-runtime-handoff.md). It assembles approved archives offline, separates fixture subjects from product subjects, binds test selection to captured discovery, and checks required runtime probes from the published scope. Bundle preparation emits the exact machine requirements sidecar; paired native readback verifies both downloaded assets. `trial-status.py` recovers current invocation paths and measured timing after compaction; fetch the live ticket for current decisions.

## Stages

| Skill | Purpose |
| --- | --- |
| `defensefactory` | Route a manually invoked workflow using live ticket state. |
| `defensefactory-intake` | Register a finding with source, evidence and scope. |
| `defensefactory-assess` | Qualify, close/disqualify when justified, or bind active repair requirements. |
| `defensefactory-repair` | Construct a bounded remediation candidate. |
| `defensefactory-verify` | Evaluate security, legitimate behavior, architecture and required runtime obligations. |
| `defensefactory-integrate` | Check the actual merge subject and governing policy. |
| `defensefactory-deploy` | Build/roll out only within separately authorized scope. |
| `defensefactory-confirm` | Confirm the identified deployed artifact and configuration. |
| `defensefactory-maintain` | Perform an explicitly requested drift/variant maintenance pass. |

Each stage package contains its own helper modules and references. Project
models, build/deployment adapters and E2E plans are case resources, not universal
defaults. Host preferences supply discovery hints, not ticket state or authority.

## Claims and evidence

Keep one canonical claim catalog with its owning component (the repository root
can itself be the component). Claims name bug classes, preserved behavior and
hard/soft fences. Controls retain their introduction Git references across moves.
Computed hashes and execution verdicts belong in generated receipts. Developers
may amend claims under normal repository policy; this is not a security-team
veto mechanism. See [component claims](skills/defensefactory/references/component-claims.md).

Use CodeIntel against the exact indexed subject and report query/SCIP coverage
limits. When formal checks apply, separate bounded model results from actual
implementation conformance. Publish raw evidence and external bundle requirements
as shareable ticket resources, then retrieve both and verify. Reconcile all
executions, including failures, against the published inventory.

## Evaluate the helpers

```sh
python3 -m unittest discover -s tests -v
python3 skills/defensefactory/scripts/eval-fences.py --output /tmp/factory-eval-new
```

The evaluation runs disposable Git/Go fixtures for bypass, deny-all, missing
controls, claim amendments and component transfer. It makes no model, ticket or
service calls and refuses to overwrite previous output. This is a helper
regression evaluation, not proof that an agent follows the procedures. See
[evaluation scope](skills/defensefactory/references/evaluation.md) and
[lessons and limitations](LESSONS.md). See the [prepublication checks](VALIDATION.md)
for the tested scope and unresolved qualifications.

Export standalone stage archives with `python3 scripts/package-skills.py --output
/new/package-directory`. Every package includes the repository's MIT license.
