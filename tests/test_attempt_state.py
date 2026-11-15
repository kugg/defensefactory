"""Offline regressions for bounded retries that preserve ticket history."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/defensefactory/scripts"
sys.path.insert(0, str(SCRIPTS))

from factorycore.attempt_state import prepare_active_attempt, validate_scope
from factorycore.trial_controls import scope_prepare


def load_ticket_handoff():
    path = SCRIPTS / "ticket_handoff.py"
    spec = importlib.util.spec_from_file_location("ticket_handoff", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ActiveAttemptTests(unittest.TestCase):
    def setUp(self):
        self.subject = {"repository": "fixture/repository", "revision": "a" * 40}
        self.module = load_ticket_handoff()

    def request(self, checkpoint="bounded-001", previous=None, applicability="satisfied_within_scope"):
        return {
            "case": "FIXTURE-1",
            "checkpoint_id": checkpoint,
            "previous_checkpoint": previous,
            "attempt": "repair-retry-001",
            "stage": "verify",
            "subject": self.subject,
            "reason": "Evaluate only the current verify stage without erasing prior research.",
            "finding_status": "active",
            "inputs": [
                {"id": "assessment", "kind": "assessment", "classification": "reusable",
                 "reference": "linear://assessment", "sha256": "1" * 64,
                 "rationale": "Current-source applicability was checked.",
                 "invalidation_triggers": ["source revision changes"], "subject": self.subject},
                {"id": "owner-decision", "kind": "authorization", "classification": "reusable",
                 "reference": "linear://decision", "native_id": "comment-owner-1",
                 "rationale": "The bounded scope remains authorized.",
                 "invalidation_triggers": ["owner revokes scope"]},
                {"id": "old-pr", "kind": "repair", "classification": "historical",
                 "reference": "github://pull/99", "native_id": "pull-99",
                 "rationale": "Prior candidate is chronology, not a current input."},
                {"id": "old-index", "kind": "codeintel", "classification": "stale",
                 "reference": "linear://attachment/index", "sha256": "2" * 64,
                 "rationale": "The semantic result names an earlier candidate."},
            ],
            "minimal_dependency_ids": ["assessment", "owner-decision"],
            "required_input_kinds": ["assessment", "authorization"],
            "applicability": {"result": applicability, "reference": "linear://applicability",
                              "sha256": "3" * 64, "limitations": ["source scope only"]},
            "authorization_reference": "linear://authorization",
            "boundaries": "Verify the exact subject; do not merge, deploy or rewrite history.",
            "next_action": "Open the verify stage if the connector readback matches.",
            "owner": "fixture-owner",
        }

    @staticmethod
    def apply_patch(description, patch):
        if patch["op"] == "prepend":
            return patch["text"] + description
        if patch["op"] == "replace":
            if description.count(patch["old_string"]) != 1:
                raise ValueError("exact anchor no longer present")
            return description.replace(patch["old_string"], patch["new_string"], 1)
        raise AssertionError("unknown patch")

    def test_checkpoint_keeps_minimal_closure_and_holds_unknown_applicability(self):
        checkpoint = prepare_active_attempt(self.request())
        self.assertTrue(checkpoint["execution_permitted"])
        self.assertEqual(checkpoint["minimal_dependency_ids"], ["assessment", "owner-decision"])
        self.assertTrue(checkpoint["historical_evidence_preserved"])

        held = prepare_active_attempt(self.request(applicability="unknown"))
        self.assertEqual(held["result"], "hold")
        self.assertFalse(held["execution_permitted"])
        self.assertIn("Current-source applicability is unknown", held["blockers"])

        invalid = self.request()
        invalid["minimal_dependency_ids"].append("old-pr")
        with self.assertRaisesRegex(ValueError, "exactly the reusable inputs"):
            prepare_active_attempt(invalid)

    def test_exact_anchor_replaces_only_current_pointer_and_preserves_history(self):
        original = "## Reported finding\n\nAssessment comment and prior receipt references remain here.\n"
        issue = {"id": "FIXTURE-1", "updatedAt": "2026-01-01T00:00:00Z", "description": original}
        first = self.module.prepare_attempt(issue, self.request())
        published = self.apply_patch(original, first["linear_request"]["patch"][0])
        readback = {**issue, "updatedAt": "2026-01-01T00:01:00Z", "description": published}
        ack = self.module.acknowledge_attempt(readback, first)
        self.assertEqual(ack["publication"], "observed_in_connector_readback")
        self.assertIn(original, published)

        second_request = self.request("bounded-002", previous="bounded-001")
        second_request["attempt"] = "repair-retry-002"
        second = self.module.prepare_attempt(readback, second_request)
        replaced = self.apply_patch(published, second["linear_request"]["patch"][0])
        self.assertIn(original, replaced)
        self.assertNotIn("Checkpoint: `bounded-001`", replaced)
        self.assertIn("Checkpoint: `bounded-002`", replaced)
        self.assertEqual(replaced.count(self.module.ATTEMPT_START), 1)

        stale = self.request("bounded-003", previous="wrong-predecessor")
        with self.assertRaisesRegex(ValueError, "Stale active attempt"):
            self.module.prepare_attempt(readback, stale)

    def test_bounded_scope_requires_published_readback_and_exact_subject(self):
        issue = {"id": "FIXTURE-1", "updatedAt": "2026-01-01T00:00:00Z", "description": "History.\n"}
        prepared = self.module.prepare_attempt(issue, self.request())
        description = self.apply_patch(issue["description"], prepared["linear_request"]["patch"][0])
        readback = self.module.acknowledge_attempt({**issue, "description": description}, prepared)
        checkpoint = prepared["checkpoint"]
        base = {"case": "FIXTURE-1", "attempt": "repair-retry-001", "stage": "verify",
                "subject": self.subject, "performed_by": "fixture-worker",
                "package": str(ROOT / "skills/defensefactory-verify"),
                "authorization_reference": "linear://authorization",
                "boundaries": "offline bounded retry"}
        with self.assertRaisesRegex(ValueError, "current active-attempt"):
            scope_prepare({**base, "attempt_mode": "bounded_retry"})

        admitted = scope_prepare({**base, "attempt_mode": "bounded_retry",
                                  "attempt_checkpoint": checkpoint, "attempt_readback": readback})
        self.assertEqual(admitted["scope"]["attempt_binding"]["result"], "satisfied_within_scope")
        self.assertEqual(admitted["scope"]["attempt_binding"]["minimal_dependency_ids"],
                         ["assessment", "owner-decision"])

        wrong_scope = {"case": "FIXTURE-1", "attempt": "repair-retry-001", "stage": "verify",
                       "subject": {**self.subject, "revision": "b" * 40}}
        with self.assertRaisesRegex(ValueError, "subject"):
            validate_scope(checkpoint, readback, wrong_scope)

    def test_public_helpers_emit_receipts_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            request_file = directory / "attempt.json"
            checkpoint_file = directory / "checkpoint.json"
            request_file.write_text(json.dumps(self.request()))
            command = [sys.executable, str(SCRIPTS / "stage.py"), "active-attempt-prepare",
                       "--input", str(request_file), "--output", str(checkpoint_file)]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(json.loads(checkpoint_file.read_text())["result"], "ready")
            second = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(second.returncode, 0)
            self.assertIn("do not overwrite a receipt", second.stderr)

            issue_file = directory / "issue.json"
            publication_file = directory / "publication.json"
            issue_file.write_text(json.dumps({"id": "FIXTURE-1", "updatedAt": "fixture",
                                              "description": "Preserved history.\n"}))
            publish = subprocess.run(
                [sys.executable, str(SCRIPTS / "ticket_handoff.py"), "attempt-prepare",
                 "--issue", str(issue_file), "--state", str(request_file),
                 "--output", str(publication_file)], capture_output=True, text=True)
            self.assertEqual(publish.returncode, 0, publish.stderr)
            self.assertEqual(json.loads(publication_file.read_text())["checkpoint_id"], "bounded-001")
            repeated = subprocess.run(
                [sys.executable, str(SCRIPTS / "ticket_handoff.py"), "attempt-prepare",
                 "--issue", str(issue_file), "--state", str(request_file),
                 "--output", str(publication_file)], capture_output=True, text=True)
            self.assertNotEqual(repeated.returncode, 0)
            self.assertIn("do not overwrite a handoff receipt", repeated.stderr)


if __name__ == "__main__":
    unittest.main()
