#!/usr/bin/env python3
"""Check, extract, compare, run and migrate canonical component RULES.md files."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from factorycore.core import GateError
from factorycore.rules_contracts import (claim_status, evaluate_candidate, migrate_legacy, parse_rules,
    resolve_contracts, run_contracts, semantic_diff, semantic_model, transitional_compare)
from factorycore.registry import source_blob


def _json(path):
    return json.loads(Path(path).read_text())


def _write(value, output):
    raw = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if output:
        path = Path(output)
        if path.exists():
            raise GateError("Output already exists: " + str(path))
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(raw)
    else:
        print(raw, end="")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check"); check.add_argument("rules", type=Path); check.add_argument("--legacy", type=Path); check.add_argument("--output")
    extract = commands.add_parser("extract"); extract.add_argument("rules", type=Path); extract.add_argument("--output")
    diff = commands.add_parser("semantic-diff"); diff.add_argument("--repo", required=True); diff.add_argument("--path", required=True); diff.add_argument("--base", required=True); diff.add_argument("--candidate", required=True); diff.add_argument("--output")
    contracts = commands.add_parser("contracts"); contracts.add_argument("--repo", required=True); contracts.add_argument("--subject", required=True); contracts.add_argument("--path", required=True); contracts.add_argument("--output")
    run = commands.add_parser("run"); run.add_argument("--repo", required=True); run.add_argument("--subject", required=True); run.add_argument("--path", required=True); run.add_argument("--destination", required=True); run.add_argument("--contract", action="append"); run.add_argument("--checks"); run.add_argument("--contexts")
    evaluate = commands.add_parser("evaluate"); evaluate.add_argument("--candidate", required=True); evaluate.add_argument("--decision", required=True); evaluate.add_argument("--output", required=True)
    status = commands.add_parser("status"); status.add_argument("--subject", required=True); status.add_argument("--rules", required=True); status.add_argument("--run", required=True); status.add_argument("--evaluations", nargs="*", default=[]); status.add_argument("--output")
    migrate = commands.add_parser("migrate"); migrate.add_argument("claims", type=Path); migrate.add_argument("rules", type=Path); migrate.add_argument("--component-type", required=True); migrate.add_argument("--owner", action="append", required=True); migrate.add_argument("--descriptors", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "check":
            model = parse_rules(args.rules.read_bytes()); result = {"result": "valid", "model": semantic_model(model)}
            if args.legacy: result["legacy"] = transitional_compare(_json(args.legacy), model)
            _write(result, args.output)
        elif args.command == "extract": _write(semantic_model(parse_rules(args.rules.read_bytes())), args.output)
        elif args.command == "semantic-diff": _write(semantic_diff(source_blob(args.repo, args.base, args.path), source_blob(args.repo, args.candidate, args.path)), args.output)
        elif args.command == "contracts": _write(resolve_contracts(args.repo, args.subject, args.path), args.output)
        elif args.command == "run":
            result = run_contracts(args.repo, args.subject, args.path, args.destination, args.contract,
                                   _json(args.checks) if args.checks else {}, _json(args.contexts) if args.contexts else {})
            print(json.dumps({"result": result["result"], "run": str(Path(args.destination) / "contract-run.json")}, sort_keys=True))
        elif args.command == "evaluate":
            candidate = _json(args.candidate); decision = _json(args.decision)
            _write(evaluate_candidate(candidate, decision["disposition"], decision["evaluator"], decision["evidence"],
                                      decision["explanation"], decision.get("coverage_limitations", []), decision["next_action"], decision.get("duplicate_of")), args.output)
        elif args.command == "status":
            model = parse_rules(Path(args.rules).read_bytes()); run_receipt = _json(args.run)
            if run_receipt.get("subject", {}).get("revision") != args.subject: raise GateError("Status subject differs from contract run")
            _write(claim_status(model, run_receipt, [_json(item) for item in args.evaluations]), args.output)
        elif args.command == "migrate":
            existing = args.rules.read_text() if args.rules.exists() else ""
            if "Grammar: `defensefactory/rules/v1`" in existing: raise GateError("Existing canonical RULES.md must be amended through normal review, not overwritten by migration")
            if args.descriptors.exists(): raise GateError("Migration refuses to overwrite an existing descriptor directory")
            raw, descriptors = migrate_legacy(_json(args.claims), args.component_type, args.owner, existing)
            args.rules.write_text(raw); args.descriptors.mkdir(parents=True)
            for item in descriptors: (args.descriptors / (item["id"].lower() + ".contract.json")).write_text(json.dumps(item, indent=2, sort_keys=True) + "\n")
            print(json.dumps({"result": "proposed_incomplete", "rules": str(args.rules), "descriptors": len(descriptors), "next_action": "Owner must resolve migration limitations and make descriptor paths match before removing claims.json"}, sort_keys=True))
    except (OSError, ValueError, json.JSONDecodeError, GateError, subprocess.CalledProcessError) as error:
        print(json.dumps({"result": "inconclusive", "error": str(error)}, sort_keys=True), file=sys.stderr); raise SystemExit(2)


if __name__ == "__main__":
    import subprocess
    main()
