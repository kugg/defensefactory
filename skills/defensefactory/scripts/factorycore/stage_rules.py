"""Deterministic stage-rule compilation, bounded satisfiability and skill conformance."""
from __future__ import annotations

import copy
import itertools
import json
from pathlib import Path
import re

from .core import GateError, identity, require, sha


RULES_START = "<!-- defensefactory-stage-rules:start -->"
RULES_END = "<!-- defensefactory-stage-rules:end -->"
MAP_START = "<!-- defensefactory-procedure-map:start -->"
MAP_END = "<!-- defensefactory-procedure-map:end -->"
VALIDATOR = "defensefactory-stage-rules/1"
EFFECTS = ("facts", "actions", "evidence", "transitions", "outcomes", "postconditions")
STRENGTHS = ("must", "must_not", "should", "may")
TERMINAL = ("terminal", "nonterminal", "either")
MUTATION = ("read_only", "write_required", "write_allowed", "none")
ID = re.compile(r"[A-Z][A-Z0-9._-]{1,127}\Z")
STAGE = re.compile(r"[a-z][a-z0-9_-]{1,63}\Z")


class UnsupportedSemantics(GateError):
    pass


def discover_root_package(package: str | Path) -> Path:
    """Find the single universal rule source in a checkout, install or export."""
    package = Path(package).resolve()
    candidates = [package] if package.name == "defensefactory" else [
        package.parent / "defensefactory",
        package / "dependencies/defensefactory",
    ]
    matches = [candidate for candidate in candidates if (candidate / "RULES.md").is_file()]
    require(matches, "A universal defensefactory/RULES.md dependency is required")
    if len(matches) > 1:
        digests = {sha((candidate / "RULES.md").read_bytes()) for candidate in matches}
        require(len(digests) == 1, "Installed and embedded universal RULES.md sources disagree")
    return matches[0]


def receipt_binding(receipt: dict) -> dict:
    """Small immutable binding suitable for a ticket-published stage opening."""
    require(receipt.get("result") == "satisfied", "Stage rules must be satisfied before opening work")
    return {key: copy.deepcopy(receipt[key]) for key in (
        "schema", "stage", "result", "validator", "effective_rules_sha256",
        "source_bindings", "receipt_sha256",
    )}


def _block(raw: bytes | str, start: str, end: str, kind: str) -> tuple[dict, str]:
    if isinstance(raw, bytes): raw = raw.decode("utf-8")
    require(isinstance(raw, str) and raw.count(start) == 1 and raw.count(end) == 1, f"{kind} needs exactly one delimited block")
    before, tail = raw.split(start, 1); body, after = tail.split(end, 1)
    match = re.fullmatch(r"\s*```json\s*\n(.*?)\n```\s*", body, re.DOTALL)
    require(match is not None, f"{kind} block must be one strict JSON fence")
    try: value = json.loads(match.group(1))
    except json.JSONDecodeError as error: raise GateError(f"{kind} JSON is invalid: {error}")
    return value, before + after


def parse_rule_file(raw: bytes | str, source: str) -> dict:
    value, prose = _block(raw, RULES_START, RULES_END, "RULES.md")
    required = {"schema_version", "stage", "inherits", "rules"}; allowed = required | {"vocabulary"}
    require(isinstance(value, dict) and set(value) <= allowed and required <= set(value), "Stage rule document has unknown/missing fields")
    require(value["schema_version"] == 1 and STAGE.fullmatch(value["stage"] or ""), "Unsupported stage-rule schema or stage")
    require(isinstance(value["inherits"], list) and all(isinstance(item, str) and item for item in value["inherits"]), "inherits must be an explicit string list")
    require(isinstance(value["rules"], list), "rules must be an array")
    for rule in value["rules"]: _validate_rule_shape(rule, value["stage"])
    result = copy.deepcopy(value); result.update(source=source, source_sha256=sha(raw.encode() if isinstance(raw, str) else raw), prose=prose.strip())
    return result


