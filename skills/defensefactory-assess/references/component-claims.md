# Component-owned architectural claims and invariant contracts

`RULES.md` at the owning component root is the sole authored source for that
component's boundaries and claims. Developers and agents amend it through the
repository's normal review and ownership policy. It is not a security-team lock
file. A repository-root file is appropriate when the repository is itself the
component; split a child file only at a real independently owned boundary.

The file uses the deliberately small `defensefactory/rules/v1` Markdown grammar.
It records stable component, claim and invariant IDs; concise boundaries;
preserved behavior; referenced contracts; and fence policy. The parser builds a
versioned Markdown AST. Unknown normative headings, malformed identities,
hidden normative content and broken references fail closed. Ordinary explanatory
prose outside claim sections is preserved and excluded from semantic diffs.

Start from [component-RULES.md](component-RULES.md). Check and inspect it with:

```text
python3 <skill>/scripts/claim-rules.py check <component>/RULES.md
python3 <skill>/scripts/claim-rules.py extract <component>/RULES.md
python3 <skill>/scripts/claim-rules.py semantic-diff --repo <repo> --path <component>/RULES.md --base <full-ref> --candidate <full-ref>
```

## Contracts are developer-owned observation mechanisms

Each contract reference resolves to a strict JSON descriptor shaped like
[contract-descriptor.json](contract-descriptor.json). The descriptor binds a
stable contract ID to one claim and invariant, its engine and entry point,
applicability, actual coverage and limitations, immutable control-introduction
provenance, runtime/tool needs, hard/soft observation kind and mandatory policy.
It contains no computed hashes, pass verdicts, model output or ticket journal.

Supported adapter classes are `cue`, `codeql`, `semgrep`, `opengrep`, `test`,
`type`, `lint`, `ast`, `runtime`, `formal` and `markdown-example`. CUE validates
structured configuration or extracted facts; it does not parse arbitrary source
without an extractor. CodeQL, pattern engines and language-specific analyzers
produce candidates. Tests, types and linters can be hard fences. Markdown
examples are always optional soft observations. Component descriptors may name
requirements but cannot grant network access or choose arbitrary process
commands; test and custom-adapter commands come from the trusted run input.

Use `claim-rules.py contracts` to resolve descriptors at an exact Git commit and
`claim-rules.py run` to execute available adapters in a detached source archive.
Every raw output is retained beside `contract-run.json`; observations normalize
to `defensefactory/candidate/v1` with exact subject, source location, coverage and
raw-result reference. Missing engines and incomplete coverage are
`inconclusive`, never zero findings.

## Candidates, evaluations and claim state

A candidate is a possible invariant violation, not a verdict. Save it unchanged.
An evaluator produces a separate `defensefactory/evaluation/v1` record with its
identity/version, evidence, explanation, limitations, next action and one of:

* `confirmed_violation`;
* `rejected_false_positive`;
* `inconclusive`;
* `duplicate`;
* `not_applicable`.

`claim-rules.py status` computes state from the exact run, declared mandatory
coverage and separate evaluations. Zero candidates satisfy a claim only within
adequate declared coverage. Missing engines, partial coverage or unevaluated
candidates remain inconclusive. Confirmed mandatory violations apply the
component's fence policy. A soft fence is never represented as hard proof.

Receipts hold exact source/rules/descriptor blobs, resolved Git subjects, engine
versions, raw outputs, evaluations, hashes and limitations. Share them through
the ticket handoff; local paths alone are not durable evidence.

## Stage use

| Stage | Use |
| --- | --- |
| Assessment | Parse the owning rules, run applicable contracts, retain candidates, and identify missing coverage without treating raw findings as confirmed. |
| Repair | Preserve claim meaning unless an owner-reviewed amendment is required; implement the control and a hard contract/fence for the invalidating invariant. |
| Verification | Resolve and run mandatory contracts against the exact candidate, evaluate candidates separately, and exercise preserved behavior. |
| Integration | Compare the actual base and merge subject semantically, require valid references/coverage, and apply the repository's native review plus declared claim policy. |
| Maintenance | Re-run explicitly, detect stale contracts or changed coverage, and open/reuse corrective work without rewriting historical receipts. |

## Legacy migration

`claims.json` is a legacy input, not a second current authority.

* Legacy only: read it, generate a proposed `RULES.md` plus descriptors with
  explicit owner-review limitations, and do not delete the source automatically.
* Transitional pair: compare the semantics legacy schema 2 could express. Block
  divergence. Remove `claims.json` only in an explicit reviewed migration.
* RULES-only: use `RULES.md`; reintroducing `claims.json` is duplicate authored
  state and must not become authoritative.

Run:

```text
python3 <skill>/scripts/claim-rules.py migrate <component>/claims.json <component>/RULES.md --component-type <type> --owner @owner --descriptors <component>/contracts
```

The migration is intentionally reported as `proposed_incomplete` until owners
replace inferred boundaries, establish descriptor coverage and reconcile paths.
Stable IDs and repository-qualified introduction provenance survive component or
repository moves; unavailable history remains an explicit limitation.
