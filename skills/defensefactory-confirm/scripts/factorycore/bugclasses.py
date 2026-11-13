"""Claim/invariant-bound bug-class receipts; no ticket or repository mutation."""
from __future__ import annotations

import copy
import json
import re

from .core import identity, require


REVISION = re.compile(r"[0-9a-f]{40}\Z")
CLASS_ID = re.compile(r"[A-Z][A-Z0-9._-]{2,127}\Z")
CURRENT = {"triage", "backlog", "active", "in_progress", "reopened"}
HISTORICAL = {"completed", "canceled", "duplicate", "superseded", "resolved", "archived"}
MEMBERSHIP = {"included_current", "included_historical", "excluded_different_invariant",
              "excluded_incompatible_boundary", "excluded_invalid_or_removed_source", "duplicate_member",
              "inconclusive_missing_evidence", "inconclusive_boundary_unknown"}
MEMBER_RESULTS = {"covered_satisfied", "covered_violation", "covered_false_positive_rejected",
                  "not_reproducible_with_evidence", "inconclusive_missing_engine", "inconclusive_missing_runtime",
                  "inconclusive_insufficient_history", "outside_final_class"}
CLASS_RESULTS = {"class_remediated_within_scope", "member_fix_only", "class_inconclusive", "class_violated", "class_definition_rejected"}


def _subject(value, name="subject"):
    require(isinstance(value, dict) and set(value) == {"repository", "revision"} and value["repository"] and REVISION.fullmatch(value["revision"] or ""), "Exact " + name + " repository/full revision required")


def _references(values, *, required=True):
    require(isinstance(values, list) and (values or not required) and all(
        isinstance(item, dict) and set(item) == {"kind", "reference"}
        and isinstance(item["kind"], str) and item["kind"]
        and isinstance(item["reference"], str) and item["reference"]
        and not item["reference"].startswith("file://") for item in values),
        "Evidence references need kind and a shareable non-file reference")


def _ticket(value):
    fields = {"ticket", "url", "lifecycle", "title", "component", "boundary", "claim_id", "invariant_id", "behavior",
              "evidence_references", "source_state", "taxonomy", "relations"}
    require(isinstance(value, dict) and set(value) == fields and value["ticket"] and value["lifecycle"] in CURRENT | HISTORICAL,
            "Candidate ticket has unknown/missing fields or lifecycle")
    require(all(isinstance(value[key], str) for key in ("title", "component", "boundary", "claim_id", "invariant_id", "behavior", "source_state")), "Candidate ticket text fields must be strings")
    require(re.fullmatch(r"https://[^\s]+", value["url"] or ""), "Candidate ticket needs a shareable HTTPS URL")
    require(value["source_state"] in ("current", "removed", "deprecated", "unknown"), "Unknown source state")
    require(isinstance(value["taxonomy"], list) and isinstance(value["relations"], list), "Taxonomy/relations must be arrays")
    _references(value["evidence_references"], required=False)


