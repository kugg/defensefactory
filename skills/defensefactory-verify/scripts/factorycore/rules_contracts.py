"""Canonical Markdown claim rules and bounded invariant-contract execution.

RULES.md is authored policy.  Everything computed by this module is a receipt.
The parser intentionally implements a small versioned Markdown AST rather than
trying to infer normative meaning from arbitrary prose.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import tempfile
import time

from .core import GateError, identity, require, sha
from .registry import source_blob
from .verification import command, git


GRAMMAR = "defensefactory/rules/v1"
PARSER = "factory-markdown-ast/1"
CONTRACT_SCHEMA = "defensefactory/contract/v1"
CANDIDATE_SCHEMA = "defensefactory/candidate/v1"
EVALUATION_SCHEMA = "defensefactory/evaluation/v1"
RUN_SCHEMA = "defensefactory/contract-run/v1"
STATUS_SCHEMA = "defensefactory/claim-status/v1"

ENGINES = {"cue", "codeql", "semgrep", "opengrep", "test", "type", "lint", "ast", "runtime", "formal", "markdown-example"}
DISPOSITIONS = {"confirmed_violation", "rejected_false_positive", "inconclusive", "duplicate", "not_applicable"}
SECTION_NAMES = ("Boundaries", "Invalidated by", "Contracts", "Preserves", "Enforcement")
ENFORCEMENT_KEYS = ("Confirmed violation", "Candidate awaiting evaluation", "Missing mandatory coverage")
ID_PATTERN = re.compile(r"[A-Z][A-Z0-9._-]{1,127}\Z")
COMPONENT_PATTERN = re.compile(r"[a-z0-9][a-z0-9._/-]{0,127}\Z")
COMMIT_PATTERN = re.compile(r"[a-f0-9]{40}\Z")


def _safe_path(value: str) -> PurePosixPath:
    require(isinstance(value, str) and value and "\\" not in value, "Nonempty POSIX path required")
    path = PurePosixPath(value)
    require(not path.is_absolute() and ".." not in path.parts and str(path) == value, "Unsafe component-relative path")
    return path


def _id(value: str, kind: str = "identity") -> str:
    require(isinstance(value, str) and ID_PATTERN.fullmatch(value) is not None,
            f"{kind} must use unambiguous uppercase ASCII identity syntax")
    return value


def _backtick(value: str, kind: str) -> str:
    require(value.startswith("`") and value.endswith("`") and value.count("`") == 2,
            f"{kind} must be a single backtick-delimited value")
    return value[1:-1]


def _claim_heading(line: str) -> str | None:
    prefix = "## Claim `"
    if not line.startswith(prefix) or not line.endswith("`"):
        return None
    return _id(line[len(prefix):-1], "claim ID")


def _section_heading(line: str) -> str | None:
    if not line.startswith("### "):
        return None
    value = line[4:]
    require(value in SECTION_NAMES, "Unknown normative claim heading: " + value)
    return value


def _split_bullet(raw: str, kind: str) -> tuple[str, str]:
    require(raw.startswith("- `"), f"{kind} must start with a backtick-delimited ID")
    close = raw.find("`", 3)
    require(close > 3 and raw[close + 1:close + 3] == ": ", f"{kind} needs `ID`: value syntax")
    return _id(raw[3:close], kind + " ID"), raw[close + 3:]


def parse_rules(raw: bytes | str) -> dict:
    """Parse the deliberately small RULES.md grammar into a normalized model."""
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise GateError("RULES.md must be UTF-8: " + str(error))
    require(isinstance(raw, str) and "\x00" not in raw, "RULES.md text required")
    lines = raw.splitlines()
    require(lines and lines[0].startswith("# ") and not lines[0].startswith("## "), "RULES.md needs one level-one title")

    metadata = {}
    preamble = []
    claims = []
    current = None
    section = None
    in_fence = False
    in_comment = False

    for number, line in enumerate(lines[1:], 2):
        stripped = line.strip()
        if "<!--" in stripped:
            in_comment = True
        if in_comment:
            if any(marker in stripped for marker in ("## Claim", "Component:", "Grammar:", "### Contracts")):
                raise GateError(f"Hidden normative content in HTML comment at line {number}")
            if "-->" in stripped:
                in_comment = False
            continue
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            if any(marker in stripped for marker in ("## Claim", "Component:", "Grammar:", "### Contracts")):
                raise GateError(f"Hidden normative content in code fence at line {number}")
            continue

        claim_id = _claim_heading(stripped)
        if claim_id is not None:
            if current is not None:
                _finish_claim(current, claims)
            current = {"id": claim_id, "statement_lines": [], "sections": {}}
            section = None
            continue
        if stripped.startswith("## ") and claims or (current is not None and stripped.startswith("## ")):
            raise GateError(f"Unknown normative level-two heading at line {number}: {stripped[3:]}")

        if current is None:
            matched = False
            for key in ("Grammar", "Component", "Type", "Owners"):
                prefix = key + ": "
                if stripped.startswith(prefix):
                    require(key not in metadata, f"Duplicate {key} metadata")
                    metadata[key] = stripped[len(prefix):]
                    matched = True
                    break
            if not matched:
                preamble.append(line)
            continue

        if stripped.startswith("### "):
            section = _section_heading(stripped)
            require(section not in current["sections"], "Duplicate claim section: " + section)
            current["sections"][section] = []
            continue
        if not stripped:
            continue
        if section is None:
            require(not stripped.startswith("#"), f"Unexpected heading at line {number}")
            current["statement_lines"].append(stripped)
        else:
            require(stripped.startswith("- "), f"Section {section} accepts list items only (line {number})")
            current["sections"][section].append(stripped)

    require(not in_fence and not in_comment, "Unclosed code fence or HTML comment")
    if current is not None:
        _finish_claim(current, claims)

    require(set(metadata) == {"Grammar", "Component", "Type", "Owners"}, "RULES.md requires Grammar, Component, Type and Owners metadata")
    grammar = _backtick(metadata["Grammar"], "Grammar")
    require(grammar == GRAMMAR, "Unsupported RULES.md grammar: " + grammar)
    component = _backtick(metadata["Component"], "Component")
    require(COMPONENT_PATTERN.fullmatch(component) is not None, "Invalid stable component identity")
    component_type = _backtick(metadata["Type"], "Type")
    require(COMPONENT_PATTERN.fullmatch(component_type) is not None, "Invalid component type")
    owners = [part.strip() for part in metadata["Owners"].split(",")]
    require(owners and all(owner.startswith("@") and len(owner) > 1 and " " not in owner for owner in owners), "Owners must be comma-separated native owner handles")
    require(claims, "At least one claim is required")
    ids = [claim["id"] for claim in claims]
    require(len(ids) == len(set(ids)), "Duplicate claim ID")
    invariant_ids = [row["id"] for claim in claims for row in claim["invariants"]]
    contract_ids = [row["id"] for claim in claims for row in claim["contracts"]]
    require(len(invariant_ids) == len(set(invariant_ids)), "Invariant IDs must be unique within a component")
    require(len(contract_ids) == len(set(contract_ids)), "Contract IDs must be unique within a component")
    return {"schema_version": 3, "grammar": grammar, "parser": PARSER, "source_sha256": sha(raw.encode("utf-8")),
            "component": {"id": component, "type": component_type, "owners": owners},
            "claims": claims, "preamble": "\n".join(preamble).strip()}


def _finish_claim(raw: dict, claims: list) -> None:
    require(set(raw["sections"]) == set(SECTION_NAMES),
            "Claim " + raw["id"] + " requires exactly: " + ", ".join(SECTION_NAMES))
    statement = " ".join(raw["statement_lines"]).strip()
    require(statement, "Claim statement required")
    sections = raw["sections"]
    boundaries = [line[2:].strip() for line in sections["Boundaries"]]
    preserves = [line[2:].strip() for line in sections["Preserves"]]
    require(boundaries and all(boundaries), "At least one explicit boundary is required")
    require(preserves and all(preserves), "At least one preserved behavior is required")
    invariants = []
    for line in sections["Invalidated by"]:
        item_id, description = _split_bullet(line, "invariant")
        require(description.strip(), "Invariant definition required")
        invariants.append({"id": item_id, "definition": description.strip()})
    require(invariants and len({row["id"] for row in invariants}) == len(invariants), "Unique invalidating invariants required")
    contracts = []
    for line in sections["Contracts"]:
        item_id, value = _split_bullet(line, "contract")
        path = _backtick(value.strip(), "contract descriptor path")
        _safe_path(path)
        contracts.append({"id": item_id, "descriptor": path})
    require(contracts and len({row["id"] for row in contracts}) == len(contracts), "Unique contract references required")
    enforcement = {}
    for line in sections["Enforcement"]:
        value = line[2:]
        require(": " in value, "Enforcement needs key: action syntax")
        key, action = value.split(": ", 1)
        require(key in ENFORCEMENT_KEYS and key not in enforcement, "Unknown/duplicate enforcement policy: " + key)
        require(action in ("block", "review", "allow"), "Enforcement action must be block, review or allow")
        enforcement[key] = action
    require(set(enforcement) == set(ENFORCEMENT_KEYS), "All enforcement outcomes must be explicit")
    claims.append({"id": raw["id"], "statement": statement, "boundaries": boundaries,
                   "invariants": invariants, "contracts": contracts, "preserves": preserves,
                   "enforcement": {"confirmed_violation": enforcement["Confirmed violation"],
                                   "candidate_pending": enforcement["Candidate awaiting evaluation"],
                                   "missing_coverage": enforcement["Missing mandatory coverage"]}})


def semantic_model(model: dict) -> dict:
    """Return only normative content; explanatory prose is intentionally excluded."""
    return {"schema_version": model["schema_version"], "grammar": model["grammar"], "parser": model["parser"],
            "component": copy.deepcopy(model["component"]), "claims": copy.deepcopy(model["claims"])}


def semantic_diff(base: bytes | str, candidate: bytes | str) -> dict:
    old = semantic_model(parse_rules(base)); new = semantic_model(parse_rules(candidate))
    old_claims = {row["id"]: row for row in old["claims"]}; new_claims = {row["id"]: row for row in new["claims"]}
    changed = sorted(key for key in old_claims.keys() & new_claims.keys() if old_claims[key] != new_claims[key])
    return {"schema": "defensefactory/rules-diff/v1", "semantic_change": old != new,
            "component_changed": old["component"] != new["component"],
            "added_claims": sorted(new_claims.keys() - old_claims.keys()),
            "removed_claims": sorted(old_claims.keys() - new_claims.keys()),
            "changed_claims": changed, "prose_only": old == new and base != candidate}


def validate_descriptor(value: dict, reference: dict | None = None, claim: dict | None = None) -> dict:
    allowed = {"schema", "id", "engine", "entrypoint", "claim", "invariant", "applies_to", "produces",
               "coverage", "introduction", "requires", "observation", "mandatory"}
    required = allowed
    require(isinstance(value, dict) and set(value) == required, "Contract descriptor has unknown or missing fields")
    require(value["schema"] == CONTRACT_SCHEMA, "Unsupported contract descriptor schema")
    _id(value["id"], "contract ID"); _id(value["claim"], "claim ID"); _id(value["invariant"], "invariant ID")
    require(value["engine"] in ENGINES, "Unsupported contract engine")
    _safe_path(value["entrypoint"])
    require(value["produces"] == CANDIDATE_SCHEMA, "Contracts must normalize to candidate/v1")
    require(value["observation"] in ("hard", "soft") and isinstance(value["mandatory"], bool), "Contract observation and mandatory policy required")
    applies = value["applies_to"]
    require(isinstance(applies, dict) and set(applies) == {"languages"} and isinstance(applies["languages"], list)
            and all(isinstance(item, str) and item for item in applies["languages"]), "Contract applicability languages required")
    coverage = value["coverage"]
    require(isinstance(coverage, dict) and set(coverage) == {"scope", "limitations"}
            and isinstance(coverage["scope"], str) and coverage["scope"]
            and isinstance(coverage["limitations"], list)
            and all(isinstance(item, str) and item for item in coverage["limitations"]), "Declared coverage and limitations required")
    introduction = value["introduction"]
    require(isinstance(introduction, dict) and set(introduction) == {"repository", "commit", "path", "selector"}
            and introduction["repository"] and COMMIT_PATTERN.fullmatch(introduction["commit"] or ""), "Immutable introduction provenance required")
    _safe_path(introduction["path"])
    require(isinstance(introduction["selector"], str) and introduction["selector"], "Introduction selector required")
    requires = value["requires"]
    require(isinstance(requires, dict) and set(requires) == {"executables", "network", "runtime"}
            and isinstance(requires["executables"], list) and all(isinstance(item, str) and item and "/" not in item for item in requires["executables"])
            and requires["network"] is False and isinstance(requires["runtime"], bool),
            "Contracts may declare tools/runtime but cannot grant network or arbitrary process authority")
    if value["engine"] == "markdown-example":
        require(value["observation"] == "soft" and not value["mandatory"], "Markdown examples are optional soft observations")
    if reference is not None:
        require(value["id"] == reference["id"], "Contract descriptor ID differs from RULES.md reference")
    if claim is not None:
        require(value["claim"] == claim["id"] and value["invariant"] in {row["id"] for row in claim["invariants"]},
                "Contract descriptor does not bind its referenced claim/invariant")
    return value


def _introduction_state(repo: str | Path, descriptor: dict, origins: dict | None = None) -> dict:
    introduction = descriptor["introduction"]; candidates = [repo]
    if (origins or {}).get(introduction["repository"]): candidates.append((origins or {})[introduction["repository"]])
    origin = None
    for candidate in candidates:
        try: git(candidate, "cat-file", "-e", introduction["commit"] + "^{commit}"); origin = candidate; break
        except (subprocess.CalledProcessError, GateError): continue
    if origin is None:
        return {"state": "history_unavailable", "repository": introduction["repository"], "commit": introduction["commit"],
                "limitation": "The declared original repository/commit was not available to this run."}
    try:
        body = source_blob(origin, introduction["commit"], introduction["path"])
        require(introduction["selector"].encode() in body, "Introduction selector is absent at declared commit")
        inherited = []
        for parent in git(origin, "show", "-s", "--format=%P", introduction["commit"]).decode().split():
            try: prior = source_blob(origin, parent, introduction["path"])
            except GateError: continue
            if introduction["selector"].encode() in prior: inherited.append(parent)
        if inherited:
            raise GateError("Declared commit inherited the control selector from parent " + inherited[0])
        return {"state": "located", "repository": introduction["repository"], "commit": introduction["commit"],
                "path": introduction["path"], "selector": introduction["selector"], "blob_sha256": sha(body)}
    except (subprocess.CalledProcessError, GateError) as error:
        return {"state": "introduction_unresolved", "repository": introduction["repository"], "commit": introduction["commit"], "reason": str(error)}


def resolve_contracts(repo: str | Path, revision: str, rules_path: str, origins: dict | None = None) -> dict:
    require(COMMIT_PATTERN.fullmatch(revision or "") is not None, "Full immutable source subject required")
    _safe_path(rules_path); git(repo, "cat-file", "-e", revision + "^{commit}")
    model = parse_rules(source_blob(repo, revision, rules_path))
    base = PurePosixPath(rules_path).parent
    rows = []
    for claim in model["claims"]:
        for reference in claim["contracts"]:
            descriptor_path = (base / _safe_path(reference["descriptor"])).as_posix()
            try:
                descriptor = json.loads(source_blob(repo, revision, descriptor_path))
            except json.JSONDecodeError as error:
                raise GateError("Contract descriptor is not strict JSON: " + str(error))
            validate_descriptor(descriptor, reference, claim)
            entrypoint = None
            if descriptor["engine"] != "test":
                entrypoint_path = (base / _safe_path(descriptor["entrypoint"])).as_posix()
                entrypoint_raw = source_blob(repo, revision, entrypoint_path)
                entrypoint = {"path": entrypoint_path, "sha256": sha(entrypoint_raw)}
            rows.append({"claim_id": claim["id"], "invariant_id": descriptor["invariant"],
                         "descriptor_path": descriptor_path, "descriptor": descriptor,
                         "descriptor_sha256": sha(source_blob(repo, revision, descriptor_path)),
                         "entrypoint": entrypoint, "introduction": _introduction_state(repo, descriptor, origins)})
    return {"schema": "defensefactory/contracts/v1", "subject": {"revision": revision},
            "rules_path": rules_path, "rules_sha256": sha(source_blob(repo, revision, rules_path)),
            "model": semantic_model(model), "contracts": rows}


def _tool(engine: str) -> str:
    return "semgrep" if engine == "semgrep" else "opengrep" if engine == "opengrep" else engine


def _tool_identities(executables: list[str]) -> list[dict]:
    rows = []
    for name in executables:
        located = _which(name)
        if not located:
            rows.append({"name": name, "state": "missing"}); continue
        path = Path(located).resolve(); row = {"name": name, "state": "located", "path": str(path)}
        try: row["sha256"] = sha(path.read_bytes())
        except OSError as error: row["identity_limitation"] = str(error)
        try:
            observed = subprocess.run([str(path), "--version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                      timeout=5, check=False).stdout.decode(errors="replace").strip()
            row["reported_version"] = observed[:1000]
        except (OSError, subprocess.TimeoutExpired) as error: row["version_limitation"] = str(error)
        rows.append(row)
    return rows


def _adapter_command(descriptor: dict, source: Path, trusted_checks: dict, contexts: dict) -> tuple[list[str] | None, str | None]:
    engine = descriptor["engine"]; entry = descriptor["entrypoint"]
    if engine == "markdown-example":
        return None, "Markdown example is review guidance, not deterministic execution"
    if engine == "test":
        check = trusted_checks.get(entry)
        if not check:
            return None, "Trusted check plan does not define test entrypoint " + entry
        require(set(check) <= {"argv", "cwd", "timeout"} and isinstance(check.get("argv"), list)
                and all(isinstance(item, str) and item for item in check["argv"]), "Invalid trusted test check")
        return check["argv"], None
    if engine == "codeql":
        database = contexts.get("codeql_database")
        if not database:
            return None, "CodeQL database capability is unavailable"
        return ["codeql", "query", "run", entry, "--database", str(database), "--format=sarif-latest"], None
    if engine == "cue":
        return ["cue", "vet", entry], None
    if engine in ("semgrep", "opengrep"):
        return [_tool(engine), "scan", "--config", entry, "--json", "."], None
    adapter = contexts.get("adapter_commands", {}).get(engine)
    if adapter:
        require(isinstance(adapter, list) and all(isinstance(item, str) and item for item in adapter), "Invalid trusted adapter command")
        return adapter + [entry], None
    return None, "No trusted adapter is configured for engine " + engine


def _candidate(descriptor: dict, subject: dict, location: str, observation: dict, coverage: dict, raw_reference: str) -> dict:
    value = {"schema": CANDIDATE_SCHEMA, "candidate_id": "",
             "claim_id": descriptor["claim"], "invariant_id": descriptor["invariant"],
             "contract_id": descriptor["id"], "subject": subject, "location": location,
             "observation": observation, "coverage": coverage, "raw_result_reference": raw_reference}
    value["candidate_id"] = identity({key: item for key, item in value.items() if key != "candidate_id"})
    return value


def _normalize(descriptor: dict, result: dict, subject: dict, raw_reference: str) -> tuple[list[dict], str]:
    engine = descriptor["engine"]
    coverage = copy.deepcopy(descriptor["coverage"])
    if result["result"] == "unsupported":
        return [], "unsupported"
    stdout = result.get("log", "")
    candidates = []
    if engine in ("semgrep", "opengrep"):
        try:
            parsed = json.loads(stdout or "{}")
            for row in parsed.get("results", []):
                location = row.get("path", descriptor["entrypoint"])
                if row.get("start", {}).get("line"):
                    location += ":" + str(row["start"]["line"])
                candidates.append(_candidate(descriptor, subject, location,
                    {"engine": engine, "check_id": row.get("check_id"), "message": row.get("extra", {}).get("message", "pattern matched")},
                    coverage, raw_reference))
        except (ValueError, TypeError) as error:
            return [], "normalization_failed: " + str(error)
    elif engine == "codeql":
        try:
            parsed = json.loads(stdout or "{}")
            for run in parsed.get("runs", []):
                for result_row in run.get("results", []):
                    location = descriptor["entrypoint"]
                    candidates.append(_candidate(descriptor, subject, location,
                        {"engine": engine, "rule_id": result_row.get("ruleId"), "message": result_row.get("message", {}).get("text", "query result")},
                        coverage, raw_reference))
        except (ValueError, TypeError) as error:
            return [], "normalization_failed: " + str(error)
    elif engine in ("cue", "test", "type", "lint", "ast", "runtime", "formal") and result["exit_code"] != 0:
        candidates.append(_candidate(descriptor, subject, descriptor["entrypoint"],
            {"engine": engine, "failure": "contract returned nonzero", "returncode": result["exit_code"]}, coverage, raw_reference))
    return candidates, "complete" if not coverage["limitations"] else "partial"


def run_contracts(repo: str | Path, revision: str, rules_path: str, output: str | Path,
                  selected: list[str] | None = None, trusted_checks: dict | None = None,
                  contexts: dict | None = None, max_seconds: int = 300) -> dict:
    """Execute built-in adapters in a detached archive of the exact Git subject."""
    registry = resolve_contracts(repo, revision, rules_path, (contexts or {}).get("origins"))
    output = Path(output)
    require(not output.exists(), "Contract run output already exists")
    output.mkdir(parents=True)
    selected_set = set(selected or [row["descriptor"]["id"] for row in registry["contracts"]])
    known = {row["descriptor"]["id"] for row in registry["contracts"]}
    require(selected_set <= known, "Unknown selected contract")
    subject = {"repository": str(repo), "revision": revision}
    receipt = {"schema": RUN_SCHEMA, "subject": subject, "rules": {"path": rules_path, "sha256": registry["rules_sha256"]},
               "contracts": [], "candidates": [], "started_at": time.time(), "result": "inconclusive"}
    with tempfile.TemporaryDirectory(prefix="factory-contracts-") as temp:
        root = Path(temp); archive = root / "source.tar"; archive.write_bytes(git(repo, "archive", revision))
        source = root / "source"; source.mkdir()
        with tarfile.open(archive) as handle:
            handle.extractall(source, filter="data")
        snapshot = lambda: {str(path.relative_to(source)): sha(path.read_bytes()) for path in source.rglob("*") if path.is_file()}
        source_before = snapshot()
        started = time.monotonic()
        for row in registry["contracts"]:
            descriptor = row["descriptor"]
            if descriptor["id"] not in selected_set:
                continue
            raw_name = descriptor["id"].lower() + ".log"
            raw_path = output / raw_name
            record = {"id": descriptor["id"], "engine": descriptor["engine"], "mandatory": descriptor["mandatory"],
                      "observation": descriptor["observation"], "descriptor_path": row["descriptor_path"],
                      "descriptor_sha256": row["descriptor_sha256"], "declared_coverage": descriptor["coverage"],
                      "tools": _tool_identities(descriptor["requires"]["executables"]), "introduction": row["introduction"]}
            missing = [item for item in descriptor["requires"]["executables"] if not _which(item)]
            argv, unsupported = _adapter_command(descriptor, source, trusted_checks or {}, contexts or {})
            if missing:
                unsupported = "Missing executables: " + ", ".join(missing)
            if unsupported:
                record.update(result="unsupported", reason=unsupported, coverage="unavailable")
                receipt["contracts"].append(record)
                continue
            remaining = max_seconds - (time.monotonic() - started)
            if remaining <= 0:
                record.update(result="inconclusive", reason="Contract run budget exhausted", coverage="unavailable")
                receipt["contracts"].append(record); continue
            cwd = source / PurePosixPath(rules_path).parent
            if descriptor["engine"] == "test" and descriptor["entrypoint"] in (trusted_checks or {}):
                cwd = source / _safe_path((trusted_checks or {})[descriptor["entrypoint"]].get("cwd", "."))
            environment = {key: value for key, value in os.environ.items() if key in ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL")}
            environment.update({"PYTHONDONTWRITEBYTECODE": "1", "FACTORY_CANDIDATE_REVISION": revision,
                                "FACTORY_CONTRACT_ID": descriptor["id"], "FACTORY_NETWORK": "disabled"})
            try:
                executed = command(argv, cwd, min(int((trusted_checks or {}).get(descriptor["entrypoint"], {}).get("timeout", 60)), int(remaining)), environment=environment)
            except OSError as error:
                executed = {"result": "unsupported", "exit_code": None, "log": str(error), "seconds": 0}
            raw_path.write_text(executed.get("log") or "")
            candidates, coverage = _normalize(descriptor, executed, subject, raw_name)
            if row["introduction"].get("state") != "located": coverage = "partial"
            record.update(result="executed" if executed.get("result") != "unsupported" else "unsupported",
                          returncode=executed.get("exit_code"), raw_result_reference=raw_name, coverage=coverage,
                          candidate_ids=[item["candidate_id"] for item in candidates],
                          execution={key: executed.get(key) for key in ("argv","started_at","finished_at","exit_code","timed_out","seconds","result","log_sha256")})
            receipt["contracts"].append(record); receipt["candidates"].extend(candidates)
        source_after = snapshot()
        receipt["source_mutations"] = sorted(name for name in source_before.keys() | source_after.keys()
                                              if source_before.get(name) != source_after.get(name))
    mandatory = [row for row in receipt["contracts"] if row["mandatory"]]
    receipt["result"] = "inconclusive" if receipt["source_mutations"] or any(row.get("coverage") != "complete" for row in mandatory) else "candidates" if receipt["candidates"] else "zero_candidates_with_adequate_coverage"
    receipt["finished_at"] = time.time()
    receipt["run_sha256"] = identity({key: value for key, value in receipt.items() if key != "run_sha256"})
    (output / "contract-run.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    (output / "candidates.json").write_text(json.dumps({"schema": "defensefactory/candidates/v1", "items": receipt["candidates"]}, indent=2, sort_keys=True) + "\n")
    return receipt


def _which(name: str) -> str | None:
    from shutil import which
    return which(name)


def evaluate_candidate(candidate: dict, disposition: str, evaluator: dict, evidence: list[dict],
                       explanation: str, limitations: list[str], next_action: str,
                       duplicate_of: str | None = None) -> dict:
    require(candidate.get("schema") == CANDIDATE_SCHEMA and candidate.get("candidate_id") == identity({key: value for key, value in candidate.items() if key != "candidate_id"}), "Candidate identity mismatch")
    require(disposition in DISPOSITIONS, "Unknown candidate disposition")
    require(isinstance(evaluator, dict) and evaluator.get("identity") and evaluator.get("version"), "Evaluator identity/version required")
    require(isinstance(evidence, list) and evidence and all(isinstance(item, dict) and item.get("reference") for item in evidence), "Evaluation evidence references required")
    require(explanation and next_action and isinstance(limitations, list), "Evaluation explanation, limitations and next action required")
    require((disposition == "duplicate") == bool(duplicate_of), "Duplicate disposition requires exactly one original candidate")
    effect = "violated" if disposition == "confirmed_violation" else "inconclusive" if disposition in ("inconclusive", "duplicate") else "no_confirmed_violation"
    value = {"schema": EVALUATION_SCHEMA, "candidate_id": candidate["candidate_id"], "subject": candidate["subject"],
             "claim_id": candidate["claim_id"], "invariant_id": candidate["invariant_id"], "contract_id": candidate["contract_id"],
             "disposition": disposition, "duplicate_of": duplicate_of, "evaluator": evaluator,
             "evidence": copy.deepcopy(evidence), "explanation": explanation, "coverage_limitations": limitations,
             "next_action": next_action, "claim_state_effect": effect}
    value["evaluation_id"] = identity(value)
    return value


def claim_status(model: dict, run: dict, evaluations: list[dict]) -> dict:
    require(run.get("schema") == RUN_SCHEMA and run.get("run_sha256") == identity({key: value for key, value in run.items() if key != "run_sha256"}), "Contract run integrity mismatch")
    require(model.get("source_sha256") == run.get("rules", {}).get("sha256"), "Claim status RULES.md differs from the exact contract run")
    model = semantic_model(model)
    evaluation_by_candidate = {row["candidate_id"]: row for row in evaluations}
    require(len(evaluation_by_candidate) == len(evaluations), "Duplicate candidate evaluation")
    candidates = {row["candidate_id"]: row for row in run["candidates"]}
    require(set(evaluation_by_candidate) <= set(candidates), "Evaluation does not bind this run")
    for candidate_id, evaluation in evaluation_by_candidate.items():
        require(evaluation.get("schema") == EVALUATION_SCHEMA
                and evaluation.get("evaluation_id") == identity({key: value for key, value in evaluation.items() if key != "evaluation_id"})
                and evaluation.get("subject") == candidates[candidate_id]["subject"], "Evaluation integrity or subject mismatch")
    states = []
    for claim in model["claims"]:
        contract_ids = {row["id"] for row in claim["contracts"]}
        contracts = [row for row in run["contracts"] if row["id"] in contract_ids]
        claim_candidates = [row for row in run["candidates"] if row["claim_id"] == claim["id"]]
        dispositions = [evaluation_by_candidate[row["candidate_id"]]["disposition"] for row in claim_candidates if row["candidate_id"] in evaluation_by_candidate]
        missing_evaluations = [row["candidate_id"] for row in claim_candidates if row["candidate_id"] not in evaluation_by_candidate]
        mandatory_incomplete = [row["id"] for row in contracts if row["mandatory"] and row.get("coverage") != "complete"]
        if "confirmed_violation" in dispositions:
            result = "violated"
        elif run.get("source_mutations") or mandatory_incomplete or missing_evaluations or any(item in ("inconclusive", "duplicate") for item in dispositions):
            result = "inconclusive"
        else:
            result = "satisfied_within_scope"
        states.append({"claim_id": claim["id"], "result": result, "mandatory_coverage_missing": mandatory_incomplete,
                       "unevaluated_candidates": missing_evaluations, "evaluations": sorted(dispositions),
                       "coverage": "Only the declared contract scopes at the exact run subject"})
    overall = "violated" if any(row["result"] == "violated" for row in states) else "satisfied_within_scope" if all(row["result"] == "satisfied_within_scope" for row in states) else "inconclusive"
    result = {"schema": STATUS_SCHEMA, "subject": run["subject"], "rules_sha256": run["rules"]["sha256"],
              "run_sha256": run["run_sha256"], "claims": states, "result": overall,
              "zero_finding_semantics": "Zero candidates satisfy a claim only when every mandatory contract has complete declared coverage."}
    result["status_sha256"] = identity(result)
    return result


def render_rules(model: dict, title: str = "Component architectural rules", preamble: str = "") -> str:
    component = model["component"]
    lines = ["# " + title, "", f"Grammar: `{GRAMMAR}`", f"Component: `{component['id']}`",
             f"Type: `{component['type']}`", "Owners: " + ", ".join(component["owners"]), ""]
    if preamble.strip():
        lines.extend([preamble.strip(), ""])
    for claim in model["claims"]:
        lines.extend([f"## Claim `{claim['id']}`", "", claim["statement"], "", "### Boundaries", ""])
        lines.extend("- " + item for item in claim["boundaries"])
        lines.extend(["", "### Invalidated by", ""])
        lines.extend(f"- `{item['id']}`: {item['definition']}" for item in claim["invariants"])
        lines.extend(["", "### Contracts", ""])
        lines.extend(f"- `{item['id']}`: `{item['descriptor']}`" for item in claim["contracts"])
        lines.extend(["", "### Preserves", ""])
        lines.extend("- " + item for item in claim["preserves"])
        lines.extend(["", "### Enforcement", "",
                      "- Confirmed violation: " + claim["enforcement"]["confirmed_violation"],
                      "- Candidate awaiting evaluation: " + claim["enforcement"]["candidate_pending"],
                      "- Missing mandatory coverage: " + claim["enforcement"]["missing_coverage"], ""])
    rendered = "\n".join(lines).rstrip() + "\n"
    parse_rules(rendered)
    return rendered


def migrate_legacy(catalog: dict, component_type: str, owners: list[str], existing_prose: str = "") -> tuple[str, list[dict]]:
    """Create a reviewable proposal; external descriptors remain explicit follow-up."""
    from .component_claims import validate_catalog
    validate_catalog(catalog)
    classes = {row["id"]: row for row in catalog["bug_classes"]}
    fences = {row["id"]: row for row in catalog["fences"]}
    claims = []
    descriptors = []
    for old in catalog["claims"]:
        invariants = [{"id": _legacy_id(item), "definition": classes[item]["definition"]} for item in old["bug_classes"]]
        refs = []
        for fence_id in old["fences"]:
            fence = fences[fence_id]; contract_id = _legacy_id(fence_id)
            for invariant in invariants:
                mapped_id = _legacy_id(contract_id + "--" + old["id"] + "--" + invariant["id"])
                descriptor_path = "contracts/" + mapped_id.lower() + ".contract.json"
                refs.append({"id": mapped_id, "descriptor": descriptor_path})
                descriptors.append({"schema": CONTRACT_SCHEMA, "id": mapped_id,
                    "engine": fence["mechanism"] if fence["mechanism"] in ENGINES else "markdown-example",
                    "entrypoint": fence.get("check") or fence["controls"][0]["path"], "claim": _legacy_id(old["id"]),
                    "invariant": invariant["id"], "applies_to": {"languages": []}, "produces": CANDIDATE_SCHEMA,
                    "coverage": {"scope": "legacy definition; owner must declare exact coverage", "limitations": ["migration proposal requires owner review"]},
                    "introduction": {"repository": fence["controls"][0]["introduced"]["repository"],
                                     "commit": fence["controls"][0]["introduced"]["ref"],
                                     "path": fence["controls"][0]["introduced"]["path"],
                                     "selector": fence["controls"][0]["introduced"].get("selector", fence["controls"][0]["selector"])},
                    "requires": {"executables": [], "network": False, "runtime": False},
                    "observation": "hard" if fence["kind"] == "hard" else "soft", "mandatory": fence["kind"] == "hard"})
        claims.append({"id": _legacy_id(old["id"]), "statement": old["statement"],
                       "boundaries": ["Legacy boundary was not explicit; owner review is required before admission."],
                       "invariants": invariants, "contracts": refs, "preserves": old["preserves"],
                       "enforcement": {"confirmed_violation": "block", "candidate_pending": "review", "missing_coverage": "block"}})
    model = {"component": {"id": catalog["component"], "type": component_type, "owners": owners}, "claims": claims}
    preamble = "Migration proposal from legacy claims.json. Resolve every stated limitation before removing the legacy file."
    if existing_prose.strip():
        preamble += "\n\n## Preserved project guidance\n\n" + existing_prose.strip()
    return render_rules(model, preamble=preamble), descriptors


def _legacy_id(value: str) -> str:
    converted = re.sub(r"[^A-Za-z0-9._-]+", "-", value).upper().strip("-")
    if len(converted) < 2:
        converted = "ID-" + converted
    return _id(converted, "migrated ID")


def transitional_compare(catalog: dict, model: dict) -> dict:
    """Compare the semantics that legacy schema 2 was capable of expressing."""
    from .component_claims import validate_catalog
    validate_catalog(catalog); model = semantic_model(model)
    old_claims = {_legacy_id(row["id"]): row for row in catalog["claims"]}
    new_claims = {row["id"]: row for row in model["claims"]}
    differences = []
    if catalog["component"] != model["component"]["id"]:
        differences.append("component")
    if set(old_claims) != set(new_claims):
        differences.append("claim_ids")
    for claim_id in sorted(set(old_claims) & set(new_claims)):
        old = old_claims[claim_id]; new = new_claims[claim_id]
        if old["statement"] != new["statement"]: differences.append(claim_id + ":statement")
        if sorted(old["preserves"]) != sorted(new["preserves"]): differences.append(claim_id + ":preserves")
        if {_legacy_id(item) for item in old["bug_classes"]} != {item["id"] for item in new["invariants"]}: differences.append(claim_id + ":invariants")
        actual_fences={item["id"].split("--",1)[0] for item in new["contracts"]}
        if {_legacy_id(item) for item in old["fences"]} != actual_fences: differences.append(claim_id + ":contracts")
    return {"state": "duplicate_legacy_source", "semantically_equal": not differences, "differences": differences,
            "next_action": "Remove claims.json only in an explicit reviewed migration" if not differences else "Reconcile divergence before migration"}


def discover_rules(repo: str | Path, revision: str) -> dict:
    """Discover only files that declare this grammar; other project RULES.md files are untouched."""
    require(COMMIT_PATTERN.fullmatch(revision or "") is not None, "Full immutable source subject required")
    git(repo, "cat-file", "-e", revision + "^{commit}")
    rows = []
    for path in git(repo, "ls-tree", "-r", "--name-only", revision).decode().splitlines():
        if PurePosixPath(path).name != "RULES.md":
            continue
        raw = source_blob(repo, revision, path)
        if ("Grammar: `" + GRAMMAR + "`").encode() not in raw:
            continue
        model = parse_rules(raw)
        rows.append({"path": path, "sha256": sha(raw), "model": semantic_model(model),
                     "component_id": model["component"]["id"]})
    require(len({row["component_id"] for row in rows}) == len(rows), "Duplicate component identity across RULES.md files")
    return {"revision": revision, "rules": rows}


def rules_change_gate(repo: str | Path, repository: str, base: str, subject: str,
                      statuses: list[dict], policy: dict, reviews: list[dict]) -> dict:
    """Apply claim-aware admission to an exact candidate/merge subject.

    Review records and policy are trusted caller inputs.  This function checks
    correspondence but does not authenticate them or install repository policy.
    """
    old = discover_rules(repo, base); new = discover_rules(repo, subject)
    old_by_id = {row["component_id"]: row for row in old["rules"]}; new_by_id = {row["component_id"]: row for row in new["rules"]}
    added = sorted(new_by_id.keys() - old_by_id.keys()); removed = sorted(old_by_id.keys() - new_by_id.keys())
    changed = []; moved = []; prose_only = []
    for component_id in sorted(old_by_id.keys() & new_by_id.keys()):
        before = old_by_id[component_id]; after = new_by_id[component_id]
        if before["path"] != after["path"]: moved.append(component_id)
        if before["model"] != after["model"]: changed.append(component_id)
        elif before["sha256"] != after["sha256"]: prose_only.append(component_id)

    status_by_rules = {row.get("rules_sha256"): row for row in statuses}
    require(len(status_by_rules) == len(statuses), "Duplicate claim status for one RULES.md")
    status_results = []; blockers = []
    for component_id, row in sorted(new_by_id.items()):
        status = status_by_rules.get(row["sha256"])
        valid = bool(status and status.get("schema") == STATUS_SCHEMA
                     and status.get("status_sha256") == identity({key: value for key, value in status.items() if key != "status_sha256"})
                     and status.get("subject", {}).get("revision") == subject)
        if not valid:
            status_results.append({"component_id": component_id, "result": "missing_or_stale"})
            blockers.append("Missing exact-subject claim status for component " + component_id)
        else:
            status_results.append({"component_id": component_id, "result": status["result"], "status_sha256": status["status_sha256"]})
            if status["result"] != "satisfied_within_scope":
                blockers.append("Component claim state is " + status["result"] + ": " + component_id)

    semantic_changes = sorted(set(added + removed + changed + moved))
    if removed:
        retired = policy.get("retired_components", {})
        unresolved = [item for item in removed if not retired.get(item)]
        if unresolved: blockers.append("Removed component rules need an explicit owner-authorized retirement/transfer decision: " + ", ".join(unresolved))
    approved = [row for row in reviews if row.get("state") == "APPROVED" and row.get("base") == base and row.get("head") == subject and row.get("reference")]
    owners = policy.get("owners", {})
    if semantic_changes and policy.get("definition_review_required", True):
        uncovered = [component_id for component_id in semantic_changes
                     if not any(review.get("reviewer") in owners.get(component_id, []) for review in approved)]
        if uncovered: blockers.append("Semantic rule/contract amendments need current native owner review: " + ", ".join(uncovered))
    result = {"schema": "defensefactory/rules-change-gate/v1", "base": {"repository": repository, "revision": base},
              "subject": {"repository": repository, "revision": subject}, "added_components": added,
              "removed_components": removed, "changed_components": changed, "moved_components": moved,
              "prose_only_components": prose_only, "claim_statuses": status_results,
              "result": "inconclusive" if blockers else "satisfied_within_scope", "blockers": blockers,
              "pr_blocked": bool(blockers), "definition_changes_allowed": not blockers,
              "review_policy": "native_repository", "additional_security_approval": False,
              "policy_sha256": identity(policy), "review_receipts_sha256": identity(reviews),
              "next_action": "Resolve listed rule, coverage, evaluation or native-review requirements; do not integrate." if blockers else "Apply ordinary repository gates to the exact merge subject.",
              "authority": "This helper checks supplied native policy/review correspondence; it does not authenticate reviews or install CI/branch protection."}
    result["change_gate_sha256"] = identity(result)
    return result
