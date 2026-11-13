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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("discover", "classify", "define", "repair-contract", "variant-matrix", "verify", "pr-section", "ticket-links", "readback"))
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists(): parser.error("Output exists; preserve it and select a new receipt path")
    try:
        data = dereference(json.loads(args.input.read_text()), args.input.resolve().parent)
        result = run(args.command, data)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as stream: json.dump(result, stream, indent=2, sort_keys=True); stream.write("\n")
        print(json.dumps({"command": args.command, "output": str(args.output), "result": result.get("outcome", result.get("result", "recorded"))}))
        return 2 if result.get("outcome") in ("class_inconclusive", "class_violated", "class_definition_rejected") or result.get("result") == "inconclusive" else 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        parser.error(str(error))


if __name__ == "__main__": raise SystemExit(main())
