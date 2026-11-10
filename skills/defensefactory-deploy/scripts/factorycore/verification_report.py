"""Combine exact-subject checks and declared scope into a reviewable verification receipt."""
from .core import identity,require
from .e2e import guidance_gate,evaluate_e2e
from .claims import qualify_query


def assemble(contract, execution, guidance, observations, code_evidence):
    require(contract.get('case') and contract.get('subject',{}).get('revision'), 'Ticket case/exact subject required')
    require(contract.get('claim_sha256') and contract.get('evaluator_manifest_sha256') and contract.get('check_specs_sha256'), 'Frozen claim/evaluator/check identities required')
    mismatches=[]
    if execution.get('candidate')!=contract['subject']['revision']:mismatches.append('candidate')
    if execution.get('claim_sha256')!=contract['claim_sha256']:mismatches.append('claim')
    if execution.get('check_specs_sha256')!=contract['check_specs_sha256']:mismatches.append('check_specs')
    if execution.get('evaluator_guard',{}).get('manifest_sha256')!=contract['evaluator_manifest_sha256']:mismatches.append('evaluator')
    if identity(guidance)!=contract.get('guidance_sha256'):mismatches.append('guidance')
    guide=guidance_gate(guidance)
    if guide['guidance_bound'] and guide['applicability']=='not_applicable':
        e2e={'result':'satisfied_within_scope','execution_result':'not_applicable','reason':guidance['reason'],'policy_reference':guidance['policy_reference']}
    elif guide['guidance_bound']:
        e2e=evaluate_e2e(contract['subject']['revision'],guidance['sha256'],contract['required_e2e_gates'],observations)
    else:e2e={'result':'inconclusive','guidance':guide}
    code_policy=contract.get('codeintel_policy',{})
    if code_policy.get('required') is True:
        code={'result':'inconclusive','diagnostics':['Required exact-source CodeIntel receipt missing.']} if not code_evidence else qualify_query(code_evidence,contract['subject'],code_policy.get('required_files',[]))
    else:
        require(code_policy.get('required') is False and code_policy.get('reason'), 'Explicit CodeIntel scope/disposition required')
        code={'result':'satisfied_within_scope','execution_result':'not_applicable_to_declared_scope','reason':code_policy['reason'],'coverage_claimed':False}
    expected_obligations=contract.get('required_obligations',{})
    require(expected_obligations and all(expected_obligations.values()), 'Full required obligation/check map missing')
    obligations=execution.get('obligations',[])
    required_checks={c for ids in expected_obligations.values() for c in ids}
    complete=(len(obligations)==len(expected_obligations) and {o['id'] for o in obligations}==set(expected_obligations) and all(set(o.get('checks',[]))==set(expected_obligations[o['id']]) for o in obligations) and len(execution.get('checks',[]))==len(required_checks) and {c['id'] for c in execution.get('checks',[])}==required_checks)
    outcomes=[execution['result'],e2e['result'],code['result']]
    if not complete:outcomes.append('inconclusive')
    overall='stale' if mismatches else 'violated' if 'violated' in outcomes else 'satisfied_within_scope' if all(r=='satisfied_within_scope' for r in outcomes) else 'inconclusive'
    return {'schema_version':1,'case':contract['case'],'stage':'verify','subject':contract['subject'],'contract_sha256':identity(contract),
            'execution_sha256':identity(execution),'execution':execution,'guidance':guidance,'e2e':e2e,'codeintel':code,'identity_mismatches':mismatches,'obligation_inventory_complete':complete,
            'result':overall,'handoff_readiness':'ready_for_integration_review' if overall=='satisfied_within_scope' else 'blocked',
            'next_action':'Publish/read back this receipt; evaluate integration policy on the actual merge subject.' if overall=='satisfied_within_scope' else 'Refresh exact subjects and rerun affected checks.' if mismatches else 'Return confirmed failed obligations to repair; retain counterexamples.' if overall=='violated' else 'Complete the recorded missing execution or evidence; do not advance.',
            'independence':execution.get('independence','unverified'),'acceptance':'Reviewable same-host evidence; no independent acceptance, merge, deployment or closure authority is granted.'}
