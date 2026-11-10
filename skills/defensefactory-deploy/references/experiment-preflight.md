# Startup, applicability and evidence capture (next experiment revision)

For new v6 attempts, first follow [stage admission and capture](trial-controls.md). Use the guarded execution path and retained receipt dependencies; legacy helper success does not establish stage admission.

Follow the [handoff completeness and scoped-source procedure](handoff-completeness.md) for originating Git namespaces, source-only versus lifecycle decisions and actual replay resources. Transport hash verification alone is not complete-handoff readiness.

Read this procedure before an experiment's first execution. Recover the live ticket and frozen protocol, then read only the references needed for the current gate. Keep historical experiments on their pinned packages; do not hot-update another active trial or install this package over its copy.

## One bounded preflight

Use `stage-preflight` with `case`, actual `performed_by`, `protocol_reference`, `scope_authorization_reference`, `tool_inventory_reference`, `exposed_tools` (names), and `targets` (`id`, `role`, exact `subject`). Tool discovery uses exposed tool metadata or the environment's supported tool registry. An empty MCP resource list proves nothing about tool availability. Record discovered capabilities once and revisit only on a real change. Use `skill-inventory` on the installed packages actually consumed, not every unused stage's repository archive. Preserve its full manifest as a resource; ticket prose needs only the manifest reference and gaps.

Each source has a role: `reported_revision` (original observation), `trial_target` (authorized experiment subject), `comparison_revision` (fix investigation), `supported_release`, or `deployed_artifact`. An old vulnerable commit is not automatically a maintained target; fixed main cannot silently exclude the designated snapshot. The complete supported inventory and its owner/reference govern terminal disposition. If missing, ask one precise scope question early while continuing already-authorized source investigation. Do not repeatedly debate a missing fact or ask for decisions already supplied.

Record toolchain and platform, private writable scratch/cache locations, required commands and permission capabilities. Prefer the host tool's timeout or portable subprocess timeouts over assuming GNU utilities exist. Project-specific cache paths must be canonical absolute paths. Managed CodeIntel checkouts and designated baselines are read-only inputs; repairs use isolated candidates. No permission is inferred from a successful capability probe.

## Resolve before classifying

Capture any authorized fetch with `command-record`, then use `source-resolve` with repository path, ref and explicitly selected dependency input paths. It reads the exact Git tree and hashes those inputs without changing refs or source. A local ref read does not prove remote freshness, and a missing local object means `unavailable_locally`, not fabricated history, removal or retirement. Fetch updating a remote-tracking ref does not establish when upstream changed. Obtain the language adapter's resolved dependency/toolchain manifest and built artifact identity as needed; unchanged application code does not establish unchanged dependency behavior.

Use `assess-observe` to retain provisional per-target applicability without manufacturing policy. Observation records name the actual performer, subject, rationale and source reference. Then invoke **`assess-eligibility` before repair planning**. It is the mandatory disposition gate in this version, not an optional formatting aid. Missing scope/policy yields a structured hold; no owner, inventory or reviewer may be invented to make it pass. Source investigation remains distinct from disposition authorization. Do not backfill a missing earlier gate as if it ran on time.

## Authority and hypothetical evaluations

Distinguish actual `performed_by`, `authorized_by` and `reviewed_by`. Acting through the owner's connector account or executing a delegated task does not mean the owner reviewed the result. Transcribe an actual instruction accurately with a reference; never attribute the agent's analysis to the invoker. Existing authorization suffices within its stated scope; this procedure creates no separate security-team approval authority.

For terminal dispositions the trusted policy must carry `assessment_scopes[case].complete: true`, a scope `reference`, and target roles. It also binds each actual scope review through `verified_scope_reviews[record_sha256]` containing `performed_by`, `authorized_by`, `authorization_reference` and `review_reference`. These are verified decisions supplied through the governing mechanism, not agent-created pass fixtures. `scope_review.performed_by` equals its `reviewer`; the configured reviewer list alone cannot qualify a decision. A delegated agent may review as itself where native policy permits it. Caller-supplied JSON still does not establish authenticated identity or protected execution.

Hypothetical scope comparisons require `evaluation_mode: hypothetical` on packet or policy. They always return `closure_permitted: false` and incomplete handoff readiness, even when a hypothetical inventory would otherwise permit closure. Never publish them as actual authority. Only actual scoped evidence and authorization can admit a lifecycle transition.

## Capture once, from execution

Use `command-record` with an explicit specification (`id`, `subject`, `performed_by`, direct `argv`, absolute `cwd`, bounded `timeout_seconds`, environment overrides, frozen `evaluator_files`, and `execution` protocol) plus a **new** evidence directory. It writes preparation metadata before launch, checks evaluator bytes, streams full combined output directly to a private file, captures the producer exit status and timestamps, and qualifies named output. It retains startup failures, timeouts and partial output; retries use new directories. Display a short tail only after capture. Do not pipe producers into `tail` or a formatter and report the formatter's exit status. Review/redact raw private outputs before attachment; hashes of original and redacted bytes have different purposes.

Named tests require `go-test-json` or `factory-jsonl-v1` and a predeclared nonempty `required_tests` inventory. Non-test commands require an explicit reason and success criterion; their exit status earns no named-test coverage. For fixed-disposition checks, freeze `argv`, evaluator digest and `execution` protocol in `required_checks`. Raw logs must qualify that inventory and captured commands must match it. `timestamp_basis: captured_at_execution` is required; file mtime, guessed durations and substituted timestamps are not execution evidence. Unknown historical timestamps stay unknown. A later replay is a new execution, never a repair of an old log.

Case probes use frozen assertions and actual response endpoints/request correlation, readiness, bounded observation, and guaranteed owned-process cleanup. `probe-assert` compares predeclared named `field`/`equals` expectations with observations; case adapters emit its events as `FACTORY_TEST <JSON>` and return failure for failed assertions. Hash the adapter, expectations and command specification before launch. Observation logging alone is not assertion execution. Refusal of an invalid request does not prove a legitimate journey succeeds. Protocol-specific response routing, session state and lifecycle details belong in the case adapter, not this reusable skill.

## Publication and measured outcomes

Pass actual connector retrieval results mechanically to `ticket-snapshot`; it hashes a declared stable projection without refreshed attachment URLs. Do not reconstruct large tool output manually and claim byte identity. If the environment cannot export exact structured bytes, record that limitation; do not reuse an earlier description hash or treat UUID/update time as immutable content. Preserve and attach original machine receipts and referenced evaluators/adapters, not just their names/hashes.

Use `publication-verify` to distinguish `published`, `retrieved_again` and `bytes_verified`. A mutation response is not a separate retrieval. Attachment titles/subtitles listing hashes are not verification of downloaded bytes. Fetch through the ticket, refresh resource URLs by ID, download and compare actual bytes before dependent work. Native document markup normalization must remain explicit.

Classification and formal-method dispositions are `used`, `not_needed` with reason, or `unavailable`; neither a classifier call nor a model run is ceremonial. Record full coverage limits. Emit bounded learning entries: expected observation, actual command/result, causal evidence versus hypothesis, next action/owner and invalidated evidence. Measure wall time, command durations, repair rounds and available model/provider usage separately. Do not add overlapping command times into elapsed run time or infer token/cost values from thought labels.

For blocked or nonactive tasks, input examples (`stage.py --describe OPERATION`), capability limits and provider-counter supplements, use [assessment resolution](assessment-resolution.md). A new session must record its own native tool inventory.
