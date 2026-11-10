New authored definitions follow the [component claim/fence procedure](component-claims.md). Hash requirements below apply to generated execution/evidence receipts, not manually maintained component catalogs.

# Exposure, durable claims and regression evidence

## Exposure and attack complexity

Assessment publishes a Mermaid attack-path graph in an issue-owned document and a downloadable `.mmd` attachment. If Linear cannot render Mermaid, attach a rendered SVG/PNG as well; keep the editable source. Label actor capabilities, ingress, trust boundaries, conditions, affected assets and the proposed control. Distinguish observed edges from hypotheses and proposed edges. Cite exact source/configuration/reproduction evidence for material edges; a diagram alone is not evidence of reachability.

State attack surface (remote, adjacent, local, physical), required identity/privileges, network/host access, user interaction, timing/race conditions, configuration and pivot chain. Describe difficulty both before and after prerequisites. Do not conflate deployment exposure, access privileges, formal attack-complexity scoring and impact. Preserve reporter severity, give a reasoned assessed priority, and state what additional evidence would change it. If using CVSS, name its version and justify each metric; do not assign a score from intuition. A localhost listener is not a demonstrated remote entry point. Conversely, a demonstrated SSRF, shared-host tenant or code-execution pivot must be represented when supported. Unknown proxy/binding/access controls are unknown, not assumed protection.

## Versioned claim chain

For each obligation retain: stable ID, requirement authority/version, prohibited transition, required legitimate transition, assumptions, implementation bindings, CodeIntel query receipt(s), specification/model/profile digests, concrete check/evaluator digest, candidate/artifact/configuration identity, raw outcomes, coverage gaps, invalidation triggers and next replay command. Store claim/specification and regression inputs in version control when constructing a candidate; link immutable bytes through the ticket. A ticket-only prose assertion is not an executable future claim.

### CodeIntel evidence

Assessment must attempt scoped CodeIntel discovery/search/read against the exact source subject when access exists; record unavailable capability explicitly otherwise. Verification must retrieve those receipts and perform fresh candidate queries when the exact candidate is indexed. Maintenance refreshes them after affected source/index changes. Use native MCP tools when present; an authorized ticket-linked wrapper is a fallback, never a required host path.

Record endpoint identity without credentials, tool/schema version, repository/index ID, indexed commit, request arguments, raw response, errors/truncation and coverage diagnostics. Bind query matches and read files to paths/content hashes. Map every identified caller/route and unresolved edge to obligations. A baseline index can help find code but cannot prove candidate coverage; compare with exact local source and report stale index results separately. Lexical search is not resolved dispatch, and absence of hits is not absence of a bypass. Missing/zero semantic occurrences or unsupported extraction prevent semantic coverage claims until current subject-bound evidence demonstrates them. Advertised native tools alone do not qualify the index.

When indexing is authorized, reconcile active jobs before submitting another. Inspect the backend's revision-selection policy and the actual available Git refs; a commit parameter alone may not pin the planner. Check which repositories share a connection before changing its policy. Expose the selected subject through a policy-selected branch/tag available in the managed checkout, sync, and verify the active manifest's full commit and ref before relying on explicitly scoped queries. Qualify language/project coverage, nonzero semantic occurrences, missing workers, skipped extraction, quality warnings and query truncation separately from activation status. Retain failed/partially applied policy or scheduling requests and read back their effects before retrying.

### TLA+ and implementation conformance

Assessment decides and records, per obligation, whether a state/transition model is required by the contract, proposed, unsupported, or out of scope with a reason and policy reference. For an applicable protocol/lifecycle claim, specify actors, state, transitions, safety invariants, legitimate reachable traces, liveness/fairness assumptions and bounds. Do not invent business semantics to author a model. Missing semantics are assessment questions; a bounded candidate experiment can be recorded without accepted proof.

Repair supplies a reviewable versioned claim/specification, model and `.cfg` when formal checking is in scope, plus a mapping from modeled transitions to concrete source and executable checks. A hand-authored model is permitted when declared; select a validated compiler/profile for the actual property family and record unsupported semantics explicitly. Keep model/profile/obligation changes explicit and separately reviewed from patch construction.

Verification executes the pinned TLC/model-check command in an isolated scratch directory with declared timeout and resource bounds. Attach `.tla`, `.cfg`, relevant dependencies, checker identity/digest, invocation, raw output, counts/completion, counterexample traces and reachable positive scenarios. Check vacuity (including deny-all), appropriate negative model variants and assumptions that could exclude the reported attack. Report specification validity, bounded model result and implementation conformance separately. Timeout, missing model/tool, incomplete exploration or missing correspondence cannot earn a pass. A clean bounded model proves only its checked abstraction; library correctness and actual runtime identity/configuration require separate evidence.

Results for another service, model or candidate cannot establish this project’s property. Retain explicit correspondence among requirement, model, source, evaluator and actual environment; missing layers remain unsupported or inconclusive.

### Resistance to security regression

Make the security property easy to rerun and difficult to bypass accidentally: canonical enforcement shared by all callers, no insecure alternate constructor/fallback, negative tests for the original exploit and bypasses, and positive lifecycle checks that reject deny-all. Name exact tests and source bindings. Seed relevant control-removal, trust-bypass and downgrade changes against the exact candidate with unchanged evaluator bytes; retain each mutant patch, detection output and surviving mutation. Retained failing counterexamples become future regression inputs. A test that merely matches a constructor's spelling cannot prove behavior.

Report two separate measures: regression detectability and resistance to evaluator tampering. Same-repository tests and hashes provide detectability; they do not stop an author from deleting both the control and tests. Check actual repository rules/protected required checks, ownership/review policy, verifier write permissions, independent identity and bypass rights before claiming enforced resistance. Record absent/unreadable protection as unverified. No CI, rule, CODEOWNERS or background workflow is installed merely by this skill. Protected acceptance must follow the governing policy and authorized tooling.

Integration checks the actual merge subject against the accepted claim and evaluator, including changes that remove/skip/weaken checks, model bounds or configuration constraints. Deployment/confirmation bind the claim to actual artifact/configuration/peer identity. Maintenance manually replays affected claims and seeded variants on source, dependency, index, model/profile, configuration, trust or evaluator-policy drift. A future change invalidates dependent evidence without erasing history.


## Project end-to-end guidance

Assessment must discover and bind the project's E2E/release plan before declaring a handoff complete when a real journey is needed. Missing guidance produces a user question and incomplete readiness, not a unit-test substitute. Store the supplied plan as an immutable case resource and extract environment, services, real/stubbed legs, candidate identity, setup, pass evidence, negative controls and safe cleanup. Record unsupported environments and absent fixtures as prerequisites. Component, end-to-end and production outcomes remain separate. Review untrusted input and log/error sinks before any test that can carry sensitive material; retain only sanitized evidence.
