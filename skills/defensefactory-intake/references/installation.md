# Discover, qualify and install the factory for OpenCode

The supported new-user entry point is:

```sh
./scripts/install-defensefactory --check
./scripts/install-defensefactory --plan --installation-id <new-id>
./scripts/install-defensefactory --install --installation-id <new-id>
```

`--check` is read-only discovery. `--plan` gathers practice and production
answers separately and prints exact intended local mutations. `--install`
refuses a blocked plan, installs an immutable release and writes append-only
receipts. For unattended use, copy
[the profile example](environment-profile.example.json), replace every
placeholder, then pass `--answers FILE --noninteractive`.

Other lifecycle modes are:

```sh
./scripts/install-defensefactory --evaluate --installation-id <id>
./scripts/install-defensefactory --resume <id>
./scripts/install-defensefactory --report --installation-id <id>
./scripts/install-defensefactory --uninstall-profile --installation-id <id>
```

Deterministic evaluation validates all installed rule/skill packages without
service calls. A monitored practice run is optional and needs all four explicit
arguments: `--practice-prompt`, `--practice-project`, `--practice-opening` and a
new `--practice-destination`. The opening must already be published/read back in
the ticket. The runner retains OpenCode JSON events, binds an optional local OTel
log by digest, writes a privacy-preserving monitor report and keeps raw thinking
local. Technical outcome, process adherence and readiness are separate fields.

The profile's `paths.state_root` is authoritative for answer-file installs. An
explicit `--state-root` must match it; lifecycle commands also reject a root that
does not match the installed profile. Resume never invents a missing external
effect. Once ownership is committed it recomputes the complete installed-release
digest and refuses changed bytes before running the next deterministic evaluation;
if interruption occurred before ownership was committed, it preserves the failure
and requires inspection plus a new installation ID. Uninstall removes only
verified installer-owned links and retires its runtime configuration. Evidence,
receipts and immutable release bytes remain recoverable.

Discovery records host/architecture/shell/timezone/disk and relevant tool
versions. Git, an executable agent runner, deterministic helper runtime, durable
ticket project, writable private evidence and a declared practice boundary are
mandatory. Containers, formal/property tools, source intelligence, OTel, PR
integration, secret managers and project toolchains are recommended or
replaceable layers. A configured endpoint is not a qualified service: Linear
read/write, CodeIntel exact-ref/coverage, OTel receiver health and runtime
isolation remain inconclusive until an authorized practice observation exists.

The practice profile captures repositories, network destinations, credential
class, cleanup, resource limits, runtime evidence and deployment-test authority.
It hard-refuses real provider calls and production credentials. The production
section captures intended hosts, repositories, branch/deployment policy,
operators, reviewers, secret references and governance, but grants no authority.

Environment improvements may change only reversible installer-owned nonsecret
configuration. Skill semantics, `RULES.md`, helper behavior, repository policy,
production deployment and authorization require a separately reviewed proposal
and new version. A single successful practice run does not demonstrate reliable
autonomy.

The monitor's guarded/unguarded command classification is an audit heuristic,
not a sandbox. It recognizes the canonical `stage-exec.py` and `stage.py
stage-command` spellings in observed shell events. Renamed helpers, wrappers,
aliases or non-shell tool calls can evade that classification and therefore need
operator review; they do not become authorized merely because the monitor did not
flag them.

## Installed runtime profile

`scripts/install-defensefactory` is the sole supported installer entry point.
The shell file only checks for Python and invokes the canonical implementation at
`skills/defensefactory/scripts/install-defensefactory.py`; standalone packages
contain that same implementation rather than a second installer.

The environment profile records a provisioned `provider/model`, Linear project,
optional Linear and CodeIntel **complete MCP endpoint URLs**, an optional
CodeIntel host indexing API base URL, credential references, OpenCode/OTel
launcher, skills directory, private evidence root, practice boundary and a
separately authorized production target. An empty MCP URL retains an already
configured native connection. A web UI base URL is not necessarily its MCP
endpoint: supply the actual endpoint; no `/mcp` suffix or connectivity is guessed.

Settings, receipts, ownership and the immutable release live below
`paths.state_root/<installation_id>`. The generated runtime profile is
`runtime/config.json`; installed skills link to the copied release, so later
source edits cannot silently change an installation. Installation IDs are
append-only and one-shot: a changed profile uses a new ID, and the installer
refuses an existing ID or unrelated/different skill links. Keep in-progress
trials on their recorded packages.

For noninteractive installation, provide a complete `--answers FILE` and
`--noninteractive`. `--source` and `--state-root` support explicit locations;
the latter must match `paths.state_root`. The installer makes no model/API calls,
authenticates nothing, fetches no dependencies and does not edit global OpenCode
JSON/JSONC. Provider credentials and GitHub/Linear/CodeIntel permissions remain
host setup. It accepts credential references but never password, API-key or
bearer-token values.

The adjacent runtime `opencode.json` is an additive native configuration using
`factory_linear`/`factory_codeintel` names for newly selected endpoints, retaining
existing same-named connections. It contains the
model and any selected remote MCP connections. Start OpenCode with
`OPENCODE_CONFIG=/path/to/opencode.json` and
`DEFENSEFACTORY_CONFIG=/path/to/config.json`, plus `OPENCODE_CONFIG_DIR` pointing
to the parent of your installed `skills/` directory, or use the installed
`scripts/opencode-trial.py --config /path/to/config.json` with explicit
`--prompt`, `--project`, a new `--destination`, and `--opening` pointing to the
operator-prepared stage-start receipt freshly retrieved from the ticket. Follow
the [manual kickoff procedure](trial-controls.md) before `--run`; the runner will
refuse to start a worker without that recorded opening. The runner snapshots settings
and the generated native fragment into the invocation, keeps `--thinking`, and
uses the selected model/launcher/installed release. Explicit model/launcher and
environment overrides take precedence over profile defaults. An existing
`OPENCODE_CONFIG` custom file is replaced for that invocation; standard global
provider/auth configuration still merges. Review effective project and inline
overrides and actual tool/model discovery at preflight.

OpenCode documents [custom config precedence](https://opencode.ai/v1/docs/config/)
and [remote MCP configuration](https://opencode.ai/v1/docs/mcp-servers/). Project,
inline and managed settings may override this fragment. OTel requires a separately
provisioned wrapper/collector; selecting a wrapper is not telemetry verification.
Finish provider/MCP authentication using your existing client setup, then check
native tool inventory and exact source indexing in a fresh session.

## Read preferences without importing case state

At stage startup, read the optional runtime profile selected by an explicit
`--config` or `DEFENSEFACTORY_CONFIG`. Its Linear project and repository are
discovery hints. Fetch the live ticket and verify its actual project/repository;
do not move tickets or silently substitute source subjects to match defaults.
An explicit ticket/user scope takes precedence. An empty optional CodeIntel endpoint does not prove that the existing native
connection or other configured host client lacks an indexing endpoint. Discover
that bounded host capability before declaring it unavailable. The separate
`codeintel_api_url` preference is a hint, not permission to alter shared policies.
Endpoint configuration does not
prove capability, authentication, index coverage, or authorization. Missing
profiles do not block an already provisioned environment. Do not copy account
preferences into canonical claims. Pin the consumed settings as a nonsecret
attempt input, while all case state, receipts and decisions remain in the ticket.

For POST-only transport compatibility, workspace API authentication and tested
indexing routes, read [CodeIntel host integration](codeintel-host-api.md). A Bearer
assumption or guessed v1 routes can fail even when native MCP works.