def discover(trigger, subject, queries, tickets, coverage):
    """Normalize caller-supplied discovery. Similarity is candidate generation only."""
    _subject(subject); _ticket(trigger)
    require(isinstance(queries, list) and queries, "At least one retained discovery query required")
    for query in queries:
        require(isinstance(query, dict) and set(query) == {"id", "source", "query", "scope", "result_reference", "coverage_limitations"}
                and all(query[key] for key in ("id", "source", "query", "scope", "result_reference"))
                and isinstance(query["coverage_limitations"], list), "Discovery query needs source/scope/result and limitations")
    require(isinstance(tickets, list), "Retrieved candidate tickets must be an array")
    for ticket in tickets: _ticket(ticket)
    all_tickets = [trigger, *[ticket for ticket in tickets if ticket["ticket"] != trigger["ticket"]]]
    require(len({ticket["ticket"] for ticket in all_tickets}) == len(all_tickets), "Duplicate candidate ticket")
    require(isinstance(coverage, dict) and set(coverage) == {"ticket_states", "repositories", "history_sources", "codeintel", "limitations"}
            and all(isinstance(coverage[key], list) for key in ("ticket_states", "repositories", "history_sources", "limitations"))
            and isinstance(coverage["codeintel"], dict), "Discovery coverage declaration required")
    require(set(coverage["ticket_states"]) & CURRENT and set(coverage["ticket_states"]) & HISTORICAL,
            "Discovery coverage must include current and historical ticket states")
    require(any(query["source"] == "ticket" for query in queries), "Discovery must retain a ticket-system query")
    candidates = []
    words = lambda text: set(re.findall(r"[a-z0-9]+", text.lower()))
    trigger_words = words(trigger["title"] + " " + trigger["behavior"])
    for ticket in all_tickets:
        basis = []
        if ticket["claim_id"] and ticket["claim_id"] == trigger["claim_id"]: basis.append("declared_claim")
        if ticket["invariant_id"] and ticket["invariant_id"] == trigger["invariant_id"]: basis.append("declared_invariant")
        if ticket["component"] == trigger["component"]: basis.append("component_hint")
        if ticket["boundary"] == trigger["boundary"]: basis.append("boundary_hint")
        overlap = sorted(trigger_words & words(ticket["title"] + " " + ticket["behavior"]))
        if overlap: basis.append("lexical_hint")
        if set(ticket["taxonomy"]) & set(trigger["taxonomy"]): basis.append("taxonomy_hint")
        candidates.append({"ticket": copy.deepcopy(ticket), "discovery_basis": basis or ["retrieved_by_declared_query"],
                           "matched_terms": overlap, "membership": "candidate_only"})
    receipt = {"schema": "defensefactory/bugclass-discovery/v1", "trigger_ticket": trigger["ticket"], "subject": copy.deepcopy(subject),
               "governing_hint": {"component": trigger["component"], "claim_id": trigger["claim_id"], "invariant_id": trigger["invariant_id"], "boundary": trigger["boundary"]},
               "queries": copy.deepcopy(queries), "coverage": copy.deepcopy(coverage), "candidates": candidates,
               "candidate_count": len(candidates), "proposal_only": True,
               "qualification": "Discovery hints do not establish membership, remediation or coverage."}
    receipt["receipt_sha256"] = identity(receipt); return receipt


def evaluate_membership(discovery, decisions, evaluator):
    require(discovery.get("schema") == "defensefactory/bugclass-discovery/v1" and discovery.get("receipt_sha256") == identity({key: value for key, value in discovery.items() if key != "receipt_sha256"}), "Changed discovery receipt")
    require(isinstance(evaluator, dict) and set(evaluator) == {"identity", "version", "method", "scope_reference"} and all(evaluator.values()), "Bounded evaluator identity/method/scope required")
    expected = {row["ticket"]["ticket"]: row for row in discovery["candidates"]}
    require(isinstance(decisions, list) and {row.get("ticket") for row in decisions} == set(expected) and len(decisions) == len(expected), "Exactly one decision per discovery candidate required")
    output = []
    for decision in decisions:
        fields = {"ticket", "disposition", "shared_or_differing_invariant", "boundary_compatibility", "component_relationship",
                  "triggering_behavior", "fence_coverability", "evidence", "limitations", "duplicate_of", "external_proposals"}
        require(set(decision) == fields and decision["disposition"] in MEMBERSHIP, "Membership decision has unknown/missing fields or disposition")
        require(decision["boundary_compatibility"] in ("compatible", "incompatible", "unknown") and decision["fence_coverability"] in ("yes", "no", "unknown"), "Invalid boundary/fence evaluation")
        require(all(decision[key] for key in ("shared_or_differing_invariant", "component_relationship", "triggering_behavior")), "Membership rationale fields required")
        _references(decision["evidence"], required=decision["disposition"].startswith(("included", "excluded")) or decision["disposition"] == "duplicate_member")
        require(isinstance(decision["limitations"], list), "Membership limitations must be an array")
        require(isinstance(decision["external_proposals"], list), "External proposals must be an array")
        for proposal in decision["external_proposals"]:
            require(isinstance(proposal, dict) and set(proposal) == {"source", "version", "proposed_disposition", "evidence_reference"}
                    and proposal["source"] and proposal["version"] and proposal["proposed_disposition"] in MEMBERSHIP
                    and isinstance(proposal["evidence_reference"], str) and proposal["evidence_reference"]
                    and not proposal["evidence_reference"].startswith("file://"),
                    "External membership proposal is incomplete or unshareable")
        candidate = expected[decision["ticket"]]["ticket"]; disposition = decision["disposition"]
        if disposition == "included_current":
            require(candidate["lifecycle"] in CURRENT and decision["boundary_compatibility"] == "compatible" and decision["fence_coverability"] == "yes", "Current inclusion needs current lifecycle and compatible coverable boundary")
        if disposition == "included_historical":
            require(candidate["lifecycle"] in HISTORICAL and decision["boundary_compatibility"] == "compatible" and decision["fence_coverability"] == "yes", "Historical inclusion needs historical lifecycle and compatible coverable boundary")
        if disposition == "excluded_different_invariant": require("different" in decision["shared_or_differing_invariant"].lower(), "Different-invariant exclusion needs explicit rationale")
        if disposition == "excluded_incompatible_boundary": require(decision["boundary_compatibility"] == "incompatible", "Boundary exclusion needs incompatible boundary")
        if disposition == "excluded_invalid_or_removed_source": require(candidate["source_state"] in ("removed", "deprecated"), "Removed-source exclusion needs source evidence")
        if disposition == "duplicate_member": require(decision["duplicate_of"] in expected and decision["duplicate_of"] != decision["ticket"], "Duplicate membership needs canonical member")
        if disposition.startswith("inconclusive_"): require(decision["limitations"], "Inconclusive membership needs limitations")
        output.append({"candidate": copy.deepcopy(candidate), "decision": copy.deepcopy(decision), "evaluator": copy.deepcopy(evaluator)})
    output.sort(key=lambda row: row["candidate"]["ticket"])
    receipt = {"schema": "defensefactory/bugclass-membership/v1", "discovery_sha256": discovery["receipt_sha256"],
               "subject": discovery["subject"], "trigger_ticket": discovery["trigger_ticket"], "evaluations": output,
               "lifecycle_preserved": all(row["candidate"]["lifecycle"] == expected[row["candidate"]["ticket"]]["ticket"]["lifecycle"] for row in output),
               "candidate_evaluation_separated": True,
               "external_proposal_disagreements": sorted(row["candidate"]["ticket"] for row in output
                   if any(item["proposed_disposition"] != row["decision"]["disposition"] for item in row["decision"]["external_proposals"]))}
    receipt["receipt_sha256"] = identity(receipt); return receipt


