# Maintenance stage rules

Maintenance is explicitly invoked, refreshes evidence without erasing history,
and may propose bounded corrective work without installing a scheduler.

<!-- defensefactory-stage-rules:start -->
```json
{
  "schema_version": 1,
  "stage": "maintain",
  "inherits": ["defensefactory/RULES.md"],
  "rules": [
    {
      "id": "MAINTAIN-BUGCLASS-VARIANTS",
      "scope": "maintain",
      "strength": "must",
      "when": {"stage_state": "active", "bugclass_state": "evaluated"},
      "requires": {"actions": ["discover_bugclass_variants"], "evidence": ["bugclass_discovery"]},
      "forbids": {"actions": ["discard_evidence"]},
      "allows": {},
      "terminal": "either",
      "mutation": "read_only",
      "overrides": [],
      "precedence": 45,
      "safety": false,
      "fulfillment": "procedure"
    },
    {
      "id": "MAINTAIN-REFRESH-EVIDENCE",
      "scope": "maintain",
      "strength": "must",
      "when": {"stage_state": "active"},
      "requires": {"actions": ["refresh_evidence"], "evidence": ["maintenance_receipt"], "outcomes": ["maintained"], "postconditions": ["maintenance_current"]},
      "forbids": {"actions": ["install_automation", "discard_evidence"]},
      "allows": {"transitions": ["handoff"]},
      "terminal": "terminal",
      "mutation": "read_only",
      "overrides": [],
      "precedence": 50,
      "safety": true,
      "fulfillment": "procedure"
    },
    {
      "id": "MAINTAIN-CORRECTIVE-WORK-AUTHORIZED",
      "scope": "maintain",
      "strength": "may",
      "when": {"stage_state": "active", "authorization": "present"},
      "requires": {},
      "forbids": {},
      "allows": {"actions": ["open_corrective_work"]},
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
