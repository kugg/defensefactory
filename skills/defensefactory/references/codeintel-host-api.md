# CodeIntel transport and indexing capability

Use native MCP tools for semantic queries. Discover their actual schemas and
scope repository and revision explicitly. A failed query is not an index-control
capability investigation. MCP and workspace HTTP APIs may have different paths
and authentication; inspect the actual configured host client/service docs.
Do not guess a few routes and treat their 404 responses as exhaustion.

## Installer transport choices

The installer can retain an existing connection (empty MCP URL), create a remote
connection, or use the bundled tools-only stdio compatibility bridge. The latter
supports the tested CodeIntel POST-only JSON-RPC tool interface with upstream
protocol `2025-06-18`, adapting initialization for the client's tools subset; it
does not advertise resources or newer features. Select remote transport only
when the deployment/client supports it directly. New entries use `factory_`
names to avoid rewriting an existing same-named local/remote connection.

CodeIntel workspace keys normally use **X-Api-Key**. Configure a header name and
credential environment-variable NAME; the value comes from the operator's secret
capability. An explicit Authorization header uses a Bearer prefix. The installer
does not obtain a key, provision a workspace or verify authentication. Native
connection settings and API URL hints are not evidence of actual access.

## One bounded workspace API request

`scripts/codeintel-api.py` reads the operator profile's `codeintel_api_url` and
the configured credential environment variable (default `CODEINTEL_API_KEY`).
It accepts one GET/POST/PUT path and optional JSON body file, writes a new
sanitized status/response receipt, refuses overwrites and redirects, and makes
no automatic retries. It does not choose source, approve scope, modify policy
or initiate jobs unless that exact request is explicitly invoked. Use it through
`stage-exec.py` when a host request needs stage-bound command capture. Inherited
credentials must never be copied into argv or explicit captured environment.

For the tested API contract, read-only discovery uses GET `/api/repos` and
`/api/connections`. Per repository, inspect GET `/api/repos/{id}/status?branch=BRANCH`
and `/api/repos/{id}/branches`. The tested branch-policy operation is PUT on that
branches route; index submission is POST `/api/repos/{id}/index?ref=BRANCH`.
Connection creation uses POST `/api/connections` with an operator-approved source
and revision policy. The tested body is `{"name":"attempt-owned-name","config":{"type":"git","url":"OPERATOR_APPROVED_URL","revisions":{"branches":["SELECTED_BRANCH"]}},"sync":true}`.
The response may contain `connectionType`; do not copy response-only fields into
the request. This version rejects unknown top-level fields. A 400 does not prove
missing provisioning capability: compare the actual body with the deployed
handler/schema and change only a demonstrated mismatch before a bounded retry.
Check the deployed version before reliance; these are not
universal routes for every CodeIntel release. See the upstream
[CodeIntel documentation](https://github.com/pghoshal/codeintel).

Reconcile active jobs before a new submission. Inspect other repos sharing a
connection before any authorized policy change; prefer an isolated mapping and
never change another trial's policy/store to make a new run pass. A file connector
may need its worktree within the service's managed storage, with consistent
origin/repository identity. Discover that root from the host, not a hardcoded
personal path. A shallow non-default branch clone must contain the selected ref.

Expose the exact source commit through a selected branch/tag. A `ref=SHA` request
alone may not pin the planner. Retain actual requests, responses, jobs, Git refs
and errors. Confirm the active current manifest's full branch and commit, then
query that branch. Separately inspect SCIP occurrences, source reads and quality
warnings; READY is not semantic coverage. Apply a bounded investigation and
report concrete remaining limitations without inventing an owner decision.
