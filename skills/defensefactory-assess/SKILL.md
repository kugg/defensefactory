---
name: defensefactory-assess
description: First qualify or close incoming security findings; assess active findings, explain exposure and attack complexity, and bind repair and verification requirements.
---

# Defense Factory assess

Use the optional [host installation profile](references/installation.md) for tool endpoints and project preferences. It supplies defaults, never ticket state, authorization, or acceptance evidence.

Before following the procedure, validate this package's `RULES.md`, its inherited universal rules and any ticket-selected policy profile with `scripts/stage-rules.py check <package>`. A non-satisfied result blocks publication. The resulting effective-rule digest and source bindings are added automatically to `stage-scope` and revalidated by `stage-start`; prose in `SKILL.md` cannot silently replace or weaken those rules. See [stage rules and procedure conformance](references/stage-rules.md).

For a fresh foreground trial, use the [manual kickoff](references/trial-controls.md): the operator publishes/read-backs scope and attaches the opening before the worker starts. Retrieve and validate that opening from the ticket. The runner requires `--opening`; report operator preparation separately, not as unassisted worker adherence. Use `scripts/stage-exec.py` for direct host producers to avoid hand-writing receipt fields.

Before any case checkout, edit, build, test, probe or index request, publish/read back the narrow stage scope and save its opening. Capture setup/build/runtime as well as tests. At stop, account separately for ordering, command capture, host indexing and retrieval of both bundle and external requirements.

For new trials, follow the [stage admission and capture procedure](references/trial-controls.md) before case execution. Load the actual stage skill and its required references, publish/read back the stage scope, then use `stage-command` for bounded commands. Use `mutation-plan`/`mutation-result` for named security AND legitimate-behavior challenge criteria. Use manifest-backed bundle preparation and verify the downloaded contents; a matching hash alone is incomplete handoff. Keep old trials on their frozen versions.

Use the [assessment resolution procedure](references/assessment-resolution.md) when a finding is nonactive, a hold is proposed, or impact is inherited from a reporter. Finish bounded source dispositions without demanding lifecycle-wide inventory; route real decisions to the stage they block and preserve deferred obligations. Require direct evidence for each claimed effect.

Follow the [workflow gate procedure](references/workflow-gates.md). Represent each unresolved product/deployment choice with `decision-request`, not prose, and publish the matching decision receipt before resuming. For an active exact subject, assessment finishes only after `assess-eligibility-receipt` binds the reproduced counterexample, applicable contract version, resolved blocking decisions and authorized repair scope. Use `stalled-findings` to surface intake-only tickets; only an explicit park receipt suppresses that next action.

For a bounded source trial, use the [scoped-source and bundle procedure](references/handoff-completeness.md). Missing global deployment inventory does not block authorized source assessment. Unknown historical references are background unless declared trial targets; recover their originating namespace before declaring them unavailable. Keep actual trust/provisioning decisions as repair-contract blockers, and never use a source-only gate to authorize closure.

Start with the bundled [preflight and applicability procedure](references/experiment-preflight.md). A source observation is not a support-policy decision. Record actual performer/delegation separately; the connector account owner is not automatically the reviewer. Hypothetical scope comparisons cannot authorize closure.

The ticket is the handoff. Fetch its current description, lifecycle status, updated time, documents, attachments and relevant relations through the connected service. Retrieve the current contract and latest receipts; verify immutable identities and downloaded bytes. Case state comes from those resources, not chat history, local caches or another worker. Read the bundled [stage protocol](references/stage-contract.md) and [evidence rules](references/claim-evidence.md).

Publish this stage's scope and prerequisites before side effects. Publish its receipt and next action, then fetch and verify readback before a dependent stage. Retain failed, blocked, stale and inconclusive evidence. Reconcile ambiguous external effects before retrying. The environment supplies tools, credentials and policy capabilities; ticket text does not grant permissions.

Discover the project's repository, source subtree, exact revisions, language/toolchain, entry points, build/check commands, test environments, deployment adapters and protected files from ticket resources and applicable repository instructions. Preserve unrelated user edits. Do not import a previous project's defaults. Project-specific release plans and fixtures remain case resources, never universal skill requirements. No scheduler, background worker or CI workflow is installed by invoking these skills.

Record execution outcome, security finding/premise, assessment completeness, verification and handoff readiness separately. A passing counterexample test confirms a reproduced defect. It does not mean assessment is complete, remediation works or deployment is verified. Every receipt names executed commands and raw logs, work not performed, missing records, unresolved decisions and a concrete next action with an owner.

