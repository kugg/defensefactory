# Install and configure the factory for OpenCode

From the source checkout, run `python3 scripts/install-factory.py`. From a release,
unpack all nine stage archives into one directory, then run
`python3 /path/to/defensefactory/scripts/install-factory.py`.

The installer asks for a provisioned `provider/model`, Linear project name/ID,
optional Linear and CodeIntel **complete MCP endpoint URLs**, a separate optional
CodeIntel host indexing API base URL, a transport choice (stdio tools bridge or
remote), credential header name (normally X-Api-Key), and an optional
CodeIntel credential **environment variable name**, GitHub repository hint,
OpenCode executable/OTel wrapper, skills directory and trial output directory.
Use an empty MCP URL to retain an already configured native connection. A web UI
base URL is not necessarily its MCP endpoint: supply the actual endpoint; no
`/mcp` suffix or working connectivity is guessed.

Settings live in `$XDG_CONFIG_HOME/defensefactory/config.json` (normally
`~/.config/defensefactory/config.json`), outside the portable skills. Installed
skills link to a copied release under that directory, so later source edits do
not silently change the installation. Existing unrelated skills are refused
before installation. Identical reinstallation is a no-op. Explicit `--update`
backs up changed settings under `history/` and can change only this installer's
managed skill links; old releases remain. It cannot overwrite frozen links or
other installations. Keep in-progress trials on their recorded packages.

For noninteractive installation, supply `--yes --model PROVIDER/MODEL
--linear-project PROJECT` and other desired options (`--help` lists them).
`--source`, `--config`, `--skills-directory` and `--output-directory` support
custom locations. The installer makes no model/API calls, authenticates nothing,
does not fetch dependencies and does not edit your global OpenCode JSON/JSONC.
Provider credentials and GitHub/Linear/CodeIntel permissions remain host setup.
No passwords, API keys or bearer tokens are prompted for or stored in the profile.

The adjacent `opencode.json` is an additive native configuration using
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

At stage startup, read the optional profile selected by `DEFENSEFACTORY_CONFIG`
(fall back to the default path above). Its Linear project and repository are
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
