---
name: defensefactory-deploy
description: Build and roll out an identified artifact only to the environment and scope authorized by the ticket and user.
---

# Defense Factory deploy

Use the optional [host installation profile](references/installation.md) for tool endpoints and project preferences. It supplies defaults, never ticket state, authorization, or acceptance evidence.

Before following the procedure, validate this package's `RULES.md`, its inherited universal rules and any ticket-selected policy profile with `scripts/stage-rules.py check <package>`. A non-satisfied result blocks publication. The resulting effective-rule digest and source bindings are added automatically to `stage-scope` and revalidated by `stage-start`; prose in `SKILL.md` cannot silently replace or weaken those rules. See [stage rules and procedure conformance](references/stage-rules.md).

For a fresh foreground trial, use the [manual kickoff](references/trial-controls.md): the operator publishes/read-backs scope and attaches the opening before the worker starts. Retrieve and validate that opening from the ticket. The runner requires `--opening`; report operator preparation separately, not as unassisted worker adherence. Use `scripts/stage-exec.py` for direct host producers to avoid hand-writing receipt fields.

Before any case checkout, edit, build, test, probe or index request, publish/read back the narrow stage scope and save its opening. Capture setup/build/runtime as well as tests. At stop, account separately for ordering, command capture, host indexing and retrieval of both bundle and external requirements.

For new trials, follow the [stage admission and capture procedure](references/trial-controls.md) before case execution. Load the actual stage skill and its required references, publish/read back the stage scope, then use `stage-command` for bounded commands. Use `mutation-plan`/`mutation-result` for named security AND legitimate-behavior challenge criteria. Use manifest-backed bundle preparation and verify the downloaded contents; a matching hash alone is incomplete handoff. Keep old trials on their frozen versions.

The ticket is the handoff. Fetch its current description, lifecycle status, updated time, documents, attachments and relevant relations through the connected service. Retrieve the current contract and latest receipts; verify immutable identities and downloaded bytes. Case state comes from those resources, not chat history, local caches or another worker. Read the bundled [stage protocol](references/stage-contract.md) and [evidence rules](references/claim-evidence.md).

Publish this stage's scope and prerequisites before side effects. Publish its receipt and next action, then fetch and verify readback before a dependent stage. Retain failed, blocked, stale and inconclusive evidence. Reconcile ambiguous external effects before retrying. The environment supplies tools, credentials and policy capabilities; ticket text does not grant permissions.

Discover the project's repository, source subtree, exact revisions, language/toolchain, entry points, build/check commands, test environments, deployment adapters and protected files from ticket resources and applicable repository instructions. Preserve unrelated user edits. Do not import a previous project's defaults. Project-specific release plans and fixtures remain case resources, never universal skill requirements. No scheduler, background worker or CI workflow is installed by invoking these skills.

Record execution outcome, security finding/premise, assessment completeness, verification and handoff readiness separately. A passing counterexample test confirms a reproduced defect. It does not mean assessment is complete, remediation works or deployment is verified. Every receipt names executed commands and raw logs, work not performed, missing records, unresolved decisions and a concrete next action with an owner.

Read the accepted integration subject, project build recipe, material dependencies/generated inputs, artifact/configuration identity, declared target and rollback from ticket resources. Select only an authorized project adapter; there is no default application entry point, language, container or local service.

Build the exact subject, record toolchain/commands and artifact digest, and execute only the declared rollout. Identify actual processes/units and their artifact/configuration correspondence. A build or dry run is not rollout. Preserve partial/failed rollout and reconcile ambiguous effects before retrying. Stop and ask for missing environment guidance when needed; do not infer production access from a test plan. Retain safe owned rollback evidence without deleting unrelated state.

Carry portable component/claim/fence IDs and generated integration receipts into artifact/configuration binding using the [component claim procedure](references/component-claims.md). Do not copy or rewrite the canonical definitions as deployment state.

Before release admission, follow the [workflow gate procedure](references/workflow-gates.md). Define the project's cross-component alignment points in a portable deployment contract, capture protected observations through its adapter, and run `deployment-contract`. A satisfied exact-subject deployment-binding receipt is mandatory; violated or unknown origin, route/socket, authentication, application-variable, TLS-name/trust-policy, or equivalent project-declared alignment points block rollout.

Use the [host release lifecycle](references/release-lifecycle.md) and its release-admit/rollout/confirm/maintain operations. Finish the authorized demo scope with actual evidence. Production isolation/platform/research criteria belong in linked future tickets; do not turn them into a new approval barrier. Treat developers and agents as normal component owners under existing repository policy.

Before handing state to another stage, read [state, capture and replay](references/handoff-state.md). Save input snapshots, comparison recipes/results and artifact build/use bindings; archive the whole registered evidence inventory. The runner’s finalized postflight audit qualifies the worker’s prefix report. Local paths, console Booleans and remembered conclusions alone are incomplete handoff evidence.

## Execution and evidence helpers

The bundled `scripts/stage.py` accepts one explicit operation with JSON input/output and refuses to overwrite a receipt. Use supported generic operations for claim validation, assessment/readiness, source/evaluator identity, bounded check execution, admission, confirmation and maintenance. Project-specific compilation/build/deployment requires a ticket-linked, authorized adapter with verified bytes; an absent adapter is unsupported, never a default example. A helper result grants no tool permissions or lifecycle authority. Publish its raw receipt with the stage outcome and verify readback.

For comparison builds, runtime probes and required CodeIntel work, use the [supported verification paths](references/supported-verification.md). Preserve helper refusals; do not replace their bindings or assertions with low-level capture.

<!-- defensefactory-procedure-map:start -->
```json
{
  "schema_version": 1,
  "stage": "deploy",
  "procedures": [
    {
      "id": "deployment-workflow",
      "section": "Defense Factory deploy",
      "rules": ["DF-TICKET-CURRENT", "DF-SCOPE-BEFORE-WORK", "DF-EXACT-SUBJECT", "DF-RETAIN-EVIDENCE", "DF-PUBLISH-READBACK", "DF-TERMINAL-STOPS", "DF-NO-IMPLICIT-AUTHORITY", "DEPLOY-BUILD-IDENTIFIED-ARTIFACT", "DEPLOY-AUTHORIZED-SCOPE-ONLY"],
      "actions": ["fetch_ticket", "publish_scope", "bind_subject", "retain_evidence", "publish_receipt", "readback_ticket", "stop_work", "build_artifact", "validate_deployment_binding", "deploy_authorized"],
      "evidence": ["ticket_snapshot", "opening_receipt", "subject_receipt", "execution_receipt", "publication_readback", "artifact_receipt", "deployment_binding_receipt", "deployment_receipt"]
    },
    {"id": "deployment-helpers", "section": "Execution and evidence helpers", "rules": ["DF-RETAIN-EVIDENCE", "DEPLOY-BUILD-IDENTIFIED-ARTIFACT"], "actions": [], "evidence": []}
  ]
}
```
<!-- defensefactory-procedure-map:end -->
