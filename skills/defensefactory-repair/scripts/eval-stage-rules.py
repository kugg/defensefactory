#!/usr/bin/env python3
"""Offline evaluation of stage rules, contradictions, exports and opening binding."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from factorycore.core import identity
from factorycore.stage_rules import validate_package_safe
from factorycore.trial_controls import scope_prepare, stage_start


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def save_human_summary(path, summary, validations, rejected, opening):
    finding = next((item for item in rejected.get("findings", []) if item["kind"] == "required_forbidden_conflict"), {})
    assignments = sorted({item["modeled_assignments"] for item in validations.values()})
    lines = [
        "# Stage-rule evaluation", "", f"Result: **{summary['result']}**", "",
        f"- Packages validated: {len(validations)} ({', '.join(sorted(validations))})",
        f"- Exhaustive assignments per package: {', '.join(map(str, assignments))}",
        f"- Synthetic contradiction rejected: {summary['contradiction_rejected']}",
        f"- Conflicting rules: {', '.join(finding.get('rule_ids', [])) or 'not recorded'}",
        f"- Counterexample condition: `{json.dumps(finding.get('counterexample', {}), sort_keys=True)}`",
        f"- Effective opening-rule digest: `{opening['stage_rules']['effective_rules_sha256']}`",
        f"- Selected profile digests: `{json.dumps(opening['scope']['rule_profile_sha256'], sort_keys=True)}`",
        "", "Limitations:", "", *["- " + item for item in summary["limitations"]], "",
    ]
    path.write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skills", type=Path, default=HERE.parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists(): parser.error("Output exists; preserve it and choose a new directory")
    args.output.mkdir(parents=True)
    skills = args.skills.resolve(); root = skills / "defensefactory"

    validations = {}
    for package in sorted(skills.glob("defensefactory*")):
        validations[package.name] = validate_package_safe(package, root)
    save(args.output / "all-packages.json", validations)
    if len(validations) != 9 or {item["result"] for item in validations.values()} != {"satisfied"}:
        raise SystemExit("all nine source packages must satisfy their effective rules")

    with tempfile.TemporaryDirectory() as temporary:
        fixture = Path(temporary); fixture_root = fixture / "defensefactory"; fixture_stage = fixture / "defensefactory-assess"
        fixture_root.mkdir(); fixture_stage.mkdir()
        shutil.copy2(root / "RULES.md", fixture_root / "RULES.md")
        shutil.copy2(root / "SKILL.md", fixture_root / "SKILL.md")
        shutil.copy2(skills / "defensefactory-assess/RULES.md", fixture_stage / "RULES.md")
        shutil.copy2(skills / "defensefactory-assess/SKILL.md", fixture_stage / "SKILL.md")
        conflict = {
            "id": "EVAL-CONTRADICTION", "scope": "assess", "strength": "must",
            "when": {"stage_state": "opened"},
            "requires": {"actions": ["execute_without_scope"]}, "forbids": {}, "allows": {},
            "terminal": "either", "mutation": "none", "overrides": [], "precedence": 10,
            "safety": False, "fulfillment": "operator_only"
        }
        raw = (fixture_stage / "RULES.md").read_text()
        raw = raw.replace('"rules": [', '"rules": [' + json.dumps(conflict, sort_keys=True) + ',', 1)
        (fixture_stage / "RULES.md").write_text(raw)
        rejected = validate_package_safe(fixture_stage, fixture_root)
        save(args.output / "synthetic-contradiction.json", rejected)
        if rejected["result"] != "violated" or not any(item["kind"] == "required_forbidden_conflict" for item in rejected.get("findings", [])):
            raise SystemExit("synthetic contradiction was not deterministically rejected")

    package = skills / "defensefactory-verify"
    preparation = scope_prepare({
        "case": "EVAL-STAGE-RULES", "attempt": "offline", "stage": "verify",
        "subject": {"repository": "fixture/component", "revision": "a" * 40},
        "performed_by": "offline-evaluator", "authorization_reference": "offline fixture",
        "boundaries": "No service, model, product or network calls", "package": str(package),
    })
    publication = {"id": "synthetic-publication", "body": preparation["scope_body"], "createdAt": preparation["prepared_at"]}
    opening = stage_start(preparation, publication, {**publication, "operation": "retrieval", "retrieved_at": preparation["prepared_at"]})
    save(args.output / "opening.json", opening)
    if opening["stage_rules"] != preparation["scope"]["stage_rules"]:
        raise SystemExit("opening did not preserve the exact effective-rule binding")
    if opening["stage_rules"]["effective_rules_sha256"] != validations["defensefactory-verify"]["effective_rules_sha256"]:
        raise SystemExit("opening digest differs from independently validated effective rules")

    summary = {
        "schema": "defensefactory/stage-rules-evaluation/v1", "result": "satisfied",
        "packages_validated": sorted(validations), "contradiction_rejected": True,
        "opening_rule_binding_sha256": identity(opening["stage_rules"]),
        "limitations": [
            "Offline deterministic helper evaluation; no ticket, model, service or cyber evaluation was performed.",
            "Procedure conformance proves mappings, not live-agent adherence or operator judgment.",
        ],
    }
    save(args.output / "summary.json", summary)
    save_human_summary(args.output / "summary.md", summary, validations, rejected, opening)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__": raise SystemExit(main())
