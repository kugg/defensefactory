"""Build and run the disposable-container alpha handoff qualification."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

from .protocol import (STAGES, TICKET_SCHEMA, canonical, identity, read_json, sha256,
                       validate_profiles, validate_ticket)
from .telemetry import attempt_trace_id, emit as emit_span, now_ns


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
COMPOSE = HERE / "compose.yaml"
PROFILES = HERE / "capability-profiles.json"
DOCKERFILE = HERE / "Dockerfile"


class TrialError(RuntimeError):
    pass


def command(argv, *, env=None, cwd=ROOT, check=True) -> subprocess.CompletedProcess:
    completed = subprocess.run(argv, cwd=cwd, env={**os.environ, **(env or {})},
                               capture_output=True, text=True)
    if check and completed.returncode:
        raise TrialError("Command failed (" + str(completed.returncode) + "): " +
                         " ".join(argv) + "\n" + completed.stdout + completed.stderr)
    return completed


def docker_compose(project: str, env: dict, *args, check=True):
    return command(["docker", "compose", "-p", project, "-f", str(COMPOSE), *args],
                   env=env, check=check)


def http(method: str, url: str, body: bytes | None = None,
         content_type: str = "application/json") -> bytes:
    headers = {"Content-Type": content_type} if body is not None else {}
    with urlopen(Request(url, method=method, data=body, headers=headers), timeout=15) as response:
        return response.read()


def wait_json(url: str, seconds: float = 45.0) -> dict:
    deadline = time.time() + seconds
    error = None
    while time.time() < deadline:
        try:
            return json.loads(http("GET", url))
        except (OSError, URLError, json.JSONDecodeError) as caught:
            error = caught
            time.sleep(0.25)
    raise TrialError(f"Service did not become ready at {url}: {error}")


def tree_digest(path: Path) -> str:
    entries = []
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        entries.append({"path": str(item.relative_to(path)), "sha256": sha256(item.read_bytes())})
    return identity(entries)


def base_images() -> list[str]:
    values = [line.strip().split()[1] for line in DOCKERFILE.read_text().splitlines()
              if line.strip().startswith("FROM ") and len(line.strip().split()) >= 2]
    if not values or any(re.fullmatch(r"[^\s@]+@sha256:[0-9a-f]{64}", value) is None
                         for value in values):
        raise TrialError("Every alpha Dockerfile base image must be pinned by registry digest")
    return values


def current_commit() -> str:
    value = command(["git", "rev-parse", "HEAD"]).stdout.strip()
    if re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise TrialError("Repository HEAD is not an exact Git commit")
    return value


def ensure_clean() -> None:
    status = command(["git", "status", "--porcelain", "--untracked-files=all"]).stdout
    if status.strip():
        paths = [line[3:] for line in status.splitlines()[:8]]
        raise TrialError("Release build/run requires a clean exact Git subject; changed paths: " +
                         ", ".join(paths))


def image_digest(image: str) -> str:
    value = command(["docker", "image", "inspect", "--format", "{{.Id}}", image]).stdout.strip()
    if re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None:
        raise TrialError("Docker returned no exact local image digest")
    return value


def image_revision(image: str) -> str:
    value = command(["docker", "image", "inspect", "--format",
                     '{{index .Config.Labels "org.opencontainers.image.revision"}}', image]).stdout.strip()
    if re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise TrialError("Candidate image has no exact source revision label")
    return value


def pinned_collector(reference: str) -> str:
    if "@sha256:" in reference:
        return reference
    command(["docker", "pull", reference])
    raw = command(["docker", "image", "inspect", "--format", "{{json .RepoDigests}}",
                   reference]).stdout
    digests = json.loads(raw)
    if not digests:
        raise TrialError("Collector image has no registry digest")
    repository = reference.rsplit(":", 1)[0] if ":" in reference.rsplit("/", 1)[-1] else reference
    matches = [item for item in digests if item.startswith(repository + "@sha256:")]
    return matches[0] if matches else digests[0]


def build(image: str, opencode_version: str) -> dict:
    ensure_clean()
    commit = current_commit()
    command(["docker", "build", "--file", str(HERE / "Dockerfile"),
             "--build-arg", f"OPENCODE_VERSION={opencode_version}",
             "--build-arg", f"FACTORY_RELEASE_COMMIT={commit}",
             "--tag", image, str(ROOT)])
    digest = image_digest(image)
    if image_revision(image) != commit:
        raise TrialError("Built image revision label differs from the exact release commit")
    inventory = json.loads(command(["docker", "run", "--rm", image, "inventory"]).stdout)
    return {"image": image, "image_digest": digest, "git_commit": commit,
            "inventory": inventory}


def stages_for(scenario: str, through: str) -> list[str]:
    if scenario == "early_disposition":
        return ["intake", "assess"]
    index = STAGES.index(through)
    return list(STAGES[:index + 1])


def release_manifest(image: str, digest: str, commit: str, inventory: dict,
                     collector: str) -> dict:
    profiles = validate_profiles(read_json(PROFILES))
    return {
        "schema": "defensefactory/alpha-release-manifest/v1",
        "candidate": "v0.1.0-alpha.1",
        "git_commit": commit,
        "image": image,
        "image_digest": digest,
        "base_images": base_images(),
        "capability_profiles_sha256": sha256(PROFILES.read_bytes()),
        "capability_profiles_identity": identity(profiles),
        "skills": {path.name: tree_digest(path) for path in sorted((ROOT / "skills").iterdir())
                   if path.is_dir()},
        "dependency_inventory": inventory,
        "otel_collector_image": collector,
        "qualification": "Candidate manifest from a local build; publication and replay are separate gates.",
    }


def export_run(ledger: str, run_id: str, output: Path, manifest: dict) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    summary = json.loads(http("GET", f"{ledger}/v1/runs/{run_id}"))
    (output / "run-summary.json").write_bytes(canonical(summary))
    (output / "release-manifest.json").write_bytes(canonical(manifest))
    evidence = output / "evidence"
    evidence.mkdir(exist_ok=True)
    for receipt in summary["receipts"]:
        binding = receipt["output_attachment"]
        raw = http("GET", f"{ledger}/v1/runs/{run_id}/attachments/{binding['sha256']}")
        if len(raw) != binding["bytes"] or sha256(raw) != binding["sha256"]:
            raise TrialError("Exported evidence does not match its durable receipt")
        (evidence / f"{receipt['stage']}.json").write_bytes(raw)
    identities = [item["container_identity"] for item in summary["receipts"]]
    if len(identities) != len(set(identities)):
        raise TrialError("Two stages reported the same container identity")
    return summary


def run_trial(image: str, output: Path, run_id: str, scenario: str,
              through: str, keep_services: bool = False, fault: str = "") -> dict:
    if shutil.which("docker") is None:
        raise TrialError("Docker CLI is required")
    ensure_clean()
    commit = current_commit()
    digest = image_digest(image)
    if image_revision(image) != commit:
        raise TrialError("Candidate image was not built from the current exact release commit")
    inventory = json.loads(command(["docker", "run", "--rm", image, "inventory"]).stdout)
    collector = pinned_collector(os.environ.get(
        "FACTORY_OTEL_IMAGE", "otel/opentelemetry-collector-contrib:0.114.0"))
    manifest = release_manifest(image, digest, commit, inventory, collector)
    requested_stages = stages_for(scenario, through)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    otel_dir = output / "otel"
    otel_dir.mkdir(exist_ok=False)
    os.chmod(otel_dir, 0o777)
    project = "dfa-" + re.sub(r"[^a-z0-9]", "", run_id.lower())[:24]
    env = {
        "FACTORY_IMAGE": image,
        "FACTORY_OUTPUT_ROOT": str(output),
        "FACTORY_LEDGER_PORT": os.environ.get("FACTORY_LEDGER_PORT", "18080"),
        "FACTORY_SOURCE_PORT": os.environ.get("FACTORY_SOURCE_PORT", "18081"),
        "FACTORY_OTEL_HTTP_PORT": os.environ.get("FACTORY_OTEL_HTTP_PORT", "14318"),
        "FACTORY_OTEL_IMAGE": collector,
    }
    ledger = f"http://127.0.0.1:{env['FACTORY_LEDGER_PORT']}"
    source = f"http://127.0.0.1:{env['FACTORY_SOURCE_PORT']}"
    telemetry = f"http://127.0.0.1:{env['FACTORY_OTEL_HTTP_PORT']}"
    attempt_trace = attempt_trace_id(run_id)
    started = False
    try:
        docker_compose(project, env, "up", "--detach", "ledger", "source", "otel")
        started = True
        wait_json(ledger + "/healthz")
        metadata = wait_json(source + "/metadata.json")
        ticket = validate_ticket({
            "schema": TICKET_SCHEMA,
            "case": "ALPHA-FIXTURE",
            "attempt": run_id,
            "subject": {"repository": metadata["repository"], "revision": metadata["revision"]},
            "release": {"git_commit": commit, "image_digest": digest,
                        "capability_profiles_sha256": manifest["capability_profiles_sha256"]},
            "scenario": scenario,
            "authorized_stages": requested_stages,
            "authorized_stop": through,
            "qualification": "Synthetic disposable-container handoff trial only.",
        })
        http("POST", f"{ledger}/v1/runs/{run_id}", canonical(ticket))
        for stage in requested_stages:
            session = f"{run_id}-{stage}-{time.time_ns()}"
            expected_refusal = fault == "tamper_after_intake" and stage == "assess"
            lifecycle_start = now_ns()
            emit_span(telemetry, f"defensefactory.container.{stage}.start", {
                "factory.run_id": run_id,
                "factory.stage": stage,
                "factory.session_identity": session,
                "factory.image_digest": digest,
            }, lifecycle_start, now_ns(), trace_id=attempt_trace, timeout=2.0)
            result = docker_compose(project, env, "run", "--rm", "--no-deps", "-T",
                "-e", f"FACTORY_SESSION_ID={session}", "stage", "stage",
                "--stage", stage, "--run-id", run_id, "--image-digest", digest,
                check=not expected_refusal)
            container_identity = "unknown"
            if not expected_refusal:
                summary = json.loads(http("GET", f"{ledger}/v1/runs/{run_id}"))
                container_identity = summary["receipts"][-1].get("container_identity", "unknown")
            lifecycle_end = now_ns()
            emit_span(telemetry, f"defensefactory.container.{stage}.exit", {
                "factory.run_id": run_id,
                "factory.stage": stage,
                "factory.session_identity": session,
                "factory.image_digest": digest,
                "factory.container_identity": container_identity,
                "factory.exit_code": result.returncode,
            }, lifecycle_start, lifecycle_end, trace_id=attempt_trace,
                status={"code": 2 if result.returncode else 1,
                        "message": "refused" if result.returncode else "exited"},
                timeout=2.0)
            emit_span(telemetry, f"defensefactory.container.{stage}.delete", {
                "factory.run_id": run_id,
                "factory.stage": stage,
                "factory.session_identity": session,
                "factory.image_digest": digest,
                "factory.container_identity": container_identity,
            }, lifecycle_end, now_ns(), trace_id=attempt_trace, timeout=2.0)
            (output / f"stage-{stage}.stdout.json").write_text(result.stdout)
            if result.stderr:
                (output / f"stage-{stage}.stderr.json").write_text(result.stderr)
            if expected_refusal:
                if result.returncode == 0:
                    raise TrialError("Tampered evidence was accepted by the receiving stage")
                summary = json.loads(http("GET", f"{ledger}/v1/runs/{run_id}"))
                if [item["stage"] for item in summary["receipts"]] != ["intake"]:
                    raise TrialError("Receiving stage published despite tampered evidence")
                fault_result = {
                    "schema": "defensefactory/alpha-fault-result/v1",
                    "fault": fault,
                    "receiving_stage": stage,
                    "receiving_exit_code": result.returncode,
                    "published_stages": [item["stage"] for item in summary["receipts"]],
                    "result": "satisfied_within_scope",
                    "qualification": "Synthetic corruption injected by the trusted trial controller.",
                }
                (output / "fault-result.json").write_bytes(canonical(fault_result))
                (output / "run-summary.json").write_bytes(canonical(summary))
                (output / "release-manifest.json").write_bytes(canonical(manifest))
                return fault_result
            if fault == "tamper_after_intake" and stage == "intake":
                summary = json.loads(http("GET", f"{ledger}/v1/runs/{run_id}"))
                attachment = summary["receipts"][0]["output_attachment"]["sha256"]
                injection = docker_compose(project, env, "exec", "-T", "ledger", "python3", "-c",
                    "from pathlib import Path;import sys;"
                    "Path('/var/lib/defensefactory-ledger/'+sys.argv[1]+'/attachments/'+sys.argv[2]).write_bytes(b'tampered by alpha fault fixture')",
                    run_id, attachment)
                if injection.returncode:
                    raise TrialError("Could not inject the synthetic attachment fault")
        summary = export_run(ledger, run_id, output, manifest)
        (output / "trial-result.json").write_bytes(canonical({
            "schema": "defensefactory/alpha-trial-result/v1",
            "run_id": run_id,
            "scenario": scenario,
            "through": through,
            "complete": summary["complete"],
            "stage_count": len(summary["receipts"]),
            "image_digest": digest,
            "result": "satisfied_within_scope" if summary["complete"] else "inconclusive",
            "qualification": "Deterministic synthetic handoff; live ticket-only agent adherence is separate.",
        }))
        return summary
    finally:
        if started:
            logs = docker_compose(project, env, "logs", "--no-color", check=False)
            (output / "service-logs.txt").write_text(logs.stdout + logs.stderr)
            if not keep_services:
                docker_compose(project, env, "down", "--volumes", "--remove-orphans", check=False)


def validate_local() -> dict:
    profiles = validate_profiles(read_json(PROFILES))
    required = [HERE / name for name in ("Dockerfile", "compose.yaml", "otel-collector.yaml")]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise TrialError("Missing release files: " + ", ".join(missing))
    return {"result": "satisfied_within_scope", "stages": list(profiles["stages"]),
            "capability_profiles_sha256": sha256(PROFILES.read_bytes()),
            "qualification": "Static release-harness validation; no container executed."}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    build_parser = sub.add_parser("build")
    build_parser.add_argument("--image", default="defensefactory:alpha-candidate")
    build_parser.add_argument("--opencode-version", default="1.19.5")
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--image", default="defensefactory:alpha-candidate")
    run_parser.add_argument("--output", type=Path, required=True)
    run_parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("alpha-%Y%m%dT%H%M%SZ"))
    run_parser.add_argument("--scenario", choices=("active", "early_disposition", "local_lifecycle"),
                            default="local_lifecycle")
    run_parser.add_argument("--through", choices=STAGES, default="maintain")
    run_parser.add_argument("--keep-services", action="store_true")
    run_parser.add_argument("--fault", choices=("", "tamper_after_intake"), default="")
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            result = validate_local()
        elif args.command == "build":
            result = build(args.image, args.opencode_version)
        else:
            result = run_trial(args.image, args.output, args.run_id, args.scenario,
                               args.through, args.keep_services, args.fault)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (OSError, TrialError, ValueError, json.JSONDecodeError, URLError) as error:
        print(json.dumps({"result": "failed", "error": str(error)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
