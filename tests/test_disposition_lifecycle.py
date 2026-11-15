"""Disposition-to-native-lifecycle planning and readback regressions."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/defensefactory/scripts"
sys.path.insert(0, str(SCRIPTS))
from factorycore.disposition_lifecycle import plan_lifecycle_transition, verify_lifecycle_readback


class DispositionLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.ticket = {"identifier": "SEC-1", "updated_at": "2026-01-01T00:00:00Z",
                       "status": "Backlog", "labels": ["Bug"]}
        self.assessment = {"disposition": "already_fixed",
                           "receipt_reference": "https://tickets.invalid/SEC-1/assessment",
                           "receipt_sha256": "a" * 64}
        self.policy = {"schema_version": 1, "id": "fixture-linear-v1",
                       "statuses": {"complete": "Done", "canceled": "Canceled",
                                    "backlog": "Backlog", "in_progress": "In Progress"},
                       "labels": {"active": "Active", "owner_decision": "Owner decision",
                                  "inconclusive": "Inconclusive", "already_fixed": "Already fixed",
                                  "accepted_risk": "Accepted risk", "false_positive": "False positive",
                                  "invalid_report": "Invalid report"}}
        self.authorization = {"authorized": True, "reference": "https://policy.invalid/lifecycle"}
        self.planned_at = "2026-01-01T00:01:00Z"

    def plan(self, disposition="already_fixed"):
        assessment = {**self.assessment, "disposition": disposition}
        return plan_lifecycle_transition(self.ticket, assessment, self.policy,
                                         self.authorization, self.planned_at)

    def observed(self, status, label):
        return {"identifier": "SEC-1", "updated_at": "2026-01-01T00:02:00Z",
                "status": status, "labels": ["Bug", label], "operation": "retrieval",
                "retrieved_at": "2026-01-01T00:03:00Z"}

    def test_every_disposition_has_explicit_state_label_and_terminal_semantics(self):
        expected = {
            "active": ("In Progress", "Active", False),
            "owner_decision": ("Backlog", "Owner decision", False),
            "inconclusive": ("Backlog", "Inconclusive", False),
            "already_fixed": ("Done", "Already fixed", True),
            "accepted_risk": ("Canceled", "Accepted risk", True),
            "false_positive": ("Canceled", "False positive", True),
            "invalid_report": ("Canceled", "Invalid report", True),
        }
        for disposition, (status, label, terminal) in expected.items():
            with self.subTest(disposition=disposition):
                plan = self.plan(disposition)
                self.assertEqual(plan["desired"], {"status": status, "disposition_label": label})
                self.assertEqual(plan["terminal"], terminal)
                self.assertEqual(plan["result"], "ready")

    def test_common_report_aliases_normalize_without_changing_policy(self):
        self.assertEqual(self.plan("rejected_false_positive")["disposition"], "false_positive")
        self.assertEqual(self.plan("hold_owner_decision")["disposition"], "owner_decision")
        self.assertEqual(self.plan("test_only")["disposition"], "invalid_report")

    def test_missing_authority_produces_pending_nonmutation_plan(self):
        authorization = {"authorized": False, "reference": None}
        plan = plan_lifecycle_transition(self.ticket, self.assessment, self.policy,
                                         authorization, self.planned_at)
        self.assertEqual(plan["result"], "pending")
        self.assertFalse(plan["mutation_permitted"])
        readback = verify_lifecycle_readback(plan, self.observed("Done", "Already fixed"))
        self.assertEqual(readback["result"], "violated")
        self.assertIn("not authorized", " ".join(readback["problems"]))

    def test_exact_fresh_readback_completes_terminal_disposition(self):
        plan = self.plan()
        receipt = verify_lifecycle_readback(plan, self.observed("Done", "Already fixed"))
        self.assertEqual(receipt["result"], "satisfied")
        self.assertTrue(receipt["disposition_visible"])
        self.assertTrue(receipt["terminal"])
        self.assertEqual(receipt["next_action"], "Stop the assessment stage.")

    def test_wrong_state_missing_label_stale_label_and_old_readback_fail_closed(self):
        plan = self.plan()
        wrong = self.observed("Backlog", "Inconclusive")
        wrong["retrieved_at"] = "2025-12-31T23:59:00Z"
        receipt = verify_lifecycle_readback(plan, wrong)
        self.assertEqual(receipt["result"], "violated")
        problems = "\n".join(receipt["problems"])
        self.assertIn("status differs", problems)
        self.assertIn("label is missing", problems)
        self.assertIn("Conflicting disposition labels", problems)
        self.assertIn("predates", problems)
        self.assertFalse(receipt["terminal"])

    def test_existing_exact_state_is_verified_without_a_redundant_mutation(self):
        self.ticket.update(status="Done", labels=["Bug", "Already fixed"])
        plan = self.plan()
        self.assertEqual(plan["operation"], "verify_existing")

    def test_cli_preserves_plan_and_rejects_mismatched_readback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan_input = root / "plan-input.json"
            plan_output = root / "plan.json"
            plan_input.write_text(json.dumps({"ticket": self.ticket, "assessment": self.assessment,
                "policy": self.policy, "authorization": self.authorization, "planned_at": self.planned_at}))
            completed = subprocess.run([sys.executable, str(SCRIPTS / "disposition-lifecycle.py"), "plan",
                                        "--input", str(plan_input), "--output", str(plan_output)],
                                       capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            plan = json.loads(plan_output.read_text())
            verify_input = root / "verify-input.json"
            verify_output = root / "verify.json"
            observed = self.observed("Canceled", "Already fixed")
            verify_input.write_text(json.dumps({"plan": plan, "observed": observed}))
            completed = subprocess.run([sys.executable, str(SCRIPTS / "disposition-lifecycle.py"), "verify",
                                        "--input", str(verify_input), "--output", str(verify_output)],
                                       capture_output=True, text=True)
            self.assertEqual(completed.returncode, 2, completed.stderr)
            self.assertEqual(json.loads(verify_output.read_text())["result"], "violated")


if __name__ == "__main__":
    unittest.main()
