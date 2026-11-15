#!/usr/bin/env python3
"""Reconcile declared batch counts against enumerated ticket outcomes."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from factorycore.batch_summary import VALIDATOR, reconcile_batch_summary
from factorycore.core import sha
from factorycore.evidence_records import strict_json, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        raw = args.input.read_bytes()
        summary = strict_json(raw)
        receipt = reconcile_batch_summary(summary)
    except (OSError, ValueError, TypeError, UnicodeError) as error:
        raw = locals().get("raw", b"")
        receipt = {
            "record_type": "batch_summary_reconciliation",
            "schema_version": 1,
            "validator": VALIDATOR,
            "batch_id": None,
            "input_sha256": sha(raw),
            "problems": [type(error).__name__ + ": " + str(error)],
            "result": "violated",
            "scope": "Input could not be reconciled; publication remains blocked.",
            "replay": "batch-summary.py --input SUMMARY.json --output RECEIPT.json",
        }
    write_json(args.output, receipt)
    print(json.dumps(receipt, indent=2))
    raise SystemExit(0 if receipt["result"] == "satisfied" else 2)


if __name__ == "__main__":
    main()
