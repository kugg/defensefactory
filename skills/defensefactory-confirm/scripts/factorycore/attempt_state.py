"""Deterministic active-attempt checkpoints for bounded stage retries.

The checkpoint replaces only the ticket's current execution pointer. Historical
comments, attachments and lifecycle receipts remain immutable ticket evidence.
"""
import copy
import re

from .core import identity, require


SCHEMA = "defensefactory/active-attempt/v1"
READBACK_SCHEMA = "defensefactory/active-attempt-readback/v1"
CLASSIFICATIONS = {"reusable", "historical", "stale", "refresh_required"}
APPLICABILITY = {"satisfied_within_scope", "requires_reassessment", "unknown"}
STAGES = {"intake", "assess", "repair", "verify", "integrate", "deploy", "confirm", "maintain"}


def _text(value, message):
    require(isinstance(value, str) and value.strip(), message)
    return value


def _sha(value, message):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value), message)
    return value


def _subject(value):
    require(isinstance(value, dict), "Attempt subject must be an object")
    repository = _text(value.get("repository"), "Attempt repository required")
    revision = value.get("revision")
    require(isinstance(revision, str) and re.fullmatch(r"[0-9a-f]{40}", revision),
            "Attempt subject needs a full immutable Git revision")
    subject = copy.deepcopy(value)
    subject["repository"] = repository
    subject["revision"] = revision
    return subject


def prepare_active_attempt(request):
    """Classify predecessor evidence and create one exact active pointer.

    Native references without portable bytes may use ``native_id``. Reusable
    byte resources use ``sha256``. Both remain claims supplied by the caller;
    connector retrieval and byte verification are separate receipts.
    """
    request = copy.deepcopy(request)
    required = ("case", "checkpoint_id", "attempt", "stage", "subject", "reason",
                "finding_status", "inputs", "minimal_dependency_ids",
                "required_input_kinds", "applicability", "authorization_reference",
                "boundaries", "next_action", "owner")
    require(all(key in request for key in required), "Incomplete active-attempt request")
    require(re.fullmatch(r"[A-Z][A-Z0-9]*-[1-9][0-9]*", request["case"] or ""),
            "Invalid ticket identifier")
    for key in ("checkpoint_id", "attempt", "reason", "finding_status",
                "authorization_reference", "boundaries", "next_action", "owner"):
        _text(request[key], key + " must be a nonempty string")
    require(re.fullmatch(r"[A-Za-z0-9._:-]+", request["checkpoint_id"]),
            "Invalid active checkpoint identifier")
    require(re.fullmatch(r"[A-Za-z0-9._:-]+", request["attempt"]),
            "Invalid attempt identifier")
    require(request["stage"] in STAGES, "Unknown active stage")
    subject = _subject(request["subject"])

    inputs = request["inputs"]
    require(isinstance(inputs, list) and inputs, "Active attempt needs classified ticket inputs")
    ids = []
    normalized = []
    for supplied in inputs:
        require(isinstance(supplied, dict), "Attempt input must be an object")
        item = copy.deepcopy(supplied)
        for key in ("id", "kind", "classification", "reference", "rationale"):
            _text(item.get(key), "Attempt input " + key + " required")
        require(re.fullmatch(r"[A-Za-z0-9._:-]+", item["id"]), "Invalid attempt input identifier")
        require(item["classification"] in CLASSIFICATIONS, "Unknown attempt input classification")
        require(bool(item.get("sha256")) != bool(item.get("native_id")),
                "Attempt input needs exactly one portable SHA-256 or stable native identity")
        if item.get("sha256"):
            _sha(item["sha256"], "Attempt input SHA-256 invalid")
            item["binding"] = {"sha256": item.pop("sha256")}
        else:
            item["binding"] = {"native_id": _text(item.pop("native_id"), "Native identity required")}
        triggers = item.get("invalidation_triggers", [])
        require(isinstance(triggers, list) and all(isinstance(value, str) and value for value in triggers),
                "Invalidation triggers must be nonempty strings")
        item["invalidation_triggers"] = triggers
        if item.get("subject") is not None:
            item["subject"] = _subject(item["subject"])
        ids.append(item["id"]); normalized.append(item)
    require(len(ids) == len(set(ids)), "Duplicate attempt input identifier")

    minimal = request["minimal_dependency_ids"]
    require(isinstance(minimal, list) and len(minimal) == len(set(minimal)),
            "Minimal dependency IDs must be a unique array")
    by_id = {item["id"]: item for item in normalized}
    require(set(minimal) == {item["id"] for item in normalized if item["classification"] == "reusable"},
            "Minimal dependency closure must contain exactly the reusable inputs")
    require(all(item in by_id for item in minimal), "Minimal dependency references an unknown input")
    kinds = request["required_input_kinds"]
    require(isinstance(kinds, list) and len(kinds) == len(set(kinds)) and
            all(isinstance(value, str) and value for value in kinds),
            "Required input kinds must be unique nonempty strings")
    reusable_kinds = {by_id[item]["kind"] for item in minimal}
    missing_kinds = sorted(set(kinds) - reusable_kinds)

    applicability = copy.deepcopy(request["applicability"])
    require(isinstance(applicability, dict) and applicability.get("result") in APPLICABILITY,
            "Applicability needs a supported result")
    _text(applicability.get("reference"), "Applicability evidence reference required")
    _sha(applicability.get("sha256"), "Applicability evidence SHA-256 invalid")
    limitations = applicability.get("limitations", [])
    require(isinstance(limitations, list) and all(isinstance(value, str) and value for value in limitations),
            "Applicability limitations must be nonempty strings")
    applicability["limitations"] = limitations

    blockers = []
    if missing_kinds:
        blockers.append("Missing reusable input kinds: " + ", ".join(missing_kinds))
    refresh = [item["id"] for item in normalized if item["classification"] == "refresh_required"]
    if refresh:
        blockers.append("Inputs require refresh before stage execution: " + ", ".join(sorted(refresh)))
    if applicability["result"] != "satisfied_within_scope":
        blockers.append("Current-source applicability is " + applicability["result"])

    checkpoint = {
        "schema": SCHEMA,
        "case": request["case"],
        "checkpoint_id": request["checkpoint_id"],
        "previous_checkpoint": request.get("previous_checkpoint"),
        "attempt": request["attempt"],
        "stage": request["stage"],
        "subject": subject,
        "reason": request["reason"],
        "finding_status": request["finding_status"],
        "inputs": normalized,
        "minimal_dependency_ids": minimal,
        "required_input_kinds": kinds,
        "applicability": applicability,
        "authorization_reference": request["authorization_reference"],
        "boundaries": request["boundaries"],
        "next_action": request["next_action"],
        "owner": request["owner"],
        "result": "ready" if not blockers else "hold",
        "execution_permitted": not blockers,
        "blockers": blockers,
        "historical_evidence_preserved": True,
        "semantics": "Replaces only the active execution pointer; it does not delete, rewrite, accept or invalidate historical ticket evidence by itself.",
    }
    checkpoint["checkpoint_sha256"] = identity(checkpoint)
    return checkpoint


