"""Offline environment installer and monitor tests; no service, model or credential calls."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/defensefactory/scripts"
sys.path.insert(0, str(SCRIPTS))
from factorycore.environment_install import (SCHEMA, apply_install, deterministic_evaluation, discover,
    plan, report, uninstall, validate_spec, verify_installed_release)
from factorycore.trial_monitor import qualify


class EnvironmentInstallTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve(); launcher = Path(shutil.which("true")).resolve()
        self.spec = {"schema": SCHEMA, "installation_id": "fixture-install", "model": "fixture/model", "launcher": str(launcher),
            "ticket": {"system": "linear", "workspace": "fixture", "team": "fixture", "project": "Fixture project", "endpoint": "", "credential_reference": "", "write_qualification": False},
            "source_intelligence": {"kind": "source_only", "mcp_url": "", "index_api_url": "", "credential_reference": "", "required": False, "sample_repository": "", "sample_ref": ""},
            "telemetry": {"otel_endpoint": "", "otel_log": "", "thinking_retained_local": True, "retention_policy": "private local only"},
            "paths": {"skills_directory": str(self.root / "client/skills"), "private_evidence_root": str(self.root / "evidence"), "state_root": str(self.root / "state")},
            "practice": {"kind": "source_only", "location": "fixture-source", "allowed_repositories": ["fixture/repository"], "allowed_network_destinations": [], "external_provider_calls": False, "credential_class": "synthetic", "cleanup_policy": "preserve evidence", "resource_limits": "bounded", "deployment_tests": False, "runtime_evidence": "none"},
            "production": {"target_kind": "developer_workstation", "description": "declared only", "repositories": [], "ticket_project": "Fixture project", "pr_repository": "", "branch_policy": "", "deployment_environments": [], "authorization_reference": "fixture reviewed plan", "secret_references": [], "evidence_retention": "fixture", "operators": [], "reviewers": [], "governance": "fixture"},
            "safety": {"default_stop": "draft_pr_or_justified_disposition", "allowed_external_mutations": [], "evidence_upload_policy": "shareable receipts only"}, "alternatives": {}}

    def test_discovery_and_plan_are_read_only_and_distinguish_soft_capabilities(self):
        spec = validate_spec(self.spec); before = set(self.root.rglob("*"))
        discovery = discover(spec); intended = plan(spec, ROOT / "skills", self.root / "state")
        self.assertNotEqual(discovery["readiness"], "blocked")
        self.assertEqual(intended["result"], "planned")
        self.assertEqual(before, set(self.root.rglob("*")))
        self.assertTrue(all(item["disposition"] in ("available", "configured", "replaceable_alternative", "missing_recommended", "not_applicable", "unknown") for item in discovery["recommended"]))

    def test_secret_values_and_unsafe_practice_defaults_are_rejected(self):
        bad = copy.deepcopy(self.spec); bad["ticket"]["credential_reference"] = "actual-secret-value"
        with self.assertRaisesRegex(ValueError, "Credentials must use"): validate_spec(bad)
        bad = copy.deepcopy(self.spec); bad["practice"]["external_provider_calls"] = True
        with self.assertRaisesRegex(ValueError, "forbid real provider"): validate_spec(bad)

    def test_install_evaluate_report_resume_and_uninstall_preserve_evidence(self):
        installed = apply_install(self.spec, ROOT / "skills", self.root / "state")
        home = Path(installed["home"]); marker = self.root / "evidence/preserve.txt"; marker.write_text("keep")
        evaluation = deterministic_evaluation(home); summary = report(home)
        self.assertEqual(evaluation["technical_result"], "deterministic_package_valid")
        self.assertEqual(summary["readiness"], "practice_only")
        self.assertGreaterEqual(summary["receipt_count"], 2)
        second = deterministic_evaluation(home)
        self.assertEqual(second["technical_result"], "deterministic_package_valid")
        retired = uninstall(home)
        self.assertEqual(retired["result"], "profile_uninstalled")
        self.assertEqual(marker.read_text(), "keep")
        self.assertTrue(Path(json.loads((home / "ownership.json").read_text())["release"]).is_dir())
        self.assertTrue((home / "receipts").is_dir())

    def test_installed_release_drift_blocks_resume_evaluation(self):
        installed = apply_install(self.spec, ROOT / "skills", self.root / "state")
        home = Path(installed["home"])
        release = Path(json.loads((home / "ownership.json").read_text())["release"])
        self.assertEqual(verify_installed_release(home)["factory_release_digest"], release.name)
        (release / "defensefactory/SKILL.md").write_text("changed after installation\n")
        with self.assertRaisesRegex(ValueError, "release bytes differ"):
            deterministic_evaluation(home)

    def test_answer_profile_state_root_is_default_and_mismatch_is_rejected(self):
        answers = self.root / "answers.json"; answers.write_text(json.dumps(self.spec))
        command = [sys.executable, str(SCRIPTS / "install-defensefactory.py"), "--plan",
                   "--answers", str(answers), "--noninteractive"]
        planned = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(planned.returncode, 0, planned.stderr)
        self.assertIn(str(self.root / "state"), planned.stdout)
        mismatched = subprocess.run(command + ["--state-root", str(self.root / "other-state")], capture_output=True, text=True)
        self.assertNotEqual(mismatched.returncode, 0)
        self.assertIn("differs from paths.state_root", mismatched.stderr)

    def test_monitor_reports_failures_without_copying_thinking_or_output(self):
        events = self.root / "events.jsonl"
        events.write_text("\n".join(json.dumps(item) for item in [
            {"type": "reasoning", "part": {"text": "SENSITIVE PRIVATE THINKING"}},
            {"type": "tool_use", "part": {"tool": "bash", "state": {"status": "completed", "input": {"command": "go test ./..."}, "output": "SENSITIVE OUTPUT"}}},
            {"type": "tool_use", "part": {"tool": "bash", "state": {"status": "completed", "input": {"command": "python stage-exec.py --help"}}}},
            {"type": "error", "error": {"message": "getaddrinfo ENOTFOUND example.invalid"}},
            {"type": "notice", "message": "tool output truncated"},
        ]) + "\n")
        result = qualify(events, {"runner_exit_code": 1, "producer_exit_code": 1, "whole_attempt_handoff_ready": False, "reasoning_events": 1})
        encoded = json.dumps(result)
        self.assertNotIn("SENSITIVE", encoded)
        self.assertEqual(result["installation_readiness"], "blocked")
        self.assertEqual(result["process_qualification"]["unguarded_command_lines"], [2])
        self.assertEqual(result["process_qualification"]["guarded_command_lines"], [3])
        self.assertEqual(result["process_qualification"]["errors"][0]["class"], "network_dns")
        self.assertEqual(result["process_qualification"]["tool_truncation_lines"], [5])


if __name__ == "__main__": unittest.main()
