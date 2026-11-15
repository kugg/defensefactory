"""Fail-closed reconciliation for batch outcome summaries."""
from __future__ import annotations

import copy

from .core import identity

VALIDATOR = "defensefactory-batch-summary/1"


def _ticket_list(value, path, problems):
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        problems.append(path + " must be a list of nonempty ticket identifiers")
        return []
    duplicates = sorted({item for item in value if value.count(item) > 1})
    if duplicates:
        problems.append(path + " contains duplicate tickets: " + ", ".join(duplicates))
    return value


def _partition(parent_name, parent_tickets, groups, path, problems):
    normalized = {}
    if not isinstance(groups, dict) or not groups:
        problems.append(path + " must contain at least one outcome group")
        return normalized

    assigned = []
    for name, group in groups.items():
        group_path = path + "." + str(name)
        if not isinstance(name, str) or not name:
            problems.append(path + " contains an empty outcome name")
            continue
        if not isinstance(group, dict) or not {"declared_count", "tickets"} <= set(group) or set(group) - {"declared_count", "tickets", "groups"}:
            problems.append(group_path + " has unknown or missing fields")
            continue
        tickets = _ticket_list(group.get("tickets"), group_path + ".tickets", problems)
        declared = group.get("declared_count")
        if isinstance(declared, bool) or not isinstance(declared, int) or declared < 0:
            problems.append(group_path + ".declared_count must be a nonnegative integer")
        elif declared != len(tickets):
            problems.append(f"{group_path} declares {declared} tickets but enumerates {len(tickets)}")
        outside = sorted(set(tickets) - set(parent_tickets))
        if outside:
            problems.append(group_path + " contains tickets outside " + parent_name + ": " + ", ".join(outside))
        assigned.extend(tickets)
        row = {"declared_count": declared, "observed_count": len(tickets), "tickets": copy.deepcopy(tickets)}
        if "groups" in group:
            row["groups"] = _partition(name, tickets, group["groups"], group_path + ".groups", problems)
        normalized[name] = row

    duplicates = sorted({item for item in assigned if assigned.count(item) > 1})
    if duplicates:
        problems.append(path + " assigns tickets to multiple sibling groups: " + ", ".join(duplicates))
    missing = sorted(set(parent_tickets) - set(assigned))
    if missing:
        problems.append(path + " does not classify: " + ", ".join(missing))
    extras = sorted(set(assigned) - set(parent_tickets))
    if extras:
        problems.append(path + " classifies unknown tickets: " + ", ".join(extras))
    return normalized


def reconcile_batch_summary(summary):
    """Return a deterministic receipt; any mismatch produces ``violated``."""
    problems = []
    allowed = {"schema_version", "batch_id", "declared_total", "selected", "groups"}
    if not isinstance(summary, dict) or set(summary) != allowed:
        problems.append("Batch summary has unknown or missing fields")
        summary = summary if isinstance(summary, dict) else {}
    if summary.get("schema_version") != 1:
        problems.append("Unsupported batch-summary schema")
    batch_id = summary.get("batch_id")
    if not isinstance(batch_id, str) or not batch_id:
        problems.append("Batch identity is required")
    selected = _ticket_list(summary.get("selected"), "selected", problems)
    declared_total = summary.get("declared_total")
    if isinstance(declared_total, bool) or not isinstance(declared_total, int) or declared_total < 0:
        problems.append("declared_total must be a nonnegative integer")
    elif declared_total != len(selected):
        problems.append(f"Batch declares {declared_total} selected tickets but enumerates {len(selected)}")
    groups = _partition("selected", selected, summary.get("groups"), "groups", problems)
    result = {
        "record_type": "batch_summary_reconciliation",
        "schema_version": 1,
        "validator": VALIDATOR,
        "batch_id": batch_id,
        "input_sha256": identity(summary),
        "declared_total": declared_total,
        "observed_total": len(selected),
        "groups": groups,
        "problems": problems,
        "result": "satisfied" if not problems else "violated",
        "scope": "Arithmetic and partition consistency only; ticket evidence and dispositions remain independently authoritative.",
        "replay": "batch-summary.py --input SUMMARY.json --output RECEIPT.json",
    }
    return result
