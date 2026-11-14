"""Portable workflow gates whose durable state is carried by ticket receipts."""
import copy
import datetime
import re

from .core import GateError, identity, require


def _timestamp(value, label):
    require(isinstance(value, str) and value, label + " timestamp required")
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise GateError(label + " timestamp must be ISO-8601") from error
    require(parsed.tzinfo is not None, label + " timestamp requires a timezone")
    return parsed


def _shareable(reference, label):
    require(isinstance(reference, str) and reference and not reference.startswith("file://"),
            label + " must be a durable ticket/repository reference")


def _subject(subject):
    require(isinstance(subject, dict) and subject.get("repository") and
            re.fullmatch(r"[0-9a-f]{40}", subject.get("revision", "")),
            "Exact repository and full Git revision required")
    return copy.deepcopy(subject)


def decision_request(spec):
    """Create the canonical open decision artifact; prose alone is not a gate."""
    require(isinstance(spec, dict), "Decision request object required")
    required = ("id", "question", "blocking_stage", "requested_by", "created_at",
                "scope_reference", "subject", "options")
    require(all(spec.get(key) for key in required), "Decision request fields missing")
    require(spec["blocking_stage"] in
            ("assessment", "repair", "verification", "integration", "deployment", "closure"),
            "Unknown blocking stage")
    _timestamp(spec["created_at"], "Decision request")
    _shareable(spec["scope_reference"], "Decision scope reference")
    options = spec["options"]
    require(isinstance(options, list) and len(options) >= 2, "At least two decision options required")
    require(len({item.get("id") for item in options}) == len(options), "Decision option IDs must be unique")
    for item in options:
        require(set(item) == {"id", "consequence"} and item["id"] and item["consequence"],
                "Each decision option needs only id and consequence")
    body = {"record_type": "decision_request", "schema_version": 1, "state": "open",
            **copy.deepcopy(spec), "result": "recorded",
            "next_action": "Record one owner choice in a decision receipt, then re-evaluate this gate.",
            "limitation": "Tracks an explicit owner decision; it does not decide policy or authenticate the named owner."}
    body["decision_request_sha256"] = identity(body)
    return body


def record_decision(request, selection, decider, decided_at, reference, scope):
    """Bind one selected option to the immutable request and owner reference."""
    verify_decision_request(request)
    require(selection in {item["id"] for item in request["options"]}, "Selected option is not offered")
    require(decider and scope, "Decision needs decider and explicit scope")
    _timestamp(decided_at, "Decision")
    require(_timestamp(decided_at, "Decision") >= _timestamp(request["created_at"], "Decision request"),
            "Decision predates its request")
    _shareable(reference, "Decision reference")
    body = {"record_type": "recorded_decision", "schema_version": 1,
            "decision_id": request["id"], "decision_request_sha256": request["decision_request_sha256"],
            "selected_option": selection, "consequence": next(item["consequence"] for item in request["options"] if item["id"] == selection),
            "decider": decider, "decided_at": decided_at, "reference": reference,
            "scope": scope, "blocking_stage": request["blocking_stage"], "subject": request["subject"],
            "result": "recorded",
            "limitation": "The caller supplies owner identity and authority; this receipt preserves the stated decision without authenticating it."}
    body["decision_receipt_sha256"] = identity(body)
    return body


def verify_decision_request(request):
    require(isinstance(request, dict) and request.get("record_type") == "decision_request",
            "Structured decision request required")
    require(request.get('state')=='open' and request.get('id') and request.get('blocking_stage')
            and request.get('subject') and isinstance(request.get('options'),list) and len(request['options'])>=2,
            'Decision request shape is incomplete')
    digest = request.get("decision_request_sha256")
    require(digest == identity({key: value for key, value in request.items() if key != "decision_request_sha256"}),
            "Decision request changed")
    return request


