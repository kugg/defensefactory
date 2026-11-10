"""Qualify declared test protocols without assuming the product language/toolchain."""
import json
from .core import require


def validate_protocol(contract):
    """Reject unusable criteria before running a producer, not after its side effects."""
    fmt = contract.get('format')
    if fmt == 'command':
        require(contract.get('reason') and contract.get('success_criteria'),
                'Non-test command needs an explicit reason and success criterion before execution')
    elif fmt == 'process-assertions-v1':
        criteria = contract.get('assertions', [])
        names = contract.get('required_tests', [])
        require(criteria and names and len(set(names)) == len(names)
                and len({c['name'] for c in criteria}) == len(criteria)
                and set(names) == {c['name'] for c in criteria}, 'Frozen named process assertion inventory required')
        for c in criteria:
            require(set(c) <= {'name','exit_code','stdout_contains'} and type(c.get('exit_code')) is int
                    and isinstance(c.get('stdout_contains', []), list)
                    and all(isinstance(s, str) and s for s in c.get('stdout_contains', [])),
                    'Process assertion needs exact exit code and optional literal diagnostics')
    else:
        names = contract.get('required_tests', [])
        require(fmt in ('go-test-json','factory-jsonl-v1') and isinstance(names,list) and names
                and all(isinstance(n,str) and n for n in names) and len(set(names)) == len(names),
                'Supported protocol and nonempty unique required-test inventory needed before execution')


def qualify_execution(check, execution, candidate):
    contract=check.get('execution') or {};fmt=contract.get('format')
    outcome=execution['result'];diagnostics=[];events=[]
    if fmt=='process-assertions-v1':
        assertions = contract.get('assertions', [])
        required = contract.get('required_tests', [])
        require(assertions and len({a['name'] for a in assertions}) == len(assertions)
                and set(required) == {a['name'] for a in assertions}, 'Frozen named process assertion inventory required')
        for criterion in assertions:
            require(set(criterion) <= {'name', 'exit_code', 'stdout_contains'}
                    and type(criterion.get('exit_code')) is int
                    and isinstance(criterion.get('stdout_contains', []), list)
                    and all(isinstance(s, str) and s for s in criterion.get('stdout_contains', [])),
                    'Process assertion needs exact child exit code and optional literal diagnostics')
            passed = (not execution.get('timed_out') and not execution.get('start_error')
                      and execution.get('exit_code') == criterion['exit_code']
                      and all(s in execution.get('log', '') for s in criterion.get('stdout_contains', [])))
            events.append({'name': criterion['name'], 'status': 'passed' if passed else 'failed',
                           'expected_exit_code': criterion['exit_code'], 'actual_exit_code': execution.get('exit_code')})
        return {'result': 'satisfied_within_scope' if all(e['status']=='passed' for e in events) else 'violated',
                'format': fmt, 'required_tests': required, 'tests': events,
                'scope': 'Actual producer exit/diagnostics; evaluator adequacy and artifact provenance remain separate.'}
    if fmt=='command':
        if not contract.get('reason') or not contract.get('success_criteria'):
            diagnostics.append('Non-test command needs an explicit reason and success criterion.')
        return {'result':outcome if not diagnostics or outcome=='violated' else 'inconclusive','format':fmt,
                'diagnostics':diagnostics,'tests':[],'scope':'Exit-status assertion only; no named-test coverage claimed.'}
    required=contract.get('required_tests',[])
    if fmt not in ('factory-jsonl-v1','go-test-json') or not isinstance(required,list) or not required or not all(isinstance(n,str) and n for n in required) or len(set(required))!=len(required):
        return {'result':outcome if outcome=='violated' else 'inconclusive','format':fmt,'tests':[],
                'diagnostics':['Declared output format and unique nonempty required-test inventory are required.']}
    for line in execution.get('log','').splitlines():
        if fmt=='factory-jsonl-v1':
            if not line.startswith('FACTORY_TEST '):continue
            try:
                record=json.loads(line[len('FACTORY_TEST '):])
                require(record.get('candidate')==candidate and record.get('check_id')==check['id'],'Test event subject/check differs')
                require(record.get('status') in ('passed','failed','skipped') and isinstance(record.get('name'),str) and record['name'],'Malformed terminal test event')
                events.append({'name':record['name'],'status':record['status']})
            except (ValueError,TypeError,AttributeError):diagnostics.append('Malformed or mixed-subject test event.')
        else:
            try:record=json.loads(line)
            except ValueError:continue  # Toolchain diagnostic lines remain in the raw log.
            if not isinstance(record,dict):continue
            if record.get('Action')=='fail' and not record.get('Test'):outcome='violated'
            if record.get('Test') and record.get('Action') in ('pass','fail','skip'):
                if not isinstance(record.get('Package'),str) or not isinstance(record.get('Test'),str):diagnostics.append('Go test event lacks package identity.');continue
                events.append({'name':record['Package']+'::'+record['Test'],'status':{'pass':'passed','fail':'failed','skip':'skipped'}[record['Action']]})
    passed={e['name'] for e in events if e['status']=='passed'}
    failed={e['name'] for e in events if e['status']=='failed'}
    skipped={e['name'] for e in events if e['status']=='skipped'}
    missing=sorted(set(required)-passed)
    if missing:diagnostics.append('Required tests did not pass: '+', '.join(missing))
    permitted=contract.get('permitted_skips',{})
    unexplained=sorted(n for n in skipped if not permitted.get(n))
    if unexplained:diagnostics.append('Unexplained skipped tests: '+', '.join(unexplained))
    if not events:diagnostics.append('No terminal test events observed.')
    return {'result':'violated' if failed or outcome=='violated' else 'inconclusive' if diagnostics or outcome!='satisfied_within_scope' else 'satisfied_within_scope',
            'format':fmt,'required_tests':required,'tests':events,'missing_tests':missing,'skipped_tests':sorted(skipped),
            'unexplained_skips':unexplained,'diagnostics':diagnostics,
            'limitation':'Observed output from the frozen check process; it does not authenticate the evaluator or establish independent permissions.'}