def _validate_rule_shape(rule: dict, file_stage: str) -> None:
    fields = {"id", "scope", "strength", "when", "requires", "forbids", "allows", "terminal", "mutation", "overrides", "precedence", "safety", "fulfillment"}
    require(isinstance(rule, dict) and set(rule) == fields, "Rule has unknown/missing fields")
    require(ID.fullmatch(rule["id"] or "") is not None, "Rule ID must be stable uppercase ASCII")
    require(rule["scope"] == "*" or STAGE.fullmatch(rule["scope"] or ""), "Rule scope must be * or a stage")
    require(file_stage == "universal" or rule["scope"] == file_stage, "Stage-local rule scope differs from its file")
    require(rule["strength"] in STRENGTHS and isinstance(rule["when"], dict), "Rule strength/condition invalid")
    for name in ("requires", "forbids", "allows"):
        require(isinstance(rule[name], dict) and set(rule[name]) <= set(EFFECTS), "Rule effects use an unknown category")
        for category, items in rule[name].items():
            require(isinstance(items, list) and all(isinstance(item, str) and item for item in items) and len(items) == len(set(items)), f"Duplicate/empty {name}.{category}")
    require(rule["terminal"] in TERMINAL and rule["mutation"] in MUTATION, "Rule terminal/mutation effect invalid")
    require(isinstance(rule["overrides"], list) and all(isinstance(item, str) and ID.fullmatch(item) for item in rule["overrides"]), "Invalid override references")
    require(isinstance(rule["precedence"], int) and 0 <= rule["precedence"] <= 100 and isinstance(rule["safety"], bool), "Invalid precedence/safety")
    require(rule["fulfillment"] in ("procedure", "operator_only"), "Rule fulfillment must be procedure or operator_only")


def parse_procedure_map(raw: bytes | str) -> dict:
    value, prose = _block(raw, MAP_START, MAP_END, "SKILL.md procedure map")
    require(isinstance(value, dict) and set(value) == {"schema_version", "stage", "procedures"}
            and value["schema_version"] == 1 and STAGE.fullmatch(value["stage"] or "") and isinstance(value["procedures"], list), "Invalid procedure-map shape")
    for row in value["procedures"]:
        require(isinstance(row, dict) and set(row) == {"id", "section", "rules", "actions", "evidence"}, "Procedure map entry has unknown/missing fields")
        require(isinstance(row["id"], str) and row["id"] and isinstance(row["section"], str) and row["section"], "Procedure identity/section required")
        for key in ("rules", "actions", "evidence"):
            require(isinstance(row[key], list) and all(isinstance(item, str) and item for item in row[key]) and len(row[key]) == len(set(row[key])), "Invalid procedure mapping list")
    require(len({row["id"] for row in value["procedures"]}) == len(value["procedures"]), "Duplicate procedure ID")
    value = copy.deepcopy(value); value["prose"] = prose; return value


def _validate_vocabulary(vocabulary: dict) -> None:
    require(isinstance(vocabulary, dict) and set(vocabulary) == {"conditions", "effects", "terminal_outcomes", "exclusive_outcome_groups", "postcondition_requires"}, "Universal vocabulary has unknown/missing fields")
    require(isinstance(vocabulary["conditions"], dict) and vocabulary["conditions"], "Condition vocabulary required")
    for key, values in vocabulary["conditions"].items():
        require(isinstance(key, str) and key and isinstance(values, list) and values and all(isinstance(item, str) and item for item in values) and len(values) == len(set(values)), "Invalid condition vocabulary")
    require(isinstance(vocabulary["effects"], dict) and set(vocabulary["effects"]) == set(EFFECTS), "Every effect category needs a bounded vocabulary")
    for values in vocabulary["effects"].values(): require(isinstance(values, list) and len(values) == len(set(values)) and all(isinstance(item, str) and item for item in values), "Invalid effect vocabulary")
    require(isinstance(vocabulary["terminal_outcomes"], list) and set(vocabulary["terminal_outcomes"]) <= set(vocabulary["effects"]["outcomes"]), "Unknown terminal outcome")
    require(isinstance(vocabulary["exclusive_outcome_groups"], list) and all(isinstance(group, list) and len(group) > 1 and set(group) <= set(vocabulary["effects"]["outcomes"]) for group in vocabulary["exclusive_outcome_groups"]), "Invalid exclusive outcome group")
    require(isinstance(vocabulary["postcondition_requires"], dict), "Invalid postcondition reachability table")
    for postcondition, needs in vocabulary["postcondition_requires"].items():
        require(postcondition in vocabulary["effects"]["postconditions"] and isinstance(needs, dict) and set(needs) <= {"actions", "evidence"}, "Unknown postcondition reachability entry")
        for category, items in needs.items(): require(set(items) <= set(vocabulary["effects"][category]), "Unknown postcondition prerequisite")


