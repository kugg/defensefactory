# Verification stage rules

Verification evaluates the exact candidate and keeps checker candidates distinct
from evaluation decisions and coverage-qualified claim state.

<!-- defensefactory-stage-rules:start -->
```json
{
  "schema_version": 1,
  "stage": "verify",
  "inherits": ["defensefactory/RULES.md"],
  "rules": [
    {
      "id": "VERIFY-BUGCLASS-MATRIX",
      "scope": "verify",
      "strength": "must",
      "when": {"stage_state": "active", "bugclass_state": "evaluated"},
      "requires": {"actions": ["evaluate_bugclass"], "evidence": ["bugclass_proof_matrix", "bugclass_verification"]},
      "forbids": {"actions": ["edit_candidate"]},
      "allows": {},
      "terminal": "either",
      "mutation": "read_only",
      "overrides": [],
      "precedence": 55,
      "safety": true,
      "fulfillment": "procedure"
    },
    {
      "id": "VERIFY-EXACT-CANDIDATE",
      "scope": "verify",
      "strength": "must",
      "when": {"stage_state": "active"},
      "requires": {"actions": ["run_checks", "evaluate_candidate"], "evidence": ["verification_receipt", "candidate_evaluations"], "outcomes": ["verified"], "postconditions": ["verification_complete"]},
      "forbids": {"actions": ["edit_candidate"]},
      "allows": {"transitions": ["handoff"]},
      "terminal": "terminal",
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
