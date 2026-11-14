"""Offline alpha release-harness tests; no model, connector, or product calls."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest

from release.alpha import source_service, stage_worker
from release.alpha.ledger_service import LedgerStore, handler_for
from release.alpha.protocol import (STAGES, TICKET_SCHEMA, ProtocolError, canonical,
                                    read_json, sha256, validate_profiles)


ROOT = Path(__file__).resolve().parents[1]
ALPHA = ROOT / "release/alpha"
PROFILES = ALPHA / "capability-profiles.json"


class SilentSource(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass


class AlphaReleaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.ledger_store = LedgerStore(self.root / "ledger")
        self.ledger_server = ThreadingHTTPServer(("127.0.0.1", 0),
                                                 handler_for(self.ledger_store))
        self.ledger_thread = threading.Thread(target=self.ledger_server.serve_forever,
                                              daemon=True)
        self.ledger_thread.start()
        self.addCleanup(self.ledger_server.server_close)
        self.addCleanup(self.ledger_server.shutdown)
        source_root = self.root / "source"
        source_service.prepare(ALPHA / "fixtures/source", source_root,
                               "http://placeholder.invalid")
        handler = partial(SilentSource, directory=str(source_root / "www"))
        self.source_server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.source_thread = threading.Thread(target=self.source_server.serve_forever,
                                              daemon=True)
        self.source_thread.start()
        self.addCleanup(self.source_server.server_close)
        self.addCleanup(self.source_server.shutdown)
        self.ledger = "http://127.0.0.1:%d" % self.ledger_server.server_address[1]
        self.repository = "http://127.0.0.1:%d/fixture.git" % self.source_server.server_address[1]
        self.revision = json.loads((source_root / "www/metadata.json").read_text())["revision"]
        self.image_digest = "sha256:" + "b" * 64

    def ticket(self, run_id="alpha-fixture", stages=STAGES, scenario="local_lifecycle"):
        return {
            "schema": TICKET_SCHEMA,
            "case": "ALPHA-FIXTURE",
            "attempt": run_id,
            "subject": {"repository": self.repository, "revision": self.revision},
            "release": {"git_commit": "a" * 40, "image_digest": self.image_digest,
                        "capability_profiles_sha256": sha256(PROFILES.read_bytes())},
            "scenario": scenario,
            "authorized_stages": list(stages),
            "authorized_stop": stages[-1],
            "qualification": "Synthetic test only",
        }

    def test_profiles_cover_exact_pipeline_and_release_files_exist(self):
        profiles = validate_profiles(read_json(PROFILES))
        self.assertEqual(list(profiles["stages"]), list(STAGES))
        for name in ("Dockerfile", "compose.yaml", "otel-collector.yaml", "README.md"):
            self.assertTrue((ALPHA / name).is_file(), name)
        dockerfile = (ALPHA / "Dockerfile").read_text()
        self.assertRegex(dockerfile, r"(?m)^FROM [^\s]+@sha256:[0-9a-f]{64}$")
        compose = (ALPHA / "compose.yaml").read_text()
        self.assertIn("read_only: true", compose)
        self.assertIn("internal: true", compose)
        self.assertNotIn("docker.sock", compose)

    def test_all_stages_reconstruct_from_ledger_and_exact_source(self):
        run_id = "full-handoff"
        self.ledger_store.create_run(run_id, self.ticket(run_id))
        receipts = []
        for stage in STAGES:
            receipts.append(stage_worker.run(stage, self.ledger, run_id, PROFILES,
                                             self.image_digest))
        summary = self.ledger_store.summary(run_id)
        self.assertTrue(summary["complete"])
        self.assertEqual([item["stage"] for item in receipts], list(STAGES))
        self.assertEqual(receipts[-1]["result"], "satisfied_within_scope")
        for receipt in receipts:
            self.assertNotIn("file://", json.dumps(receipt))
            evidence = json.loads(self.ledger_store.attachment(
                run_id, receipt["output_attachment"]["sha256"]))
            self.assertTrue(evidence["reproduction"])
            self.assertEqual(evidence["subject"]["revision"], self.revision)

    def test_early_disposition_ends_before_repair(self):
        run_id = "early-stop"
        stages = STAGES[:2]
        self.ledger_store.create_run(run_id, self.ticket(run_id, stages, "early_disposition"))
        for stage in stages:
            stage_worker.run(stage, self.ledger, run_id, PROFILES, self.image_digest)
        summary = self.ledger_store.summary(run_id)
        self.assertTrue(summary["complete"])
        self.assertEqual(summary["receipts"][-1]["result"], "premise_disputed")
        with self.assertRaisesRegex(ProtocolError, "outside the ticket-authorized"):
            # Direct ledger assertion: no later receipt can enter this run.
            self.ledger_store.put_receipt(run_id, "repair", {})

    def test_tampered_prior_attachment_blocks_next_stage(self):
        run_id = "tamper"
        self.ledger_store.create_run(run_id, self.ticket(run_id, STAGES[:2], "active"))
        intake = stage_worker.run("intake", self.ledger, run_id, PROFILES, self.image_digest)
        path = self.ledger_store.run_root(run_id) / "attachments" / intake["output_attachment"]["sha256"]
        path.write_bytes(b"changed after publication")
        with self.assertRaisesRegex(ProtocolError, "Stored attachment bytes changed"):
            stage_worker.run("assess", self.ledger, run_id, PROFILES, self.image_digest)
        self.assertEqual(self.ledger_store.receipt_names(run_id), ["intake"])

    def test_wrong_frozen_image_and_profiles_fail_before_publication(self):
        run_id = "wrong-release"
        self.ledger_store.create_run(run_id, self.ticket(run_id, STAGES[:1], "active"))
        with self.assertRaisesRegex(ProtocolError, "Running image differs"):
            stage_worker.run("intake", self.ledger, run_id, PROFILES, "sha256:" + "c" * 64)
        changed = self.root / "profiles.json"
        value = read_json(PROFILES)
        value["qualification"] = "changed"
        changed.write_bytes(canonical(value))
        with self.assertRaisesRegex(ProtocolError, "Capability profiles differ"):
            stage_worker.run("intake", self.ledger, run_id, changed, self.image_digest)
        self.assertEqual(self.ledger_store.receipt_names(run_id), [])


if __name__ == "__main__":
    unittest.main()
