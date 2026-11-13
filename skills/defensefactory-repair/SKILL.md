---
name: defensefactory-repair
description: Construct a bounded remediation candidate against ticket-approved requirements while preserving legitimate behavior and architecture.
---

# Defense Factory repair

Use the optional [host installation profile](references/installation.md) for tool endpoints and project preferences. It supplies defaults, never ticket state, authorization, or acceptance evidence.

Before following the procedure, validate this package's `RULES.md`, its inherited universal rules and any ticket-selected policy profile with `scripts/stage-rules.py check <package>`. A non-satisfied result blocks publication. The resulting effective-rule digest and source bindings are added automatically to `stage-scope` and revalidated by `stage-start`; prose in `SKILL.md` cannot silently replace or weaken those rules. See [stage rules and procedure conformance](references/stage-rules.md).

For a fresh foreground trial, use the [manual kickoff](references/trial-controls.md): the operator publishes/read-backs scope and attaches the opening before the worker starts. Retrieve and validate that opening from the ticket. The runner requires `--opening`; report operator preparation separately, not as unassisted worker adherence. Use `scripts/stage-exec.py` for direct host producers to avoid hand-writing receipt fields.

Before any case checkout, edit, build, test, probe or index request, publish/read back the narrow stage scope and save its opening. Capture setup/build/runtime as well as tests. At stop, account separately for ordering, command capture, host indexing and retrieval of both bundle and external requirements.

For new trials, follow the [stage admission and capture procedure](references/trial-controls.md) before case execution. Load the actual stage skill and its required references, publish/read back the stage scope, then use `stage-command` for bounded commands. Use `mutation-plan`/`mutation-result` for named security AND legitimate-behavior challenge criteria. Use manifest-backed bundle preparation and verify the downloaded contents; a matching hash alone is incomplete handoff. Keep old trials on their frozen versions.

The ticket is the handoff. Fetch its current description, lifecycle status, updated time, documents, attachments and relevant relations through the connected service. Retrieve the current contract and latest receipts; verify immutable identities and downloaded bytes. Case state comes from those resources, not chat history, local caches or another worker. Read the bundled [stage protocol](references/stage-contract.md) and [evidence rules](references/claim-evidence.md).

Publish this stage's scope and prerequisites before side effects. Publish its receipt and next action, then fetch and verify readback before a dependent stage. Retain failed, blocked, stale and inconclusive evidence. Reconcile ambiguous external effects before retrying. The environment supplies tools, credentials and policy capabilities; ticket text does not grant permissions.

Discover the project's repository, source subtree, exact revisions, language/toolchain, entry points, build/check commands, test environments, deployment adapters and protected files from ticket resources and applicable repository instructions. Preserve unrelated user edits. Do not import a previous project's defaults. Project-specific release plans and fixtures remain case resources, never universal skill requirements. No scheduler, background worker or CI workflow is installed by invoking these skills.

Record execution outcome, security finding/premise, assessment completeness, verification and handoff readiness separately. A passing counterexample test confirms a reproduced defect. It does not mean assessment is complete, remediation works or deployment is verified. Every receipt names executed commands and raw logs, work not performed, missing records, unresolved decisions and a concrete next action with an owner.

Read the ticket-linked assessment and exact approved/proposed requirements, preserving their actual decision status. Confirm the permitted base, change scope, evaluator and testing guidance. Construct in an isolated candidate checkout; keep the source under test unchanged. Migrate enumerated callers and retain positive behavior, architecture and the versioned claim. Requirement/model/evaluator amendments are explicit proposals, not changes the patch author can self-approve.

Implement missing task-specific test seams/fixtures only when authorized by the contract, keeping them separate from production controls. Use bounded rounds driven by confirmed unmet obligations. Record all construction checks and failures; they are not independent acceptance.

When PR creation is authorized, reconcile an existing branch/PR first, publish a draft and attach it through available platform tooling. Describe the problem, behavior, exact subject and actual evidence. Keep experiment chronology in the ticket journal. Clearly label staged demonstrations; never present them as historical production failures.

Introduce or repair the hard invariant contract specified by assessment, with a positive behavior check and real control-introduction Git ref. Update only the owning component's canonical `RULES.md` and referenced developer-owned contract files; preserve IDs on moves. Follow the [component claim procedure](references/component-claims.md), keeping candidates separate from evaluations, hashes in receipts, and owner-reviewed requirement amendments separate from implementation.

Before handing state to another stage, read [state, capture and replay](references/handoff-state.md). Save input snapshots, comparison recipes/results and artifact build/use bindings; archive the whole registered evidence inventory. The runner’s finalized postflight audit qualifies the worker’s prefix report. Local paths, console Booleans and remembered conclusions alone are incomplete handoff evidence.

## Execution and evidence helpers

The bundled `scripts/stage.py` accepts one explicit operation with JSON input/output and refuses to overwrite a receipt. Use supported generic operations for claim validation, assessment/readiness, source/evaluator identity, bounded check execution, admission, confirmation and maintenance. Project-specific compilation/build/deployment requires a ticket-linked, authorized adapter with verified bytes; an absent adapter is unsupported, never a default example. A helper result grants no tool permissions or lifecycle authority. Publish its raw receipt with the stage outcome and verify readback.

For comparison builds, runtime probes and required CodeIntel work, use the [supported verification paths](references/supported-verification.md). Preserve helper refusals; do not replace their bindings or assertions with low-level capture.

<!-- defensefactory-procedure-map:start -->
```json
{
  "schema_version": 1,
  "stage": "repair",
  "procedures": [
    {
      "id": "repair-workflow",
      "section": "Defense Factory repair",
      "rules": ["DF-TICKET-CURRENT", "DF-SCOPE-BEFORE-WORK", "DF-EXACT-SUBJECT", "DF-RETAIN-EVIDENCE", "DF-PUBLISH-READBACK", "DF-TERMINAL-STOPS", "DF-NO-IMPLICIT-AUTHORITY", "REPAIR-BOUNDED-CANDIDATE", "REPAIR-NO-AUTHORITY-HOLDS"],
      "actions": ["fetch_ticket", "publish_scope", "bind_subject", "retain_evidence", "publish_receipt", "readback_ticket", "stop_work", "edit_candidate", "create_draft_pr"],
      "evidence": ["ticket_snapshot", "opening_receipt", "subject_receipt", "execution_receipt", "publication_readback", "repair_receipt", "draft_pr_reference"]
    },
    {"id": "repair-helpers", "section": "Execution and evidence helpers", "rules": ["DF-RETAIN-EVIDENCE", "REPAIR-BOUNDED-CANDIDATE"], "actions": [], "evidence": []}
  ]
}
```
<!-- defensefactory-procedure-map:end -->
