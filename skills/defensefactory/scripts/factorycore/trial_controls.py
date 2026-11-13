"""Manual stage admission and assertion-based mutation evidence for new trials.

These are same-host correspondence checks, not authenticated connector identities
or a sandbox that can prevent an agent from bypassing the helpers.
"""
import datetime
import json
from pathlib import Path
import re
from .core import require, identity, sha
from .execution_capture import capture
from .check_results import qualify_execution
from .stage_rules import discover_root_package, receipt_binding, validate_package_safe


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def instant(value):
    parsed = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(parsed.tzinfo is not None, 'Timezone-aware captured timestamp required')
    return parsed


def scope_prepare(data):
    """Snapshot identities for the stage package actually loaded; no publication."""
    stage = data['stage']
    require(stage in ('intake', 'assess', 'repair', 'verify', 'integrate', 'deploy', 'confirm', 'maintain'), 'Unknown stage')
    require(all(data.get(k) for k in ('case', 'attempt', 'subject', 'performed_by', 'authorization_reference', 'boundaries')), 'Actual case/stage scope and authority reference required')
    package = Path(data['package']).resolve()
    expected = 'defensefactory-' + stage
    resources = ['SKILL.md', 'RULES.md', 'references/stage-contract.md', 'references/claim-evidence.md']
    if stage == 'verify':
        resources.append('references/verification-execution.md')
    if stage == 'maintain':
        resources.append('references/component-claims.md')
    require(('name: ' + expected + '\n') in (package / 'SKILL.md').read_text(), 'Load the stage skill, not only orchestration')
    files = {}
    for name in resources:
        path = package / name
        require(path.is_file() and not path.is_symlink(), 'Required stage resource missing: ' + name)
        files[name] = sha(path.read_bytes())
    profiles = data.get('rule_profiles', [])
    require(isinstance(profiles, list), 'rule_profiles must be a list')
    profile_paths = []
    for value in profiles:
        path = Path(value).resolve()
        require(path.is_absolute() and str(path) == value and path.is_file() and not path.is_symlink(), 'Rule profiles need canonical regular-file paths')
        profile_paths.append(path)
    rules_validation = validate_package_safe(package, discover_root_package(package), profile_paths)
    rules_binding = receipt_binding(rules_validation)
    scope = {key: data[key] for key in ('case', 'attempt', 'stage', 'subject', 'performed_by', 'authorization_reference', 'boundaries')}
    scope.update(package=str(package), loaded_resource_sha256=files, rule_profiles=[str(path) for path in profile_paths],
                 stage_rules=rules_binding)
    if 'comparisons' in data:
        comparisons = data['comparisons']
        require(isinstance(comparisons, list) and len({c['id'] for c in comparisons}) == len(comparisons), 'Unique comparison subjects required')
        for c in comparisons:
            require(c.get('id') and c.get('purpose') and c.get('reference') and c.get('subject')
                    and re.fullmatch('[0-9a-f]{40}', c['subject'].get('revision', '')),
                    'Comparison needs exact subject, purpose and existing scope/authorization reference')
            require(c['subject'] != scope['subject'], 'Comparison must name its actual differing subject')
        scope['comparisons'] = comparisons
    if 'codeintel_requirement' in data:
        policy = data['codeintel_requirement']
        require(type(policy.get('required')) is bool and policy.get('reference'), 'CodeIntel scope requirement needs a boolean and governing reference')
        scope['codeintel_requirement'] = policy
    if 'runtime_requirement' in data:
        from .runtime_plan import validate_requirement
        validate_requirement(data['runtime_requirement'], scope)
        scope['runtime_requirement'] = data['runtime_requirement']
    body = 'Factory stage scope — before execution\n\n```json\n' + json.dumps(scope, sort_keys=True, indent=2) + '\n```'
    return {'result': 'prepared', 'prepared_at': now(), 'scope': scope, 'scope_body': body,
            'rules_validation': rules_validation,
            'scope_sha256': identity(scope), 'limitation': 'File correspondence, not proof of model comprehension or authenticated authority.'}


