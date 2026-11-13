#!/usr/bin/env python3
"""Evaluate canonical RULES.md mechanics in disposable local fixtures only."""
import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE if (HERE / "factorycore").is_dir() else HERE.parents[1]))
from factorycore.core import require
from factorycore.rules_contracts import (CANDIDATE_SCHEMA, CONTRACT_SCHEMA, claim_status,
    evaluate_candidate, parse_rules, render_rules, rules_change_gate, run_contracts, semantic_diff)


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.PIPE).decode().strip()


def commit(repo, message):
    git(repo, "add", "-A"); git(repo, "commit", "-qm", message); return git(repo, "rev-parse", "HEAD")


def save(root, name, value):
    (root / (name + ".json")).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    for tool in ("git", Path(sys.executable).name):
        if not shutil.which(tool): parser.error("Install " + tool + " before running this evaluation")
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="factory-rules-eval-") as temp:
        repo = Path(temp) / "repo"; repo.mkdir(); git(repo, "init", "-q"); git(repo, "config", "user.name", "Rules fixture"); git(repo, "config", "user.email", "fixture@example.invalid")
        component = repo / "service"; component.mkdir(); (component / "control.py").write_text("def allowed(peer):\n    return peer == 'trusted'\n")
        (component / "check.py").write_text("from control import allowed\nassert not allowed('other')\nassert allowed('trusted')\n")
        introduction = commit(repo, "Introduce synthetic component control")
        model = {"component": {"id": "fixture-service", "type": "service", "owners": ["@fixture-owner"]},
            "claims": [{"id": "INTENDED-BOUNDARY", "statement": "Only the intended peer crosses the synthetic boundary.",
                "boundaries": ["Applies only to this disposable fixture."],
                "invariants": [{"id": "BOUNDARY-BYPASS", "definition": "Another peer crosses the boundary."}],
                "contracts": [{"id": "BOUNDARY-TEST", "descriptor": "contracts/boundary.contract.json"}],
                "preserves": ["The intended peer continues to cross the boundary."],
                "enforcement": {"confirmed_violation": "block", "candidate_pending": "review", "missing_coverage": "block"}}]}
        descriptor = {"schema": CONTRACT_SCHEMA, "id": "BOUNDARY-TEST", "engine": "test", "entrypoint": "boundary-check",
            "claim": "INTENDED-BOUNDARY", "invariant": "BOUNDARY-BYPASS", "applies_to": {"languages": ["python"]},
            "produces": CANDIDATE_SCHEMA, "coverage": {"scope": "named negative and positive synthetic assertions", "limitations": []},
            "introduction": {"repository": "fixture/repo", "commit": introduction, "path": "service/check.py", "selector": "assert not allowed"},
            "requires": {"executables": [Path(sys.executable).name], "network": False, "runtime": False},
            "observation": "hard", "mandatory": True}
        (component / "contracts").mkdir(); (component / "RULES.md").write_text(render_rules(model, preamble="Synthetic evaluation only.")); (component / "contracts/boundary.contract.json").write_text(json.dumps(descriptor, indent=2) + "\n")
        base = commit(repo, "Add canonical synthetic rules")
        checks = {"boundary-check": {"argv": [sys.executable, "check.py"], "cwd": "service", "timeout": 10}}
        baseline_run = run_contracts(repo, base, "service/RULES.md", output / "baseline-run", trusted_checks=checks)
        baseline_status = claim_status(parse_rules((component / "RULES.md").read_text()), baseline_run, [])
        require(baseline_status["result"] == "satisfied_within_scope", "Baseline claim status did not satisfy declared scope")
        save(output, "baseline-status", baseline_status)

        original_rules = (component / "RULES.md").read_text(); (component / "RULES.md").write_text(original_rules.replace("Synthetic evaluation only.", "Reworded synthetic explanation."))
        require(semantic_diff(original_rules, (component / "RULES.md").read_text())["prose_only"], "Prose-only edit changed normative model")
        (component / "control.py").write_text("def allowed(peer):\n    return True\n"); bypass = commit(repo, "Introduce synthetic bypass")
        bypass_run = run_contracts(repo, bypass, "service/RULES.md", output / "bypass-run", trusted_checks=checks)
        require(len(bypass_run["candidates"]) == 1, "Failing hard contract did not produce one candidate")
        pending = claim_status(parse_rules((component / "RULES.md").read_text()), bypass_run, []); require(pending["result"] == "inconclusive", "Unevaluated candidate was not inconclusive")
        evaluation = evaluate_candidate(bypass_run["candidates"][0], "confirmed_violation", {"identity": "synthetic-evaluator", "version": "1"}, [{"reference": "bypass-run/boundary-test.log"}], "The named synthetic hard fence failed.", [], "Restore both negative and positive behavior.")
        violated = claim_status(parse_rules((component / "RULES.md").read_text()), bypass_run, [evaluation]); require(violated["result"] == "violated", "Confirmed candidate did not violate claim")
        save(output, "bypass-evaluation", evaluation); save(output, "bypass-status", violated)

        policy = {"definition_review_required": True, "owners": {"fixture-service": ["fixture-owner"]}}
        gate = rules_change_gate(repo, "fixture/repo", base, bypass, [violated], policy, [{"reviewer": "fixture-owner", "state": "APPROVED", "base": base, "head": bypass, "reference": "synthetic-review"}])
        require(gate["pr_blocked"] and any("violated" in item for item in gate["blockers"]), "Integration gate admitted violated claim")
        save(output, "integration-gate", gate)
        git(repo, "bundle", "create", str(output / "fixture.bundle"), "--all")
        save(output, "summary", {"result": "satisfied_within_scope", "baseline": baseline_status["result"], "unevaluated_candidate": pending["result"], "evaluated_candidate": violated["result"], "integration_blocked": gate["pr_blocked"], "scope": "Disposable Git/Python mechanics only; no product, ticket, model, network or security evaluation."})
        print(json.dumps({"result": "satisfied_within_scope", "output": str(output)}, sort_keys=True))


if __name__ == "__main__": main()
