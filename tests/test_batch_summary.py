"""Regression tests for batch-summary arithmetic and partition drift."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/defensefactory/scripts"
sys.path.insert(0, str(SCRIPTS))
from factorycore.batch_summary import reconcile_batch_summary


class BatchSummaryTests(unittest.TestCase):
    def setUp(self):
        self.summary = {
            "schema_version": 1,
            "batch_id": "allsec-fixture",
            "declared_total": 4,
            "selected": ["SEC-1", "SEC-2", "SEC-3", "SEC-4"],
            "groups": {
                "early_disqualified": {"declared_count": 2, "tickets": ["SEC-1", "SEC-2"]},
                "active": {
                    "declared_count": 2,
                    "tickets": ["SEC-3", "SEC-4"],
                    "groups": {
                        "draft_pr": {"declared_count": 1, "tickets": ["SEC-3"]},
                        "hold": {"declared_count": 1, "tickets": ["SEC-4"]},
                    },
                },
            },
        }

    def test_exact_nested_partition_is_satisfied_and_replayable(self):
        receipt = reconcile_batch_summary(self.summary)
        self.assertEqual(receipt["result"], "satisfied")
        self.assertEqual(receipt["validator"], "defensefactory-batch-summary/1")
        self.assertEqual(receipt["observed_total"], 4)
        self.assertEqual(receipt["groups"]["active"]["groups"]["hold"]["observed_count"], 1)
        self.assertEqual(receipt["problems"], [])

    def test_jer81_shape_catches_both_manual_count_errors(self):
        wrong = copy.deepcopy(self.summary)
        wrong["groups"]["early_disqualified"]["declared_count"] = 1
        wrong["groups"]["active"]["declared_count"] = 3
        receipt = reconcile_batch_summary(wrong)
        self.assertEqual(receipt["result"], "violated")
        self.assertTrue(any("early_disqualified declares 1" in item for item in receipt["problems"]))
        self.assertTrue(any("active declares 3" in item for item in receipt["problems"]))

    def test_missing_overlapping_and_unknown_tickets_fail_closed(self):
        wrong = copy.deepcopy(self.summary)
        wrong["groups"]["early_disqualified"]["tickets"] = ["SEC-1", "SEC-X"]
        wrong["groups"]["active"]["tickets"] = ["SEC-1", "SEC-3"]
        receipt = reconcile_batch_summary(wrong)
        self.assertEqual(receipt["result"], "violated")
        joined = "\n".join(receipt["problems"])
        self.assertIn("outside selected", joined)
        self.assertIn("multiple sibling groups", joined)
        self.assertIn("does not classify: SEC-2, SEC-4", joined)

    def test_nested_groups_must_partition_their_parent(self):
        wrong = copy.deepcopy(self.summary)
        wrong["groups"]["active"]["groups"]["hold"]["tickets"] = []
        wrong["groups"]["active"]["groups"]["hold"]["declared_count"] = 0
        receipt = reconcile_batch_summary(wrong)
        self.assertEqual(receipt["result"], "violated")
        self.assertTrue(any("does not classify: SEC-4" in item for item in receipt["problems"]))

    def test_cli_preserves_a_violation_receipt_and_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "summary.json"
            output = root / "receipt.json"
            wrong = copy.deepcopy(self.summary)
            wrong["declared_total"] = 99
            source.write_text(json.dumps(wrong))
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "batch-summary.py"), "--input", str(source), "--output", str(output)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 2, completed.stderr)
            self.assertEqual(json.loads(output.read_text())["result"], "violated")

    def test_cli_accepts_only_a_consistent_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "summary.json"
            output = root / "receipt.json"
            source.write_text(json.dumps(self.summary))
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "batch-summary.py"), "--input", str(source), "--output", str(output)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(output.read_text())["result"], "satisfied")


if __name__ == "__main__":
    unittest.main()
