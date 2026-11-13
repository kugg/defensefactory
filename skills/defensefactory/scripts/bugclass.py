#!/usr/bin/env python3
"""Create durable bug-class discovery, membership, repair, proof and linkage receipts."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from factorycore.bugclasses import (define_class, discover, evaluate_membership, linkage_plan, linkage_readback,
    pr_section, repair_contract, variant_matrix, verify_class)


COMMANDS = ("discover", "classify", "define", "repair-contract", "variant-matrix", "verify", "pr-section", "ticket-links", "readback")


def dereference(value, base):
    if isinstance(value, dict) and set(value) == {"receipt_file"}:
        path = Path(value["receipt_file"]); path = path if path.is_absolute() else base / path
        return json.loads(path.read_text())
    if isinstance(value, dict): return {key: dereference(item, base) for key, item in value.items()}
    if isinstance(value, list): return [dereference(item, base) for item in value]
    return value


def run(command, data):
    if command == "discover": return discover(data["trigger"], data["subject"], data["queries"], data["tickets"], data["coverage"])
    if command == "classify": return evaluate_membership(data["discovery"], data["decisions"], data["evaluator"])
    if command == "define": return define_class(data["membership"], data["definition"])
    if command == "repair-contract": return repair_contract(data["bug_class"], data["design"])
    if command == "variant-matrix": return variant_matrix(data["bug_class"], data["repair"], data["pr_head"], data["merge_subject"], data["rows"], data["evaluator"])
    if command == "verify": return verify_class(data["bug_class"], data["matrix"], data["fence"], data["claim"], data["preservation"], data["other_claims"], data.get("boundary_review"))
    if command == "pr-section": return pr_section(data["bug_class"], data["matrix"], data["verification"], data["pr_url"])
    if command == "ticket-links": return linkage_plan(data["bug_class"], data["section"], data["lifecycles"])
    if command == "readback": return linkage_readback(data["plan"], data["observation"])
    raise ValueError("Unknown command")


def templates():
    """Return editable, receipt-linked inputs for the complete nine-step walk."""
    receipt = lambda name: {"receipt_file": name}
    replace = "__REPLACE__"
    return {
        "01-discover-input.json": {"trigger": {"ticket": "CURRENT-1", "url": "https://tickets.example/CURRENT-1", "lifecycle": "active", "title": replace, "component": replace, "boundary": replace, "claim_id": replace, "invariant_id": replace, "behavior": replace, "evidence_references": [{"kind": "ticket_attachment", "reference": "https://tickets.example/CURRENT-1/evidence"}], "source_state": "current", "taxonomy": [], "relations": []}, "subject": {"repository": "owner/repository", "revision": "0" * 40}, "queries": [{"id": "ticket-history", "source": "ticket", "query": replace, "scope": replace, "result_reference": "https://tickets.example/query-evidence", "coverage_limitations": []}], "tickets": [{"ticket": "HISTORICAL-1", "url": "https://tickets.example/HISTORICAL-1", "lifecycle": "completed", "title": replace, "component": replace, "boundary": replace, "claim_id": replace, "invariant_id": replace, "behavior": replace, "evidence_references": [{"kind": "ticket_attachment", "reference": "https://tickets.example/HISTORICAL-1/evidence"}], "source_state": "current", "taxonomy": [], "relations": []}], "coverage": {"ticket_states": ["active", "completed"], "repositories": ["owner/repository"], "history_sources": ["ticket"], "codeintel": {"disposition": "__REPLACE__", "reason": "__REPLACE__"}, "limitations": []}},
        "02-classify-input.json": {"discovery": receipt("01-discovery.json"), "decisions": [], "evaluator": {"identity": replace, "version": replace, "method": replace, "scope_reference": replace}},
        "03-define-input.json": {"membership": receipt("02-membership.json"), "definition": {"id": "REPLACE-CLASS", "statement": replace, "claim_id": replace, "invariant_id": replace, "applicable_component_types": [], "boundary": replace, "mandatory_contracts": [], "required_hard_fence": replace, "coverage_expectations": replace, "owner": replace, "reviewers": [], "lineage": []}},
        "04-repair-contract-input.json": {"bug_class": receipt("03-class.json"), "design": {"restores_claim": replace, "closes_invariant": replace, "path_analysis": [], "preserves": [], "hard_fence": {}, "historical_variants": [], "other_claims": [], "limitations": [], "boundary_change": "unchanged", "boundary_review_reference": ""}},
        "05-variant-matrix-input.json": {"bug_class": receipt("03-class.json"), "repair": receipt("04-repair-contract.json"), "pr_head": {"repository": "owner/repository", "revision": "0" * 40}, "merge_subject": {"repository": "owner/repository", "revision": "0" * 40}, "rows": [], "evaluator": {"identity": replace, "version": replace, "policy_reference": replace}},
        "06-verify-input.json": {"bug_class": receipt("03-class.json"), "matrix": receipt("05-matrix.json"), "fence": {"id": replace, "result": "inconclusive", "evidence_reference": replace}, "claim": {"id": replace, "result": "inconclusive", "evidence_reference": replace}, "preservation": [], "other_claims": [], "boundary_review": None},
        "07-pr-section-input.json": {"bug_class": receipt("03-class.json"), "matrix": receipt("05-matrix.json"), "verification": receipt("06-verification.json"), "pr_url": "https://github.com/owner/repository/pull/1"},
        "08-ticket-links-input.json": {"bug_class": receipt("03-class.json"), "section": receipt("07-pr-section.json"), "lifecycles": {"CURRENT-1": "active", "HISTORICAL-1": "completed"}},
        "09-readback-input.json": {"plan": receipt("08-link-plan.json"), "observation": {"pr": {"url": "https://github.com/owner/repository/pull/1", "content_sha256": replace}, "tickets": [{"ticket": "CURRENT-1", "lifecycle": "active", "pr_urls": ["https://github.com/owner/repository/pull/1"]}, {"ticket": "HISTORICAL-1", "lifecycle": "completed", "pr_urls": ["https://github.com/owner/repository/pull/1"]}], "completed_effect_keys": [], "retrieved_at": replace}},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=COMMANDS + ("templates",))
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists(): parser.error("Output exists; preserve it and select a new receipt path")
    try:
        if args.command == "templates":
            if args.input: raise ValueError("templates does not consume an input receipt")
            args.output.mkdir(parents=True)
            for name, value in templates().items():
                with (args.output / name).open("x") as stream: json.dump(value, stream, indent=2, sort_keys=True); stream.write("\n")
            print(json.dumps({"command": "templates", "output": str(args.output), "files": sorted(templates())}))
            return 0
        if not args.input: raise ValueError("--input is required for " + args.command)
        data = dereference(json.loads(args.input.read_text()), args.input.resolve().parent)
        result = run(args.command, data)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as stream: json.dump(result, stream, indent=2, sort_keys=True); stream.write("\n")
        print(json.dumps({"command": args.command, "output": str(args.output), "result": result.get("outcome", result.get("result", "recorded"))}))
        return 2 if result.get("outcome") in ("class_inconclusive", "class_violated", "class_definition_rejected") or result.get("result") == "inconclusive" else 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        parser.error(str(error))


if __name__ == "__main__": raise SystemExit(main())
