#!/usr/bin/env python3
"""Plan or verify an assessment disposition's native ticket lifecycle state."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from factorycore.disposition_lifecycle import plan_lifecycle_transition, verify_lifecycle_readback
from factorycore.evidence_records import strict_json, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("plan", "verify"))
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        data = strict_json(args.input.read_bytes())
        if args.operation == "plan":
            result = plan_lifecycle_transition(data["ticket"], data["assessment"], data["policy"],
                                               data["authorization"], data["planned_at"], data.get("routing"))
        else:
            result = verify_lifecycle_readback(data["plan"], data["observed"])
    except (OSError, KeyError, ValueError, TypeError, UnicodeError) as error:
        result = {"record_type": "disposition_lifecycle_" + args.operation, "schema_version": 1,
                  "result": "violated", "problems": [type(error).__name__ + ": " + str(error)]}
    write_json(args.output, result)
    print(json.dumps(result, indent=2))
    return 0 if result["result"] in ("ready", "pending", "satisfied") else 2


if __name__ == "__main__":
    raise SystemExit(main())
