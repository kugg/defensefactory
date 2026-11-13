# Confirmation stage rules

Confirmation observes the identified deployed artifact and declared rollout
scope before requesting any lifecycle closure.

<!-- defensefactory-stage-rules:start -->
```json
{
  "schema_version": 1,
  "stage": "confirm",
  "inherits": ["defensefactory/RULES.md"],
  "rules": [
    {
      "id": "CONFIRM-DEPLOYED-SCOPE",
      "scope": "confirm",
      "strength": "must",
      "when": {"stage_state": "active"},
      "requires": {"actions": ["observe_deployment"], "evidence": ["confirmation_receipt"], "outcomes": ["confirmed"], "postconditions": ["deployment_observed"]},
      "forbids": {"actions": ["edit_candidate"]},
      "allows": {"actions": ["request_closure"], "transitions": ["close"], "outcomes": ["closed"]},
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
