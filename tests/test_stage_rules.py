"""Bounded stage-rule satisfiability and skill-conformance checks."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "skills/defensefactory/scripts"))
from factorycore.stage_rules import (MAP_END, MAP_START, RULES_END, RULES_START, UnsupportedSemantics,
    parse_rule_file, validate_effective, validate_package_safe)
from factorycore.trial_controls import scope_prepare, stage_start


class StageRuleTests(unittest.TestCase):
    def setUp(self):
        self.root_doc = parse_rule_file((ROOT / "skills/defensefactory/RULES.md").read_bytes(), "defensefactory/RULES.md")
        self.root_doc["rules"] = []
        self.stage_doc = {"schema_version": 1, "stage": "fixture", "inherits": ["defensefactory/RULES.md"],
                          "rules": [], "source": "fixture/RULES.md", "source_sha256": "a" * 64, "prose": "Fixture"}

    def rule(self, rule_id, *, when=None, requires=None, forbids=None, allows=None, terminal="either", mutation="none",
             overrides=None, precedence=20, safety=False, strength="must", fulfillment="operator_only", scope="fixture"):
        return {"id": rule_id, "scope": scope, "strength": strength, "when": when or {},
                "requires": requires or {}, "forbids": forbids or {}, "allows": allows or {},
                "terminal": terminal, "mutation": mutation, "overrides": overrides or [],
                "precedence": precedence, "safety": safety, "fulfillment": fulfillment}

    def validate(self, *rules, procedure=None):
        doc = copy.deepcopy(self.stage_doc); doc["rules"] = list(rules)
        return validate_effective("fixture", [self.root_doc, doc], procedure)

    def kinds(self, result): return {row["kind"] for row in result["findings"]}

    def test_satisfiable_and_mutually_exclusive_conditions_do_not_conflict(self):
        left = self.rule("FIXTURE-WRITE", when={"authorization": "present"}, requires={"actions": ["edit_candidate"]})
        right = self.rule("FIXTURE-NO-WRITE", when={"authorization": "absent"}, forbids={"actions": ["edit_candidate"]})
        self.assertEqual(self.validate(left, right)["result"], "satisfied")

    def test_direct_and_overlapping_require_forbid_conflicts_include_counterexample(self):
        left = self.rule("FIXTURE-REQUIRE", when={"stage_state": "active"}, requires={"actions": ["edit_candidate"]})
        right = self.rule("FIXTURE-FORBID", when={"applicability": "active"}, forbids={"actions": ["edit_candidate"]})
        result = self.validate(left, right)
        conflict = next(row for row in result["findings"] if row["kind"] == "required_forbidden_conflict")
        self.assertEqual(conflict["rule_ids"], ["FIXTURE-FORBID", "FIXTURE-REQUIRE"])
        self.assertEqual(conflict["counterexample"]["stage_state"], "active")
        self.assertEqual(conflict["counterexample"]["applicability"], "active")

    def test_terminal_continue_and_mutation_readonly_conflicts(self):
        terminal = self.rule("FIXTURE-TERMINAL", requires={"outcomes": ["stopped"], "transitions": ["continue"]}, terminal="terminal")
        read = self.rule("FIXTURE-READ", mutation="read_only")
        write = self.rule("FIXTURE-WRITE", mutation="write_required")
        kinds = self.kinds(self.validate(terminal, read, write))
        self.assertIn("continue_terminal_conflict", kinds); self.assertIn("mutation_readonly_conflict", kinds)

    def test_unreachable_mandatory_postcondition_is_detected(self):
        rule = self.rule("FIXTURE-UNREACHABLE", requires={"postconditions": ["candidate_bounded"]}, forbids={"actions": ["edit_candidate"]})
        self.assertIn("unreachable_postcondition", self.kinds(self.validate(rule)))

    def test_narrow_higher_precedence_override_resolves_conflict(self):
        parent = self.rule("FIXTURE-PARENT", when={"stage_state": "active"}, requires={"actions": ["edit_candidate"]}, precedence=20)
        exception = self.rule("FIXTURE-EXCEPTION", when={"stage_state": "active", "authorization": "absent"}, forbids={"actions": ["edit_candidate"]}, overrides=["FIXTURE-PARENT"], precedence=30)
        self.assertEqual(self.validate(parent, exception)["result"], "satisfied")

    def test_broad_or_equal_precedence_overrides_and_cycles_fail(self):
        parent = self.rule("FIXTURE-PARENT", when={"authorization": "present"}, requires={"actions": ["edit_candidate"]}, precedence=20)
        broad = self.rule("FIXTURE-BROAD", forbids={"actions": ["edit_candidate"]}, overrides=["FIXTURE-PARENT"], precedence=30)
        equal = self.rule("FIXTURE-EQUAL", when={"authorization": "present"}, forbids={"actions": ["edit_candidate"]}, overrides=["FIXTURE-PARENT"], precedence=20)
        kinds = self.kinds(self.validate(parent, broad, equal))
        self.assertIn("exception_not_narrower", kinds); self.assertIn("invalid_override_precedence", kinds)
        a = self.rule("FIXTURE-A", overrides=["FIXTURE-B"], precedence=30)
        b = self.rule("FIXTURE-B", overrides=["FIXTURE-A"], precedence=20)
        self.assertIn("override_cycle", self.kinds(self.validate(a, b)))

    def test_equal_precedence_incompatible_overrides_fail(self):
        parent = self.rule("FIXTURE-PARENT", requires={"facts": ["scope_bound"]}, precedence=10)
        one = self.rule("FIXTURE-ONE", when={"authorization": "present"}, requires={"actions": ["edit_candidate"]}, overrides=["FIXTURE-PARENT"], precedence=20)
        two = self.rule("FIXTURE-TWO", when={"authorization": "present"}, forbids={"actions": ["edit_candidate"]}, overrides=["FIXTURE-PARENT"], precedence=20)
        self.assertIn("equal_precedence_override_conflict", self.kinds(self.validate(parent, one, two)))

    def test_stage_cannot_override_universal_safety_rule(self):
        universal = self.rule("DF-SAFETY", scope="*", safety=True, precedence=50)
        universal["source"] = "defensefactory/RULES.md"; universal["source_stage"] = "universal"
        self.root_doc["rules"] = [{key: value for key, value in universal.items() if key not in ("source", "source_stage")}]
        local = self.rule("FIXTURE-WEAKEN", when={"authorization": "present"}, overrides=["DF-SAFETY"], precedence=60)
        self.assertIn("universal_safety_weakened", self.kinds(self.validate(local)))

    def test_unsupported_condition_is_inconclusive_at_safe_boundary(self):
        rule = self.rule("FIXTURE-UNKNOWN", when={"arbitrary_expression": "true"})
        with self.assertRaises(UnsupportedSemantics): self.validate(rule)

    def test_minimal_counterexamples_are_stable(self):
        left = self.rule("FIXTURE-REQUIRE", requires={"actions": ["edit_candidate"]})
        right = self.rule("FIXTURE-FORBID", forbids={"actions": ["edit_candidate"]})
        self.assertEqual(self.validate(left, right)["findings"], self.validate(left, right)["findings"])

    def procedure(self, rules, actions=None, evidence=None, section="Fixture procedure"):
        return {"schema_version": 1, "stage": "fixture", "prose": "# Fixture procedure\n",
                "procedures": [{"id": "fixture", "section": section, "rules": rules,
                                "actions": actions or [], "evidence": evidence or []}]}

    def test_conformance_detects_orphan_unmapped_unauthorized_and_missing_producer(self):
        mandatory = self.rule("FIXTURE-MANDATORY", requires={"actions": ["edit_candidate"], "evidence": ["repair_receipt"]}, fulfillment="procedure")
        orphan = self.validate(mandatory, procedure=self.procedure(["MISSING-RULE"], ["deploy_authorized"]))
        kinds = self.kinds(orphan)
        self.assertIn("orphaned_procedure_rule", kinds); self.assertIn("unmapped_mandatory_rule", kinds)
        missing = self.validate(mandatory, procedure=self.procedure(["FIXTURE-MANDATORY"], ["deploy_authorized"]))
        kinds = self.kinds(missing)
        self.assertIn("procedure_unauthorized_action", kinds); self.assertIn("procedure_omits_required_producer", kinds)

    def test_prose_only_rule_change_keeps_semantic_digest_but_changes_source_binding(self):
        body = json.dumps({"schema_version": 1, "stage": "fixture", "inherits": ["defensefactory/RULES.md"], "rules": []}, indent=2)
        first = parse_rule_file("# One\n\n" + RULES_START + "\n```json\n" + body + "\n```\n" + RULES_END + "\n", "fixture/RULES.md")
        second = parse_rule_file("# Reworded\n\n" + RULES_START + "\n```json\n" + body + "\n```\n" + RULES_END + "\n", "fixture/RULES.md")
        one = validate_effective("fixture", [self.root_doc, first]); two = validate_effective("fixture", [self.root_doc, second])
        self.assertEqual(one["effective_rules_sha256"], two["effective_rules_sha256"])
        self.assertNotEqual(one["source_bindings"], two["source_bindings"])

    def test_inheritance_cycle_and_missing_parent_fail_package_validation(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup); root = Path(temporary.name)
        universal = root / "defensefactory"; stage = root / "defensefactory-assess"; universal.mkdir(); stage.mkdir()
        root_raw = (ROOT / "skills/defensefactory/RULES.md").read_text().replace('"inherits": []', '"inherits": ["defensefactory-assess/RULES.md"]', 1)
        (universal / "RULES.md").write_text(root_raw); shutil.copy2(ROOT / "skills/defensefactory/SKILL.md", universal / "SKILL.md")
        shutil.copy2(ROOT / "skills/defensefactory-assess/RULES.md", stage / "RULES.md"); shutil.copy2(ROOT / "skills/defensefactory-assess/SKILL.md", stage / "SKILL.md")
        result = validate_package_safe(stage, universal); self.assertEqual(result["result"], "violated"); self.assertIn("cycle", result["error"].lower())
        (universal / "RULES.md").write_text((ROOT / "skills/defensefactory/RULES.md").read_text())
        raw = (stage / "RULES.md").read_text().replace("defensefactory/RULES.md", "missing/RULES.md", 1); (stage / "RULES.md").write_text(raw)
        result = validate_package_safe(stage, universal); self.assertEqual(result["result"], "violated"); self.assertIn("Missing inherited", result["error"])

    def test_every_published_package_is_satisfied(self):
        packages = sorted((ROOT / "skills").glob("defensefactory*"))
        for package in packages:
            with self.subTest(package=package.name):
                result = validate_package_safe(package, ROOT / "skills/defensefactory")
                self.assertEqual(result["result"], "satisfied", result)

    def test_stage_opening_binds_and_revalidates_exact_effective_rules(self):
        package = (ROOT / "skills/defensefactory-verify").resolve()
        preparation = scope_prepare({"case": "FIXTURE-1", "attempt": "rules", "stage": "verify",
            "subject": {"repository": "fixture/component", "revision": "a" * 40},
            "performed_by": "fixture-agent", "authorization_reference": "fixture policy",
            "boundaries": "offline fixture", "package": str(package)})
        independent = validate_package_safe(package, ROOT / "skills/defensefactory")
        self.assertEqual(preparation["scope"]["stage_rules"]["effective_rules_sha256"], independent["effective_rules_sha256"])
        publication = {"id": "fixture-comment", "body": preparation["scope_body"], "createdAt": preparation["prepared_at"]}
        opening = stage_start(preparation, publication, {**publication, "operation": "retrieval", "retrieved_at": preparation["prepared_at"]})
        self.assertEqual(opening["stage_rules"], preparation["scope"]["stage_rules"])
        changed = copy.deepcopy(preparation); changed["rules_validation"]["result"] = "violated"
        with self.assertRaisesRegex(Exception, "receipt missing or changed"):
            stage_start(changed, publication, {**publication, "operation": "retrieval", "retrieved_at": preparation["prepared_at"]})


if __name__ == "__main__": unittest.main()