def decision_gate(request, decision=None):
    verify_decision_request(request)
    if decision is None:
        body={"record_type": "decision_gate", "schema_version": 1, "decision_id": request["id"],
                "blocking_stage": request["blocking_stage"], "subject": request["subject"],
                "state": "open", "result": "blocked", "resume_permitted": False,
                "decision_request_sha256": request["decision_request_sha256"],
                "next_action": "Obtain and record one explicit owner decision."}
        body['decision_gate_sha256']=identity(body);return body
    require(decision.get("record_type") == "recorded_decision" and
            decision.get("decision_request_sha256") == request["decision_request_sha256"] and
            decision.get("decision_id") == request["id"], "Decision does not resolve this request")
    require(decision.get("decision_receipt_sha256") ==
            identity({key: value for key, value in decision.items() if key != "decision_receipt_sha256"}),
            "Decision receipt changed")
    require(decision.get('selected_option') in {item['id'] for item in request['options']} and
            decision.get('blocking_stage')==request['blocking_stage'] and decision.get('subject')==request['subject'],
            'Decision receipt content differs from its request')
    _timestamp(decision.get('decided_at'),'Decision');_shareable(decision.get('reference'),'Decision reference')
    body={"record_type": "decision_gate", "schema_version": 1, "decision_id": request["id"],
            "blocking_stage": request["blocking_stage"], "subject": request["subject"],
            "state": "decided", "result": "resume", "resume_permitted": True,
            "decision_request_sha256": request["decision_request_sha256"],
            "decision_receipt_sha256": decision["decision_receipt_sha256"],
            "selected_option": decision["selected_option"], "decision_reference": decision["reference"]}
    body['decision_gate_sha256']=identity(body);return body


def issue_eligibility(assessment, subject, counterexample, contract, authorized_scope, decision_gates=()):
    """Issue the append-only assessment result that admits repair construction."""
    subject = _subject(subject)
    require(assessment.get("stage") == "assess" and assessment.get("result") == "satisfied_within_scope"
            and assessment.get("disposition") == "continue", "Active satisfied assessment required")
    matches = [row for row in assessment.get("target_decisions", [])
               if row.get("reason") == "active" and row.get("subject") == subject]
    require(matches, "Assessment does not mark the exact repair subject active")
    require(counterexample.get("id") and counterexample.get("result") == "reproduced",
            "A reproduced counterexample is required")
    evidence = counterexample.get("evidence", [])
    require(isinstance(evidence, list) and evidence, "Counterexample evidence required")
    for reference in evidence:
        _shareable(reference, "Counterexample evidence")
    require(contract.get("id") and contract.get("version") and contract.get("reference") and
            re.fullmatch(r"[0-9a-f]{64}", contract.get("requirements_sha256", "")),
            "Applicable versioned contract and requirements digest required")
    _shareable(contract["reference"], "Contract reference")
    require(authorized_scope.get("authorized_by") and authorized_scope.get("reference") and
            "repair" in authorized_scope.get("operations", []), "Repair authorization and scope required")
    _shareable(authorized_scope["reference"], "Authorization reference")
    blockers = {item.get("id") for item in assessment.get("repair_contract_blockers", [])}
    gates = {item.get("decision_id"): item for item in decision_gates}
    require(len(gates)==len(decision_gates),'Duplicate decision gate identity')
    require(blockers == gates.keys(), "Decision gates must exactly cover every repair blocker")
    require(all(gates[key].get("resume_permitted") is True and gates[key].get("blocking_stage") == "repair"
                and gates[key].get('decision_gate_sha256')==
                    identity({k:v for k,v in gates[key].items() if k!='decision_gate_sha256'})
                for key in blockers), "An open/stale decision still blocks repair")
    body = {"record_type": "assess_eligibility", "schema_version": 1, "result": "eligible",
            "repair_permitted": True, "subject": subject, "subject_sha256": identity(subject),
            "assessment_sha256": identity(assessment), "counterexample": copy.deepcopy(counterexample),
            "counterexample_sha256": identity(counterexample), "contract": copy.deepcopy(contract),
            "authorized_scope": copy.deepcopy(authorized_scope),
            "decision_gates": copy.deepcopy(list(decision_gates)),
            "limitation": "Admission correspondence only; repair and later verification remain separate stages."}
    body["eligibility_sha256"] = identity(body)
    return body


