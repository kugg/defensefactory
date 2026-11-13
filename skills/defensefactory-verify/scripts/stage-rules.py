#!/usr/bin/env python3
"""Validate effective factory stage rules and procedure conformance."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from factorycore.stage_rules import discover_root_package, validate_package_safe


def main():
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check"); check.add_argument("package", type=Path); check.add_argument("--root", type=Path); check.add_argument("--profile", action="append", default=[]); check.add_argument("--output", type=Path)
    args = parser.parse_args(); root = args.root or discover_root_package(args.package)
    result = validate_package_safe(args.package, root, args.profile)
    raw = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        if args.output.exists(): parser.error("Output exists; preserve it and choose a new receipt")
        args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(raw)
    else: print(raw, end="")
    return 0 if result["result"] == "satisfied" else 2


if __name__ == "__main__": raise SystemExit(main())
