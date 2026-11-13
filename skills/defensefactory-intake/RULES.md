# Intake stage rules

Intake registers original finding evidence and exact scope without changing the
source under review or manufacturing a finding.

<!-- defensefactory-stage-rules:start -->
```json
{
  "schema_version": 1,
  "stage": "intake",
  "inherits": ["defensefactory/RULES.md"],
  "rules": [
    {
      "id": "INTAKE-REGISTER-ORIGINAL",
      "scope": "intake",
      "strength": "must",
      "when": {"stage_state": "active"},
      "requires": {"actions": ["register_finding", "preserve_original_evidence"], "evidence": ["intake_receipt"], "outcomes": ["registered"]},
      "forbids": {"actions": ["edit_candidate"]},
      "allows": {"transitions": ["handoff"]},
      "terminal": "nonterminal",
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