def _condition_values(rule: dict, vocabulary: dict) -> dict[str, set[str]]:
    result = {}
    for key, raw in rule["when"].items():
        if key not in vocabulary["conditions"]: raise UnsupportedSemantics("Unsupported condition key: " + key)
        values = {raw} if isinstance(raw, str) else set(raw) if isinstance(raw, list) and raw else None
        if values is None or not all(isinstance(item, str) for item in values): raise UnsupportedSemantics("Unsupported condition expression in " + rule["id"])
        if not values <= set(vocabulary["conditions"][key]): raise UnsupportedSemantics("Unsupported condition value in " + rule["id"])
        result[key] = values
    return result


def _active(rule: dict, assignment: dict, vocabulary: dict) -> bool:
    return all(assignment[key] in values for key, values in _condition_values(rule, vocabulary).items())


def _narrower(child: dict, parent: dict, vocabulary: dict) -> bool:
    c = _condition_values(child, vocabulary); p = _condition_values(parent, vocabulary); strict = False
    for key in vocabulary["conditions"]:
        cv = c.get(key, set(vocabulary["conditions"][key])); pv = p.get(key, set(vocabulary["conditions"][key]))
        if not cv <= pv: return False
        if cv != pv: strict = True
    return strict


def _overlap(left: dict, right: dict, vocabulary: dict) -> bool:
    l = _condition_values(left, vocabulary); r = _condition_values(right, vocabulary)
    return all((l.get(key, set(vocabulary["conditions"][key])) & r.get(key, set(vocabulary["conditions"][key])))
               for key in vocabulary["conditions"])


def _effects(rule: dict, name: str, category: str) -> set[str]:
    return set(rule[name].get(category, []))


def _incompatible(left: dict, right: dict) -> bool:
    for category in EFFECTS:
        if _effects(left, "requires", category) & _effects(right, "forbids", category): return True
        if _effects(right, "requires", category) & _effects(left, "forbids", category): return True
    return left["terminal"] != "either" and right["terminal"] != "either" and left["terminal"] != right["terminal"] or {left["mutation"], right["mutation"]} == {"read_only", "write_required"}


def _finding(kind: str, rules: list[str], assignment: dict, effects: list[str], suggestion: str, precedence: str = "none") -> dict:
    return {"kind": kind, "rule_ids": sorted(rules), "overlapping_condition": dict(sorted(assignment.items())),
            "conflicting_effects": sorted(effects), "precedence_analysis": precedence,
            "counterexample": dict(sorted(assignment.items())), "remediation_suggestion": suggestion}


def _cycles(edges: dict[str, list[str]]) -> list[list[str]]:
    result = []; visiting = []; visited = set()
    def walk(node):
        if node in visiting:
            result.append(visiting[visiting.index(node):] + [node]); return
        if node in visited: return
        visiting.append(node)
        for child in edges.get(node, []): walk(child)
        visiting.pop(); visited.add(node)
    for node in sorted(edges): walk(node)
    return result


