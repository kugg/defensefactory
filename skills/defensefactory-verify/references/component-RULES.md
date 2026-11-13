# Component security rules

Place this file beside the owning component's `claims.json`. Developers and
agents own it with the component through normal repository review. It is not a
security-team lock file.

The reserved block is the human review surface for `claims.json` and must hold
the exact same schema-2 object. Replace every placeholder, then run:

```text
python3 <skill>/scripts/claim-rules.py --claims <component>/claims.json --rules <component>/RULES.md --check
```

Computed hashes, execution verdicts, model output and ticket journals belong in
receipts, not in this authored definition.

## Exact claim shape

| Object | Required fields | Meaning |
| --- | --- | --- |
| Catalog | `schema_version`, `component`, `claims`, `fences`, `bug_classes` | One portable definition at the owning component root. |
| Claim | `id`, `statement`, `preserves`, `bug_classes`, `fences` | The security property, legitimate behavior, mapped failure classes and enforcing fences. |
| Bug class | `id`, `definition` | A recurring failure mechanism; optional `cwe` is descriptive, not coverage proof. |
| Fence | `id`, `kind`, `mechanism`, `controls` | A hard deterministic check or complementary soft intent. Hard fences also require `check`. |
| Control | `path`, `selector`, `introduced` | Current component-relative control and its stable selector. |
| Introduction | `repository`, `ref`, `path` | Original repository, full introducing commit and original path; optional `selector` records a reviewed rename. |

<!-- defensefactory-claims:start -->
```json
{
  "bug_classes": [
    {
      "definition": "<recurring failure mechanism>",
      "id": "<class-id>"
    }
  ],
  "claims": [
    {
      "bug_classes": [
        "<class-id>"
      ],
      "fences": [
        "<fence-id>"
      ],
      "id": "<claim-id>",
      "preserves": [
        "<legitimate behavior>"
      ],
      "statement": "<canonical property>"
    }
  ],
  "component": "<stable-component-id>",
  "fences": [
    {
      "check": "<trusted-check-id>",
      "controls": [
        {
          "introduced": {
            "path": "<original-repo-relative-path>",
            "ref": "<full-introduction-commit>",
            "repository": "<original-repository>"
          },
          "path": "<component-relative-control-path>",
          "selector": "<test-or-rule-name>"
        }
      ],
      "id": "<fence-id>",
      "kind": "hard",
      "mechanism": "test"
    }
  ],
  "schema_version": 2
}
```
<!-- defensefactory-claims:end -->
