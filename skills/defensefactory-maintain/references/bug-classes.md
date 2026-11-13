# Architectural bug classes in repair and verification

A bug class groups findings that invalidate the same canonical claim/invariant
inside a compatible component boundary. Titles, CWE labels, embeddings, scanner
identity and source proximity can generate candidates only. Durable membership
requires a separate bounded evaluation with evidence and evaluator identity.

Run this workflow before product edits when authoring a repair PR:

1. Resolve the owning component `RULES.md`, claim, invariant, boundary and exact
   repair subject from the ticket/assessment.
2. Through the native ticket connector, retrieve current and historical findings
   across the authorized project/lifecycle scope. Retain exact queries, linked
   repairs, repository history, available exact-ref source intelligence, existing
   contracts and every coverage limitation.
3. Save normalized ticket/query inputs and run `bugclass.py discover`. The output
   is a candidate set, never membership.
4. Compare every candidate's invariant, boundary, component relationship,
   behavior and fence coverability. Run `classify`; each candidate becomes
   included, excluded, duplicate or inconclusive. Preserve lifecycle state and
   the original candidate evidence. Retain any classifier/model proposal as an
   external proposal; disagreement is expected and the durable evaluated decision
   remains authoritative.
5. Run `define`, then `repair-contract`. The latter requires primary, retry,
   fallback, alternate-constructor and configuration-path analysis; preserved
   behavior; other affected claims; one deterministic hard fence; and a
   regression contract or explicit limitation for every included historical
   member. Save these receipts before any product edit. A model can prioritize
   candidates but cannot establish membership or closure.
6. Construct the bounded candidate. Encode historical variants with the most
   reliable efficient mechanism available in that repository—tests, types,
   policy/static contracts, runtime assertions or formal scenarios. Static tool
   output remains a candidate until evaluated.
7. At verification, run `variant-matrix` against the exact PR head and actual
   merge subject. Every included current and historical ticket needs raw contract
   output plus a separate evaluation. Run `verify` with the governing claim,
   required hard-fence evaluation, every preserved legitimate behavior, and every
   other claim named by the repair contract. Zero findings count only with
   adequate declared coverage. A failing positive behavior or affected claim is
   a class violation, not a successful repair.
8. Run `pr-section`, then `ticket-links`. Apply its idempotent effect keys through
   native PR/Linear tools. Link every included current and historical ticket in
   both directions without reopening or changing historical lifecycle state.
   Retrieve both sides and run `readback`; resume only missing/unreconciled effect
   keys after partial failure.

The helper is deterministic and never calls Linear, GitHub, CodeIntel or a
classifier. It consumes retained external observations and creates new receipts:

```text
python3 <skill>/scripts/bugclass.py discover --input discovery.json --output NEW/discovery.json
python3 <skill>/scripts/bugclass.py classify --input membership.json --output NEW/membership.json
python3 <skill>/scripts/bugclass.py define --input definition.json --output NEW/class.json
python3 <skill>/scripts/bugclass.py repair-contract --input design.json --output NEW/repair-contract.json
python3 <skill>/scripts/bugclass.py variant-matrix --input matrix.json --output NEW/matrix.json
python3 <skill>/scripts/bugclass.py verify --input verification.json --output NEW/verification.json
python3 <skill>/scripts/bugclass.py pr-section --input pr.json --output NEW/pr-section.json
python3 <skill>/scripts/bugclass.py ticket-links --input links.json --output NEW/link-plan.json
python3 <skill>/scripts/bugclass.py readback --input readback.json --output NEW/link-readback.json
```

Start a concrete nine-step walk with one current and one historical ticket using:

```sh
python3 <skill>/scripts/bugclass.py templates --output NEW/walk-inputs
```

The command writes nine literal JSON inputs named in execution order. The first
contains both ticket lifecycles; later files use `receipt_file` links to the exact
prior output names. Replace every `__REPLACE__`, complete empty decision/proof
arrays from retained evidence, and use a fresh output path for each command. The
readback input is intentionally completed last: copy the actual effect keys and
PR-section content digest from the generated linkage plan and native readback,
never predict them. This makes the example a safe walk rather than a set of
unbound snippets.

Use `{"receipt_file":"relative/or/absolute.json"}` anywhere a previously saved
receipt is expected. Paths are resolved relative to the current input file. The
CLI refuses to overwrite outputs so discovery, candidate, membership, repair,
execution, evaluation and linkage generations cannot collapse into memory-only
state. Ticket and evidence references must be shareable; `file://` references are
rejected.

`lineage` is empty when the component has not moved. Each nonempty entry should
identify the prior repository and component, the move/split/rename relationship,
and a shareable evidence reference; lineage explains portability and never adds
members by itself. `coverage_expectations` names the path families that must be
considered (at minimum primary, retry, fallback, alternate-constructor and
configuration), the legitimate behavior that must remain, the hard fence expected
to cover them, and any known boundary that remains outside the class. It is not a
promise that a scanner has complete coverage: the proof matrix still records
per-member limitations.

Technical outcomes are:

* `class_remediated_within_scope`: every included current and historical member,
  claim and hard fence pass at the exact merge subject with adequate coverage;
* `member_fix_only`: the trigger passes but at least one class member is not
  covered, without an unresolved mandatory-evidence condition;
* `class_inconclusive`: membership, engine, history, runtime or coverage is
  insufficient;
* `class_violated`: an included member, claim or hard fence still fails;
* `class_definition_rejected`: the proposed class combines incompatible
  boundaries/invariants.

These outcomes describe the candidate/current architecture. They never claim to
rewrite historical commits. Excluded or inconclusive tickets are not described
as fixed. Repair reports the technical class result separately from whether the
agent followed discovery-before-edit, capture and linkage/readback procedures.
The integration stage applies project policy to `member_fix_only` and
`class_inconclusive`; helpers do not grant merge authority.
