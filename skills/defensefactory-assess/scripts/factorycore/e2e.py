"""Project-neutral testing-guidance and end-to-end evidence gates."""
import re
from .core import require


def guidance_gate(guidance):
    if guidance and guidance.get('status')=='not_applicable':
        if all(guidance.get(k) for k in ('reason','scope','policy_reference')):
            return {'result':'satisfied_within_scope','guidance_bound':True,'applicability':'not_applicable','question_required':False,'scope':guidance['scope'],'execution_result':'not_applicable'}
    fields=('reference','sha256','scope','environment','journeys','pass_criteria','negative_controls','cleanup','authorized_scope')
    missing=[k for k in fields if not guidance or not guidance.get(k)]
    if guidance and guidance.get('sha256') and not re.fullmatch('[a-f0-9]{64}',guidance['sha256']):missing.append('valid_sha256')
    if not guidance or guidance.get('status')!='provided':missing.append('provided_guidance_or_justified_not_applicable')
    if missing:
        return {'result':'inconclusive','guidance_bound':False,'question_required':True,'missing':sorted(set(missing)),
                'question':'What end-to-end/release testing guidance should this assessment use? Please identify the plan, authorized test environment, real user journey, required success evidence, negative controls and safe cleanup; the currently missing details are: '+', '.join(sorted(set(missing)))+'.',
                'next_action':'Ask the user for the missing guidance, record the question and blocking scope in the ticket, and continue independent source work.'}
    prerequisites=guidance.get('prerequisites',[])
    return {'result':'satisfied_within_scope','guidance_bound':True,'question_required':False,'applicability':'required',
            'reference':guidance['reference'],'sha256':guidance['sha256'],'execution_result':'not_run',
            'execution_readiness':'blocked_by_prerequisites' if prerequisites else 'not_yet_evaluated','prerequisites':prerequisites,
            'note':'A bound plan is not evidence of executed or passing end-to-end tests.'}


def evaluate_e2e(candidate, guidance_sha256, required_gates, observations):
    require(bool(required_gates) and len(required_gates)==len(set(required_gates)), 'Declared required E2E gate identities missing/duplicated')
    require(len({x['id'] for x in observations})==len(observations), 'Duplicate E2E gate observation')
    results=[]
    for gate in required_gates:
        observation=next((x for x in observations if x['id']==gate),None)
        if observation is None:
            results.append({'id':gate,'status':'BLOCKED','reason':'no_execution_record'});continue
        require(observation.get('candidate')==candidate and observation.get('guidance_sha256')==guidance_sha256, 'Mixed E2E candidate or guidance identity')
        require(observation.get('status') in ('PASS','FAIL','BLOCKED'), 'Unknown E2E outcome')
        item=dict(observation)
        if item['status']=='PASS' and (not item.get('evidence') or item.get('stubbed_required_legs') or not item.get('complete_required_scope')):
            item.update(status='BLOCKED',reason='Missing evidence, substituted leg or incomplete required scope')
        results.append(item)
    return {'result':'violated' if any(x['status']=='FAIL' for x in results) else 'satisfied_within_scope' if all(x['status']=='PASS' for x in results) else 'inconclusive',
            'candidate':candidate,'guidance_sha256':guidance_sha256,'end_to_end_verified':all(x['status']=='PASS' for x in results),'gates':results,'production_verified':False}
