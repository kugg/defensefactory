"""Project-agnostic bug-class receipts and class-wide proof tests."""
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
from factorycore.bugclasses import (define_class, discover, evaluate_membership, linkage_plan, linkage_readback,
    pr_section, repair_contract, variant_matrix, verify_class)
from factorycore.core import GateError


class BugClassTests(unittest.TestCase):
    def setUp(self):
        evidence = lambda name: [{"kind": "ticket_attachment", "reference": "https://evidence.invalid/" + name}]
        def ticket(identifier, lifecycle, invariant, boundary="credential boundary", source="current", title="Credential reaches peer", behavior="credential sent to peer", taxonomy=None, relations=None):
            return {"ticket": identifier, "url": "https://tickets.invalid/" + identifier, "lifecycle": lifecycle, "title": title, "component": "gateway", "boundary": boundary,
                    "claim_id": "PEER-AUTH", "invariant_id": invariant, "behavior": behavior, "evidence_references": evidence(identifier),
                    "source_state": source, "taxonomy": taxonomy or ["CWE-200"], "relations": relations or []}
        self.trigger = ticket("FIX-1", "active", "CREDENTIAL-TO-UNVERIFIED-PEER")
        self.history = ticket("FIX-2", "completed", "CREDENTIAL-TO-UNVERIFIED-PEER", title="Fallback leaks credential", behavior="fallback sends credential")
        self.different = ticket("FIX-3", "active", "LOG-REDACTION", title="Credential appears in log")
        self.boundary = ticket("FIX-4", "completed", "CREDENTIAL-TO-UNVERIFIED-PEER", boundary="operator export boundary", title="Credential export")
        self.missing = ticket("FIX-5", "active", "", source="unknown", title="Possible credential behavior")
        self.duplicate = ticket("FIX-6", "duplicate", "CREDENTIAL-TO-UNVERIFIED-PEER", relations=["duplicate-of:FIX-2"])
        self.subject = {"repository": "fixture/repository", "revision": "a" * 40}
        self.queries = [{"id": "tickets", "source": "ticket", "query": "claim/invariant plus active and historical", "scope": "fixture project all lifecycle states", "result_reference": "https://evidence.invalid/query",
                         "coverage_limitations": ["synthetic corpus"]}]
        self.coverage = {"ticket_states": ["active", "completed", "duplicate"], "repositories": ["fixture/repository"],
                         "history_sources": ["ticket"], "codeintel": {"disposition": "not_needed", "reason": "synthetic metadata corpus"},
                         "limitations": ["offline fixture"]}
        self.discovery = discover(self.trigger, self.subject, self.queries, [self.history, self.different, self.boundary, self.missing, self.duplicate], self.coverage)
        def decision(identifier, disposition, invariant, boundary="compatible", fence="yes", evidence_rows=None, limitations=None, duplicate_of=None, proposals=None):
            return {"ticket": identifier, "disposition": disposition, "shared_or_differing_invariant": invariant,
                    "boundary_compatibility": boundary, "component_relationship": "same portable component type",
                    "triggering_behavior": "synthetic behavior comparison", "fence_coverability": fence,
                    "evidence": evidence(identifier) if evidence_rows is None else evidence_rows,
                    "limitations": limitations or [], "duplicate_of": duplicate_of, "external_proposals": proposals or []}
        decisions = [
            decision("FIX-1", "included_current", "shared invariant"),
            decision("FIX-2", "included_historical", "shared invariant"),
            decision("FIX-3", "excluded_different_invariant", "different invariant", fence="no", proposals=[{
                "source": "fixture-model", "version": "1", "proposed_disposition": "included_current",
                "evidence_reference": "https://evidence.invalid/model-FIX-3"}]),
            decision("FIX-4", "excluded_incompatible_boundary", "same invariant but different boundary", boundary="incompatible", fence="no"),
            decision("FIX-5", "inconclusive_missing_evidence", "invariant unknown", boundary="unknown", fence="unknown", evidence_rows=[], limitations=["missing ticket evidence"]),
            decision("FIX-6", "duplicate_member", "shared invariant", duplicate_of="FIX-2"),
        ]
        evaluator = {"identity": "fixture-reviewer", "version": "1", "method": "bounded evidence comparison", "scope_reference": "fixture policy"}
        self.decisions = decisions; self.evaluator = evaluator
        self.membership = evaluate_membership(self.discovery, decisions, evaluator)
        definition = {"id": "UNVERIFIED-PEER-CREDENTIAL", "statement": "Credentials must not cross to an unverified peer.",
                      "claim_id": "PEER-AUTH", "invariant_id": "CREDENTIAL-TO-UNVERIFIED-PEER", "applicable_component_types": ["gateway"],
                      "boundary": "credential boundary", "mandatory_contracts": ["PEER-REGRESSION"], "required_hard_fence": "PEER-IDENTITY-FENCE",
                      "coverage_expectations": "primary, fallback, retry, alternate constructor and configuration paths plus preserved legitimate peer",
                      "owner": "@fixture-owner", "reviewers": ["@fixture-reviewer"], "lineage": []}
        self.definition = definition; self.bug_class = define_class(self.membership, definition)
        path_analysis = [{"kind": kind, "disposition": "covered", "rationale": "fixture contract covers " + kind} for kind in ("primary", "retry", "fallback", "alternate_constructor", "configuration")]
        design = {"restores_claim": "PEER-AUTH", "closes_invariant": "CREDENTIAL-TO-UNVERIFIED-PEER", "path_analysis": path_analysis,
                  "preserves": [{"id": "VERIFIED-PEER-USABLE", "behavior": "verified peer remains usable", "contract": "PEER-POSITIVE"}],
                  "hard_fence": {"id": "PEER-IDENTITY-FENCE", "mechanism": "test", "contract": "PEER-REGRESSION", "coverage": "named negative and positive paths", "introduction_ref_status": "candidate"},
                  "historical_variants": [{"ticket": "FIX-2", "contract": "PEER-REGRESSION", "disposition": "encoded"}],
                  "other_claims": [{"id": "LEGITIMATE-PEER", "protection_contract": "PEER-POSITIVE"}],
                  "limitations": [], "boundary_change": "unchanged", "boundary_review_reference": ""}
        self.design = design; self.repair = repair_contract(self.bug_class, design)

    def rows(self, history_result="covered_satisfied", history_fence="yes"):
        def row(ticket, lifecycle, membership, result, fence):
            return {"ticket": ticket, "lifecycle": lifecycle, "membership": membership, "variant_contract": "PEER-REGRESSION",
                    "candidate": {"result": result, "raw_reference": "https://evidence.invalid/raw-" + ticket},
                    "evaluation": {"disposition": result, "evidence": ["https://evidence.invalid/eval-" + ticket]},
                    "covered_by_fence": fence, "evidence_references": [{"kind": "execution", "reference": "https://evidence.invalid/run-" + ticket}], "coverage_limitations": []}
        return [row("FIX-1", "active", "included_current", "covered_satisfied", "yes"),
                row("FIX-2", "completed", "included_historical", history_result, history_fence)]

    def matrix(self, rows=None, bug_class=None, repair=None):
        bug_class = bug_class or self.bug_class; repair = repair or self.repair
        return variant_matrix(bug_class, repair, {"repository": "fixture/repository", "revision": "b" * 40},
                              {"repository": "fixture/repository", "revision": "c" * 40}, rows or self.rows(),
                              {"identity": "fixture-evaluator", "version": "1", "policy_reference": "fixture policy"})

    def resolved(self):
        decisions = copy.deepcopy(self.decisions)
        row = next(item for item in decisions if item["ticket"] == "FIX-5")
        row.update(disposition="excluded_different_invariant", shared_or_differing_invariant="different invariant established by reviewed fixture",
                   boundary_compatibility="compatible", fence_coverability="no",
                   evidence=[{"kind": "review", "reference": "https://evidence.invalid/FIX-5-resolution"}], limitations=[])
        bug_class = define_class(evaluate_membership(self.discovery, decisions, self.evaluator), self.definition)
        return bug_class, repair_contract(bug_class, self.design)

    def support(self, result="satisfied"):
        return ([{"id": "VERIFIED-PEER-USABLE", "result": result, "evidence_reference": "https://evidence.invalid/preservation"}],
                [{"id": "LEGITIMATE-PEER", "result": result, "evidence_reference": "https://evidence.invalid/other-claim"}])

    def test_discovery_hints_are_candidates_not_membership(self):
        candidates = {row["ticket"]["ticket"]: row for row in self.discovery["candidates"]}
        self.assertEqual(candidates["FIX-3"]["membership"], "candidate_only")
        self.assertIn("taxonomy_hint", candidates["FIX-3"]["discovery_basis"])
        self.assertFalse(self.discovery.get("closure_permitted", False))
        no_matches = discover(self.trigger, self.subject, self.queries, [], self.coverage)
        self.assertEqual(no_matches["candidate_count"], 1)

    def test_membership_corpus_preserves_lifecycle_and_all_dispositions(self):
        decisions = {row["candidate"]["ticket"]: row["decision"]["disposition"] for row in self.membership["evaluations"]}
        self.assertEqual(decisions["FIX-1"], "included_current")
        self.assertEqual(decisions["FIX-2"], "included_historical")
        self.assertEqual(decisions["FIX-3"], "excluded_different_invariant")
        self.assertEqual(decisions["FIX-4"], "excluded_incompatible_boundary")
        self.assertEqual(decisions["FIX-5"], "inconclusive_missing_evidence")
        self.assertEqual(decisions["FIX-6"], "duplicate_member")
        self.assertTrue(self.membership["lifecycle_preserved"])
        self.assertEqual(self.bug_class["member_lifecycles"], {"FIX-1": "active", "FIX-2": "completed"})
        self.assertEqual(self.membership["external_proposal_disagreements"], ["FIX-3"])

    def test_membership_cannot_be_included_without_compatible_evidence(self):
        bad = copy.deepcopy(self.membership["evaluations"][0]["decision"]); bad["evidence"] = []
        decisions = [copy.deepcopy(row["decision"]) for row in self.membership["evaluations"]]
        decisions = [bad if row["ticket"] == bad["ticket"] else row for row in decisions]
        with self.assertRaisesRegex(GateError, "Evidence references"):
            evaluate_membership(self.discovery, decisions, {"identity": "x", "version": "1", "method": "x", "scope_reference": "x"})
        bad = copy.deepcopy(self.membership["evaluations"][0]["decision"]); bad["evidence"] = [{"kind": "local", "reference": "file:///tmp/evidence.json"}]
        decisions = [copy.deepcopy(row["decision"]) for row in self.membership["evaluations"]]
        decisions = [bad if row["ticket"] == bad["ticket"] else row for row in decisions]
        with self.assertRaisesRegex(GateError, "shareable"):
            evaluate_membership(self.discovery, decisions, self.evaluator)

    def test_repair_contract_requires_all_paths_hard_fence_and_historical_variant(self):
        self.assertTrue(self.repair["required_before_product_edit"])
        self.assertFalse(self.repair["class_wide_claim_permitted"])
        bad = copy.deepcopy(self.repair["design"]); bad["path_analysis"] = bad["path_analysis"][:-1]
        with self.assertRaisesRegex(GateError, "Analyze primary"):
            repair_contract(self.bug_class, bad)
        bad = copy.deepcopy(self.repair["design"]); bad["hard_fence"]["mechanism"] = "markdown"
        with self.assertRaisesRegex(GateError, "hard fence"):
            repair_contract(self.bug_class, bad)

    def test_exact_merge_subject_and_separate_evaluation_are_required(self):
        with self.assertRaisesRegex(GateError, "Exact merge subject"):
            variant_matrix(self.bug_class, self.repair, {"repository": "fixture/repository", "revision": "b" * 40},
                           {"repository": "fixture/repository", "revision": "short"}, self.rows(),
                           {"identity": "x", "version": "1", "policy_reference": "x"})
        rows = self.rows(); rows[0]["evaluation"]["disposition"] = "covered_violation"
        with self.assertRaisesRegex(GateError, "disagree"):
            self.matrix(rows)

    def test_class_outcomes_do_not_overstate_partial_or_failed_coverage(self):
        bug_class, repair = self.resolved(); full = self.matrix(bug_class=bug_class, repair=repair)
        fence = {"id": "PEER-IDENTITY-FENCE", "result": "satisfied", "evidence_reference": "https://evidence.invalid/fence"}
        claim = {"id": "PEER-AUTH", "result": "satisfied", "evidence_reference": "https://evidence.invalid/claim"}
        preservation, other_claims = self.support()
        accepted = verify_class(bug_class, full, fence, claim, preservation, other_claims)
        self.assertEqual(accepted["outcome"], "class_remediated_within_scope")
        self.assertTrue(accepted["class_wide_remediation_claim_permitted"])
        partial = verify_class(bug_class, self.matrix(self.rows(history_fence="no"), bug_class, repair), fence, claim, preservation, other_claims)
        self.assertEqual(partial["outcome"], "member_fix_only")
        inconclusive = verify_class(bug_class, self.matrix(self.rows("inconclusive_insufficient_history", "unknown"), bug_class, repair), fence, claim, preservation, other_claims)
        self.assertEqual(inconclusive["outcome"], "class_inconclusive")
        limited_rows = self.rows(); limited_rows[1]["coverage_limitations"] = ["historical branch unavailable"]
        limited = verify_class(bug_class, self.matrix(limited_rows, bug_class, repair), fence, claim, preservation, other_claims)
        self.assertEqual(limited["outcome"], "class_inconclusive")
        violated_fence = verify_class(bug_class, full, {**fence, "result": "violated"}, claim, preservation, other_claims)
        self.assertEqual(violated_fence["outcome"], "class_violated")
        violated_behavior, _ = self.support("violated")
        self.assertEqual(verify_class(bug_class, full, fence, claim, violated_behavior, other_claims)["outcome"], "class_violated")
        rejected = verify_class(bug_class, full, fence, claim, preservation, other_claims, {"result": "rejected", "reference": "fixture review"})
        self.assertEqual(rejected["outcome"], "class_definition_rejected")

    def test_pr_section_and_linkage_readback_preserve_historical_state_and_resume(self):
        preservation, other_claims = self.support()
        matrix = self.matrix(); verification = verify_class(self.bug_class, matrix,
            {"id": "PEER-IDENTITY-FENCE", "result": "satisfied", "evidence_reference": "https://evidence.invalid/fence"},
            {"id": "PEER-AUTH", "result": "satisfied", "evidence_reference": "https://evidence.invalid/claim"}, preservation, other_claims)
        section = pr_section(self.bug_class, matrix, verification, "https://github.com/fixture/repository/pull/1")
        self.assertIn("FIX-2", section["markdown"]); self.assertIn("Historical members", section["markdown"])
        self.assertIn("https://tickets.invalid/FIX-2", section["markdown"])
        self.assertIn("Architectural repair", section["markdown"])
        plan = linkage_plan(self.bug_class, section, {"FIX-1": "active", "FIX-2": "completed"})
        observation = {"pr": {"url": section["pr_url"], "content_sha256": plan["operations"][0]["content_sha256"]},
                       "tickets": [{"ticket": "FIX-1", "lifecycle": "active", "pr_urls": [section["pr_url"]]},
                                   {"ticket": "FIX-2", "lifecycle": "completed", "pr_urls": []}],
                       "completed_effect_keys": [row["effect_key"] for row in plan["operations"][:-1]], "retrieved_at": "2026-01-01T00:00:00Z"}
        partial = linkage_readback(plan, observation)
        self.assertEqual(partial["result"], "inconclusive")
        self.assertEqual(partial["resume_without_duplicates"], [plan["operations"][-1]["effect_key"]])
        observation["tickets"][1]["pr_urls"] = [section["pr_url"]]; observation["completed_effect_keys"] = [row["effect_key"] for row in plan["operations"]]
        self.assertEqual(linkage_readback(plan, observation)["result"], "satisfied")
        changed = copy.deepcopy(observation); changed["tickets"][1]["lifecycle"] = "reopened"
        self.assertEqual(linkage_readback(plan, changed)["result"], "inconclusive")

    def test_bugclass_cli_refuses_receipt_overwrite(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup); root = Path(temporary.name)
        source = root / "input.json"; output = root / "receipt.json"
        source.write_text(json.dumps({"trigger": self.trigger, "subject": self.subject, "queries": self.queries,
                                      "tickets": [self.history], "coverage": self.coverage}))
        command = [sys.executable, str(SCRIPTS / "bugclass.py"), "discover", "--input", str(source), "--output", str(output)]
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
        self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)

    def test_bugclass_identity_is_portable_across_repository_moves(self):
        moved_trigger = copy.deepcopy(self.trigger)
        moved_trigger["url"] = "https://tickets.invalid/FIX-MOVED"
        moved_trigger["ticket"] = "FIX-MOVED"
        moved_subject = {"repository": "fixture/moved-repository", "revision": "d" * 40}
        discovery = discover(moved_trigger, moved_subject, self.queries, [], {**self.coverage, "repositories": ["fixture/moved-repository"]})
        decision = copy.deepcopy(self.decisions[0]); decision["ticket"] = "FIX-MOVED"
        membership = evaluate_membership(discovery, [decision], self.evaluator)
        moved_class = define_class(membership, {**self.definition, "lineage": [{"repository": "fixture/repository", "component": "gateway"}]})
        self.assertEqual(moved_class["portable_identity"], self.bug_class["portable_identity"])
        self.assertNotEqual(moved_class["subject"]["repository"], self.bug_class["subject"]["repository"])


if __name__ == "__main__": unittest.main()
