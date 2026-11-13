"""Canonical RULES.md grammar, contracts, candidates and claim-state tests."""
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tarfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/defensefactory/scripts"
sys.path.insert(0, str(SCRIPTS))

from factorycore.core import GateError, identity
from factorycore.rules_contracts import (CANDIDATE_SCHEMA, CONTRACT_SCHEMA, claim_status,
    evaluate_candidate, migrate_legacy, parse_rules, render_rules, resolve_contracts,
    rules_change_gate, run_contracts, semantic_diff, semantic_model, transitional_compare, validate_descriptor)


class RulesContractTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name); self.repo = self.root / "repo"; self.repo.mkdir()
        self.git("init", "-q"); self.git("config", "user.name", "Fixture"); self.git("config", "user.email", "fixture@example.invalid")
        self.component = self.repo / "service"; self.component.mkdir()
        (self.component / "boundary_test.py").write_text("raise SystemExit(0)\n")
        intro = self.commit("Introduce control")
        self.descriptor = {"schema": CONTRACT_SCHEMA, "id": "BOUNDARY-TEST", "engine": "test",
            "entrypoint": "boundary-check", "claim": "AUTHENTICATED-BOUNDARY", "invariant": "UNAUTHENTICATED-PEER",
            "applies_to": {"languages": ["python"]}, "produces": CANDIDATE_SCHEMA,
            "coverage": {"scope": "named boundary regression", "limitations": []},
            "introduction": {"repository": "fixture/repo", "commit": intro, "path": "service/boundary_test.py", "selector": "raise SystemExit"},
            "requires": {"executables": [Path(sys.executable).name], "network": False, "runtime": False},
            "observation": "hard", "mandatory": True}
        self.model = {"component": {"id": "fixture-service", "type": "network-service", "owners": ["@fixture"]},
            "claims": [{"id": "AUTHENTICATED-BOUNDARY", "statement": "Only an authenticated peer crosses the privileged boundary.",
                "boundaries": ["Applies to every configured and fallback connection path."],
                "invariants": [{"id": "UNAUTHENTICATED-PEER", "definition": "A privileged boundary accepts an unauthenticated peer."}],
                "contracts": [{"id": "BOUNDARY-TEST", "descriptor": "contracts/boundary-test.contract.json"}],
                "preserves": ["Authenticated peers continue to cross the boundary."],
                "enforcement": {"confirmed_violation": "block", "candidate_pending": "review", "missing_coverage": "block"}}]}

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], stderr=subprocess.PIPE).decode().strip()

    def commit(self, message):
        self.git("add", "-A"); self.git("commit", "-qm", message); return self.git("rev-parse", "HEAD")

    def write_rules(self, descriptor=None):
        (self.component / "contracts").mkdir(exist_ok=True)
        (self.component / "RULES.md").write_text(render_rules(self.model, preamble="Ordinary explanatory prose remains developer-owned."))
        (self.component / "contracts/boundary-test.contract.json").write_text(json.dumps(descriptor or self.descriptor, indent=2) + "\n")

    def test_concise_rules_round_trip_and_ignore_explanatory_prose_semantically(self):
        original = render_rules(self.model, preamble="First explanation.")
        changed = original.replace("First explanation.", "Reworded explanation.")
        parsed = parse_rules(original)
        self.assertEqual(semantic_model(parsed)["claims"], self.model["claims"])
        self.assertEqual(semantic_diff(original, changed)["prose_only"], True)

    def test_rejects_duplicate_missing_unknown_unicode_and_hidden_normative_syntax(self):
        valid = render_rules(self.model)
        cases = [
            (valid + "\n## Claim `AUTHENTICATED-BOUNDARY`\n", "Duplicate claim ID|requires exactly"),
            (valid.replace("### Preserves", "### Kept behavior"), "Unknown normative"),
            (valid.replace("AUTHENTICATED-BOUNDARY", "AUTHENTICATED-BÖUNDARY"), "uppercase ASCII"),
            (valid.replace("### Contracts\n", "<!-- ### Contracts -->\n### Contracts\n", 1), "Hidden normative"),
            (valid.replace("### Contracts\n", "```text\n### Contracts\n```\n### Contracts\n", 1), "Hidden normative"),
        ]
        for raw, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(GateError, message): parse_rules(raw)

    def test_descriptor_is_strict_and_cannot_request_network_or_escape(self):
        self.assertEqual(validate_descriptor(self.descriptor)["id"], "BOUNDARY-TEST")
        for mutation, message in [
            (("entrypoint", "../escape"), "Unsafe"),
            (("requires", {"executables": [], "network": True, "runtime": False}), "cannot grant network"),
            (("extra", True), "unknown or missing"),
        ]:
            value = copy.deepcopy(self.descriptor); value[mutation[0]] = mutation[1]
            with self.subTest(mutation=mutation), self.assertRaisesRegex(GateError, message): validate_descriptor(value)

    def test_exact_subject_contract_execution_and_zero_finding_coverage(self):
        self.write_rules(); revision = self.commit("Add canonical claim and contract")
        registry = resolve_contracts(self.repo, revision, "service/RULES.md")
        self.assertEqual(registry["contracts"][0]["descriptor"]["id"], "BOUNDARY-TEST")
        checks = {"boundary-check": {"argv": [sys.executable, "boundary_test.py"], "cwd": "service", "timeout": 10}}
        run = run_contracts(self.repo, revision, "service/RULES.md", self.root / "run", trusted_checks=checks)
        self.assertEqual(run["result"], "zero_candidates_with_adequate_coverage")
        status = claim_status(parse_rules((self.component / "RULES.md").read_text()), run, [])
        self.assertEqual(status["result"], "satisfied_within_scope")
        self.assertTrue((self.root / "run/boundary-test.log").is_file())

    def test_nonzero_fence_creates_candidate_and_requires_separate_evaluation(self):
        self.write_rules(); revision = self.commit("Add failing fixture")
        checks = {"boundary-check": {"argv": [sys.executable, "-c", "raise SystemExit(7)"], "cwd": "service", "timeout": 10}}
        run = run_contracts(self.repo, revision, "service/RULES.md", self.root / "run", trusted_checks=checks)
        self.assertEqual(run["result"], "candidates"); candidate = run["candidates"][0]
        pending = claim_status(parse_rules((self.component / "RULES.md").read_text()), run, [])
        self.assertEqual(pending["result"], "inconclusive")
        evaluation = evaluate_candidate(candidate, "confirmed_violation", {"identity": "fixture-evaluator", "version": "1"},
            [{"reference": "boundary-test.log"}], "The named hard fence failed at the exact subject.", [], "Repair the invariant.")
        self.assertNotIn("candidate", evaluation)
        self.assertEqual(claim_status(parse_rules((self.component / "RULES.md").read_text()), run, [evaluation])["result"], "violated")

    def test_contract_that_mutates_the_detached_source_cannot_satisfy_claim(self):
        self.write_rules(); revision = self.commit("Add mutation fixture")
        checks = {"boundary-check": {"argv": [sys.executable, "-c", "from pathlib import Path;Path('generated').write_text('x')"], "cwd": "service", "timeout": 10}}
        run = run_contracts(self.repo, revision, "service/RULES.md", self.root / "run", trusted_checks=checks)
        self.assertEqual(run["result"], "inconclusive"); self.assertEqual(run["source_mutations"], ["service/generated"])
        self.assertEqual(claim_status(parse_rules((self.component / "RULES.md").read_text()), run, [])["result"], "inconclusive")

    def test_unavailable_mandatory_engine_is_inconclusive_not_zero_findings(self):
        descriptor = copy.deepcopy(self.descriptor); descriptor["engine"] = "cue"; descriptor["entrypoint"] = "contracts/boundary.cue"; descriptor["requires"]["executables"] = ["factory-definitely-missing-cue"]
        self.write_rules(descriptor); (self.component / "contracts/boundary.cue").write_text("package boundary\n")
        revision = self.commit("Add unavailable contract")
        run = run_contracts(self.repo, revision, "service/RULES.md", self.root / "run")
        self.assertEqual(run["result"], "inconclusive")
        self.assertEqual(claim_status(parse_rules((self.component / "RULES.md").read_text()), run, [])["result"], "inconclusive")

    def test_cross_repository_move_preserves_ids_and_reports_or_resolves_original_history(self):
        self.write_rules(); revision = self.commit("Add portable component")
        destination = self.root / "destination"; destination.mkdir()
        archive = subprocess.check_output(["git", "-C", str(self.repo), "archive", revision])
        with tarfile.open(fileobj=io.BytesIO(archive)) as handle: handle.extractall(destination, filter="data")
        subprocess.check_call(["git", "-C", str(destination), "init", "-q"])
        subprocess.check_call(["git", "-C", str(destination), "config", "user.name", "Fixture"]); subprocess.check_call(["git", "-C", str(destination), "config", "user.email", "fixture@example.invalid"])
        subprocess.check_call(["git", "-C", str(destination), "add", "-A"]); subprocess.check_call(["git", "-C", str(destination), "commit", "-qm", "Move component"])
        moved_revision = subprocess.check_output(["git", "-C", str(destination), "rev-parse", "HEAD"]).decode().strip()
        checks = {"boundary-check": {"argv": [sys.executable, "boundary_test.py"], "cwd": "service", "timeout": 10}}
        missing = run_contracts(destination, moved_revision, "service/RULES.md", self.root / "missing-history", trusted_checks=checks)
        self.assertEqual(missing["result"], "inconclusive"); self.assertEqual(missing["contracts"][0]["introduction"]["state"], "history_unavailable")
        recovered = run_contracts(destination, moved_revision, "service/RULES.md", self.root / "recovered-history", trusted_checks=checks,
                                  contexts={"origins": {"fixture/repo": str(self.repo)}})
        self.assertEqual(recovered["result"], "zero_candidates_with_adequate_coverage")
        self.assertEqual(parse_rules((destination / "service/RULES.md").read_text())["claims"][0]["id"], "AUTHENTICATED-BOUNDARY")

    def test_change_gate_requires_exact_status_and_native_owner_review(self):
        base = self.git("rev-parse", "HEAD")
        self.write_rules(); subject = self.commit("Add component architecture")
        checks = {"boundary-check": {"argv": [sys.executable, "boundary_test.py"], "cwd": "service", "timeout": 10}}
        run = run_contracts(self.repo, subject, "service/RULES.md", self.root / "run", trusted_checks=checks)
        status = claim_status(parse_rules((self.component / "RULES.md").read_text()), run, [])
        policy = {"definition_review_required": True, "owners": {"fixture-service": ["fixture-owner"]}}
        blocked = rules_change_gate(self.repo, "fixture/repo", base, subject, [status], policy, [])
        self.assertTrue(blocked["pr_blocked"]); self.assertIn("native owner review", " ".join(blocked["blockers"]))
        review = {"reviewer": "fixture-owner", "state": "APPROVED", "base": base, "head": subject, "reference": "fixture-review"}
        admitted = rules_change_gate(self.repo, "fixture/repo", base, subject, [status], policy, [review])
        self.assertFalse(admitted["pr_blocked"], admitted["blockers"])
        stale = copy.deepcopy(status); stale["subject"]["revision"] = base
        stale["status_sha256"] = identity({key: value for key, value in stale.items() if key != "status_sha256"})
        self.assertTrue(rules_change_gate(self.repo, "fixture/repo", base, subject, [stale], policy, [review])["pr_blocked"])

    def test_markdown_example_must_be_optional_soft_evidence(self):
        descriptor = copy.deepcopy(self.descriptor); descriptor.update(engine="markdown-example", entrypoint="examples/boundary.md", observation="soft", mandatory=False); descriptor["requires"]["executables"] = []
        self.assertEqual(validate_descriptor(descriptor)["observation"], "soft")
        descriptor["mandatory"] = True
        with self.assertRaisesRegex(GateError, "optional soft"): validate_descriptor(descriptor)

    def test_initial_adapter_classes_normalize_to_candidates_without_component_commands(self):
        bin_dir = self.root / "bin"; bin_dir.mkdir()
        tools = {
            "cue": "#!/bin/sh\nexit 0\n",
            "semgrep": "#!/bin/sh\nprintf '%s' '{\"results\":[{\"check_id\":\"fixture.semgrep\",\"path\":\"service/source.go\",\"start\":{\"line\":7},\"extra\":{\"message\":\"fixture match\"}}]}'\n",
            "codeql": "#!/bin/sh\nprintf '%s' '{\"runs\":[{\"results\":[{\"ruleId\":\"fixture/codeql\",\"message\":{\"text\":\"fixture flow\"}}]}]}'\n",
        }
        for name, body in tools.items():
            path = bin_dir / name; path.write_text(body); path.chmod(0o755)
        old_path = os.environ.get("PATH", ""); os.environ["PATH"] = str(bin_dir) + os.pathsep + old_path
        self.addCleanup(lambda: os.environ.__setitem__("PATH", old_path))
        claim = self.model["claims"][0]
        claim["invariants"].extend([
            {"id": "STRUCTURED-CONSTRAINT", "definition": "A structured constraint fails."},
            {"id": "SYNTAX-PATTERN", "definition": "A bounded syntax pattern matches."},
            {"id": "SEMANTIC-FLOW", "definition": "A semantic flow reaches the boundary."},
            {"id": "REVIEW-EXAMPLE", "definition": "A documented example needs review."},
        ])
        specs = [("CUE-CONTRACT", "cue", "STRUCTURED-CONSTRAINT", "contracts/check.cue", True, "hard", ["cue"]),
                 ("SEMGREP-CONTRACT", "semgrep", "SYNTAX-PATTERN", "contracts/check.yaml", True, "hard", ["semgrep"]),
                 ("CODEQL-CONTRACT", "codeql", "SEMANTIC-FLOW", "contracts/check.ql", True, "hard", ["codeql"]),
                 ("MARKDOWN-EXAMPLE", "markdown-example", "REVIEW-EXAMPLE", "examples/review.md", False, "soft", [])]
        for contract_id, engine, invariant, entrypoint, mandatory, observation, executables in specs:
            path = "contracts/" + contract_id.lower() + ".contract.json"
            claim["contracts"].append({"id": contract_id, "descriptor": path})
            descriptor = copy.deepcopy(self.descriptor); descriptor.update(id=contract_id, engine=engine,
                invariant=invariant, entrypoint=entrypoint, mandatory=mandatory, observation=observation)
            descriptor["requires"]["executables"] = executables
            target = self.component / path; target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(descriptor) + "\n")
        (self.component / "contracts").mkdir(exist_ok=True)
        (self.component / "RULES.md").write_text(render_rules(self.model))
        (self.component / "contracts/boundary-test.contract.json").write_text(json.dumps(self.descriptor) + "\n")
        for relative in ("contracts/check.cue", "contracts/check.yaml", "contracts/check.ql", "examples/review.md"):
            target = self.component / relative; target.parent.mkdir(parents=True, exist_ok=True); target.write_text("fixture\n")
        revision = self.commit("Demonstrate adapter classes")
        checks = {"boundary-check": {"argv": [sys.executable, "boundary_test.py"], "cwd": "service", "timeout": 10}}
        run = run_contracts(self.repo, revision, "service/RULES.md", self.root / "adapters", trusted_checks=checks,
                            contexts={"codeql_database": self.root / "codeql-db"})
        self.assertEqual({item["observation"]["engine"] for item in run["candidates"]}, {"semgrep", "codeql"})
        by_id = {row["id"]: row for row in run["contracts"]}
        self.assertEqual(by_id["CUE-CONTRACT"]["coverage"], "complete")
        self.assertEqual(by_id["MARKDOWN-EXAMPLE"]["result"], "unsupported")

    def test_migration_is_proposed_and_transitional_comparison_detects_drift(self):
        legacy = {"schema_version": 2, "component": "fixture-service",
            "bug_classes": [{"id": "unauthenticated-peer", "definition": "A peer is not authenticated."}],
            "claims": [{"id": "authenticated-boundary", "statement": "Only an authenticated peer crosses the boundary.",
                        "preserves": ["Authenticated use works."], "bug_classes": ["unauthenticated-peer"], "fences": ["boundary-test"]}],
            "fences": [{"id": "boundary-test", "kind": "hard", "mechanism": "test", "check": "boundary-check",
                        "controls": [{"path": "boundary_test.py", "selector": "boundary",
                            "introduced": {"repository": "fixture/repo", "ref": self.descriptor["introduction"]["commit"], "path": "service/boundary_test.py"}}]}]}
        raw, descriptors = migrate_legacy(legacy, "network-service", ["@fixture"], "# Existing guidance\n\nKeep this explanation."); model = parse_rules(raw)
        self.assertIn("owner review is required", raw); self.assertIn("Keep this explanation.", raw); self.assertEqual(len(descriptors), 1)
        self.assertTrue(transitional_compare(legacy, model)["semantically_equal"])
        changed = copy.deepcopy(model); changed["claims"][0]["statement"] = "Different"
        self.assertFalse(transitional_compare(legacy, changed)["semantically_equal"])


if __name__ == "__main__": unittest.main()
