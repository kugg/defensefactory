"""Qualify declared test protocols without assuming the product language/toolchain."""
import json
from .core import require


def qualify_execution(check, execution, candidate):
    contract=check.get('execution') or {};fmt=contract.get('format')
    outcome=execution['result'];diagnostics=[];events=[]
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
