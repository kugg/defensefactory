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