def validate_effective(stage: str, documents: list[dict], procedure: dict | None = None) -> dict:
    root = next((item for item in documents if item["stage"] == "universal"), None)
    require(root is not None and "vocabulary" in root, "Universal RULES.md with vocabulary is required")
    vocabulary = root["vocabulary"]; _validate_vocabulary(vocabulary)
    rules = [copy.deepcopy(rule) | {"source": document["source"], "source_stage": document["stage"]}
             for document in documents for rule in document["rules"] if rule["scope"] in ("*", stage)]
    ids = [rule["id"] for rule in rules]; require(len(ids) == len(set(ids)), "Duplicate effective rule ID")
    by_id = {rule["id"]: rule for rule in rules}
    findings = []
    for rule in rules:
        _condition_values(rule, vocabulary)
        for name in ("requires", "forbids", "allows"):
            for category, values in rule[name].items():
                unknown = set(values) - set(vocabulary["effects"][category])
                if unknown: raise UnsupportedSemantics(f"Unsupported {category} in {rule['id']}: {sorted(unknown)}")
        for target in rule["overrides"]:
            require(target in by_id, "Missing override rule: " + target)
            if by_id[target]["safety"] and by_id[target]["scope"] == "*" and rule["source_stage"] != "universal":
                findings.append(_finding("universal_safety_weakened", [rule["id"], target], {}, [], "Do not override universal safety rules from a stage-local package.", "universal safety has precedence"))
            if rule["precedence"] <= by_id[target]["precedence"]:
                findings.append(_finding("invalid_override_precedence", [rule["id"], target], {}, [], "Give an explicit narrower exception strictly higher precedence.", f"{rule['precedence']} <= {by_id[target]['precedence']}"))
            if not _narrower(rule, by_id[target], vocabulary):
                findings.append(_finding("exception_not_narrower", [rule["id"], target], {}, [], "Narrow the exception condition; an override may not broaden authority.", "condition is not a strict subset"))
    override_cycles = _cycles({rule["id"]: rule["overrides"] for rule in rules})
    for cycle in override_cycles: findings.append(_finding("override_cycle", cycle, {}, [], "Remove the cyclic override chain."))

    condition_keys = sorted(vocabulary["conditions"])
    assignments = [dict(zip(condition_keys, values)) for values in itertools.product(*(vocabulary["conditions"][key] for key in condition_keys))]
    satisfiable = {(state, disposition): False for state in vocabulary["conditions"].get("stage_state", []) for disposition in vocabulary["conditions"].get("disposition_class", [])}
    for assignment in assignments:
        active = [rule for rule in rules if _active(rule, assignment, vocabulary)]
        active_ids = {rule["id"] for rule in active}
        overriding = [rule for rule in active if set(rule["overrides"]) & active_ids]
        for target in sorted({target for rule in overriding for target in rule["overrides"] if target in active_ids}):
            contenders = [rule for rule in overriding if target in rule["overrides"]]
            top = max((rule["precedence"] for rule in contenders), default=-1); top_rules = [rule for rule in contenders if rule["precedence"] == top]
            for left, right in itertools.combinations(top_rules, 2):
                if _incompatible(left, right): findings.append(_finding("equal_precedence_override_conflict", [left["id"], right["id"], target], assignment, [], "Select one higher-precedence narrower override or make their effects compatible.", f"equal precedence {top}"))
        overridden = {target for rule in overriding for target in rule["overrides"] if rule["precedence"] > by_id[target]["precedence"] and _narrower(rule, by_id[target], vocabulary)}
        effective = [rule for rule in active if rule["id"] not in overridden]
        local = []
        for category in EFFECTS:
            required = {}; forbidden = {}; allowed = set()
            for rule in effective:
                for item in _effects(rule, "requires", category): required.setdefault(item, []).append(rule["id"])
                for item in _effects(rule, "forbids", category): forbidden.setdefault(item, []).append(rule["id"])
                allowed |= _effects(rule, "allows", category)
            for item in sorted(required.keys() & forbidden.keys()):
                local.append(_finding("required_forbidden_conflict", required[item] + forbidden[item], assignment, [category + ":" + item], "Remove one effect or add a valid narrower precedence rule."))
            if category == "postconditions":
                for postcondition, rule_ids in required.items():
                    needs = vocabulary["postcondition_requires"].get(postcondition, {})
                    for needed_category, needed_items in needs.items():
                        available = set().union(*(_effects(rule, "requires", needed_category) | _effects(rule, "allows", needed_category) for rule in effective)) if effective else set()
                        blocked = set().union(*(_effects(rule, "forbids", needed_category) for rule in effective)) if effective else set()
                        missing = set(needed_items) - available
                        unreachable = set(needed_items) & blocked
                        if missing or unreachable:
                            local.append(_finding("unreachable_postcondition", rule_ids + [rule["id"] for rule in effective if _effects(rule,"forbids",needed_category)&set(needed_items)], assignment,
                                [postcondition, "missing:" + ",".join(sorted(missing)), "forbidden:" + ",".join(sorted(unreachable))], "Map and permit every prerequisite for the mandatory postcondition."))
        terminal_rules = [rule for rule in effective if rule["terminal"] != "either"]
        if {rule["terminal"] for rule in terminal_rules} == {"terminal", "nonterminal"}:
            local.append(_finding("terminal_state_conflict", [rule["id"] for rule in terminal_rules], assignment, ["terminal", "nonterminal"], "Narrow one condition or establish valid precedence."))
        mutation_rules = [rule for rule in effective if rule["mutation"] in ("read_only", "write_required")]
        if {rule["mutation"] for rule in mutation_rules} == {"read_only", "write_required"}:
            local.append(_finding("mutation_readonly_conflict", [rule["id"] for rule in mutation_rules], assignment, ["read_only", "write_required"], "Separate read-only and mutation conditions."))
        required_outcomes = {item for rule in effective for item in _effects(rule, "requires", "outcomes")}
        required_transitions = {item for rule in effective for item in _effects(rule, "requires", "transitions")}
        if "continue" in required_transitions and (required_outcomes & set(vocabulary["terminal_outcomes"]) or any(rule["terminal"] == "terminal" for rule in effective)):
            local.append(_finding("continue_terminal_conflict", [rule["id"] for rule in effective if "continue" in _effects(rule,"requires","transitions") or rule["terminal"]=="terminal" or _effects(rule,"requires","outcomes")&set(vocabulary["terminal_outcomes"])], assignment, ["continue", "terminal"], "Stop after the terminal disposition or narrow the continue rule."))
        for group in vocabulary["exclusive_outcome_groups"]:
            conflict = required_outcomes & set(group)
            if len(conflict) > 1: local.append(_finding("mutually_exclusive_outcomes", [rule["id"] for rule in effective if _effects(rule,"requires","outcomes")&conflict], assignment, list(conflict), "Require only one outcome in the exclusive group."))
        findings.extend(local)
        key = (assignment.get("stage_state"), assignment.get("disposition_class"))
        if key in satisfiable and not local: satisfiable[key] = True
    for (state, disposition), ok in sorted(satisfiable.items()):
        if not ok: findings.append(_finding("unsatisfiable_state", [], {"stage_state": state, "disposition_class": disposition}, [], "Change conditions/effects so at least one execution path is satisfiable."))

    conformance = _conformance(stage, rules, vocabulary, procedure) if procedure is not None else {"result": "not_checked", "findings": []}
    findings.extend(conformance["findings"])
    dedup = {identity(item): item for item in findings}; findings = [dedup[key] for key in sorted(dedup)]
    effective = {"schema_version": 1, "stage": stage, "validator": VALIDATOR,
                 "sources": [item["source"] for item in documents],
                 "rules": [{key: value for key, value in rule.items() if key not in ("source", "source_stage")} for rule in rules]}
    receipt = {"schema": "defensefactory/stage-rules-validation/v1", "stage": stage,
               "result": "violated" if findings else "satisfied", "validator": VALIDATOR,
               "effective_rules_sha256": identity(effective), "effective_rules": effective,
               "source_bindings": [{"path": item["source"], "sha256": item["source_sha256"]} for item in documents],
               "findings": findings, "conformance": conformance,
               "modeled_assignments": len(assignments), "satisfiable_state_classes": sum(satisfiable.values()),
               "state_classes": len(satisfiable)}
    receipt["receipt_sha256"] = identity(receipt); return receipt