def define_class(membership, definition):
    require(membership.get("schema") == "defensefactory/bugclass-membership/v1" and membership.get("receipt_sha256") == identity({key: value for key, value in membership.items() if key != "receipt_sha256"}), "Changed membership receipt")
    fields = {"id", "statement", "claim_id", "invariant_id", "applicable_component_types", "boundary", "mandatory_contracts",
              "required_hard_fence", "coverage_expectations", "owner", "reviewers", "lineage"}
    require(isinstance(definition, dict) and set(definition) == fields and CLASS_ID.fullmatch(definition["id"] or ""), "Bug-class definition has unknown/missing fields or ID")
    require(all(definition[key] for key in ("statement", "claim_id", "invariant_id", "boundary", "mandatory_contracts", "required_hard_fence", "coverage_expectations", "owner", "reviewers")), "Bug-class definition is incomplete")
    require(isinstance(definition["applicable_component_types"], list) and isinstance(definition["mandatory_contracts"], list) and isinstance(definition["reviewers"], list) and isinstance(definition["lineage"], list), "Bug-class collection fields must be arrays")
    groups = {name: [] for name in ("included_current", "included_historical", "excluded", "inconclusive", "duplicates")}
    member_lifecycles = {}
    member_urls = {}
    for row in membership["evaluations"]:
        disposition = row["decision"]["disposition"]; ticket = row["candidate"]["ticket"]
        if disposition in groups:
            groups[disposition].append(ticket); member_lifecycles[ticket] = row["candidate"]["lifecycle"]; member_urls[ticket] = row["candidate"]["url"]
        elif disposition.startswith("excluded_"): groups["excluded"].append({"ticket": ticket, "reason": disposition})
        elif disposition.startswith("inconclusive_"): groups["inconclusive"].append({"ticket": ticket, "reason": disposition})
        elif disposition == "duplicate_member": groups["duplicates"].append({"ticket": ticket, "of": row["decision"]["duplicate_of"]})
    require(membership["trigger_ticket"] in groups["included_current"] + groups["included_historical"], "Triggering ticket must be an included member")
    included = [row["candidate"] for row in membership["evaluations"] if row["decision"]["disposition"].startswith("included_")]
    require(all(row["claim_id"] == definition["claim_id"] and row["invariant_id"] == definition["invariant_id"]
                and row["component"] in definition["applicable_component_types"] for row in included),
            "Included members must bind the class claim, invariant and applicable component type")
    receipt = {"schema": "defensefactory/bugclass-definition/v1", "definition": copy.deepcopy(definition),
               "subject": membership["subject"], "trigger_ticket": membership["trigger_ticket"], **groups,
               "member_lifecycles": member_lifecycles, "member_urls": member_urls,
               "membership_sha256": membership["receipt_sha256"], "definition_complete": not groups["inconclusive"],
               "portable_identity": definition["id"], "qualification": "Class identity describes the current/component boundary and does not rewrite historical Git subjects."}
    receipt["receipt_sha256"] = identity(receipt); return receipt


