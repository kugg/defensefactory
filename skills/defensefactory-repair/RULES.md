# Repair stage rules

Repair mutates only a bounded candidate when applicability and authority permit,
and stops at a draft PR with construction evidence.

<!-- defensefactory-stage-rules:start -->
```json
{
  "schema_version": 1,
  "stage": "repair",
  "inherits": ["defensefactory/RULES.md"],
  "rules": [
    {
      "id": "REPAIR-BUGCLASS-BEFORE-EDIT",
      "scope": "repair",
      "strength": "must",
      "when": {"stage_state": "active", "applicability": "active", "authorization": "present", "bugclass_state": "unknown"},
      "requires": {"actions": ["discover_bugclass", "evaluate_bugclass_membership", "define_bugclass", "design_class_repair"], "evidence": ["bugclass_discovery", "bugclass_membership", "bugclass_definition", "bugclass_repair_contract"], "postconditions": ["bugclass_evaluated"]},
      "forbids": {"actions": ["edit_candidate", "create_draft_pr"]},
      "allows": {},
      "terminal": "nonterminal",
      "mutation": "read_only",
      "overrides": [],
      "precedence": 60,
      "safety": true,
      "fulfillment": "procedure"
    },
    {
      "id": "REPAIR-BOUNDED-CANDIDATE",
      "scope": "repair",
      "strength": "must",
      "when": {"stage_state": "active", "applicability": "active", "authorization": "present", "bugclass_state": "evaluated"},
      "requires": {"actions": ["edit_candidate", "create_draft_pr"], "evidence": ["repair_receipt", "draft_pr_reference"], "outcomes": ["draft_pr"], "transitions": ["draft_pr"], "postconditions": ["candidate_bounded"]},
      "forbids": {},
      "allows": {"actions": ["execute_bounded_work"]},
      "terminal": "terminal",
      "mutation": "write_required",
      "overrides": [],
      "precedence": 40,
      "safety": false,
      "fulfillment": "procedure"
    },
    {
      "id": "REPAIR-NO-AUTHORITY-HOLDS",
      "scope": "repair",
      "strength": "must",
      "when": {"stage_state": "active", "authorization": "absent"},
      "requires": {"outcomes": ["hold"], "transitions": ["hold"]},
      "forbids": {"actions": ["edit_candidate", "create_draft_pr"]},
      "allows": {},
      "terminal": "nonterminal",
      "mutation": "read_only",
      "overrides": [],
      "precedence": 50,
      "safety": true,
      "fulfillment": "procedure"
    }
  ]
}
```
<!-- defensefactory-stage-rules:end -->