def _headings(prose: str) -> set[str]:
    result = set()
    for line in prose.splitlines():
        if line.startswith("# "): result.add(line[2:].strip())
        elif line.startswith("## "): result.add(line[3:].strip())
    return result


def _conformance(stage: str, rules: list[dict], vocabulary: dict, procedure: dict) -> dict:
    findings = []; by_id = {rule["id"]: rule for rule in rules}; headings = _headings(procedure["prose"])
    if procedure["stage"] != stage: findings.append(_finding("procedure_stage_mismatch", [], {}, [procedure["stage"], stage], "Use the package stage in its procedure map."))
    mapped_rules = set(); mapped_sections = set()
    for row in procedure["procedures"]:
        mapped_sections.add(row["section"])
        if row["section"] not in headings: findings.append(_finding("missing_procedure_section", row["rules"], {}, [row["section"]], "Reference an existing H1/H2 procedure section."))
        unknown = set(row["rules"]) - set(by_id)
        if unknown: findings.append(_finding("orphaned_procedure_rule", list(unknown), {}, [], "Reference only effective rule IDs."))
        mapped_rules |= set(row["rules"]) & set(by_id)
        cited = [by_id[item] for item in row["rules"] if item in by_id]
        permission_rules = {action: [rule for rule in cited if action in (_effects(rule,"requires","actions")|_effects(rule,"allows","actions"))]
                            for action in row["actions"]}
        permitted_actions = {action for action, authorizers in permission_rules.items() if authorizers}
        unauthorized = set(row["actions"]) - permitted_actions
        forbidden = {action for action, authorizers in permission_rules.items() if authorizers and all(
            any(action in _effects(blocker,"forbids","actions") and _overlap(authorizer, blocker, vocabulary) for blocker in cited)
            for authorizer in authorizers)}
        if unauthorized or forbidden: findings.append(_finding("procedure_unauthorized_action", row["rules"], {}, list(unauthorized|forbidden), "Map the action to an authorizing rule or remove it from the procedure."))
        permitted_evidence = {item for rule in cited for item in _effects(rule,"requires","evidence")|_effects(rule,"allows","evidence")}
        if set(row["evidence"]) - permitted_evidence: findings.append(_finding("procedure_unauthorized_evidence", row["rules"], {}, list(set(row["evidence"])-permitted_evidence), "Map the evidence producer to a rule."))
    for heading in sorted(headings - mapped_sections): findings.append(_finding("unmapped_procedure_section", [], {}, [heading], "Map every H1/H2 procedure section to applicable rule IDs."))
    for rule in rules:
        if rule["strength"] in ("must", "must_not") and rule["fulfillment"] == "procedure" and rule["id"] not in mapped_rules:
            findings.append(_finding("unmapped_mandatory_rule", [rule["id"]], {}, [], "Map the mandatory rule to a procedure/helper or declare it operator_only."))
        rows = [row for row in procedure["procedures"] if rule["id"] in row["rules"]]
        produced_actions = {item for row in rows for item in row["actions"]}; produced_evidence = {item for row in rows for item in row["evidence"]}
        missing_actions = _effects(rule,"requires","actions") - produced_actions
        missing_evidence = _effects(rule,"requires","evidence") - produced_evidence
        if rule["fulfillment"] == "procedure" and (missing_actions or missing_evidence):
            findings.append(_finding("procedure_omits_required_producer", [rule["id"]], {}, ["action:"+item for item in sorted(missing_actions)]+["evidence:"+item for item in sorted(missing_evidence)], "Add the required producer to a mapped procedure or make the rule explicitly operator_only."))
    return {"result": "violated" if findings else "satisfied", "findings": findings,
            "mapped_rules": sorted(mapped_rules), "mapped_sections": sorted(mapped_sections)}


