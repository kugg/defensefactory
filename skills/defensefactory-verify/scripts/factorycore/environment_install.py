"""Environment discovery and append-only installation qualification.

No service calls, credential reads, production deployment or lifecycle authority.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile

from .installation import STAGES, install, validate as validate_runtime_profile
from .stage_rules import validate_package_safe


SCHEMA = "defensefactory/environment-profile/v1"
INSTALLER = "defensefactory-environment-installer/1"
READINESS = ("ready_for_practice", "ready_for_bounded_production_trial", "practice_only", "inconclusive", "blocked")
SOFT_DISPOSITIONS = ("available", "configured", "replaceable_alternative", "missing_recommended", "not_applicable", "unknown")


def timestamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _absolute(value, name):
    path = Path(value).expanduser().resolve()
    if not path.is_absolute(): raise ValueError(name + " must be absolute")
    return str(path)


def _credential_reference(value):
    if not value: return ""
    if not (re.fullmatch(r"env:[A-Z_][A-Z0-9_]*", value) or value.startswith("op://") or value.startswith("keychain://")):
        raise ValueError("Credentials must use env:NAME, op://… or keychain://… references")
    return value


def validate_spec(spec):
    required = {"schema", "installation_id", "model", "launcher", "ticket", "source_intelligence", "telemetry",
                "paths", "practice", "production", "safety", "alternatives"}
    if not isinstance(spec, dict) or set(spec) != required or spec.get("schema") != SCHEMA:
        raise ValueError("Environment profile has unknown/missing fields or schema")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,79}", spec["installation_id"] or ""):
        raise ValueError("installation_id must be a stable local identifier")
    if not re.fullmatch(r"[^\s/]+/\S+", spec["model"] or ""):
        raise ValueError("model must be provider/model")
    spec = json.loads(json.dumps(spec))
    spec["launcher"] = _absolute(spec["launcher"], "launcher")
    if not Path(spec["launcher"]).is_file(): raise ValueError("launcher must exist")
    ticket = spec["ticket"]
    if set(ticket) != {"system", "workspace", "team", "project", "endpoint", "credential_reference", "write_qualification"}:
        raise ValueError("ticket configuration has unknown/missing fields")
    if ticket["system"] != "linear" or not ticket["project"]: raise ValueError("Linear project is required")
    ticket["credential_reference"] = _credential_reference(ticket["credential_reference"])
    intelligence = spec["source_intelligence"]
    if set(intelligence) != {"kind", "mcp_url", "index_api_url", "credential_reference", "required", "sample_repository", "sample_ref"}:
        raise ValueError("source_intelligence has unknown/missing fields")
    if intelligence["kind"] not in ("codeintel", "equivalent", "source_only") or type(intelligence["required"]) is not bool:
        raise ValueError("unsupported source-intelligence selection")
    intelligence["credential_reference"] = _credential_reference(intelligence["credential_reference"])
    telemetry = spec["telemetry"]
    if set(telemetry) != {"otel_endpoint", "otel_log", "thinking_retained_local", "retention_policy"} or type(telemetry["thinking_retained_local"]) is not bool:
        raise ValueError("telemetry has unknown/missing fields")
    telemetry["otel_log"] = _absolute(telemetry["otel_log"], "otel_log") if telemetry["otel_log"] else ""
    paths = spec["paths"]
    if set(paths) != {"skills_directory", "private_evidence_root", "state_root"}:
        raise ValueError("paths have unknown/missing fields")
    for name in paths: paths[name] = _absolute(paths[name], name)
    if Path(paths["skills_directory"]).name != "skills": raise ValueError("skills_directory must end in skills")
    practice = spec["practice"]
    practice_fields = {"kind", "location", "allowed_repositories", "allowed_network_destinations", "external_provider_calls",
                       "credential_class", "cleanup_policy", "resource_limits", "deployment_tests", "runtime_evidence"}
    if set(practice) != practice_fields or practice["kind"] not in ("docker", "podman", "vm", "test_host", "kubernetes_namespace", "digital_twin", "source_only"):
        raise ValueError("practice boundary is incomplete")
    for key in ("allowed_repositories", "allowed_network_destinations"):
        if not isinstance(practice[key], list) or not all(isinstance(item, str) and item for item in practice[key]): raise ValueError("invalid practice list: " + key)
    if practice["external_provider_calls"] is not False or practice["credential_class"] not in ("none", "synthetic", "test_only"):
        raise ValueError("practice defaults must forbid real provider calls and production credentials")
    if type(practice["deployment_tests"]) is not bool: raise ValueError("deployment_tests must be boolean")
    production = spec["production"]
    production_fields = {"target_kind", "description", "repositories", "ticket_project", "pr_repository", "branch_policy",
                         "deployment_environments", "authorization_reference", "secret_references", "evidence_retention", "operators", "reviewers", "governance"}
    if set(production) != production_fields or not production["target_kind"] or not production["authorization_reference"]:
        raise ValueError("production target and its separate authority reference are required")
    for key in ("repositories", "deployment_environments", "secret_references", "operators", "reviewers"):
        if not isinstance(production[key], list): raise ValueError("invalid production list: " + key)
    production["secret_references"] = [_credential_reference(value) for value in production["secret_references"]]
    safety = spec["safety"]
    if set(safety) != {"default_stop", "allowed_external_mutations", "evidence_upload_policy"} or safety["default_stop"] not in ("draft_pr_or_justified_disposition", "justified_disposition"):
        raise ValueError("safety boundary is incomplete")
    if not isinstance(safety["allowed_external_mutations"], list): raise ValueError("allowed_external_mutations must be a list")
    if not isinstance(spec["alternatives"], dict): raise ValueError("alternatives must be a capability mapping")
    encoded = json.dumps(spec, sort_keys=True)
    if re.search(r'(?i)"(?:password|secret|token|api_key)"\s*:', encoded):
        raise ValueError("Profile may contain credential references, never secret-value fields")
    return spec


def _version(argv):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=3)
        line = (result.stdout or result.stderr).splitlines()
        return {"available": result.returncode == 0, "path": shutil.which(argv[0]) or argv[0], "version": line[0][:300] if line else "", "exit_code": result.returncode}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"available": False, "path": shutil.which(argv[0]), "error": type(error).__name__}


def _writable_target(path):
    candidate = Path(path)
    while not candidate.exists() and candidate != candidate.parent: candidate = candidate.parent
    return candidate.is_dir() and os.access(candidate, os.W_OK)


def discover(spec=None):
    """Read-only host discovery. It does not contact configured services."""
    commands = {name: _version(argv) for name, argv in {
        "git": ["git", "--version"], "python": [os.sys.executable, "--version"], "opencode": ["opencode", "--version"],
        "docker": ["docker", "--version"], "podman": ["podman", "--version"], "go": ["go", "version"],
        "node": ["node", "--version"], "java": ["java", "-version"], "tlc": ["tlc", "-help"],
        "gh": ["gh", "--version"], "op": ["op", "--version"], "opencode_otel": ["opencode-otel", "--help"],
    }.items()}
    disk_path = Path(spec["paths"]["state_root"] if spec else Path.cwd())
    while not disk_path.exists() and disk_path != disk_path.parent: disk_path = disk_path.parent
    disk = shutil.disk_usage(disk_path)
    host = {"system": platform.system(), "release": platform.release(), "architecture": platform.machine(),
            "shell": os.environ.get("SHELL", ""), "timezone": datetime.datetime.now().astimezone().tzname(),
            "cwd": str(Path.cwd()), "disk_free_bytes": disk.free, "commands": commands}
    mandatory = []
    def required(identifier, satisfied, detail): mandatory.append({"id": identifier, "required": True, "result": "satisfied" if satisfied else "violated", "detail": detail})
    required("git_repository_access", commands["git"]["available"], commands["git"])
    required("deterministic_helper_runtime", commands["python"]["available"] and sys.version_info >= (3, 10), {**commands["python"], "minimum": "3.10"})
    if spec:
        required("supported_agent_runner", Path(spec["launcher"]).is_file() and os.access(spec["launcher"], os.X_OK), spec["launcher"])
        required("durable_ticket_project", bool(spec["ticket"]["project"]), spec["ticket"]["project"])
        required("private_evidence_directory", _writable_target(spec["paths"]["private_evidence_root"]), spec["paths"]["private_evidence_root"])
        required("practice_execution_boundary", bool(spec["practice"]["location"]), {key: spec["practice"][key] for key in ("kind", "location")})
    soft = []
    def optional(identifier, available, loss, configured=False, alternative=False, applicable=True):
        disposition = "not_applicable" if not applicable else "configured" if configured else "available" if available else "replaceable_alternative" if alternative else "missing_recommended"
        soft.append({"id": identifier, "required": False, "disposition": disposition, "confidence_loss": "" if disposition in ("available", "configured") else loss})
    optional("disposable_container", commands["docker"]["available"] or commands["podman"]["available"], "Runtime isolation and cleanup must be supplied by the declared alternative.", alternative=bool(spec and spec["practice"]["kind"] not in ("docker", "podman", "source_only")), applicable=not bool(spec and spec["practice"]["kind"] == "source_only"))
    optional("formal_or_exhaustive", commands["tlc"]["available"], "Formal/exhaustive claims remain unsupported unless a declared alternative runs.", alternative=bool(spec and spec["alternatives"].get("formal")))
    configured_intelligence = bool(spec and spec["source_intelligence"]["kind"] != "source_only" and (spec["source_intelligence"]["mcp_url"] or spec["source_intelligence"]["kind"] == "equivalent"))
    optional("exact_revision_source_intelligence", False, "Semantic source/architecture coverage must be qualified as unavailable or source-only.", configured=configured_intelligence)
    optional("otel_monitoring", commands["opencode_otel"]["available"], "JSON events remain available, but OTel correlation/collector evidence is absent.", configured=bool(spec and (spec["telemetry"]["otel_endpoint"] or spec["telemetry"]["otel_log"])))
    optional("repository_pr_integration", commands["gh"]["available"], "PR operations require another explicit adapter or manual handoff.")
    optional("secret_manager", commands["op"]["available"], "Credential references require another host-provided resolver.", alternative=bool(spec and any(ref.startswith(("env:", "keychain:")) for ref in [spec["ticket"]["credential_reference"], spec["source_intelligence"]["credential_reference"], *spec["production"]["secret_references"]])))
    confidence_layers = {
        "hard_deterministic": {"status": "configured" if spec else "unknown", "examples": ["stage-rule validation", "helper tests"]},
        "formal_or_exhaustive": next(item for item in soft if item["id"] == "formal_or_exhaustive"),
        "source_and_architecture": next(item for item in soft if item["id"] == "exact_revision_source_intelligence"),
        "runtime": next(item for item in soft if item["id"] == "disposable_container"),
        "soft": {"status": "configured" if spec else "unknown", "examples": ["RULES.md", "SKILL.md", "human review"], "not_equivalent_to_hard_fences": True},
    }
    readiness = "blocked" if any(item["result"] == "violated" for item in mandatory) else "ready_for_practice"
    if spec and spec["source_intelligence"]["required"] and not configured_intelligence: readiness = "blocked"
    elif any(item["disposition"] == "missing_recommended" for item in soft): readiness = "practice_only" if readiness != "blocked" else readiness
    return {"schema": "defensefactory/environment-discovery/v1", "observed_at": timestamp(), "host": host,
            "mandatory": mandatory, "recommended": soft, "confidence_layers": confidence_layers, "readiness": readiness,
            "configured_service_destinations": [] if not spec else [value for value in (spec["ticket"]["endpoint"], spec["source_intelligence"]["mcp_url"], spec["source_intelligence"]["index_api_url"], spec["telemetry"]["otel_endpoint"]) if value],
            "local_configuration_locations": {"opencode": str(Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "opencode"),
                                               "factory_state": None if not spec else spec["paths"]["state_root"]},
            "limitations": ["No network, service authentication, repository credential, OTel receiver or exact-index query was attempted."]}


def plan(spec, source, state_root):
    spec = validate_spec(spec); source = Path(source).resolve(); state_root = Path(state_root).resolve()
    discovery = discover(spec); release_files = sum(1 for stage in STAGES for path in (source / stage).rglob("*") if path.is_file())
    return {"schema": "defensefactory/environment-install-plan/v1", "installation_id": spec["installation_id"],
            "result": "blocked" if discovery["readiness"] == "blocked" else "planned", "discovery": discovery,
            "mutations": [{"kind": "create_installation_state", "path": str(state_root / spec["installation_id"])},
                          {"kind": "install_immutable_release_and_managed_skill_links", "skills": str(source), "file_count": release_files},
                          {"kind": "write_nonsecret_profiles", "paths": [str(state_root / spec["installation_id"] / "profile.json"), str(state_root / spec["installation_id"] / "runtime/config.json")]},
                          {"kind": "create_private_evidence_root", "path": spec["paths"]["private_evidence_root"]}],
            "excluded": ["service authentication", "secret reads", "ticket mutation", "index policy mutation", "practice trial", "production deployment", "merge/deploy authority"],
            "spec_sha256": identity(spec), "installer": INSTALLER}


def _write_new(path, value, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    raw = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    with path.open("xb") as stream: stream.write(raw)
    os.chmod(path, mode)
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def append_receipt(home, kind, record):
    receipts = Path(home) / "receipts"; receipts.mkdir(parents=True, exist_ok=True, mode=0o700)
    sequence = len(list(receipts.glob("*.json"))) + 1
    envelope = {"schema": "defensefactory/installation-receipt/v1", "sequence": sequence, "kind": kind,
                "recorded_at": timestamp(), "record": record}
    envelope["receipt_sha256"] = identity(envelope)
    return _write_new(receipts / f"{sequence:04d}-{kind}.json", envelope)


def apply_install(spec, source, state_root, *, update=False):
    spec = validate_spec(spec); state_root = Path(state_root).resolve(); home = state_root / spec["installation_id"]
    intended = plan(spec, source, state_root)
    if intended["result"] == "blocked": raise ValueError("Mandatory environment capability missing; inspect discovery before installation")
    if home.exists(): raise ValueError("Installation ID already exists; use --resume or a new ID")
    home.mkdir(parents=True, mode=0o700)
    try:
        _write_new(home / "profile.json", spec)
        runtime = home / "runtime/config.json"
        credential = spec["source_intelligence"]["credential_reference"]
        token_env = credential[4:] if credential.startswith("env:") else ""
        preferences = {"model": spec["model"], "linear_project": spec["ticket"]["project"], "linear_url": spec["ticket"]["endpoint"],
            "codeintel_url": spec["source_intelligence"]["mcp_url"], "codeintel_api_url": spec["source_intelligence"]["index_api_url"],
            "codeintel_token_env": token_env, "codeintel_transport": "stdio", "codeintel_header_name": "X-Api-Key",
            "github_repository": spec["production"]["pr_repository"], "launcher": spec["launcher"],
            "skills_directory": spec["paths"]["skills_directory"], "output_directory": spec["paths"]["private_evidence_root"]}
        result = install(Path(source), runtime, preferences, update=update)
        evidence = Path(spec["paths"]["private_evidence_root"]); evidence.mkdir(parents=True, exist_ok=True, mode=0o700)
        installed_profile = {"schema": "defensefactory/installed-environment-profile/v1", "installer": INSTALLER,
            "installed_at": timestamp(), "environment_spec": spec, "environment_spec_sha256": identity(spec),
            "factory_release_digest": Path(result["release"]).name, "release": result["release"],
            "runtime_profile": result["configuration"], "capability_matrix": intended["discovery"],
            "authority": "Configuration only; no merge, deployment, ticket lifecycle or production authority."}
        installed_profile_record = _write_new(home / "installed-profile.json", installed_profile)
        ownership = {"schema": "defensefactory/installation-ownership/v1", "installation_id": spec["installation_id"],
                     "home": str(home), "runtime_config": result["configuration"], "opencode_config": result["opencode_config"],
                     "release": result["release"], "managed_links": [str(Path(spec["paths"]["skills_directory"]) / stage) for stage in STAGES],
                     "installed_profile": installed_profile_record, "evidence_root": str(evidence),
                     "preserve_on_uninstall": [str(evidence), str(Path(result["release"]).parent), str(home / "receipts"), str(home / "installed-profile.json")]}
        _write_new(home / "ownership.json", ownership)
        append_receipt(home, "installed", {"plan_sha256": identity(intended), "installation": result, "ownership_sha256": identity(ownership), "readiness": intended["discovery"]["readiness"]})
        return {"result": "installed", "installation_id": spec["installation_id"], "home": str(home), "runtime": result,
                "readiness": intended["discovery"]["readiness"], "next_action": "Run deterministic evaluation, then a separately authorized fresh practice trial."}
    except Exception:
        append_receipt(home, "installation-failed", {"result": "failed", "next_action": "Inspect preserved state; use a new installation ID after correcting inputs."})
        raise


def deterministic_evaluation(home):
    home = Path(home); spec = validate_spec(json.loads((home / "profile.json").read_text())); ownership = json.loads((home / "ownership.json").read_text())
    release = Path(ownership["release"]); results = []
    for stage in STAGES:
        receipt = validate_package_safe(release / stage, release / "defensefactory")
        results.append({"id": "stage_rules:" + stage, "result": receipt["result"], "receipt_sha256": receipt["receipt_sha256"]})
    generation = len(list((home / "receipts").glob("*.json"))) + 1
    evaluation_root = home / "evaluations" / f"{generation:04d}"
    evaluation_root.mkdir(parents=True, mode=0o700)
    for identifier, script, destination in (
        ("component_rules_evaluator", "eval-rules.py", "component-rules"),
        ("stage_rules_evaluator", "eval-stage-rules.py", "stage-rules"),
    ):
        command = [os.sys.executable, str(release / "defensefactory/scripts" / script), "--output", str(evaluation_root / destination)]
        try:
            process = subprocess.run(command, capture_output=True, timeout=120)
            returncode, stdout_bytes, stderr_bytes = process.returncode, process.stdout, process.stderr
        except (OSError, subprocess.TimeoutExpired) as error:
            returncode = 124 if isinstance(error, subprocess.TimeoutExpired) else 127
            stdout_bytes = getattr(error, "stdout", b"") or b""
            stderr_bytes = (getattr(error, "stderr", b"") or b"") + ("\n" + type(error).__name__ + ": " + str(error)).encode()
        stdout = evaluation_root / (identifier + ".stdout"); stderr = evaluation_root / (identifier + ".stderr")
        stdout.write_bytes(stdout_bytes); stderr.write_bytes(stderr_bytes)
        results.append({"id": identifier, "result": "satisfied" if returncode == 0 else "violated",
                        "exit_code": returncode, "argv": command,
                        "stdout": {"path": str(stdout), "sha256": hashlib.sha256(stdout_bytes).hexdigest(), "bytes": len(stdout_bytes)},
                        "stderr": {"path": str(stderr), "sha256": hashlib.sha256(stderr_bytes).hexdigest(), "bytes": len(stderr_bytes)}})
    results.append({"id": "configuration_schema", "result": "satisfied", "profile_sha256": identity(spec)})
    credential_references = [spec["ticket"]["credential_reference"], spec["source_intelligence"]["credential_reference"], *spec["production"]["secret_references"]]
    results.append({"id": "credential_references", "result": "satisfied", "configured_reference_count": sum(bool(item) for item in credential_references),
                    "note": "Reference syntax was validated; secret values were not resolved or logged."})
    for name, configured, note in (
        ("ticket_read_write", spec["ticket"]["write_qualification"], "Requires a dedicated authorized test target and native readback."),
        ("source_intelligence_exact_revision", bool(spec["source_intelligence"]["sample_repository"] and spec["source_intelligence"]["sample_ref"]), "Requires live index/query qualification; reachability alone is insufficient."),
        ("otel_receiver", bool(spec["telemetry"]["otel_endpoint"] or spec["telemetry"]["otel_log"]), "Requires actual event/trace observation."),
        ("practice_isolation", spec["practice"]["kind"] == "source_only", "Runtime isolation needs a separately observed disposable environment."),
    ):
        results.append({"id": name, "result": "inconclusive" if configured else "not_configured", "note": note})
    rules_ok = all(item["result"] == "satisfied" for item in results if item["id"].startswith("stage_rules:") or item["id"].endswith("_evaluator") or item["id"] in ("configuration_schema", "credential_references"))
    readiness = "practice_only" if rules_ok else "blocked"
    improvements = [{"capability": item["id"], "reason": item.get("note") or item.get("confidence_loss") or "qualification incomplete",
                     "proposal": "Qualify this capability in a separately authorized practice environment and attach its receipt.",
                     "automatic_change_applied": False} for item in results if item["result"] in ("inconclusive", "not_configured", "violated")]
    evaluation = {"schema": "defensefactory/environment-evaluation/v1", "evaluated_at": timestamp(), "results": results,
                  "technical_result": "deterministic_package_valid" if rules_ok else "deterministic_package_invalid",
                  "process_qualification": "not_run", "installation_readiness": readiness,
                  "improvement_proposals": improvements,
                  "limitations": ["No service, model, ticket, index, runtime or production call was made.", "Live practice adherence requires a fresh separately authorized trial."]}
    append_receipt(home, "deterministic-evaluation", evaluation)
    return evaluation


def report(home):
    home = Path(home); profile = validate_spec(json.loads((home / "profile.json").read_text()))
    installed_profile = json.loads((home / "installed-profile.json").read_text())
    receipts = [json.loads(path.read_text()) for path in sorted((home / "receipts").glob("*.json"))]
    readiness = "inconclusive"
    for item in receipts:
        value = item["record"].get("installation_readiness") or item["record"].get("readiness")
        if value in READINESS: readiness = value
    return {"schema": "defensefactory/installation-report/v1", "installation_id": profile["installation_id"],
            "profile_sha256": identity(profile), "installed_profile_sha256": identity(installed_profile),
            "factory_release_digest": installed_profile["factory_release_digest"],
            "receipt_count": len(receipts), "last_receipt_sha256": receipts[-1]["receipt_sha256"] if receipts else None,
            "readiness": readiness, "practice": profile["practice"], "declared_production_target": profile["production"],
            "qualification": "Installation does not grant merge, deploy, ticket lifecycle or production authority."}


def uninstall(home):
    home = Path(home); ownership = json.loads((home / "ownership.json").read_text()); removed = []
    release = Path(ownership["release"]).resolve()
    for raw in ownership["managed_links"]:
        link = Path(raw)
        if link.is_symlink() and link.resolve() == release / link.name:
            link.unlink(); removed.append(str(link))
    retired = home / "retired"; retired.mkdir(exist_ok=True, mode=0o700)
    for key in ("runtime_config", "opencode_config"):
        path = Path(ownership[key])
        if path.is_file() and path.parent == home / "runtime":
            target = retired / path.name
            if target.exists(): raise ValueError("Retired profile target already exists")
            path.rename(target); removed.append(str(path))
    result = {"result": "profile_uninstalled", "removed": removed, "preserved": ownership["preserve_on_uninstall"],
              "qualification": "Evidence, receipts and immutable release bytes were preserved."}
    append_receipt(home, "uninstalled", result); return result
