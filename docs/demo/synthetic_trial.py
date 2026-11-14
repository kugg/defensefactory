#!/usr/bin/env python3
"""Render a deterministic, service-free README demo from the tested bug-class fixture."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "skills/defensefactory/scripts"))

from factorycore.bugclasses import pr_section, verify_class
from tests.test_bugclasses import BugClassTests


def build():
    case = BugClassTests(methodName="test_pr_section_and_linkage_readback_preserve_historical_state_and_resume")
    case.setUp()
    try:
        bug_class, repair = case.resolved()
        matrix = case.matrix(bug_class=bug_class, repair=repair)
        preserved, other_claims = case.support()
        verification = verify_class(
            bug_class,
            matrix,
            {
                "id": "PEER-IDENTITY-FENCE",
                "result": "satisfied",
                "evidence_reference": "https://evidence.invalid/fence",
            },
            {
                "id": "PEER-AUTH",
                "result": "satisfied",
                "evidence_reference": "https://evidence.invalid/claim",
            },
            preserved,
            other_claims,
        )
        section = pr_section(
            bug_class,
            matrix,
            verification,
            "https://github.com/fixture/repository/pull/7",
        )
        return {
            "schema": "defensefactory/readme-synthetic-trial/v1",
            "qualification": "Offline deterministic fixture; no model, ticket service, product target or deployment call.",
            "report": {
                "ticket": case.trigger["ticket"],
                "lifecycle": case.trigger["lifecycle"],
                "title": case.trigger["title"],
            },
            "assessment": {
                "claim": case.definition["claim_id"],
                "invariant": case.definition["invariant_id"],
                "boundary": case.definition["boundary"],
                "included_current": ["FIX-1"],
                "included_historical": ["FIX-2"],
            },
            "repair": {
                "restores_claim": repair["design"]["restores_claim"],
                "paths": [row["kind"] for row in repair["design"]["path_analysis"]],
                "hard_fence": repair["design"]["hard_fence"],
            },
            "verification": {
                "outcome": verification["outcome"],
                "class_wide_remediation_claim_permitted": verification["class_wide_remediation_claim_permitted"],
                "merge_subject": matrix["merge_subject"],
                "variant_count": len(matrix["rows"]),
            },
            "delivery": {
                "pr": section["pr_url"],
                "proof_section_generated": bool(section["markdown"]),
                "section_sha256": section["receipt_sha256"],
            },
            "architecture_improvement": {
                "suggestion": "Make verified peer identity a required architectural fence for credential-bearing gateways.",
                "rule": "Credentials must not cross to an unverified peer.",
                "contract": repair["design"]["hard_fence"]["contract"],
                "applies_to_future_attempts": True,
            },
            "limitations": [
                "Synthetic metadata and execution evidence only.",
                "No live finding, source index, runtime, pull request mutation or deployment was evaluated.",
            ],
        }
    finally:
        case.doCleanups()


def human(record):
    paths = " · ".join(record["repair"]["paths"])
    return "\n".join(
        [
            "DARK FACTORY · SYNTHETIC HELPER DEMO",
            "scope        offline fixture · no model or service calls",
            f"report       {record['report']['ticket']} [{record['report']['lifecycle']}] · {record['report']['title']}",
            f"assess       claim {record['assessment']['claim']} · invariant {record['assessment']['invariant']}",
            f"history      FIX-2 [completed] · included in the same evaluated bug class",
            f"repair       restores {record['repair']['restores_claim']} · {paths}",
            f"fence        {record['repair']['hard_fence']['id']} · {record['repair']['hard_fence']['contract']}",
            f"verify       {record['verification']['outcome']} · {record['verification']['variant_count']} variants",
            "delivery     PR proof section generated · exact merge subject retained",
            f"suggestion   {record['architecture_improvement']['suggestion']}",
            "next         version the rule, contract and fence for a fresh attempt",
            "limits       synthetic corpus · no live product or deployment claim",
        ]
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    record = build()
    print(json.dumps(record, indent=2, sort_keys=True) if args.json else human(record))


if __name__ == "__main__":
    main()