def validate_package(package: str | Path, root_package: str | Path, profiles: list[str | Path] | None = None) -> dict:
    package = Path(package); root_package = Path(root_package)
    documents = {}
    root_ref = "defensefactory/RULES.md"
    root = parse_rule_file((root_package / "RULES.md").read_bytes(), root_ref); documents[root_ref] = root
    package_ref = package.name + "/RULES.md"
    if package.resolve() != root_package.resolve(): documents[package_ref] = parse_rule_file((package / "RULES.md").read_bytes(), package_ref)
    for profile_path in profiles or []:
        path = Path(profile_path); reference = "profile:" + path.stem
        require(reference not in documents, "Duplicate policy profile identity"); documents[reference] = parse_rule_file(path.read_bytes(), reference)
    target = root_ref if package.resolve() == root_package.resolve() else package_ref
    cycles = _cycles({reference: value["inherits"] for reference, value in documents.items()})
    if cycles: raise GateError("Rule inheritance cycle: " + " -> ".join(cycles[0]))
    ordered = []; seen = set()
    def collect(reference):
        require(reference in documents, "Missing inherited rule set: " + reference)
        if reference in seen:return
        for parent in documents[reference]["inherits"]: collect(parent)
        seen.add(reference);ordered.append(documents[reference])
    collect(target)
    for reference in sorted(documents):
        if reference.startswith("profile:"): collect(reference)
    stage = "orchestrate" if package.resolve() == root_package.resolve() else documents[target]["stage"]
    procedure = parse_procedure_map((package / "SKILL.md").read_bytes())
    return validate_effective(stage, ordered, procedure)


def validate_package_safe(package: str | Path, root_package: str | Path, profiles: list[str | Path] | None = None) -> dict:
    try: return validate_package(package, root_package, profiles)
    except UnsupportedSemantics as error:
        result = {"schema": "defensefactory/stage-rules-validation/v1", "stage": Path(package).name,
                  "result": "inconclusive", "validator": VALIDATOR, "error": str(error), "findings": []}
    except (GateError, OSError, ValueError, json.JSONDecodeError) as error:
        result = {"schema": "defensefactory/stage-rules-validation/v1", "stage": Path(package).name,
                  "result": "violated", "validator": VALIDATOR, "error": str(error), "findings": []}
    result["receipt_sha256"] = identity(result); return result
