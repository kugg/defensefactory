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
      "id": "REPAIR-BOUNDED-CANDIDATE",
      "scope": "repair",
      "strength": "must",
      "when": {"stage_state": "active", "applicability": "active", "authorization": "present"},
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
