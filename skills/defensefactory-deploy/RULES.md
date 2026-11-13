# Deployment stage rules

Deployment identifies the built artifact and changes only the environment and
scope explicitly authorized by current ticket state.

<!-- defensefactory-stage-rules:start -->
```json
{
  "schema_version": 1,
  "stage": "deploy",
  "inherits": ["defensefactory/RULES.md"],
  "rules": [
    {
      "id": "DEPLOY-BUILD-IDENTIFIED-ARTIFACT",
      "scope": "deploy",
      "strength": "must",
      "when": {"stage_state": "active"},
      "requires": {"actions": ["build_artifact"], "evidence": ["artifact_receipt"], "postconditions": ["artifact_identified"]},
      "forbids": {"actions": ["edit_candidate"]},
      "allows": {"actions": ["rollback"]},
      "terminal": "either",
      "mutation": "write_allowed",
      "overrides": [],
      "precedence": 40,
      "safety": true,
      "fulfillment": "procedure"
    },
    {
      "id": "DEPLOY-AUTHORIZED-SCOPE-ONLY",
      "scope": "deploy",
      "strength": "may",
      "when": {"stage_state": "active", "authorization": "present"},
      "requires": {},
      "forbids": {},
      "allows": {"actions": ["deploy_authorized"], "evidence": ["deployment_receipt"], "transitions": ["deploy"], "outcomes": ["deployed"]},
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
