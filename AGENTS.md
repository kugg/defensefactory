# Maintaining the publishable factory

Keep skills project agnostic. Source, models, environments, credentials and E2E
plans come from the current ticket and operator-provided host capabilities.
Keep user settings and raw trial data outside this repository. Do not add real
credentials, private ticket IDs, host paths, demo adapters or personal defaults.

The canonical shared implementation/resources are under `skills/defensefactory`.
Each stage keeps its own `SKILL.md`; synchronize common `scripts/`, `references/`
and license with `scripts/package-skills.py`. Do not hot-update frozen trials.

Use local disposable tests and the bundled evaluation. Do not contact live
services, mutate tickets, start model calls or publish from a test. Preserve
failed evidence and state the actual qualification of any live experiment.
The MIT copyright notice must accompany every standalone package.

## One installer

Keep exactly one supported installation workflow. The public source-checkout
entry point is `scripts/install-defensefactory`; it may be a small prerequisite
bootstrap, but it must invoke the sole canonical implementation at
`skills/defensefactory/scripts/install-defensefactory.py`. Extend and version
that implementation and its environment profile instead of adding a parallel
installer, wrapper or profile format.

This repository is pre-release. When a new implementation replaces an earlier
one, remove the superseded entry point, implementation, documentation and tests
in the same change. Do not retain or describe code as “legacy” unless a concrete
current user, deployed installation and migration requirement are documented in
the governing ticket. Standalone-package tests must exercise the canonical
installer, and repository tests must fail if another installer-shaped entry
point appears.
