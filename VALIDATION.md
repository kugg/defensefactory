# Prepublication validation

Validated on 2026-11-10. These are bounded checks of this experimental package.

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
repositories on failure. Subsequent persisted evaluation, full suite and exported
evaluation passed; this does not retroactively explain the earlier failure.

Live agent trials required manual scope bootstrap and operator correction. They
still showed capture/provenance mistakes, unsupported causal attribution and
incomplete exact-source indexing/runtime checks. Those results stay qualified in
their original ticket records. The new helper checks are prospective corrections,
not evidence that a fresh agent will consistently follow the workflow. Evaluate
that separately before expanding operational scope.
