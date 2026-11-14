"""Shared, deterministic protocol validation for the alpha container harness."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any


STAGES = ("intake", "assess", "repair", "verify", "integrate", "deploy", "confirm", "maintain")
PROFILE_SCHEMA = "defensefactory/alpha-capability-profiles/v1"
TICKET_SCHEMA = "defensefactory/alpha-ticket/v1"
RECEIPT_SCHEMA = "defensefactory/alpha-stage-receipt/v1"
EVIDENCE_SCHEMA = "defensefactory/alpha-stage-evidence/v1"
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class ProtocolError(ValueError):
    """The durable handoff contract is missing, stale, or malformed."""


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identity(value: Any) -> str:
    return sha256(canonical(value))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProtocolError(message)


def safe_identifier(value: str, label: str = "identifier") -> str:
    require(isinstance(value, str) and IDENTIFIER.fullmatch(value) is not None,
            f"Unsafe {label}")
    return value


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ProtocolError(f"Cannot read JSON from {path}: {error}") from error
    require(isinstance(value, dict), f"{path} must contain a JSON object")
    return value


def validate_profiles(value: dict) -> dict:
    require(value.get("schema") == PROFILE_SCHEMA, "Unsupported capability-profile schema")
    profiles = value.get("stages")
    require(isinstance(profiles, dict) and set(profiles) == set(STAGES),
            "Capability profiles must cover exactly the eight stages")
    for stage in STAGES:
        profile = profiles[stage]
        require(isinstance(profile, dict), f"{stage} capability profile must be an object")
        require(profile.get("skill") == f"defensefactory-{stage}",
                f"{stage} profile names the wrong skill")
        allowed = profile.get("allow")
        denied = profile.get("deny")
        require(isinstance(allowed, list) and allowed == sorted(set(allowed)) and allowed,
                f"{stage} allow list must be nonempty, unique, and sorted")
        require(isinstance(denied, list) and denied == sorted(set(denied)),
                f"{stage} deny list must be unique and sorted")
        require(not set(allowed) & set(denied), f"{stage} capability is both allowed and denied")
        require({"ticket_read", "ticket_write"} <= set(allowed),
                f"{stage} must read and publish durable ticket state")
        require(profile.get("workspace") == "ephemeral",
                f"{stage} workspace must be ephemeral")
        require(profile.get("session") == "fresh", f"{stage} session must be fresh")
    return value


def validate_ticket(value: dict) -> dict:
    require(value.get("schema") == TICKET_SCHEMA, "Unsupported alpha ticket schema")
    safe_identifier(value.get("case", ""), "case")
    safe_identifier(value.get("attempt", ""), "attempt")
    subject = value.get("subject")
    require(isinstance(subject, dict) and subject.get("repository") and
            HEX40.fullmatch(str(subject.get("revision", ""))) is not None,
            "Ticket must bind an exact Git subject")
    release = value.get("release")
    require(isinstance(release, dict), "Ticket release binding missing")
    require(HEX40.fullmatch(str(release.get("git_commit", ""))) is not None,
            "Release Git commit must be exact")
    require(re.fullmatch(r"sha256:[0-9a-f]{64}", str(release.get("image_digest", ""))) is not None,
            "Release image digest must be exact")
    require(HEX64.fullmatch(str(release.get("capability_profiles_sha256", ""))) is not None,
            "Capability-profile digest missing")
    require(value.get("scenario") in ("active", "early_disposition", "local_lifecycle"),
            "Unknown alpha scenario")
    required = value.get("authorized_stages")
    require(isinstance(required, list) and required and all(stage in STAGES for stage in required),
            "Authorized stage list missing or invalid")
    require(required == list(STAGES[:len(required)]), "Authorized stages must be a pipeline prefix")
    return value


def receipt_identity(receipt: dict) -> str:
    return identity({key: value for key, value in receipt.items() if key != "receipt_sha256"})


def validate_receipt(receipt: dict, ticket: dict, expected_stage: str,
                     previous_sha256: str | None) -> dict:
    require(receipt.get("schema") == RECEIPT_SCHEMA, "Unsupported stage receipt schema")
    require(receipt.get("case") == ticket["case"] and receipt.get("attempt") == ticket["attempt"],
            "Receipt names another case or attempt")
    require(receipt.get("stage") == expected_stage, "Receipt names another stage")
    require(receipt.get("subject") == ticket["subject"], "Receipt exact subject changed")
    require(receipt.get("release") == ticket["release"], "Receipt release binding changed")
    require(receipt.get("ticket_sha256") == identity(ticket), "Receipt ticket snapshot changed")
    require(receipt.get("previous_receipt_sha256") == previous_sha256,
            "Receipt does not extend the durable stage chain")
    output = receipt.get("output_attachment")
    require(isinstance(output, dict) and HEX64.fullmatch(str(output.get("sha256", ""))) is not None
            and isinstance(output.get("bytes"), int) and output["bytes"] > 0,
            "Receipt output attachment binding missing")
    require(receipt.get("result") in
            ("satisfied_within_scope", "premise_disputed", "inconclusive", "violated", "failed"),
            "Unsupported receipt result")
    require(receipt.get("qualification"), "Receipt qualification missing")
    if "receipt_sha256" in receipt:
        require(receipt["receipt_sha256"] == receipt_identity(receipt), "Receipt bytes changed")
    return receipt
