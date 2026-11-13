"""Privacy-preserving qualification of OpenCode JSON events and optional local OTel bytes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


def _events(path):
    result = []
    for number, line in enumerate(Path(path).read_text(errors="replace").splitlines(), 1):
        try: value = json.loads(line)
        except ValueError: continue
        if isinstance(value, dict): result.append((number, value))
    return result


def qualify(event_log, invocation_result, *, otel_log=None):
    """Return counts/locations only; never copy reasoning or command output text."""
    events = _events(event_log); tool_calls = []; errors = []; truncations = []; compactions = []; publications = []
    guarded = []; unguarded = []; mutation_candidates = []
    for number, event in events:
        kind = str(event.get("type", "")); lowered = json.dumps(event, sort_keys=True).lower()
        if kind in ("reasoning", "thinking"): continue
        if "compact" in kind.lower() or "compaction" in lowered: compactions.append(number)
        if kind == "error" or event.get("error"): errors.append({"line": number, "class": "network_dns" if "enotfound" in lowered or "name resolution" in lowered else "context_exhaustion" if "context" in lowered and ("limit" in lowered or "exhaust" in lowered) else "tool_or_model_error"})
        if "truncat" in lowered or "output limit" in lowered: truncations.append(number)
        part = event.get("part", {}); tool = str(part.get("tool") or event.get("tool") or "")
        state = part.get("state", {}) if isinstance(part, dict) else {}
        if tool:
            tool_calls.append({"line": number, "tool": tool, "status": state.get("status", "unknown")})
            name = tool.lower()
            if any(word in name for word in ("linear", "comment", "attachment", "upload")):
                publications.append({"line": number, "tool": tool, "status": state.get("status", "unknown")})
            if name in ("bash", "shell", "exec", "exec_command"):
                inputs = state.get("input", {}) if isinstance(state, dict) else {}
                command = str(inputs.get("command") or inputs.get("cmd") or "")
                if "stage-exec.py" in command or "stage.py stage-command" in command: guarded.append(number)
                else: unguarded.append(number)
            if any(word in name for word in ("write", "edit", "apply_patch", "delete", "merge", "deploy")):
                mutation_candidates.append({"line": number, "tool": tool})
    completed_publications = sum(item["status"] == "completed" for item in publications)
    failed_publications = sum(item["status"] in ("error", "failed") for item in publications)
    result = json.loads(json.dumps(invocation_result))
    otel = {"configured": bool(otel_log), "observed": False}
    if otel_log:
        path = Path(otel_log)
        if path.is_file():
            raw = path.read_bytes(); otel.update(observed=bool(raw), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), path=str(path.resolve()))
        else: otel["error"] = "configured OTel log does not exist"
    process = {
        "ticket_first_ordering": "not_established_by_event_monitor",
        "guarded_command_lines": guarded, "unguarded_command_lines": unguarded,
        "tool_truncation_lines": truncations, "compaction_lines": compactions,
        "errors": errors, "publication_calls": len(publications), "completed_publication_calls": completed_publications,
        "failed_publication_calls": failed_publications,
        "mutation_candidates_requiring_scope_review": mutation_candidates,
        "capture_complete": result.get("whole_attempt_handoff_ready") is True and not unguarded and not truncations,
        "operator_recovery_required": bool(errors or failed_publications),
    }
    technical = {"producer_exit_code": result.get("producer_exit_code"), "runner_exit_code": result.get("runner_exit_code"),
                 "whole_attempt_handoff_ready": result.get("whole_attempt_handoff_ready"),
                 "factory_outcome": "not_inferred_from_process_exit"}
    readiness = "inconclusive"
    if result.get("runner_exit_code") != 0 or errors: readiness = "blocked"
    elif process["capture_complete"] and otel["observed"]: readiness = "ready_for_practice"
    elif result.get("whole_attempt_handoff_ready"): readiness = "practice_only"
    return {"schema": "defensefactory/trial-monitor/v1", "technical_result": technical,
            "process_qualification": process, "installation_readiness": readiness, "telemetry": otel,
            "event_counts": {"parsed": len(events), "tool_calls": len(tool_calls), "reasoning_events": result.get("reasoning_events", 0)},
            "privacy": "Raw thinking and command output are retained locally in the invocation log and are not copied into this report.",
            "limitations": ["Tool-name/event heuristics identify review candidates; they do not prove authorization or causal correctness.",
                            "Ticket-first ordering needs the separately bound stage opening and ticket readback evidence."]}
