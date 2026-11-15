# Assessment stage rules

Assessment determines applicability before repair planning, separates candidate
observations from judgments, and stops on a justified source disposition.

<!-- defensefactory-stage-rules:start -->
```json
{
  "schema_version": 1,
  "stage": "assess",
  "inherits": ["defensefactory/RULES.md"],
  "rules": [
    {
      "id": "ASSESS-ELIGIBILITY-FIRST",
      "scope": "assess",
      "strength": "must",
      "when": {"stage_state": "opened"},
      "requires": {"actions": ["evaluate_eligibility"], "evidence": ["assessment_receipt"], "postconditions": ["eligibility_known"]},
      "forbids": {"actions": ["edit_candidate"]},
      "allows": {"actions": ["record_decision_request", "record_owner_decision", "detect_stalled_findings"], "evidence": ["decision_request", "decision_receipt", "stalled_findings_report"]},
      "terminal": "either",
      "mutation": "read_only",
      "overrides": [],
      "precedence": 40,
      "safety": true,
      "fulfillment": "procedure"
    },
    {
      "id": "ASSESS-INACTIVE-STOPS",
      "scope": "assess",
      "strength": "must",
      "when": {"stage_state": "active", "applicability": "inactive"},
      "requires": {"outcomes": ["disqualified"], "transitions": ["stop"]},
      "forbids": {"actions": ["edit_candidate"], "transitions": ["continue"]},
      "allows": {},
      "terminal": "terminal",
      "mutation": "read_only",
      "overrides": [],
      "precedence": 60,
      "safety": true,
      "fulfillment": "procedure"
    },
    {
      "id": "ASSESS-ACTIVE-BINDS-REPAIR",
      "scope": "assess",
      "strength": "must",
      "when": {"stage_state": "active", "applicability": "active"},
      "requires": {"actions": ["assess_finding", "issue_eligibility_receipt"], "evidence": ["assessment_receipt", "eligibility_receipt"], "outcomes": ["active_finding"], "transitions": ["continue"]},
      "forbids": {"actions": ["edit_candidate"]},
      "allows": {"actions": ["request_guidance", "discover_bugclass"], "evidence": ["e2e_guidance", "bugclass_discovery"]},
      "terminal": "nonterminal",
      "mutation": "read_only",
      "overrides": [],
      "precedence": 40,
      "safety": false,
      "fulfillment": "procedure"
    },
    {
      "id": "ASSESS-UNKNOWN-HOLDS",
      "scope": "assess",
      "strength": "must",
      "when": {"stage_state": "active", "applicability": "unknown"},
      "requires": {"actions": ["request_guidance"], "evidence": ["assessment_receipt"], "outcomes": ["hold"], "transitions": ["hold"]},
      "forbids": {"actions": ["edit_candidate"]},
      "allows": {"evidence": ["e2e_guidance"]},
      "terminal": "nonterminal",
      "mutation": "read_only",
      "overrides": [],
      "precedence": 40,
      "safety": false,
      "fulfillment": "procedure"
    },
    {
      "id": "ASSESS-DISPOSITION-PLANNED",
      "scope": "assess",
      "strength": "must",
      "when": {"stage_state": "handoff", "disposition_class": ["hold", "stop", "complete"]},
      "requires": {"actions": ["plan_lifecycle_transition"], "evidence": ["lifecycle_transition_plan"]},
      "forbids": {"actions": ["leave_unmarked_disposition"]},
      "allows": {"actions": ["apply_lifecycle_transition", "verify_lifecycle_readback"], "evidence": ["lifecycle_transition_readback"]},
      "terminal": "either",
      "mutation": "write_allowed",
      "overrides": [],
      "precedence": 70,
      "safety": true,
      "fulfillment": "procedure"
    },
    {
      "id": "ASSESS-AUTHORIZED-DISPOSITION-READBACK",
      "scope": "assess",
      "strength": "must",
      "when": {"stage_state": "handoff", "disposition_class": ["hold", "stop", "complete"], "lifecycle_authority": "present"},
      "requires": {"actions": ["apply_lifecycle_transition", "verify_lifecycle_readback"], "evidence": ["lifecycle_transition_readback"], "postconditions": ["disposition_visible"]},
      "forbids": {},
      "allows": {},
      "terminal": "either",
      "mutation": "write_required",
      "overrides": [],
      "precedence": 80,
      "safety": true,
      "fulfillment": "procedure"
    },
    {
      "id": "ASSESS-NO-LIFECYCLE-WITHOUT-AUTHORITY",
      "scope": "assess",
      "strength": "must_not",
      "when": {"stage_state": "handoff", "disposition_class": ["hold", "stop", "complete"], "lifecycle_authority": "absent"},
      "requires": {},
      "forbids": {"actions": ["apply_lifecycle_transition"]},
      "allows": {},
      "terminal": "either",
      "mutation": "read_only",
      "overrides": [],
      "precedence": 90,
      "safety": true,
      "fulfillment": "procedure"
    }
  ]
}
```
<!-- defensefactory-stage-rules:end -->