def stage_start(preparation, publication, retrieval):
    scope = preparation['scope']
    require(preparation['result'] == 'prepared' and preparation['scope_sha256'] == identity(scope), 'Changed scope preparation')
    rebuilt = scope_prepare(scope)
    require(rebuilt['scope'] == scope and rebuilt['scope_body'] == preparation['scope_body'], 'Required stage resources/body missing or changed')
    require(rebuilt['rules_validation'] == preparation.get('rules_validation'), 'Effective stage rule receipt missing or changed')
    require(publication.get('id') and publication['id'] == retrieval.get('id'), 'Ticket scope resource differs')
    require(retrieval.get('operation') == 'retrieval', 'Separate connector readback required')
    require(publication.get('body') == retrieval.get('body') == preparation['scope_body'], 'Published/read-back scope body differs')
    require(instant(preparation['prepared_at']) <= instant(publication['createdAt']) <= instant(retrieval['retrieved_at']) <= instant(now()), 'Scope publication/readback order invalid')
    package = Path(scope['package'])
    for name, digest in scope['loaded_resource_sha256'].items():
        require(sha((package / name).read_bytes()) == digest, 'Loaded stage resource changed')
    return {'result': 'recorded', 'stage_execution_permitted': True, 'opened_at': now(),
            'scope': scope, 'stage_rules': scope['stage_rules'], 'scope_comment_id': publication['id'], 'preparation_sha256': identity(preparation),
            'readback_sha256': identity(retrieval), 'acceptance': 'not_granted',
            'preparation': preparation, 'publication': publication, 'retrieval': retrieval,
            'limitation': 'Caller supplies connector records. This is not a protected identity or host-tool restriction.'}


def validate_plan(plan):
    require(plan.get('baseline_subject') and plan.get('argv') and plan.get('execution', {}).get('required_tests'), 'Exact baseline, command and named test protocol required')
    require(plan['execution']['format'] in ('go-test-json', 'factory-jsonl-v1'), 'Mutants require named assertion output')
    required = plan['execution']['required_tests']
    require(len(set(required)) == len(required), 'Duplicate required test')
    evaluators = plan.get('evaluators', {})
    require(evaluators and not set(evaluators).intersection(plan.get('controls', [])), 'Keep evaluator files separate from controls')
    for name, digest in evaluators.items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and re.fullmatch('[0-9a-f]{64}', digest), 'Relative evaluator path and SHA-256 required')
    variants = plan.get('variants', [])
    require(variants and len({v['id'] for v in variants}) == len(variants), 'Unique bounded variant inventory required')
    for variant in variants:
        require(variant.get('kind') in ('security', 'legitimate_behavior'), 'Declare security or legitimate-behavior detection')
        require(variant.get('subject') != plan['baseline_subject'] and variant.get('subject'), 'Exact derived subject required')
        tests = variant.get('expected_failures', [])
        require(tests and len(set(tests)) == len(tests) and set(tests) <= set(required), 'Predeclare named failure criteria for every variant')


def mutation_plan(plan):
    validate_plan(plan)
    return {'record_type':'mutation_plan', 'result': 'recorded', 'declared_at': now(), 'plan': plan, 'plan_sha256': identity(plan)}


