# Validation scope

Validated on 2026-11-10. These are bounded checks of this experimental package.

The capture/handoff update passes **34 offline tests** in this repository. New
checks cover input-preserving comparison replay, erased original inputs/build
hosts, artifact/source mismatch and payload changes, failed build retention,
actual nonzero child assertions versus printed statuses, whole-root inventory
and subset limits, non-execution dependencies, native output caches/redactions,
changed evidence generations, forged readiness fields, signed-metadata transfer
and final runner audits. A next-stage fixture restores/runs an artifact after
the original build paths are deleted, without rewriting old receipts; repeated
handoffs retain a direct build origin rather than an accumulating archive chain.
Native connector events in the tests are explicitly
synthetic; model/service traffic is mocked or absent. This is not a new live
ticket-only agent-adherence experiment.

The prior initial-publication checks remain historical:

- The development helper suite completed 407 tests, with 3 skipped. Those skipped
  checks are not passes. Project-specific development fixtures are not published.
- This repository's 9 offline tests passed: installer preservation/idempotence,
  opening-required launch, actual producer failure capture, finished-receipt
  dependency enforcement, transport/auth behavior, and licensed relocated exports.
- All nine skill entrypoints passed frontmatter validation and shared-resource
  synchronization checks. Standalone exports were deterministic in the tests.
- A relocated assessment package ran the bundled Git/Go evaluation: baseline,
  refactor, owner-reviewed amendment and component transfers passed; bypass,
  deny-all and removed controls were detected; unreviewed amendment and unavailable
  introduction history remained inconclusive.
- Live qualification of the tools-only CodeIntel bridge initialized and discovered
  16 native tools. This does not establish exact-source indexing or semantic
  coverage for another deployment.

One intermediate development packaging evaluation failed on the expected missing-
history result before it saved the observation. Its cause was not established.
The evaluator now saves observations before assertions and retains both Git
repositories on failure. During the capture/handoff update, the exported matrix
reproduced the symptom and retained a concrete Go setup failure: access to the
host-default build cache was denied, with zero named tests executed. The evaluator
now uses a private disposable writable cache and records the selected toolchain.
This explains the newly preserved failure; it does not prove the earlier
unrecorded failure had the same cause. Failed output/fixtures remain preserved.

Live agent trials required manual scope bootstrap and operator correction. They
still showed capture/provenance mistakes, unsupported causal attribution and
incomplete exact-source indexing/runtime checks. Those results stay qualified in
their original ticket records. The new helper checks are prospective corrections,
not evidence that a fresh agent will consistently follow the workflow. Evaluate
that separately before expanding operational scope.
