# Defense Factory

Manually invoked skills for ticket-driven security remediation. The ticket holds
the current requirements, decisions, receipts and next action. Developers own
component claims and their controls under normal repository policy.

This is an **experimental, manually operated workflow**. It does not provide
enforced agent isolation, independent acceptance or demonstrated reliable
end-to-end autonomy. Human review is required. No scheduler, CI, branch
protection, credential store or production deployment is installed.

## Qualify and install for OpenCode

Use Python 3.10+ and an installed OpenCode executable. Git is needed for source
operations; the bundled synthetic evaluation also needs Go 1.22+. Project
toolchains and test environments come from the ticket.

```sh
git clone https://github.com/kugg/defensefactory.git
cd defensefactory
./scripts/install-defensefactory --check
./scripts/install-defensefactory --plan --installation-id my-practice
./scripts/install-defensefactory --install --installation-id my-practice
```

This environment-aware installer is the supported onboarding entry point. The
first command is read-only host discovery. Plan mode asks separately where safe
practice may run and where production use is intended, but changes nothing.
Install mode refuses missing mandatory capabilities, writes a versioned nonsecret
profile and immutable release, and preserves unrelated OpenCode configuration.
Use `--answers skills/defensefactory/references/environment-profile.example.json
--noninteractive` after replacing every placeholder for deterministic setup.

The installer distinguishes mandatory contracts from recommended/replaceable
confidence services. It asks for the preferred model, Linear project,
CodeIntel or an exact-revision equivalent, OTel settings, private evidence path,
practice isolation and a separately reviewed production plan. TLA+/TLC,
CodeIntel, Python, container runtimes and other product names are capabilities,
not universal policy: missing optional layers report the confidence lost. The
small shell bootstrap explains the Python requirement; an equivalent installer
may satisfy the same documented contract.

It never asks for or stores credential values. Use `env:NAME`, `op://…` or
`keychain://…` references. Authenticate providers and native connections
separately. Practice defaults prohibit production credentials and real provider
calls. Supplying a production target records intent only; installation grants no
merge, deploy, lifecycle or production authority.

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

The legacy `scripts/install-factory.py` remains a bounded runtime-profile helper;
new users should use `install-defensefactory`. Evaluate an installed profile with
`--evaluate --installation-id ID`, resume an interrupted post-install evaluation
with `--resume ID`, inspect it with `--report`, and retire only installer-owned
links/settings with `--uninstall-profile`. Evidence, receipts and immutable
release bytes are preserved. A live practice evaluation additionally requires an
explicit prompt, project, ticket-backed opening and new destination.

See the complete
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

Keep one concise component-owned `RULES.md` as the sole authored claim and
boundary source (the repository root can itself be the component). It references
developer-owned invariant contracts implemented with the repository's useful
tests, types, CUE, CodeQL, Semgrep/OpenGrep, AST analyzers, runtime assertions or
formal tools. Checker output is a candidate until separately evaluated. Claim
state depends on declared coverage, not finding count. Controls retain their
introduction Git references across moves; computed hashes and execution verdicts
belong in receipts. Developers amend rules and contracts under normal repository
policy. Legacy `claims.json` is only a migration input. See [component claims and
contracts](skills/defensefactory/references/component-claims.md).

Use CodeIntel against the exact indexed subject and report query/SCIP coverage
limits. When formal checks apply, separate bounded model results from actual
implementation conformance. Publish raw evidence and external bundle requirements
as shareable ticket resources, then retrieve both and verify. Reconcile all
executions, including failures, against the published inventory.

## Evaluate the helpers

```sh
python3 -m unittest discover -s tests -v
python3 skills/defensefactory/scripts/eval-rules.py --output /tmp/factory-rules-eval-new
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
Each stage archive also carries the one inherited universal rule source under
`dependencies/defensefactory/RULES.md`. Validate rules and skill conformance with
`python3 <package>/scripts/stage-rules.py check <package>` before opening work;
the opening receipt binds the exact effective digest and source-byte identities.
