# Disposable component-fence evaluation

Use this optional helper evaluation before adapting the skill to a project or
after changing its bundled claim/fence helpers. It runs actual Git and Go
processes against a generated component, not against a ticket or product. It
does not require Linear, GitHub, CodeIntel, Docker, a classifier, or credentials.

Requirements: Python 3.12+, Git, Go 1.22+ already installed on PATH, and a POSIX
host (Linux/macOS). Invoke from any directory, using the installed skill path:

```sh
python3 /path/to/defensefactory/scripts/eval-fences.py --output /new/evaluation-directory
```

The output directory must not exist. Reusing it fails without overwriting old
evidence. The script creates disposable repositories, executes named negative
and positive Go tests, and keeps receipts plus Git bundles in that directory.
No dependencies or toolchains are downloaded. No remote repository, ticket,
installation, or lifecycle status is changed. A failed evaluation exits nonzero;
keep its partial output for investigation and use a new directory for another run.

Expected cases cover a correct control, harmless refactor, unconditional bypass,
deny-all, removed test, claim amendment under an explicitly selected example
owner-review policy, directory move, cross-repository transfer, and unavailable
original history. The last case must remain inconclusive. See `summary.json`
and the per-case receipts for observed results, logs and exact revisions. The
authored component example has one claim definition represented by synchronized `claims.json` and `RULES.md`, with control introduction refs;
computed identities and verdicts live in receipts. The policy fixture is not a
universal extra security approval requirement: developers own their claims under
their normal repository policy.

This is a synthetic helper regression evaluation. It does not exercise live
ticket publication, fresh-context handoff, stage admission, CodeIntel indexing,
formal checking, runtime deployment, or independent acceptance. It cannot certify
a real project's security or the agent's adherence to these skills. Use the
ticket's actual contract, adapters and environment for case verification. Do not
publish these synthetic owner-review objects as actual approval records.