def repair_contract(class_record, design):
    require(class_record.get("schema") == "defensefactory/bugclass-definition/v1" and class_record.get("receipt_sha256") == identity({key: value for key, value in class_record.items() if key != "receipt_sha256"}), "Changed bug-class definition")
    fields = {"restores_claim", "closes_invariant", "path_analysis", "preserves", "hard_fence", "historical_variants",
              "other_claims", "limitations", "boundary_change", "boundary_review_reference"}
    require(isinstance(design, dict) and set(design) == fields, "Repair design has unknown/missing fields")
    require(design["restores_claim"] == class_record["definition"]["claim_id"] and design["closes_invariant"] == class_record["definition"]["invariant_id"], "Repair design must bind the class claim/invariant")
    require(isinstance(design["path_analysis"], list), "Path analysis must be an array")
    required_paths = {"primary", "retry", "fallback", "alternate_constructor", "configuration"}
    observed = {row.get("kind") for row in design["path_analysis"]}
    require(observed == required_paths and all(row.get("disposition") in ("covered", "not_applicable", "inconclusive") and row.get("rationale") for row in design["path_analysis"]), "Analyze primary, retry, fallback, alternate constructor and configuration paths")
    require(isinstance(design["preserves"], list) and design["preserves"] and isinstance(design["other_claims"], list)
            and isinstance(design["limitations"], list), "Preserved behavior, other claims and limitations required")
    require(all(isinstance(row, dict) and set(row) == {"id", "behavior", "contract"} and all(row.values()) for row in design["preserves"]),
            "Preserved behaviors need stable IDs, behavior and contracts")
    require(all(isinstance(row, dict) and set(row) == {"id", "protection_contract"} and all(row.values()) for row in design["other_claims"]),
            "Other affected claims need protection contracts")
    fence = design["hard_fence"]
    require(isinstance(fence, dict) and set(fence) == {"id", "mechanism", "contract", "coverage", "introduction_ref_status"}
            and all(fence.values()) and fence["mechanism"] not in ("markdown", "agent_instruction", "human_review"), "A deterministic hard fence/contract is required")
    require(fence["id"] == class_record["definition"]["required_hard_fence"] and fence["contract"] in class_record["definition"]["mandatory_contracts"], "Repair hard fence/contract must match the class definition")
    expected_historical = set(class_record["included_historical"])
    variants = {row.get("ticket"): row for row in design["historical_variants"]}
    require(set(variants) == expected_historical and all(row.get("contract") and row.get("disposition") in ("encoded", "explicit_limitation") for row in variants.values()), "Every historical member needs a regression contract or explicit limitation")
    require(design["boundary_change"] in ("unchanged", "proposed_expansion") and (design["boundary_change"] == "unchanged" or design["boundary_review_reference"]), "Boundary expansion needs explicit review reference")
    receipt = {"schema": "defensefactory/bugclass-repair-contract/v1", "class_id": class_record["definition"]["id"],
               "class_sha256": class_record["receipt_sha256"], "subject": class_record["subject"], "design": copy.deepcopy(design),
               "required_before_product_edit": True, "class_wide_claim_permitted": False,
               "readiness": "inconclusive" if class_record["inconclusive"] or any(row["disposition"] == "inconclusive" for row in design["path_analysis"]) else "ready_for_bounded_construction"}
    receipt["receipt_sha256"] = identity(receipt); return receipt


