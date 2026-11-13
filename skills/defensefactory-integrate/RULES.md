# Integration stage rules

Integration evaluates the actual merge subject and may merge only under existing
authorization and the repository's governing policy.

<!-- defensefactory-stage-rules:start -->
```json
{
  "schema_version": 1,
  "stage": "integrate",
  "inherits": ["defensefactory/RULES.md"],
  "rules": [
    {
      "id": "INTEGRATE-EVALUATE-SUBJECT",
      "scope": "integrate",
      "strength": "must",
      "when": {"stage_state": "active"},
      "requires": {"actions": ["evaluate_merge"], "evidence": ["integration_receipt"], "postconditions": ["integration_admitted"]},
      "forbids": {"actions": ["edit_candidate"]},
      "allows": {"transitions": ["hold", "handoff"]},
      "terminal": "either",
      "mutation": "read_only",
      "overrides": [],
      "precedence": 50,
      "safety": true,
      "fulfillment": "procedure"
    },
    {
      "id": "INTEGRATE-BUGCLASS-CLAIM",
      "scope": "integrate",
      "strength": "must",
      "when": {"stage_state": "active", "bugclass_state": "evaluated"},
      "requires": {"actions": ["evaluate_bugclass"], "evidence": ["bugclass_proof_matrix", "bugclass_verification"]},
      "forbids": {},
      "allows": {},
      "terminal": "either",
      "mutation": "read_only",
      "overrides": [],
      "precedence": 55,
      "safety": true,
      "fulfillment": "procedure"
    },
    {
      "id": "INTEGRATE-MERGE-AUTHORIZED",
      "scope": "integrate",
      "strength": "may",
      "when": {"stage_state": "active", "authorization": "present"},
      "requires": {},
      "forbids": {},
      "allows": {"actions": ["merge_authorized"], "transitions": ["merge"], "outcomes": ["integrated"]},
      "terminal": "either",
      "mutation": "write_allowed",
      "overrides": [],
      "precedence": 20,
      "safety": false,
      "fulfillment": "procedure"
    }
  ]
}
```
<!-- defensefactory-stage-rules:end -->
