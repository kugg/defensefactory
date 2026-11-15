"""Plan and verify native ticket lifecycle state for assessment dispositions."""
from __future__ import annotations

from datetime import datetime
import re

from .core import identity, require


VALIDATOR = "defensefactory-disposition-lifecycle/1"
DISPOSITIONS = {
    "active": {"lifecycle_class": "in_progress", "terminal": False},
    "owner_decision": {"lifecycle_class": "backlog", "terminal": False},
    "inconclusive": {"lifecycle_class": "backlog", "terminal": False},
    "already_fixed": {"lifecycle_class": "complete", "terminal": True},
    "accepted_risk": {"lifecycle_class": "canceled", "terminal": True},
    "false_positive": {"lifecycle_class": "canceled", "terminal": True},
    "invalid_report": {"lifecycle_class": "canceled", "terminal": True},
}
ALIASES = {
    "rejected_false_positive": "false_positive",
    "invalid": "invalid_report",
    "test_only": "invalid_report",
    "hold_owner_decision": "owner_decision",
}


def _timestamp(value, name):
    require(isinstance(value, str) and value, name + " timestamp required")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(name + " timestamp must be ISO-8601") from error


def _canonical_disposition(value):
    value = ALIASES.get(value, value)
    require(value in DISPOSITIONS, "Unsupported assessment disposition")
    return value


def _policy(policy):
    require(isinstance(policy, dict) and set(policy) == {"schema_version", "id", "statuses", "labels"},
            "Lifecycle policy has unknown or missing fields")
    require(policy["schema_version"] == 1 and isinstance(policy["id"], str) and policy["id"],
            "Lifecycle policy identity required")
    require(set(policy["statuses"]) == {"complete", "canceled", "backlog", "in_progress"},
            "Lifecycle policy must map every semantic state class")
    require(set(policy["labels"]) == set(DISPOSITIONS),
            "Lifecycle policy must map every canonical disposition")
    require(all(isinstance(value, str) and value for value in policy["statuses"].values()),
            "Native status names must be nonempty")
    require(all(isinstance(value, str) and value for value in policy["labels"].values()),
            "Native disposition labels must be nonempty")
    require(len(set(policy["labels"].values())) == len(policy["labels"]),
            "Disposition labels must be distinct")
    return policy


def plan_lifecycle_transition(ticket, assessment, policy, authorization, planned_at):
    """Create a portable plan; this function never calls or mutates a ticket service."""
    require(isinstance(ticket, dict) and set(ticket) == {"identifier", "updated_at", "status", "labels"},
            "Ticket snapshot has unknown or missing fields")
    require(isinstance(ticket["identifier"], str) and ticket["identifier"] and
            isinstance(ticket["status"], str) and ticket["status"] and
            isinstance(ticket["labels"], list) and
            all(isinstance(label, str) and label for label in ticket["labels"]),
            "Ticket snapshot identity, status and labels required")
    _timestamp(ticket["updated_at"], "Ticket update")
    _timestamp(planned_at, "Plan")
    require(isinstance(assessment, dict) and set(assessment) == {
        "disposition", "receipt_reference", "receipt_sha256"},
        "Assessment binding has unknown or missing fields")
    disposition = _canonical_disposition(assessment["disposition"])
    require(isinstance(assessment["receipt_reference"], str) and assessment["receipt_reference"] and
            not assessment["receipt_reference"].startswith("file://"),
            "Assessment receipt needs a shareable reference")
    require(re.fullmatch(r"[a-f0-9]{64}", assessment["receipt_sha256"] or "") is not None,
            "Assessment receipt SHA-256 required")
    policy = _policy(policy)
    require(isinstance(authorization, dict) and set(authorization) == {"authorized", "reference"}
            and isinstance(authorization["authorized"], bool),
            "Explicit lifecycle authorization required")
    if authorization["authorized"]:
        require(isinstance(authorization["reference"], str) and authorization["reference"] and
                not authorization["reference"].startswith("file://"),
                "Authorized mutation needs a shareable authority reference")
    else:
        require(authorization["reference"] is None, "Unauthorized plans cannot cite mutation authority")

    semantics = DISPOSITIONS[disposition]
    desired = {
        "status": policy["statuses"][semantics["lifecycle_class"]],
        "disposition_label": policy["labels"][disposition],
    }
    already_matches = (ticket["status"] == desired["status"] and
                       desired["disposition_label"] in ticket["labels"] and
                       not (set(ticket["labels"]) & (set(policy["labels"].values()) - {desired["disposition_label"]})))
    permitted = authorization["authorized"]
    result = {
        "record_type": "disposition_lifecycle_plan",
        "schema_version": 1,
        "validator": VALIDATOR,
        "ticket": ticket["identifier"],
        "ticket_snapshot_sha256": identity(ticket),
        "ticket_updated_at": ticket["updated_at"],
        "assessment": dict(assessment),
        "disposition": disposition,
        "lifecycle_class": semantics["lifecycle_class"],
        "terminal": semantics["terminal"],
        "desired": desired,
        "configured_disposition_labels": sorted(policy["labels"].values()),
        "policy_id": policy["id"],
        "policy_sha256": identity(policy),
        "planned_at": planned_at,
        "authorization_reference": authorization["reference"],
        "mutation_permitted": permitted,
        "operation": "verify_existing" if already_matches else "apply_native_transition",
        "result": "ready" if permitted else "pending",
        "next_action": ("Use the native ticket connector, then fetch and verify the resulting status and disposition label."
                        if permitted else
                        "Publish the pending transition plan; obtain native lifecycle authority without changing the assessment result."),
        "scope": "Maps an evidence-bound factory disposition to configured native state; it does not call the ticket service.",
    }
    return result