def variant_matrix(class_record, repair, pr_head, merge_subject, rows, evaluator):
    for value, name in ((pr_head, "PR head"), (merge_subject, "merge subject")): _subject(value, name)
    require(pr_head["repository"] == merge_subject["repository"] == class_record["subject"]["repository"],
            "PR head, merge subject and repair subject must name the same repository")
    require(repair.get("class_sha256") == class_record.get("receipt_sha256") and repair.get("receipt_sha256") == identity({key: value for key, value in repair.items() if key != "receipt_sha256"}), "Repair contract does not bind class")
    expected = set(class_record["included_current"] + class_record["included_historical"])
    require(isinstance(rows, list) and {row.get("ticket") for row in rows} == expected and len(rows) == len(expected), "Proof matrix needs exactly every included member")
    require(isinstance(evaluator, dict) and set(evaluator) == {"identity", "version", "policy_reference"} and all(evaluator.values()), "Evaluator identity/version/policy required")
    matrix = []
    for row in rows:
        fields = {"ticket", "lifecycle", "membership", "variant_contract", "candidate", "evaluation", "covered_by_fence", "evidence_references", "coverage_limitations"}
        require(set(row) == fields and row["candidate"].get("result") in MEMBER_RESULTS and row["evaluation"].get("disposition") in MEMBER_RESULTS,
                "Proof row has unknown/missing fields or result")
        require(row["candidate"]["result"] == row["evaluation"]["disposition"], "Candidate result and separate evaluation disagree")
        require(row["covered_by_fence"] in ("yes", "no", "unknown") and row["membership"] in ("included_current", "included_historical"), "Invalid proof membership/fence result")
        if row["ticket"] in class_record["included_current"]: require(row["membership"] == "included_current" and row["lifecycle"] in CURRENT, "Current proof row lifecycle/membership mismatch")
        if row["ticket"] in class_record["included_historical"]: require(row["membership"] == "included_historical" and row["lifecycle"] in HISTORICAL, "Historical proof row lifecycle/membership mismatch")
        require(row["lifecycle"] == class_record["member_lifecycles"][row["ticket"]], "Proof row changed the ticket lifecycle")
        require(row["variant_contract"] and row["candidate"].get("raw_reference") and row["evaluation"].get("evidence") and isinstance(row["coverage_limitations"], list), "Proof row needs contract/raw/evaluation evidence")
        _references(row["evidence_references"])
        matrix.append(copy.deepcopy(row))
    matrix.sort(key=lambda row: row["ticket"])
    receipt = {"schema": "defensefactory/bugclass-proof-matrix/v1", "class_id": class_record["definition"]["id"],
               "class_sha256": class_record["receipt_sha256"], "repair_sha256": repair["receipt_sha256"],
               "pr_head": copy.deepcopy(pr_head), "merge_subject": copy.deepcopy(merge_subject), "rows": matrix,
               "evaluator": copy.deepcopy(evaluator), "candidate_evaluation_separated": True,
               "repair_design": copy.deepcopy(repair["design"]),
               "preservation_requirements": copy.deepcopy(repair["design"]["preserves"]),
               "other_claim_requirements": copy.deepcopy(repair["design"]["other_claims"])}
    receipt["receipt_sha256"] = identity(receipt); return receipt