def validate_scope(checkpoint, readback, scope):
    """Bind a bounded retry opening to a published/read-back active pointer."""
    require(checkpoint.get("schema") == SCHEMA, "Active attempt checkpoint schema mismatch")
    digest = checkpoint.get("checkpoint_sha256")
    require(digest == identity({key: value for key, value in checkpoint.items()
                                if key != "checkpoint_sha256"}), "Active attempt checkpoint digest mismatch")
    require(readback.get("schema") == READBACK_SCHEMA and
            readback.get("publication") == "observed_in_connector_readback",
            "Active attempt connector readback required")
    require(readback.get("case") == checkpoint["case"] and
            readback.get("checkpoint_id") == checkpoint["checkpoint_id"] and
            readback.get("checkpoint_sha256") == digest,
            "Active attempt readback identifies another checkpoint")
    for key in ("case", "attempt", "stage", "subject"):
        require(scope.get(key) == checkpoint.get(key), "Stage scope differs from active attempt: " + key)
    require(checkpoint.get("execution_permitted") is True and checkpoint.get("result") == "ready",
            "Active attempt is on hold: " + "; ".join(checkpoint.get("blockers", [])))
    return {
        "schema": "defensefactory/active-attempt-scope-binding/v1",
        "case": checkpoint["case"],
        "attempt": checkpoint["attempt"],
        "stage": checkpoint["stage"],
        "subject": checkpoint["subject"],
        "checkpoint_id": checkpoint["checkpoint_id"],
        "checkpoint_sha256": digest,
        "readback_sha256": identity(readback),
        "minimal_dependency_ids": checkpoint["minimal_dependency_ids"],
        "result": "satisfied_within_scope",
    }
