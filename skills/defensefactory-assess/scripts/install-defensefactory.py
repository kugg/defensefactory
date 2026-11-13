#!/usr/bin/env python3
"""Discover, plan, install, evaluate, resume, report or retire a factory profile."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE if (HERE / "factorycore").is_dir() else HERE.parent))
from factorycore.environment_install import (SCHEMA, append_receipt, apply_install, deterministic_evaluation, discover,
    plan, report, uninstall, validate_spec)


def source_default():
    candidate = HERE.parent / "skills"
    return candidate if (candidate / "defensefactory").is_dir() else HERE.parent.parent


def default_state():
    return Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "defensefactory/installations"


def ask(label, default="", *, required=False):
    value = input(label + (f" [{default}]" if default else "") + ": ").strip() or str(default)
    if required and not value: raise ValueError(label + " is required")
    return value


def split(value):
    return [item.strip() for item in value.split(",") if item.strip()]


def interactive(installation_id, state_root):
    launcher = shutil.which("opencode-otel") or shutil.which("opencode") or ""
    model = ask("Preferred provisioned provider/model", required=True)
    project = ask("Linear project name or ID", required=True)
    skills = ask("OpenCode skills directory", str(Path.home() / ".config/opencode/skills"), required=True)
    evidence = ask("Private evidence root", str(state_root.parent / "evidence"), required=True)
    print("Practice and production are separate. Practice defaults cannot use production credentials or real provider calls.")
    practice_kind = ask("Practice kind (docker/podman/vm/test_host/kubernetes_namespace/digital_twin/source_only)", "docker", required=True)
    practice_location = ask("Practice location/name", required=True)
    practice_repositories = split(ask("Practice repositories (comma separated)", "none"))
    practice_network = split(ask("Allowed practice network destinations (comma separated)", "none"))
    source_kind = ask("Source intelligence (codeintel/equivalent/source_only)", "codeintel", required=True)
    source_mcp = ask("CodeIntel/equivalent MCP URL (blank for source_only or preconfigured equivalent)")
    source_api = ask("Index API URL (optional)")
    source_credential = ask("Credential reference only: env:NAME, op://… or keychain://… (optional)")
    source_required = ask("Must exact-revision source intelligence block practice when unavailable? (yes/no)", "yes").lower() in ("y", "yes")
    sample_repository = ask("Authorized sample repository for qualification (optional)")
    sample_ref = ask("Exact sample branch/ref/commit for qualification (optional)")
    otel_endpoint = ask("OTel endpoint (optional)")
    otel_log = ask("Local OTel log path (optional)")
    production_kind = ask("Intended production target kind (workstation/build_host/ci_worker/security_workstation/service_account)", required=True)
    production_description = ask("Describe the intended production use", required=True)
    production_repositories = split(ask("Production repositories (comma separated)"))
    pr_repository = ask("Default PR owner/repository (optional)")
    production_authority = ask("Existing reviewed production authority/plan reference", required=True)
    return validate_spec({
        "schema": SCHEMA, "installation_id": installation_id, "model": model,
        "launcher": str(Path(ask("OpenCode/OTel launcher", launcher, required=True)).expanduser().resolve()),
        "ticket": {"system": "linear", "workspace": ask("Linear workspace (optional)"), "team": ask("Linear team (optional)"),
                   "project": project, "endpoint": ask("Linear MCP URL (blank uses native connection)"),
                   "credential_reference": ask("Linear credential reference only (optional)"), "write_qualification": False},
        "source_intelligence": {"kind": source_kind, "mcp_url": source_mcp, "index_api_url": source_api,
            "credential_reference": source_credential, "required": source_required,
            "sample_repository": sample_repository, "sample_ref": sample_ref},
        "telemetry": {"otel_endpoint": otel_endpoint, "otel_log": otel_log, "thinking_retained_local": True,
                      "retention_policy": "private local debugging; raw thinking is not uploaded by default"},
        "paths": {"skills_directory": str(Path(skills).expanduser().resolve()),
                  "private_evidence_root": str(Path(evidence).expanduser().resolve()), "state_root": str(state_root.resolve())},
        "practice": {"kind": practice_kind, "location": practice_location, "allowed_repositories": practice_repositories,
            "allowed_network_destinations": practice_network, "external_provider_calls": False, "credential_class": "synthetic",
            "cleanup_policy": ask("Practice cleanup policy", "operator-reviewed cleanup after evidence capture"),
            "resource_limits": ask("Practice resource limits", "host defaults; review before runtime"),
            "deployment_tests": False, "runtime_evidence": ask("Runtime evidence collection", "captured logs and assertions")},
        "production": {"target_kind": production_kind, "description": production_description, "repositories": production_repositories,
            "ticket_project": project, "pr_repository": pr_repository, "branch_policy": ask("Production branch policy reference (optional)"),
            "deployment_environments": split(ask("Intended deployment environments (comma separated)")),
            "authorization_reference": production_authority, "secret_references": split(ask("Production secret references only (comma separated)")),
            "evidence_retention": ask("Production evidence retention policy", "project policy required"),
            "operators": split(ask("Intended operators (comma separated)")), "reviewers": split(ask("Intended reviewers (comma separated)")),
            "governance": ask("Evaluator/policy governance reference", "not yet qualified")},
        "safety": {"default_stop": "draft_pr_or_justified_disposition", "allowed_external_mutations": [],
                   "evidence_upload_policy": "shareable receipts only; no secrets or raw thinking"},
        "alternatives": {},
    })


def load_spec(path, installation_id, state_root, interactive_allowed):
    if path:
        value = json.loads(Path(path).read_text())
        if installation_id and value.get("installation_id") != installation_id: raise ValueError("--installation-id differs from answers")
        return validate_spec(value)
    if not interactive_allowed: raise ValueError("Supply --answers for noninteractive plan/install")
    if not installation_id: raise ValueError("--installation-id is required")
    return interactive(installation_id, state_root)


def practice_run(home, args):
    if not (args.practice_prompt and args.practice_project and args.practice_opening and args.practice_destination):
        raise ValueError("Practice evaluation needs --practice-prompt, --practice-project, --practice-opening and --practice-destination")
    ownership = json.loads((home / "ownership.json").read_text()); spec = json.loads((home / "profile.json").read_text())
    argv = [sys.executable, str(Path(ownership["release"]) / "defensefactory/scripts/opencode-trial.py"),
            "--config", ownership["runtime_config"], "--opening", str(Path(args.practice_opening).resolve()),
            "--prompt", str(Path(args.practice_prompt).resolve()), "--project", str(Path(args.practice_project).resolve()),
            "--destination", str(Path(args.practice_destination).resolve()), "--skills", ownership["release"],
            "--installed-skills", spec["paths"]["skills_directory"], "--run"]
    if spec["telemetry"]["otel_log"]: argv += ["--otel-log", spec["telemetry"]["otel_log"]]
    completed = subprocess.run(argv)
    destination = Path(args.practice_destination).resolve()
    monitor = destination / "monitor-report.json"
    observation = {"schema": "defensefactory/practice-evaluation-reference/v1", "runner_exit_code": completed.returncode,
                   "invocation": str(destination), "monitor_report": str(monitor) if monitor.is_file() else None,
                   "installation_readiness": "inconclusive" if not monitor.is_file() else json.loads(monitor.read_text()).get("installation_readiness", "inconclusive"),
                   "qualification": "The invocation/monitor bytes are local evidence; publish and read them back separately before ticket handoff."}
    append_receipt(home, "practice-evaluation", observation)
    return observation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for flag in ("check", "plan", "install", "evaluate", "report", "uninstall-profile"):
        modes.add_argument("--" + flag, action="store_true")
    modes.add_argument("--resume", metavar="INSTALLATION_ID")
    parser.add_argument("--installation-id")
    parser.add_argument("--answers", type=Path, help="Complete nonsecret environment profile JSON")
    parser.add_argument("--source", type=Path, default=source_default())
    parser.add_argument("--state-root", type=Path, default=default_state())
    parser.add_argument("--noninteractive", action="store_true")
    parser.add_argument("--practice-prompt", type=Path)
    parser.add_argument("--practice-project", type=Path)
    parser.add_argument("--practice-opening", type=Path)
    parser.add_argument("--practice-destination", type=Path)
    args = parser.parse_args(); state = args.state_root.expanduser().resolve()
    try:
        identifier = args.resume or args.installation_id
        home = state / identifier if identifier else None
        if args.check:
            spec = validate_spec(json.loads(args.answers.read_text())) if args.answers else None
            result = discover(spec)
        elif args.plan:
            spec = load_spec(args.answers, identifier, state, not args.noninteractive); result = plan(spec, args.source, state)
        elif args.install:
            spec = load_spec(args.answers, identifier, state, not args.noninteractive); result = apply_install(spec, args.source, state)
        elif args.resume:
            if not home.is_dir(): raise ValueError("Unknown installation ID")
            if not (home / "ownership.json").is_file(): raise ValueError("Interrupted before ownership was committed; inspect preserved failure receipt and use a new installation ID")
            result = deterministic_evaluation(home)
        elif args.evaluate:
            if not home or not home.is_dir(): raise ValueError("--installation-id must name an installed profile")
            result = deterministic_evaluation(home)
            if args.practice_prompt or args.practice_project or args.practice_opening or args.practice_destination:
                result["practice_evaluation"] = practice_run(home, args)
                result["process_qualification"] = "see practice invocation monitor receipt"
        elif args.report:
            if not home or not home.is_dir(): raise ValueError("--installation-id must name an installed profile")
            result = report(home)
        else:
            if not home or not home.is_dir(): raise ValueError("--installation-id must name an installed profile")
            result = uninstall(home)
        print(json.dumps(result, indent=2, sort_keys=True))
        blocked = result.get("result") == "blocked" or result.get("readiness") == "blocked" or result.get("installation_readiness") == "blocked"
        practice = result.get("practice_evaluation", {})
        return 2 if blocked or practice.get("runner_exit_code") not in (None, 0) else 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))


if __name__ == "__main__": raise SystemExit(main())
