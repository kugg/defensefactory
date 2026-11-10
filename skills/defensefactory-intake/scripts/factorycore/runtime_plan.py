"""Frozen local-artifact probes: setup is separate, runtime criteria cannot be downgraded."""
import json
from pathlib import Path
from .core import require, identity, sha
from .check_results import validate_protocol, qualify_execution
from .evidence_records import now


def selected_subject(opening, comparison=None):
    if comparison is None:
        return opening['scope']['subject']
    item = next((c for c in opening['scope'].get('comparisons', []) if c['id'] == comparison), None)
    require(item, 'Publish/read back an opening admitting this comparison before work')
    return item['subject']


def protocol(assertions):
    result = {'format':'process-assertions-v1', 'assertions':assertions,
              'required_tests':[a['name'] for a in assertions]}
    validate_protocol(result)
    return result


def direct_probe(argv):
    require(isinstance(argv,list) and argv and all(isinstance(a,str) and a for a in argv), 'Direct runtime argv required')
    shells = {'sh','bash','zsh','dash'}
    require(not any(Path(a).name in shells and any(
        f == '-c' or (f.startswith('-') and not f.startswith('--') and 'c' in f)
        for f in argv[i+1:i+3]) for i,a in enumerate(argv)),
        'Separate fixture setup from the direct runtime producer; do not remove assertions to run an inline shell')


def validate_requirement(policy, scope):
    require(type(policy.get('required')) is bool and policy.get('reference'), 'Runtime requirement needs governing reference and boolean')
    probes = policy.get('probes', [])
    require(isinstance(probes,list) and (not policy['required'] or probes)
            and len({p['id'] for p in probes}) == len(probes), 'Required runtime probes must be explicit and unique')
    comparisons = {p['id'] for p in scope.get('comparisons',[])}
    for p in probes:
        require(p.get('id') and p.get('artifacts') and p.get('assertions')
                and all(isinstance(n,str) and n for n in [*p['artifacts'],*p['assertions']])
                and len(set(p['artifacts'])) == len(p['artifacts'])
                and len(set(p['assertions'])) == len(p['assertions']), 'Runtime obligation needs artifact and assertion names')
        require(not p.get('comparison_id') or p['comparison_id'] in comparisons, 'Runtime obligation comparison is not admitted')


def scoped_probe(opening, probe):
    policy = opening['scope'].get('runtime_requirement', {})
    for required in policy.get('probes',[]):
        if required['id'] != probe['id']: continue
        require(probe.get('comparison_id') == required.get('comparison_id')
                and set(probe['artifacts']) == set(required['artifacts'])
                and set(required['assertions']) <= {a['name'] for a in probe['assertions']}, 'Runtime probe differs from published obligation')


def scoped_coverage(opening, declarations):
    policy = opening.get('scope',{}).get('runtime_requirement',{})
    if not policy.get('required'): return []
    problems = []
    for required in policy['probes']:
        matches = [p for d in declarations for p in d['probes'] if p['id'] == required['id']]
        if len(matches) != 1: problems.append('Required runtime probe missing/ambiguous in declarations: '+required['id']); continue
        try: scoped_probe(opening,matches[0])
        except ValueError as error: problems.append(str(error)+': '+required['id'])
    return problems


def declare(opening, probes, reference):
    require(opening.get('stage_execution_permitted') is True and reference and probes, 'Opened scope and ticket runtime reference required')
    require(len({p['id'] for p in probes}) == len(probes), 'Unique probe IDs required')
    saved = []
    for p in probes:
        require(p.get('id') and p.get('purpose') and p.get('artifacts'), 'Probe needs ID, purpose and sealed artifact names')
        direct_probe(p['argv'])
        require(len(set(p['artifacts'])) == len(p['artifacts']) and all(isinstance(a,str) and a for a in p['artifacts']), 'Unique artifact names required')
        require(all(any('{artifact:'+a+'}' in arg for arg in p['argv']) for a in p['artifacts']), 'Probe argv must consume every sealed artifact')
        scoped_probe(opening, p)
        saved.append({**p, 'subject':selected_subject(opening,p.get('comparison_id')),
                      'execution':protocol(p['assertions'])})
    return {'record_type':'runtime_plan', 'schema_version':1, 'declared_at':now(),
            'stage_start_sha256':identity(opening), 'reference':reference, 'probes':saved,
            'scope':'Actual child status/diagnostics and artifact correspondence; assertion adequacy and causal claims need review.'}


def validate_probe(declaration, spec, opening):
    require(declaration.get('record_type') == 'runtime_plan'
            and declaration['stage_start_sha256'] == identity(opening), 'Runtime declaration/opening differs')
    require(declaration['probes'] and len({p['id'] for p in declaration['probes']})==len(declaration['probes']), 'Ambiguous runtime probe inventory')
    p = next((p for p in declaration['probes'] if p['id'] == spec['id']), None)
    require(p and spec.get('runtime_plan_sha256') == identity(declaration), 'Probe ID/declaration differs')
    scoped_probe(opening, p)
    require(spec['subject'] == p['subject'] == selected_subject(opening,p.get('comparison_id'))
            and spec.get('comparison_id') == p.get('comparison_id'), 'Runtime comparison subject differs')
    require(spec['execution'] == p['execution'] == protocol(p['assertions']), 'Runtime assertions downgraded or changed')
    require(spec.get('invoker_argv',spec['argv']) == p['argv'], 'Runtime argv changed')
    direct_probe(spec['argv'])
    require(set(spec.get('uses_artifacts',{})) == set(p['artifacts']), 'Runtime artifact binding omitted or changed')
    return p


def outcomes(declaration, opening, executions, read_file):
    problems = []
    for p in declaration['probes']:
        found = [e for e in executions if e.get('check_id') == p['id']]
        if len(found) != 1:
            problems.append('Missing/ambiguous runtime probe: '+p['id'])
            continue
        e = found[0]
        try:
            require(e.get('execution_state') == 'finished' and e.get('started_at','') >= declaration['declared_at'], 'Probe missing or predates declaration')
            spec_raw = read_file(e['specification_reference']);spec = json.loads(spec_raw)
            require(identity(spec) == e['specification_sha256'], 'Probe specification changed')
            validate_probe(declaration,spec,opening)
            require(e['subject']==p['subject'] and e['command']==spec['argv'], 'Runtime receipt subject/command differs from its actual specification')
            raw = read_file(e['raw_log_reference'])
            require(sha(raw) == e['raw_log_sha256'] and len(raw) == e['raw_log_bytes'], 'Probe log changed')
            actual = qualify_execution(spec,{'result':e['result'],'log':raw.decode(errors='replace'),
                'exit_code':e.get('exit_code'),'timed_out':e.get('timed_out'),'start_error':e.get('start_error')},p['subject']['revision'])
            require(actual == e.get('test_evidence') and actual['result'] == e['result'] == 'satisfied_within_scope', 'Runtime assertions unsatisfied')
            uses = e.get('artifact_evidence',{}).get('uses',{})
            require(set(uses) == set(p['artifacts']) and all(u['subject'] == p['subject'] for u in uses.values()), 'Runtime artifact provenance incomplete')
        except (ValueError,OSError,KeyError,TypeError) as error:
            problems.append(p['id']+': '+str(error))
    return {'result':'inconclusive' if problems else 'satisfied_within_scope','problems':problems,
            'runtime_plan_sha256':identity(declaration), 'acceptance':'not_granted'}