def verify_class(class_record, matrix, fence, claim, preservation, other_claims, boundary_review=None):
    require(matrix.get("class_sha256") == class_record.get("receipt_sha256") and matrix.get("receipt_sha256") == identity({key: value for key, value in matrix.items() if key != "receipt_sha256"}), "Proof matrix does not bind class")
    require(fence.get("id") == class_record["definition"]["required_hard_fence"] and fence.get("result") in ("satisfied", "violated", "inconclusive") and fence.get("evidence_reference"), "Required hard-fence evaluation missing")
    require(claim.get("id") == class_record["definition"]["claim_id"] and claim.get("result") in ("satisfied", "violated", "inconclusive") and claim.get("evidence_reference"), "Governing claim evaluation missing")
    expected_preservation = {row["id"] for row in matrix["preservation_requirements"]}
    expected_claims = {row["id"] for row in matrix["other_claim_requirements"]}
    require(isinstance(preservation, list) and len(preservation) == len(expected_preservation)
            and {row.get("id") for row in preservation} == expected_preservation
            and all(row.get("result") in ("satisfied", "violated", "inconclusive") and row.get("evidence_reference") for row in preservation),
            "Every preserved behavior needs an evaluated result")
    require(isinstance(other_claims, list) and len(other_claims) == len(expected_claims)
            and {row.get("id") for row in other_claims} == expected_claims
            and all(row.get("result") in ("satisfied", "violated", "inconclusive") and row.get("evidence_reference") for row in other_claims),
            "Every affected claim needs an evaluated protection result")
    results = {row["ticket"]: row["evaluation"]["disposition"] for row in matrix["rows"]}
    trigger = results[class_record["trigger_ticket"]]
    support_results = [row["result"] for row in preservation + other_claims]
    violated = fence["result"] == "violated" or claim["result"] == "violated" or "covered_violation" in results.values() or "violated" in support_results
    definition_rejected = boundary_review is not None and boundary_review.get("result") == "rejected"
    inconclusive_results = {"inconclusive_missing_engine", "inconclusive_missing_runtime", "inconclusive_insufficient_history", "not_reproducible_with_evidence"}
    unresolved = bool(class_record["inconclusive"] or any(value in inconclusive_results for value in results.values())
                      or any(row["coverage_limitations"] for row in matrix["rows"])
                      or fence["result"] == "inconclusive" or claim["result"] == "inconclusive" or "inconclusive" in support_results)
    all_covered = all(value in ("covered_satisfied", "covered_false_positive_rejected") for value in results.values()) and all(row["covered_by_fence"] == "yes" for row in matrix["rows"])
    if definition_rejected: outcome = "class_definition_rejected"
    elif violated: outcome = "class_violated"
    elif all_covered and not unresolved and fence["result"] == claim["result"] == "satisfied": outcome = "class_remediated_within_scope"
    elif trigger == "covered_satisfied": outcome = "class_inconclusive" if unresolved else "member_fix_only"
    else: outcome = "class_inconclusive"
    receipt = {"schema": "defensefactory/bugclass-verification/v1", "class_id": class_record["definition"]["id"],
               "merge_subject": matrix["merge_subject"], "matrix_sha256": matrix["receipt_sha256"], "fence": copy.deepcopy(fence),
               "claim": copy.deepcopy(claim), "preservation": copy.deepcopy(preservation), "other_claims": copy.deepcopy(other_claims),
               "boundary_review": copy.deepcopy(boundary_review), "outcome": outcome,
               "class_wide_remediation_claim_permitted": outcome == "class_remediated_within_scope",
               "technical_result": outcome, "process_adherence": "not_established_by_technical_matrix"}
    receipt["receipt_sha256"] = identity(receipt); return receipt