def stage_command(opening, specification, evidence_directory, challenge=None):
    require(opening.get('stage_execution_permitted') is True and opening.get('result') == 'recorded', 'Ticket stage scope must be opened before execution')
    require(instant(opening['opened_at']) <= instant(now()), 'Stage opening is in the future')
    verified = stage_start(opening['preparation'], opening['publication'], opening['retrieval'])
    require({k:v for k,v in opening.items() if k!='opened_at'} == {k:v for k,v in verified.items() if k!='opened_at'}, 'Stage-opening correspondence changed')
    require(instant(opening['opened_at']) >= instant(opening['retrieval']['retrieved_at']), 'Stage opening predates readback')
    scope = opening['scope']
    require(Path(specification['cwd']).is_absolute() and str(Path(specification['cwd']).resolve()) == specification['cwd'], 'Use canonical absolute cwd/evaluator paths (resolve host symlinks)')
    require(specification['performed_by'] == scope['performed_by'], 'Actual performer differs')
    require(specification.get('stage_start_sha256') == identity(opening), 'Command must bind the stage-opening receipt')
    require(json.loads(Path(specification['stage_start_reference']).read_text()) == opening, 'Stage-opening bytes missing/changed')
    argv = specification['argv']
    require(not (Path(argv[0]).name in ('sh', 'bash', 'zsh', 'dash') and any(a == '-c' or (a.startswith('-') and not a.startswith('--') and 'c' in a) for a in argv[1:])), 'Do not hide producer status in shell -c; freeze a reviewed adapter or use direct argv')
    if specification['execution']['format'] == 'process-assertions-v1':
        require(not any(Path(arg).name in ('sh','bash','zsh','dash') and
                        any(flag == '-c' or (flag.startswith('-') and not flag.startswith('--') and 'c' in flag)
                            for flag in argv[i+1:i+3]) for i,arg in enumerate(argv)),
                'Runtime assertions require the actual producer exit, not an inline container shell/echo wrapper')
    comparison = specification.get('comparison_id')
    if specification.get('fixture_reference'):
        from .fixtures import validate_live
        fixture = json.loads(Path(specification['fixture_reference']).read_text())
        require(comparison is None and challenge is None and not any(specification.get(k) for k in
            ('source_repository','produces_artifacts','uses_artifacts','runtime_plan_reference')), 'Fixture cannot substitute for a candidate artifact/runtime subject')
        validate_live(fixture, opening, specification['cwd'])
        require(specification['subject'] == fixture['subject'] and identity(fixture) == specification['fixture_sha256'], 'Fixture subject differs')
    elif comparison:
        require(challenge is None, 'Select either an admitted comparison or a challenge variant')
        admitted = next((c for c in scope.get('comparisons', []) if c['id'] == comparison), None)
        require(admitted and specification['subject'] == admitted['subject'], 'Comparison subject is not admitted by the published opening')
        require(specification.get('purpose'), 'Comparison capture needs its declared purpose')
    elif challenge is None:
        require(specification['subject'] == scope['subject'], 'Execution subject differs from ticket stage scope')
    else:
        plan = challenge['plan']; validate_plan(plan)
        require(challenge['plan_sha256'] == identity(plan), 'Changed challenge plan')
        require(plan['baseline_subject'] == scope['subject'], 'Challenge base differs from ticket scope')
        allowed = [plan['baseline_subject'], *[v['subject'] for v in plan['variants']]]
        require(specification['subject'] in allowed and specification.get('challenge_plan_sha256') == identity(challenge), 'Command differs from predeclared challenge subject/plan')
        require(json.loads(Path(specification['challenge_plan_reference']).read_text()) == challenge, 'Mutation declaration bytes missing/changed')
        role = specification.get('challenge_role', 'evaluation')
        require(role in ('evaluation', 'support'), 'Unknown challenge command role')
        if role == 'support':
            require(specification.get('purpose') and specification['execution']['format'] in ('command', 'factory-jsonl-v1', 'process-assertions-v1'),
                    'Support command needs a declared purpose and command/probe protocol')
        else:
            require(specification['argv'] == plan['argv'] and specification['execution'] == plan['execution'], 'Challenge command/evaluator protocol changed')
            expected = {str((Path(specification['cwd']) / name).resolve()): digest for name, digest in plan['evaluators'].items()}
            require(specification.get('evaluator_files') == expected, 'Challenge evaluator inventory changed or control included')
    if specification.get('runtime_plan_reference'):
        from .runtime_plan import validate_probe
        declaration = json.loads(Path(specification['runtime_plan_reference']).read_text())
        validate_probe(declaration, specification, opening)
    return capture(specification, evidence_directory)


