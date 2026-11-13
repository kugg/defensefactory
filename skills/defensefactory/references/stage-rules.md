# Stage rules and procedure conformance

Each factory package has a short `RULES.md` for its normative invariants and a
`SKILL.md` for the procedure that performs them. The orchestration package owns
the universal vocabulary and rules once. Stage packages inherit that source and
may strengthen it; they cannot silently weaken a universal safety rule.

The delimited JSON block in `RULES.md` is the machine-readable policy. Ordinary
Markdown explains intent but is not compiled into new authority. Stable rule IDs
let receipts and procedure maps cite policy without copying it. Context-specific
profiles are additional, explicitly selected rule documents; their bytes and
effective semantics are bound in the receipt.

Validate a source checkout or installed package before publishing stage scope:

```sh
python3 <package>/scripts/stage-rules.py check <package> --output <new-receipt.json>
```

Use `--profile <file>` once per selected policy profile. A standalone stage
archive carries the one universal `RULES.md` under
`dependencies/defensefactory/RULES.md`; an ordinary installation resolves the
sibling `defensefactory` package. If both are present their bytes must agree;
no source or disagreeing sources are errors.

The validator checks schema and bounded semantics, inherited rule identity,
condition overlap, required-versus-forbidden effects, terminal/continue and
read-only/write conflicts, unreachable postconditions, exception precedence,
override cycles and mutually exclusive outcomes. It exhaustively enumerates the
declared finite condition vocabulary. A conflict receipt contains the rule IDs,
overlapping assignment, effects and a remediation hint. Unsupported semantics
are `inconclusive`; violations and inconclusive results both block publication.

The delimited procedure map in `SKILL.md` maps every H1/H2 procedure section to
stable rules and to the actions/evidence it produces. The checker rejects
missing or orphaned mappings, unauthorized actions and mandatory effects without
a producer. It does not prove that an agent followed the procedure or that an
operator-only judgment is correct.

`stage-scope` validates the package again and embeds a compact binding containing
the validator version, exact effective-rule digest, every source byte digest and
the validation-receipt digest. The full deterministic validation receipt remains
inside the preparation record. `stage-start` rebuilds both from the current
files, and refuses changed, missing or non-satisfied rules before permitting case
work. Rule-file hashes belong in these receipts, not in authored policy prose.

Changing only explanatory Markdown changes the source binding but not the
effective semantic digest. Changing a compiled rule changes both. Preserve old
receipts; never overwrite a previous validation to make a later ruleset appear
to have governed earlier work.