def verify_eligibility(receipt, current_subject, contract_version=None, scope_reference=None):
    require(receipt.get("record_type") == "assess_eligibility" and receipt.get("result") == "eligible"
            and receipt.get("repair_permitted") is True, "Eligible assessment receipt required")
    require(receipt.get("eligibility_sha256") ==
            identity({key: value for key, value in receipt.items() if key != "eligibility_sha256"}),
            "Eligibility receipt changed")
    subject = _subject(current_subject)
    require(receipt.get("subject") == subject and receipt.get("subject_sha256") == identity(subject),
            "Eligibility is stale for the current repair subject")
    if contract_version is not None:
        require(receipt.get("contract", {}).get("version") == contract_version,
                "Eligibility is stale for the applicable contract version")
    if scope_reference is not None:
        require(receipt.get("authorized_scope", {}).get("reference") == scope_reference,
                "Eligibility is bound to a different authorized scope")
    return receipt


def repair_admission(receipt, current_subject, contract_version=None, scope_reference=None):
    """Return a preserved refusal instead of allowing a missing/stale receipt to be ignored."""
    try:
        require(isinstance(receipt, dict), "Assess-eligibility receipt missing")
        verified = verify_eligibility(receipt, current_subject, contract_version, scope_reference)
        return {"record_type": "repair_admission", "schema_version": 1,
                "result": "satisfied_within_scope", "repair_permitted": True,
                "subject": copy.deepcopy(current_subject), "eligibility_sha256": verified["eligibility_sha256"],
                "next_action": "Begin only the bounded repair authorized by the receipt."}
    except (GateError, KeyError, TypeError) as error:
        return {"record_type": "repair_admission", "schema_version": 1,
                "result": "blocked", "repair_permitted": False,
                "subject": copy.deepcopy(current_subject), "problems": [str(error)],
                "next_action": "Return to assessment and publish a current exact-subject eligibility receipt."}


def stalled_findings(findings):
    """Find intake-only tickets unless a current explicit park receipt explains the stop."""
    require(isinstance(findings, list), "Finding inventory must be an array")
    rows = []
    for finding in findings:
        require(finding.get("id") and finding.get("subject"), "Finding ID and subject required")
        receipts = finding.get("receipts", [])
        intake = [item for item in receipts if item.get("record_type") == "intake_receipt"
                  and item.get("subject") == finding["subject"]]
        assessed = [item for item in receipts if item.get("record_type") in
                    ("assessment_receipt", "assess_eligibility") and item.get("subject") == finding["subject"]]
        park = finding.get("park_receipt")
        parked = False
        if park is not None:
            require(park.get("record_type") == "finding_park" and park.get("finding") == finding["id"]
                    and park.get("subject") == finding["subject"] and park.get("reason")
                    and park.get("decided_by") and park.get("reference") and park.get("parked_at"),
                    "Park receipt is incomplete or belongs to a different finding/subject")
            _timestamp(park["parked_at"], "Park")
            _shareable(park["reference"], "Park reference")
            parked = True
        if intake and not assessed and not parked:
            rows.append({"finding": finding["id"], "subject": copy.deepcopy(finding["subject"]),
                         "state": "stalled_after_intake", "required_stage": "assess",
                         "next_action": "Run assessment against this exact subject and publish its receipt.",
                         "intake_references": [item.get("reference") for item in intake]})
    return {"record_type": "stalled_findings_report", "schema_version": 1,
            "result": "attention_required" if rows else "clear", "stalled": rows,
            "count": len(rows),
            "limitation": "Evaluates the supplied ticket inventory; it does not discover tickets or infer hidden operator intent."}