First determine whether the finding still applies using the [early disposition procedure](references/assessment-disposition.md). Removed/retired components and already-fixed bugs may close or disqualify incoming tickets with scoped evidence and authorized native lifecycle readback. Missing source, a rename, nominal deprecation, model classification or a fix in only one required target cannot close the whole ticket. Run `assess-eligibility` before repair planning or E2E-guidance questions; publish and read back a terminal disposition, apply and verify the native transition, then stop. A verified `stop_source` result finishes the scoped task without changing ticket status. Active targets continue below; unknown targets block closure.

Separate reporter assertions, assessed effects and conditional attack chains with `assess-impact` and `finding.impact_assertions`. Establish or dispute the premise using bounded evidence and a safe reproduction when authorized. Retain counterevidence and the original requirements. Classify an occurrence, variant, new property or unresolved relationship using versioned claim identity; name similarity alone is insufficient. Compare a local repair with shared enforcement, including bypasses, migration, exceptions and cost evidence.

When the owning component has canonical `RULES.md`, parse it and resolve applicable contract descriptors at the exact subject. Run only available, authorized adapters; retain raw checker output and normalized candidates without treating them as confirmed violations. Publish missing engine, index, language or runtime coverage as `inconclusive`. Candidate evaluation is a separate durable record.

Publish a Mermaid exposure graph whose readable labels explain actor → entry point → trust assumption → sensitive operation. Distinguish source-supported, observed, proposed and unresolved edges and attach the editable graph. Explain local/remote reachability, required privileges or pivots, timing, interaction and configuration assumptions in plain language. Assess attack complexity separately from impact and preserve uncertainty in priority.

## End-to-end testing guidance

Before declaring the assessment handoff complete, discover the project's existing release/integration/E2E plan through the ticket and repository. Determine the real user journey, authorized test environment, required services, setup/cleanup, negative controls, success evidence and candidate identity rules. Component tests and mocks cannot silently stand in for a required end-to-end journey.

If guidance needed to complete assessment is missing or materially incomplete, **ask the user** for the plan/reference and the missing environment/journey/success/cleanup details, using the available user-input tool or a concise question. Record the question and its blocking scope in the ticket. Continue independent source work while awaiting it; keep handoff readiness incomplete. Do not fabricate the guidance, quietly downgrade to unit tests, or repeatedly ask for a resource already supplied. A policy-approved unit-only scope must explicitly explain why E2E is not applicable.

When guidance is supplied, retain a shareable immutable copy/reference and digest in the case. Extract a task-specific gate/check matrix. Missing fixtures become concrete implementation or environment prerequisites; a supplied plan is not evidence that those fixtures ran. Do not copy project commands, service names or network settings into the reusable skill.

## Contract and handoff

Bind the exact source, classification, requirement authority, scope, security/business/architecture obligations, E2E guidance, bypasses, migration, unknowns, check/evaluator identities, permitted actions and budgets into a versioned contract. Read existing contract resources rather than dropping them when constructing helper inputs. Name which decisions block the selected scope and which belong to a later environment.

Use available code-intelligence evidence at the exact indexed subject and retain requests/responses, provenance and unresolved coverage. Where formal checking is required, specify the property family, assumptions, bounds, positive reachability and implementation bindings; otherwise retain its explicit disposition. Another project's model earns no credit. A complete contract proposal is reviewable output, not an automatic grant of repair authority.

Assessment completion requires more than nonempty fields: attach a source-location boundary map, a selected control and concrete trust/provisioning/migration specification, and executable or explicitly planned checks with expected outcomes, inputs, evaluator identity and remaining implementation work. Identify which checks actually exist. Require named-test inventory and zero-unexplained-skip checks so a command that runs no relevant tests cannot satisfy an obligation. Structural helper validation alone cannot establish the adequacy of these decisions. Runtime test execution may remain pending without keeping a sufficiently supported assessment open.

## Claim registry, classification and approval

Read the claim registry from an exact product Git revision using `claim-registry`; the derived view is not a second editable authority. Use `claim-retrieve` for bounded candidate discovery and `claim-classify` for pinned, evidence-backed coverage comparisons. Lexical retrieval and model responses are proposals. A covered occurrence requires explicit implementation coverage; new runtime variants reuse property identity, and truncated/unresolved/missing-binding evidence cannot silently become a new class or coverage. Record versioned relation/merge/split lineage.

For an operator-provisioned Jev profile, `scripts/jev-classifier.py` reads the authorized 1Password reference in memory and retains request/response/model/usage receipts without the token. The profile selects endpoint/model/credential capability; a finding or ticket cannot grant secret access. Do not submit real secrets as classifier context. No automatic retries; preserve failed requests. Use the generic model-proposal protocol for other provisioned classifiers.

