# Batch summary reconciliation

A prose batch summary is a projection of ticket outcomes, never an independent
source of truth. Before publishing one, save the selected tickets and every
declared outcome as one JSON manifest, then run:

```sh
python3 scripts/batch-summary.py --input batch-summary.json --output batch-summary-reconciliation.json
```

The root groups must partition `selected` exactly. A group with nested `groups`
must likewise be partitioned exactly by its children. Declared totals must equal
the number of enumerated ticket identifiers. Tickets may not be omitted,
invented, duplicated or assigned to two sibling groups.

```json
{
  "schema_version": 1,
  "batch_id": "batch-example",
  "declared_total": 3,
  "selected": ["SEC-1", "SEC-2", "SEC-3"],
  "groups": {
    "early_disqualified": {
      "declared_count": 1,
      "tickets": ["SEC-1"]
    },
    "active": {
      "declared_count": 2,
      "tickets": ["SEC-2", "SEC-3"],
      "groups": {
        "draft_pr": {"declared_count": 1, "tickets": ["SEC-2"]},
        "hold": {"declared_count": 1, "tickets": ["SEC-3"]}
      }
    }
  }
}
```

Only a `satisfied` reconciliation receipt permits publication. Attach both the
manifest and receipt, cite their digests in the summary, then fetch the ticket
and verify readback. Preserve a mistaken prior summary and publish an additive
correction linked to it; never rewrite receipts or silently replace history.

This check establishes arithmetic and partition consistency. It does not prove
the correctness of any disposition, evidence, repair or ticket state.
