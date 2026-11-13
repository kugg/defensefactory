# Universal Defense Factory rules

These are the bounded normative invariants shared by every factory stage. Stage
packages inherit this file and may strengthen it. They may not silently weaken a
universal safety rule. Procedures live in `SKILL.md`; exact versions, selected
profiles, digests, observations and outcomes live in receipts.

<!-- defensefactory-stage-rules:start -->
```json
{
  "schema_version": 1,
  "stage": "universal",
  "inherits": [],
  "vocabulary": {
    "conditions": {
      "stage_state": ["opened", "active", "handoff", "terminal"],
      "disposition_class": ["none", "continue", "hold", "stop", "complete"],
      "authorization": ["absent", "present"],
      "applicability": ["unknown", "active", "inactive"]
    },
    "effects": {
      "facts": ["ticket_current", "scope_bound", "subject_exact", "evidence_retained", "handoff_readable", "eligibility_known", "candidate_bounded", "verification_complete", "integration_admitted", "artifact_identified", "deployment_observed", "maintenance_current"],
      "actions": ["fetch_ticket", "publish_scope", "bind_subject", "execute_bounded_work", "retain_evidence", "publish_receipt", "readback_ticket", "stop_work", "select_stage", "register_finding", "preserve_original_evidence", "evaluate_eligibility", "assess_finding", "request_guidance", "edit_candidate", "create_draft_pr", "run_checks", "evaluate_candidate", "evaluate_merge", "merge_authorized", "build_artifact", "deploy_authorized", "rollback", "observe_deployment", "request_closure", "refresh_evidence", "open_corrective_work", "execute_without_scope", "discard_evidence", "infer_authority", "install_automation"],
      "evidence": ["ticket_snapshot", "opening_receipt", "subject_receipt", "execution_receipt", "publication_readback", "intake_receipt", "assessment_receipt", "e2e_guidance", "repair_receipt", "draft_pr_reference", "verification_receipt", "candidate_evaluations", "integration_receipt", "artifact_receipt", "deployment_receipt", "confirmation_receipt", "maintenance_receipt"],
      "transitions": ["continue", "hold", "stop", "handoff", "draft_pr", "merge", "deploy", "close"],
      "outcomes": ["continue", "hold", "stopped", "registered", "disqualified", "active_finding", "draft_pr", "verified", "integrated", "deployed", "confirmed", "maintained", "closed"],
      "postconditions": ["ticket_current", "scope_bound", "exact_subject_bound", "evidence_retained", "handoff_readable", "eligibility_known", "candidate_bounded", "verification_complete", "integration_admitted", "artifact_identified", "deployment_observed", "maintenance_current"]
    },
    "terminal_outcomes": ["stopped", "disqualified", "draft_pr", "integrated", "deployed", "confirmed", "maintained", "closed"],
    "exclusive_outcome_groups": [["continue", "hold"], ["active_finding", "disqualified"]],
    "postcondition_requires": {
      "ticket_current": {"actions": ["fetch_ticket"], "evidence": ["ticket_snapshot"]},
      "scope_bound": {"actions": ["publish_scope"], "evidence": ["opening_receipt"]},
      "exact_subject_bound": {"actions": ["bind_subject"], "evidence": ["subject_receipt"]},
      "evidence_retained": {"actions": ["retain_evidence"], "evidence": ["execution_receipt"]},
      "handoff_readable": {"actions": ["publish_receipt", "readback_ticket"], "evidence": ["publication_readback"]},
      "eligibility_known": {"actions": ["evaluate_eligibility"], "evidence": ["assessment_receipt"]},
      "candidate_bounded": {"actions": ["edit_candidate"], "evidence": ["repair_receipt"]},
      "verification_complete": {"actions": ["run_checks", "evaluate_candidate"], "evidence": ["verification_receipt", "candidate_evaluations"]},
      "integration_admitted": {"actions": ["evaluate_merge"], "evidence": ["integration_receipt"]},
      "artifact_identified": {"actions": ["build_artifact"], "evidence": ["artifact_receipt"]},
      "deployment_observed": {"actions": ["observe_deployment"], "evidence": ["confirmation_receipt"]},
      "maintenance_current": {"actions": ["refresh_evidence"], "evidence": ["maintenance_receipt"]}
    }
  },
  "rules": [
    {
      "id": "DF-TICKET-CURRENT",
      "scope": "*",
      "strength": "must",
      "when": {"stage_state": "opened"},
      "requires": {"actions": ["fetch_ticket"], "evidence": ["ticket_snapshot"], "postconditions": ["ticket_current"]},
      "forbids": {"actions": ["infer_authority"]},
      "allows": {},
      "terminal": "either",
      "mutation": "none",
      "overrides": [],
      "precedence": 90,
      "safety": true,
      "fulfillment": "procedure"
    },
    {
      "id": "DF-SCOPE-BEFORE-WORK",
      "scope": "*",
      "strength": "must",
      "when": {"stage_state": "opened"},
      "requires": {"actions": ["publish_scope"], "evidence": ["opening_receipt"], "postconditions": ["scope_bound"]},
      "forbids": {"actions": ["execute_without_scope"]},
      "allows": {},
      "terminal": "either",
      "mutation": "none",
      "overrides": [],
      "precedence": 90,
      "safety": true,
      "fulfillment": "procedure"
    },
    {
      "id": "DF-EXACT-SUBJECT",
      "scope": "*",
      "strength": "must",
      "when": {"stage_state": "active"},
      "requires": {"actions": ["bind_subject"], "evidence": ["subject_receipt"], "postconditions": ["exact_subject_bound"]},
      "forbids": {},
      "allows": {"actions": ["execute_bounded_work"]},
      "terminal": "either",
      "mutation": "none",
      "overrides": [],
      "precedence": 90,
      "safety": true,
      "fulfillment": "procedure"
    },
    {
      "id": "DF-RETAIN-EVIDENCE",
      "scope": "*",
      "strength": "must",
      "when": {"stage_state": ["active", "handoff", "terminal"]},
      "requires": {"actions": ["retain_evidence"], "evidence": ["execution_receipt"], "postconditions": ["evidence_retained"]},
      "forbids": {"actions": ["discard_evidence"]},
      "allows": {},
      "terminal": "either",
      "mutation": "none",
      "overrides": [],
      "precedence": 90,
      "safety": true,
      "fulfillment": "procedure"
    },
    {
      "id": "DF-PUBLISH-READBACK",
      "scope": "*",
      "strength": "must",
      "when": {"stage_state": "handoff"},
      "requires": {"actions": ["publish_receipt", "readback_ticket"], "evidence": ["publication_readback"], "postconditions": ["handoff_readable"]},
      "forbids": {},
      "allows": {"transitions": ["handoff"]},
      "terminal": "either",
      "mutation": "none",
      "overrides": [],
      "precedence": 90,
      "safety": true,
      "fulfillment": "procedure"
    },
    {
      "id": "DF-TERMINAL-STOPS",
      "scope": "*",
      "strength": "must",
      "when": {"stage_state": "terminal", "disposition_class": ["stop", "complete"]},
      "requires": {"actions": ["stop_work"], "transitions": ["stop"], "outcomes": ["stopped"]},
      "forbids": {"transitions": ["continue"]},
      "allows": {},
      "terminal": "terminal",
      "mutation": "none",
      "overrides": [],
      "precedence": 100,
      "safety": true,
      "fulfillment": "procedure"
    },
    {
      "id": "DF-NO-IMPLICIT-AUTHORITY",
      "scope": "*",
      "strength": "must_not",
      "when": {"authorization": "absent"},
      "requires": {},
      "forbids": {"actions": ["merge_authorized", "deploy_authorized", "install_automation"]},
      "allows": {},
      "terminal": "either",
      "mutation": "none",
      "overrides": [],
      "precedence": 100,
      "safety": true,
      "fulfillment": "procedure"
    },
    {
      "id": "ORCH-SELECT-LIVE-STAGE",
      "scope": "orchestrate",
      "strength": "must",
      "when": {"stage_state": "active"},
      "requires": {"actions": ["select_stage"]},
      "forbids": {},
      "allows": {"transitions": ["continue", "hold", "stop"]},
      "terminal": "either",
      "mutation": "read_only",
      "overrides": [],
      "precedence": 20,
      "safety": false,
      "fulfillment": "procedure"
    }
  ]
}
```
<!-- defensefactory-stage-rules:end -->