def pr_section(class_record, matrix, verification, pr_url):
    require(verification.get("matrix_sha256") == matrix.get("receipt_sha256") and verification.get("outcome") in CLASS_RESULTS, "Verification/matrix mismatch")
    require(re.fullmatch(r"https://[^\s]+", pr_url or ""), "HTTPS PR URL required")
    member = lambda ticket: f"[{ticket}]({class_record['member_urls'][ticket]})"
    included_current = ", ".join(member(ticket) for ticket in class_record["included_current"]) or "None"
    historical = ", ".join(member(ticket) for ticket in class_record["included_historical"]) or "None"
    excluded = ", ".join(row["ticket"] + " (" + row["reason"] + ")" for row in class_record["excluded"]) or "None"
    inconclusive = ", ".join(row["ticket"] + " (" + row["reason"] + ")" for row in class_record["inconclusive"]) or "None"
    table = ["| Ticket | Lifecycle | Membership | Variant contract | Candidate result | Evaluation | Covered by fence |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for row in matrix["rows"]:
        table.append(f"| {member(row['ticket'])} | {row['lifecycle']} | {row['membership']} | {row['variant_contract']} | {row['candidate']['result']} | {row['evaluation']['disposition']} | {row['covered_by_fence']} |")
    definition = class_record["definition"]
    markdown = "\n".join([f"## Architectural bug class: {definition['id']}", "", definition["statement"], "",
        f"- Governing claim/invariant: `{definition['claim_id']}` / `{definition['invariant_id']}`",
        f"- Triggering ticket: {class_record['trigger_ticket']}", f"- Current members: {included_current}",
        f"- Historical members: {historical}", f"- Excluded: {excluded}", f"- Inconclusive: {inconclusive}",
        f"- Required hard fence: `{definition['required_hard_fence']}`", f"- Exact PR head: `{matrix['pr_head']['revision']}`",
        f"- Exact merge subject: `{matrix['merge_subject']['revision']}`", f"- Outcome: `{verification['outcome']}`", "", *table,
        "", "### Architectural repair", "", f"- Restores claim: `{matrix['repair_design']['restores_claim']}`",
        f"- Closes invariant: `{matrix['repair_design']['closes_invariant']}`",
        f"- Hard-fence contract: `{matrix['repair_design']['hard_fence']['contract']}`",
        f"- Remaining limitations: {', '.join(matrix['repair_design']['limitations']) or 'None declared'}", "",
        "Class-wide remediation applies only to this merge subject/current architecture; it does not rewrite historical Git subjects."])
    receipt = {"schema": "defensefactory/bugclass-pr-section/v1", "pr_url": pr_url, "class_id": definition["id"],
               "matrix_sha256": matrix["receipt_sha256"], "verification_sha256": verification["receipt_sha256"], "markdown": markdown,
               "linked_tickets": sorted(class_record["included_current"] + class_record["included_historical"]),
               "excluded_not_claimed_fixed": [row["ticket"] for row in class_record["excluded"] + class_record["inconclusive"]]}
    receipt["receipt_sha256"] = identity(receipt); return receipt


def linkage_plan(class_record, section, lifecycles):
    included = sorted(class_record["included_current"] + class_record["included_historical"])
    require(set(lifecycles) == set(included) and all(lifecycles.values()) and lifecycles == class_record["member_lifecycles"], "Capture every included ticket lifecycle unchanged before linking")
    operations = [{"effect_key": f"pr:{section['pr_url']}:class:{section['class_id']}", "target": section["pr_url"], "kind": "pr_section", "content_sha256": identity(section["markdown"])}]
    for ticket in included:
        operations.append({"effect_key": f"ticket:{ticket}:pr:{section['pr_url']}", "target": ticket, "kind": "ticket_pr_link", "url": section["pr_url"], "preserve_lifecycle": lifecycles[ticket]})
    receipt = {"schema": "defensefactory/bugclass-linkage-plan/v1", "class_sha256": class_record["receipt_sha256"],
               "section_sha256": section["receipt_sha256"], "operations": operations, "idempotent_effect_keys": True,
               "authority": "Plan only. Use native PR/ticket tools, preserve partial effects, then retrieve both sides."}
    receipt["receipt_sha256"] = identity(receipt); return receipt


def linkage_readback(plan, observation):
    require(plan.get("receipt_sha256") == identity({key: value for key, value in plan.items() if key != "receipt_sha256"}), "Changed linkage plan")
    require(isinstance(observation, dict) and set(observation) == {"pr", "tickets", "completed_effect_keys", "retrieved_at"}, "Linkage readback has unknown/missing fields")
    expected = {row["effect_key"]: row for row in plan["operations"]}; completed = set(observation["completed_effect_keys"])
    require(completed <= set(expected), "Readback includes an unknown effect key")
    pr_operation = next(row for row in plan["operations"] if row["kind"] == "pr_section")
    problems = []
    if observation["pr"].get("url") != pr_operation["target"] or observation["pr"].get("content_sha256") != pr_operation["content_sha256"]: problems.append("PR section missing or changed")
    ticket_views = {row.get("ticket"): row for row in observation["tickets"]}
    for operation in plan["operations"]:
        if operation["kind"] != "ticket_pr_link": continue
        view = ticket_views.get(operation["target"])
        if not view or operation["url"] not in view.get("pr_urls", []): problems.append(operation["target"] + ": PR backlink missing")
        elif view.get("lifecycle") != operation["preserve_lifecycle"]: problems.append(operation["target"] + ": lifecycle changed")
    missing_effects = sorted(set(expected) - completed)
    if missing_effects: problems.append("Unreconciled effects: " + ", ".join(missing_effects))
    receipt = {"schema": "defensefactory/bugclass-linkage-readback/v1", "plan_sha256": plan["receipt_sha256"],
               "result": "satisfied" if not problems else "inconclusive", "problems": problems,
               "completed_effect_keys": sorted(completed), "missing_effect_keys": missing_effects,
               "retrieved_at": observation["retrieved_at"], "resume_without_duplicates": missing_effects}
    receipt["receipt_sha256"] = identity(receipt); return receipt
