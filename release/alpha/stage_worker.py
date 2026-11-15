"""Run one deterministic handoff qualification in a fresh stage environment."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .protocol import (EVIDENCE_SCHEMA, ProtocolError, RECEIPT_SCHEMA, STAGES, canonical,
                       identity, read_json, receipt_identity, require, sha256,
                       validate_profiles, validate_receipt, validate_ticket)
from .telemetry import attempt_trace_id, emit, now_ns


CANDIDATE_PATCH = """diff --git a/component.py b/component.py
--- a/component.py
+++ b/component.py
@@ -2,6 +2,6 @@
 
 
 def release_credential(credential, peer_verified=False):
-    # The active fixture starts with a violated claim. Repair evidence is passed
-    # between stages; the release harness itself never calls a real provider.
+    if not peer_verified:
+        raise PermissionError("peer verification required")
     return credential
"""


def request(method: str, url: str, data: bytes | None = None,
            content_type: str = "application/json") -> bytes:
    headers = {"Content-Type": content_type} if data is not None else {}
    try:
        with urlopen(Request(url, method=method, data=data, headers=headers), timeout=15) as response:
            return response.read()
    except HTTPError as error:
        detail = error.read().decode(errors="replace")
        raise ProtocolError(f"Ledger {method} {url} failed: {error.code} {detail}") from error


def get_json(url: str) -> dict:
    value = json.loads(request("GET", url))
    require(isinstance(value, dict), "Ledger returned a non-object")
    return value


def put_json(url: str, value: dict) -> dict:
    result = json.loads(request("PUT", url, canonical(value)))
    require(isinstance(result, dict), "Ledger returned a non-object")
    return result


def clone_subject(subject: dict, destination: Path) -> None:
    completed = subprocess.run(["git", "clone", "--quiet", "--no-checkout",
                                subject["repository"], str(destination)],
                               capture_output=True, text=True)
    if completed.returncode:
        raise ProtocolError("Exact-subject clone failed: " + completed.stderr.strip())
    completed = subprocess.run(["git", "-C", str(destination), "checkout", "--quiet",
                                "--detach", subject["revision"]], capture_output=True, text=True)
    if completed.returncode:
        raise ProtocolError("Exact-subject checkout failed: " + completed.stderr.strip())
    actual = subprocess.run(["git", "-C", str(destination), "rev-parse", "HEAD"],
                            check=True, capture_output=True, text=True).stdout.strip()
    require(actual == subject["revision"], "Source checkout resolved another revision")


def apply_candidate(source: Path, patch: str) -> None:
    require(patch == CANDIDATE_PATCH, "Candidate patch changed between stages")
    completed = subprocess.run(["git", "-C", str(source), "apply", "--check", "-"],
                               input=patch, capture_output=True, text=True)
    require(completed.returncode == 0, "Candidate no longer applies: " + completed.stderr.strip())
    subprocess.run(["git", "-C", str(source), "apply", "-"], input=patch,
                   check=True, capture_output=True, text=True)


def verify_candidate(source: Path) -> dict:
    unit = subprocess.run(["python3", "-m", "unittest", "-v"], cwd=source,
                          capture_output=True, text=True)
    negative = subprocess.run(["python3", "-c",
        "from component import release_credential\n"
        "try: release_credential('fixture', peer_verified=False)\n"
        "except PermissionError: raise SystemExit(0)\n"
        "raise SystemExit(1)"], cwd=source, capture_output=True, text=True)
    require(unit.returncode == 0 and negative.returncode == 0,
            "Synthetic candidate checks did not pass")
    return {
        "unit_exit": unit.returncode,
        "negative_exit": negative.returncode,
        "unit_output_sha256": sha256((unit.stdout + unit.stderr).encode()),
    }


def prior_evidence(ledger: str, run_id: str, ticket: dict, stage: str,
                   summary: dict) -> tuple[dict | None, str | None]:
    index = STAGES.index(stage)
    require(len(summary["receipts"]) == index and summary.get("next_stage") == stage,
            "Ticket ledger does not name this stage as the next handoff")
    if index == 0:
        return None, None
    previous_stage = STAGES[index - 1]
    receipt = get_json(f"{ledger}/v1/runs/{run_id}/stages/{previous_stage}")
    older = None if index == 1 else summary["receipts"][index - 2]["receipt_sha256"]
    validate_receipt(receipt, ticket, previous_stage, older)
    binding = receipt["output_attachment"]
    raw = request("GET", f"{ledger}/v1/runs/{run_id}/attachments/{binding['sha256']}")
    require(len(raw) == binding["bytes"] and sha256(raw) == binding["sha256"],
            "Prior stage evidence bytes changed")
    value = json.loads(raw)
    require(isinstance(value, dict) and value.get("schema") == EVIDENCE_SCHEMA and
            value.get("stage") == previous_stage and value.get("subject") == ticket["subject"],
            "Prior stage evidence content is not bound to this handoff")
    return value, receipt["receipt_sha256"]


def evaluate(stage: str, ticket: dict, previous: dict | None, source: Path,
             coverage_limitations: list[str] | None = None) -> tuple[str, dict]:
    scenario = ticket["scenario"]
    inherited_patch = previous.get("candidate_patch") if previous else None
    details = {"mode": "deterministic_synthetic_handoff", "external_product_call": False}
    result = "satisfied_within_scope"
    patch = inherited_patch
    if stage == "intake":
        details["finding"] = "synthetic credential release lacks the declared peer fence"
    elif stage == "assess":
        if scenario == "early_disposition":
            result = "premise_disputed"
            details["disposition"] = "synthetic component removed by the ticket fixture"
        else:
            details.update({"finding_status": "active", "attack_complexity": "low in fixture scope"})
    elif stage == "repair":
        patch = CANDIDATE_PATCH
        details["candidate_patch_sha256"] = sha256(patch.encode())
    elif stage in ("verify", "deploy", "confirm"):
        require(patch, f"{stage} did not receive the repair candidate through evidence")
        apply_candidate(source, patch)
        details["checks"] = verify_candidate(source)
        details["candidate_patch_sha256"] = sha256(patch.encode())
        if stage == "deploy":
            details["artifact_sha256"] = sha256((source / "component.py").read_bytes())
            details["deployment_scope"] = "ephemeral local fixture only"
        if stage == "confirm":
            details["runtime_assertion"] = "verified and unverified fixture paths exercised"
    elif stage == "integrate":
        require(patch, "Integrate did not receive the repair candidate through evidence")
        details["merge_subject_sha256"] = identity({"source": ticket["subject"], "patch": patch})
        details["merge_performed"] = False
    elif stage == "maintain":
        require(patch, "Maintain did not receive the accepted candidate through evidence")
        details["drift"] = "none in immutable synthetic subject"
        details["scheduled"] = False
    return result, {"details": details, "candidate_patch": patch}


def run(stage: str, ledger: str, run_id: str, profiles_path: Path,
        image_digest: str, telemetry_endpoint: str = "") -> dict:
    start = now_ns()
    container_identity = os.environ.get("HOSTNAME", "unknown")
    session_identity = os.environ.get("FACTORY_SESSION_ID", "fresh-process-unreported")
    trace_id = attempt_trace_id(run_id)
    try:
        return _run(stage, ledger, run_id, profiles_path, image_digest,
                    telemetry_endpoint, start, container_identity, session_identity, trace_id)
    except (OSError, ProtocolError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        emit(telemetry_endpoint, f"defensefactory.stage.{stage}", {
            "factory.run_id": run_id,
            "factory.stage": stage,
            "factory.container_identity": container_identity,
            "factory.session_identity": session_identity,
            "factory.image_digest": image_digest,
            "factory.result": "failed",
            "factory.error": str(error)[:300],
        }, start, now_ns(), trace_id=trace_id,
            status={"code": 2, "message": "refused"}) if telemetry_endpoint else None
        raise


def _run(stage: str, ledger: str, run_id: str, profiles_path: Path,
         image_digest: str, telemetry_endpoint: str, start: int,
         container_identity: str, session_identity: str, trace_id: str) -> dict:
    require(stage in STAGES, "Unknown stage")
    profiles = validate_profiles(read_json(profiles_path))
    profiles_digest = sha256(profiles_path.read_bytes())
    summary = get_json(f"{ledger.rstrip('/')}/v1/runs/{run_id}")
    ticket = validate_ticket(summary["ticket"])
    require(ticket["release"]["image_digest"] == image_digest,
            "Running image differs from the ticket-frozen image")
    require(ticket["release"]["capability_profiles_sha256"] == profiles_digest,
            "Capability profiles differ from the ticket-frozen profiles")
    profile = profiles["stages"][stage]
    previous, previous_receipt_sha = prior_evidence(ledger.rstrip("/"), run_id, ticket,
                                                    stage, summary)
    work_parent = Path(os.environ.get("FACTORY_WORK_ROOT", "/tmp"))
    coverage_limitations = []
    if "codeintel_read" in profile["allow"]:
        coverage_limitations.append("Optional CodeIntel/equivalent confidence service was not available or consulted in this deterministic alpha fixture; no semantic coverage is inferred from its absence.")
    with tempfile.TemporaryDirectory(prefix=f"factory-{stage}-", dir=work_parent) as temporary:
        source = Path(temporary) / "source"
        clone_subject(ticket["subject"], source)
        result, observation = evaluate(stage, ticket, previous, source, coverage_limitations)
    evidence = {
        "schema": EVIDENCE_SCHEMA,
        "case": ticket["case"],
        "attempt": ticket["attempt"],
        "stage": stage,
        "subject": ticket["subject"],
        "previous_evidence_sha256": previous.get("evidence_sha256") if previous else None,
        "result": result,
        "capabilities_used": [name for name in profile["allow"] if name in
                              {"ticket_read", "ticket_write", "source_read",
                               "draft_candidate_write", "disposable_runtime",
                               "merge_subject_read", "local_fixture_deploy",
                               "local_fixture_read", "rules_read"}],
        "coverage_limitations": coverage_limitations if coverage_limitations else None,
        "reproduction": [
            "Fetch the exact ticket snapshot and prior attachment from the ledger.",
            "Clone the exact Git subject into a fresh workspace.",
            f"Run the deterministic {stage} alpha fixture operation.",
        ],
        **observation,
        "qualification": "Synthetic handoff evidence only; no product, merge, or production deployment claim.",
    }
    evidence["evidence_sha256"] = identity({key: value for key, value in evidence.items()
                                            if key != "evidence_sha256"})
    raw = canonical(evidence)
    attachment_sha = sha256(raw)
    request("PUT", f"{ledger.rstrip('/')}/v1/runs/{run_id}/attachments/{attachment_sha}",
            raw, "application/octet-stream")
    end = now_ns()
    telemetry_emitted = emit(telemetry_endpoint, f"defensefactory.stage.{stage}", {
        "factory.run_id": run_id,
        "factory.stage": stage,
        "factory.subject_revision": ticket["subject"]["revision"],
        "factory.image_digest": image_digest,
        "factory.container_identity": container_identity,
        "factory.session_identity": session_identity,
        "factory.result": result,
    }, start, end, trace_id=trace_id) if telemetry_endpoint else False
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "case": ticket["case"],
        "attempt": ticket["attempt"],
        "stage": stage,
        "subject": ticket["subject"],
        "release": ticket["release"],
        "ticket_sha256": identity(ticket),
        "previous_receipt_sha256": previous_receipt_sha,
        "output_attachment": {"sha256": attachment_sha, "bytes": len(raw)},
        "capability_profile": {"stage": stage, "sha256": identity(profile)},
        "container_identity": container_identity,
        "session_identity": session_identity,
        "started_unix_nano": start,
        "ended_unix_nano": end,
        "telemetry_emitted": telemetry_emitted,
        "result": result,
        "qualification": "Fresh-process deterministic fixture; Docker is not claimed as adversarial isolation.",
    }
    stored = put_json(f"{ledger.rstrip('/')}/v1/runs/{run_id}/stages/{stage}", receipt)
    require(stored["receipt_sha256"] == receipt_identity(stored), "Ledger receipt readback changed")
    return stored


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=STAGES)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--image-digest", required=True)
    parser.add_argument("--telemetry-endpoint", default="")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(run(args.stage, args.ledger, args.run_id, args.profiles,
                             args.image_digest, args.telemetry_endpoint),
                         indent=2, sort_keys=True))
        return 0
    except (OSError, ProtocolError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        print(json.dumps({"stage": args.stage, "result": "failed", "error": str(error)}),
              file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