def verify_lifecycle_readback(plan, observed):
    """Verify a fresh normalized connector readback against an authorized plan."""
    problems = []
    if not isinstance(plan, dict) or plan.get("record_type") != "disposition_lifecycle_plan" or plan.get("validator") != VALIDATOR:
        problems.append("Input is not a disposition lifecycle plan from this validator")
        plan = plan if isinstance(plan, dict) else {}
    if plan.get("result") != "ready" or plan.get("mutation_permitted") is not True:
        problems.append("Lifecycle plan is not authorized and ready")
    required = {"identifier", "updated_at", "status", "labels", "operation", "retrieved_at"}
    if not isinstance(observed, dict) or set(observed) != required:
        problems.append("Readback has unknown or missing fields")
        observed = observed if isinstance(observed, dict) else {}
    if observed.get("operation") != "retrieval":
        problems.append("Observed ticket state is not marked as a connector retrieval")
    if observed.get("identifier") != plan.get("ticket"):
        problems.append("Readback ticket differs from planned ticket")
    desired = plan.get("desired", {})
    if observed.get("status") != desired.get("status"):
        problems.append("Native status differs from the planned disposition")
    labels = observed.get("labels")
    if not isinstance(labels, list) or not all(isinstance(label, str) and label for label in labels):
        problems.append("Readback labels must be a list of nonempty names")
        labels = []
    if desired.get("disposition_label") not in labels:
        problems.append("Planned disposition label is missing")
    stale = sorted((set(labels) & set(plan.get("configured_disposition_labels", []))) -
                   {desired.get("disposition_label")})
    if stale:
        problems.append("Conflicting disposition labels remain: " + ", ".join(stale))
    try:
        if _timestamp(observed.get("retrieved_at"), "Readback") < _timestamp(plan.get("planned_at"), "Plan"):
            problems.append("Readback predates the transition plan")
        _timestamp(observed.get("updated_at"), "Observed ticket update")
    except (ValueError, TypeError) as error:
        problems.append(str(error))
    return {
        "record_type": "disposition_lifecycle_readback",
        "schema_version": 1,
        "validator": VALIDATOR,
        "ticket": plan.get("ticket"),
        "plan_sha256": identity(plan),
        "observed_sha256": identity(observed),
        "desired": desired,
        "observed": {key: observed.get(key) for key in ("status", "labels", "updated_at", "retrieved_at")},
        "problems": problems,
        "result": "satisfied" if not problems else "violated",
        "disposition_visible": not problems,
        "terminal": plan.get("terminal") if not problems else False,
        "next_action": ("Stop the assessment stage." if not problems and plan.get("terminal") else
                        "Continue only from the explicitly recorded nonterminal disposition." if not problems else
                        "Preserve the mismatch, reconcile remote state and do not claim the lifecycle transition."),
        "scope": "Exact native status/label and fresh-readback correspondence only; assessment evidence remains independently authoritative.",
    }
