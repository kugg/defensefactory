# Disposable-stage alpha harness

This harness qualifies one narrow release claim: each stage can reconstruct its
synthetic work from an exact source subject plus durable ledger receipts and
attachments after the previous stage container has been deleted.

It uses one Defense Factory image for the ledger, source fixture and all eight
stage invocations. The OpenTelemetry collector is a separately pinned
observability service. Stage containers are read-only, have fresh tmpfs
workspaces, no host mounts, no Docker socket and an internal-only network.
The common image pins its Python 3.12, Node 22 and Go 1.23 build stages by
registry digest so the repository tests and bundled Go fence evaluation use the
same declared toolchains as the candidate.

The deterministic worker is a transport and artifact-binding evaluation. It is
not a substitute for the separate fresh-session OpenCode experiment described
in the release plan.

## Run

```sh
python3 -m release.alpha.controller validate
python3 -m release.alpha.controller build --image defensefactory:alpha-candidate
python3 -m release.alpha.controller run \
  --image defensefactory:alpha-candidate \
  --scenario local_lifecycle \
  --through maintain \
  --output /private/path/to/new-alpha-output
```

Use a new output directory for every attempt. The controller exports the ticket
summary, every evidence attachment, the release manifest, stage stdout, service
logs and OTel file before deleting the Compose services and ledger volume.

For a real-ticket alpha boundary, use `--scenario active --through verify` and
stop before integration. That fixture still does not create a real draft PR;
the live-agent qualification owns that external effect.

Exercise the fail-closed handoff with a trusted test-controller mutation:

```sh
python3 -m release.alpha.controller run \
  --image defensefactory:alpha-candidate \
  --scenario active --through assess \
  --fault tamper_after_intake \
  --output /private/path/to/new-fault-output
```

The controller corrupts the already-published intake attachment inside the
synthetic ledger volume. The assessment container must exit nonzero and must not
publish a receipt. The injected failure is never enabled as a ledger API.

## Qualifications

- The local ledger has no authentication and must only be exposed on loopback
  with synthetic data.
- Capability profiles constrain the supported runner and document authority;
  they are not proof of hostile-container isolation.
- The Compose network intentionally has no external route. No Linear, GitHub,
  model-provider or product credentials belong in this trial.
- Final release artifacts must pin the image and collector by digest and pass a
  second-host replay before the alpha tag is cut.