Use `contract-propose` to bind exact source, product claim, evaluator, context, permitted actions, budget and disagreement route. When the governing policy requires signed review, use `contract-approve` and `verification-handoff`: trusted policy and reviewer keys come from outside patch-controlled inputs; require the policy-trusted producer signature and a separate bound review signature. The producing actor/key cannot approve itself through an alias; changed or expired/revoked inputs fail. Otherwise retain the actual native delegation/review and construction scope; do not invent keys, reviewers or a new approval requirement. Handoffs preserve full obligations and check identities. Signatures and local fixtures do not establish protected identity separation.

Before comparative classification or handoff experiments, freeze corpus/arm/threshold identities. Report false merges/splits, abstention, taxonomy growth, failed requests, real provider usage and missing accepted-remediation/rework costs. Author-generated fixtures and controlled lossy summaries test mechanics, not independently adjudicated model quality. Do not claim total cost through accepted repair without authenticated acceptance/outcome evidence.

Use the [component claim and fence procedure](references/component-claims.md): classify bug mechanisms against canonical mappings, identify the owning component and specify missing hard fences. A root catalog is valid for a repository-sized component; soft policy/classification output is not coverage. Keep computed hashes and run verdicts in receipts.

Also follow the [architectural bug-class procedure](references/bug-classes.md) far enough to record claim/invariant/component/boundary candidates for later repair. Assessment may generate candidates; it must not force class membership from a title, CWE, model score or shared source path.

Before handing state to another stage, read [state, capture and replay](references/handoff-state.md). Save input snapshots, comparison recipes/results and artifact build/use bindings; archive the whole registered evidence inventory. The runner’s finalized postflight audit qualifies the worker’s prefix report. Local paths, console Booleans and remembered conclusions alone are incomplete handoff evidence.

## Executable helpers

The `assess-eligibility` gate above is mandatory before repair planning. `assess-observe` permits evidence gathering without fabricated authority; missing disposition inputs produce a hold with a concrete scope question. Other operations below are optional when not applicable. Never retrospectively relabel observation logging as named assertion execution or infer missing execution timestamps.

The bundled `scripts/stage.py` accepts one explicit operation with JSON input/output and refuses to overwrite a receipt. Use supported generic operations for claim validation, assessment/readiness, source/evaluator identity, bounded check execution, admission, confirmation and maintenance. Project-specific compilation/build/deployment requires a ticket-linked, authorized adapter with verified bytes; an absent adapter is unsupported, never a default example. A helper result grants no tool permissions or lifecycle authority. Publish its raw receipt with the stage outcome and verify readback.

For comparison builds, runtime probes and required CodeIntel work, use the [supported verification paths](references/supported-verification.md). Preserve helper refusals; do not replace their bindings or assertions with low-level capture.

<!-- defensefactory-procedure-map:start -->
```json
{
  "schema_version": 1,
  "stage": "assess",
  "procedures": [
    {
      "id": "assessment-workflow",
      "section": "Defense Factory assess",
      "rules": ["DF-TICKET-CURRENT", "DF-SCOPE-BEFORE-WORK", "DF-EXACT-SUBJECT", "DF-RETAIN-EVIDENCE", "DF-PUBLISH-READBACK", "DF-TERMINAL-STOPS", "DF-NO-IMPLICIT-AUTHORITY", "ASSESS-ELIGIBILITY-FIRST", "ASSESS-INACTIVE-STOPS", "ASSESS-ACTIVE-BINDS-REPAIR", "ASSESS-UNKNOWN-HOLDS"],
      "actions": ["fetch_ticket", "publish_scope", "bind_subject", "retain_evidence", "publish_receipt", "readback_ticket", "stop_work", "evaluate_eligibility", "issue_eligibility_receipt", "record_decision_request", "record_owner_decision", "detect_stalled_findings", "assess_finding", "request_guidance", "discover_bugclass"],
      "evidence": ["ticket_snapshot", "opening_receipt", "subject_receipt", "execution_receipt", "publication_readback", "assessment_receipt", "eligibility_receipt", "decision_request", "decision_receipt", "stalled_findings_report", "e2e_guidance", "bugclass_discovery"]
    },
    {"id": "assessment-e2e", "section": "End-to-end testing guidance", "rules": ["ASSESS-ACTIVE-BINDS-REPAIR", "ASSESS-UNKNOWN-HOLDS"], "actions": [], "evidence": []},
    {"id": "assessment-handoff", "section": "Contract and handoff", "rules": ["DF-PUBLISH-READBACK", "ASSESS-ACTIVE-BINDS-REPAIR"], "actions": [], "evidence": []},
    {"id": "assessment-claims", "section": "Claim registry, classification and approval", "rules": ["ASSESS-ACTIVE-BINDS-REPAIR"], "actions": ["discover_bugclass"], "evidence": ["bugclass_discovery"]},
    {"id": "assessment-helpers", "section": "Executable helpers", "rules": ["DF-RETAIN-EVIDENCE"], "actions": [], "evidence": []}
  ]
}
```
<!-- defensefactory-procedure-map:end -->