def mutation_result(declaration, variant_id, baseline, mutant):
    plan = declaration['plan']; validate_plan(plan)
    require(declaration['plan_sha256'] == identity(plan), 'Changed mutation declaration')
    variant = next((v for v in plan['variants'] if v['id'] == variant_id), None)
    require(variant is not None, 'Undeclared variant')
    problems = []
    for label, record, subject in [('baseline', baseline, plan['baseline_subject']), ('mutant', mutant, variant['subject'])]:
        if record.get('execution_state') != 'finished' or record.get('timestamp_basis') != 'captured_at_execution' or record.get('timed_out') or record.get('start_error'):
            problems.append(label + ': execution missing/incomplete')
            continue
        if instant(record['started_at']) < instant(declaration['declared_at']): problems.append(label + ': declaration postdates execution')
        if record.get('challenge_plan_sha256') != identity(declaration) or record.get('subject') != subject or record.get('command') != plan['argv']:
            problems.append(label + ': plan/subject/command differs')
        expected = {str((Path(record['cwd']) / n).resolve()): h for n, h in plan['evaluators'].items()}
        if record.get('evaluator_files') != expected: problems.append(label + ': evaluator bytes/inventory changed')
        observed = record.get('test_evidence', {})
        if observed.get('format') != plan['execution']['format'] or observed.get('required_tests') != plan['execution']['required_tests']:
            problems.append(label + ': named protocol changed')
        try:
            raw = Path(record['raw_log_reference']).read_bytes()
            spec = json.loads(Path(record['specification_reference']).read_text())
            if spec.get('challenge_role', 'evaluation') != 'evaluation':
                problems.append(label + ': support command cannot establish mutation detection')
            if sha(raw) != record['raw_log_sha256'] or len(raw) != record['raw_log_bytes'] or identity(spec) != record['specification_sha256']:
                problems.append(label + ': captured raw log/specification changed')
            outcome = 'satisfied_within_scope' if record['exit_code'] == 0 else 'violated'
            qualified = qualify_execution(spec, {'result': outcome, 'log': raw.decode(errors='replace')}, subject.get('revision') or identity(subject))
            if qualified != observed or spec.get('execution') != plan['execution']:
                problems.append(label + ': assertion report differs from captured raw execution')
        except (OSError, KeyError, ValueError, TypeError):
            problems.append(label + ': raw log/specification bytes unavailable')
    tests = lambda record: record.get('test_evidence', {}).get('tests', [])
    if baseline.get('exit_code') != 0 or baseline.get('result') != 'satisfied_within_scope': problems.append('Baseline is not green')
    terminal = {e['name'] for e in tests(mutant) if e.get('status') in ('passed', 'failed')}
    if not set(plan['execution']['required_tests']) <= terminal: problems.append('Mutant has missing/skipped assertions')
    failures = {e['name'] for e in tests(mutant) if e.get('status') == 'failed'}
    intended = failures.intersection(variant['expected_failures'])
    if not intended: problems.append('No intended named assertion failed (compilation/hash/unrelated error is not detection)')
    # Compiler errors/package failures have no named assertion; malformed subject events are never detection.
    if any('Malformed' in d or 'mixed-subject' in d for d in mutant.get('test_evidence', {}).get('diagnostics', [])):
        problems.append('Malformed/mixed-subject output')
    return {'result': 'satisfied_within_scope' if not problems else 'inconclusive', 'detected': not problems,
            'variant': variant_id, 'kind': variant['kind'], 'intended_failures': sorted(intended), 'all_failed_tests': sorted(failures),
            'problems': problems, 'declaration_sha256': identity(declaration), 'baseline_receipt_sha256': identity(baseline),
            'mutant_receipt_sha256': identity(mutant), 'acceptance': 'not_granted',
            'limitation': 'Named assertion failure is observed; review assertion adequacy and causal attribution separately.'}


def index_subject(subject, manifests, branch, *, request_repository=None, job_active=False, warnings=None, scip=None):
    require(subject.get('repository') and re.fullmatch('[0-9a-f]{40}', subject.get('revision', '')) and branch, 'Explicit repository, full commit and branch required')
    require(request_repository == subject['repository'], 'Index status request repository differs from subject (unscoped status is insufficient)')
    exact = [m for m in manifests if m.get('repository', request_repository) == subject['repository'] and m.get('branch') == branch and m.get('commitHash') == subject['revision'] and m.get('active') is True]
    quality = scip or {}
    return {'result': 'satisfied_within_scope' if exact else 'inconclusive', 'subject': subject, 'branch': branch,
            'exact_index_available': bool(exact), 'active_manifests': exact, 'job_active': job_active,
            'next_action': 'Query the exact scoped branch and retain returned locations/commit.' if exact else 'Reconcile active job before another request.' if job_active else 'Expose exact commit in an isolated policy-selected branch, request indexing, and verify full active manifest before semantic reliance.',
            'warnings': warnings or [], 'scip': quality,
            'semantic_coverage_established': False,
            'limitation': 'Index identity only. READY or positive symbol counts do not establish source readability, occurrences, query coverage or complete dispatch.'}
