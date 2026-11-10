"""Integration admission, deployment correspondence and manual evidence maintenance."""
from .core import require, identity, authorize
from .signatures import verify_signed


def integrate(subject, verification, policy, *, actor, case, protection, approved_claim_sha256, verifier_envelope=None):
    authorize(policy,actor,'evaluate_merge',case)
    reasons=[]
    verifier=policy.get('verifier',{})
    if verifier_envelope is None or not verifier.get('public_key') or not verifier.get('isolation_evidence'):
        reasons.append('authenticated_isolated_verifier_missing')
    else:
        signed=verify_signed(verifier_envelope,verifier['public_key'],expected_actor=verifier['actor'],expected_subject=subject['revision'])
        require(signed['receipt'].get('verification_sha256')==identity(verification), 'Signed verifier result differs')
        require(verifier['public_key']!=policy.get('repair_public_key'), 'Repair key cannot self-approve')
    if verification.get('candidate')!=subject['revision']:reasons.append('merge_subject_changed; reevaluate')
    if verification.get('claim_sha256')!=approved_claim_sha256:reasons.append('claim_changed')
    if verification.get('result')!='satisfied_within_scope':reasons.append('required_obligations_not_satisfied')
    if verification.get('independence')!='protected_independent':reasons.append('independent_acceptance_missing')
    if not protection.get('required_checks') or not protection.get('enforced') or protection.get('bypass_allowed') is not False:reasons.append('protected_policy_unverified_or_bypassable')
    return {'schema_version':1,'stage':'integrate','subject':subject,'result':'inconclusive' if reasons else 'satisfied_within_scope','blocked_reasons':reasons,'merge_permitted':not reasons and 'merge' in policy['actors'][actor]['operations'],'policy_sha256':identity(policy)}


def deployment_event(current, event):
    """Replay from ticket receipts. Duplicate/out-of-order callbacks cannot advance rollout."""
    state=dict(current);state['units']={k:dict(v) for k,v in current.get('units',{}).items()};state['events']=dict(current.get('events',{}))
    require(event.get('id') and event.get('unit') and event.get('sequence',0)>0, 'Deployment callback identity/order missing')
    digest=identity(event)
    if event['id'] in state['events']:
        require(state['events'][event['id']]==digest,'Callback id collision')
        return state
    unit=state['units'].get(event['unit'],{})
    if event['sequence']<=unit.get('sequence',0):
        state['events'][event['id']]=digest
        return state
    require(event['kind'] in ('deployed','rolled_back','failed'), 'Unknown rollout callback')
    state['units'][event['unit']]={'sequence':event['sequence'],'artifact_sha256':event['artifact_sha256'],'configuration_sha256':event['configuration_sha256'],'status':event['kind'],'confirmation_valid':False}
    state['events'][event['id']]=digest
    return state


def confirm(accepted, rollout, observations, required_units, *, now, max_age):
    results=[]
    for unit in required_units:
        state=rollout.get('units',{}).get(unit);obs=observations.get(unit)
        if not state or not obs:
            results.append({'unit':unit,'result':'inconclusive','reason':'rollout_or_observation_missing'});continue
        identities=(state['artifact_sha256']==accepted['artifact_sha256']==obs.get('artifact_sha256') and state['configuration_sha256']==accepted['configuration_sha256']==obs.get('configuration_sha256') and obs.get('claim_sha256')==accepted['claim_sha256'])
        fresh=0<=now-obs['observed_at']<=max_age
        binding=obs.get('binding')==accepted.get('binding') and obs.get('control_active') is True
        checks=obs.get('negative_pass') is True and obs.get('positive_pass') is True
        result='violated' if not identities or not binding or not checks else 'stale' if not fresh or state['status']=='rolled_back' else 'inconclusive' if state['status']!='deployed' else 'satisfied_within_scope'
        results.append({'unit':unit,'result':result,'identity_matches':identities,'binding_matches':binding,'behavior_passes':checks,'fresh':fresh})
    complete=bool(results) and all(r['result']=='satisfied_within_scope' for r in results)
    return {'schema_version':1,'stage':'confirm','result':'satisfied_within_scope' if complete else 'violated' if any(r['result']=='violated' for r in results) else 'inconclusive','units':results,'complete':complete,'confirmed_units':[r['unit'] for r in results if r['result']=='satisfied_within_scope']}


def closure(policy, *, actor, case, confirmation, scope, architectural_open):
    authorize(policy,actor,'request_closure',case)
    require(confirmation.get('complete') and confirmation.get('result')=='satisfied_within_scope', 'Missing deployed confirmation')
    require(set(confirmation['confirmed_units'])==set(scope), 'Confirmation scope incomplete')
    return {'operation':'request_linear_transition','case':case,'occurrence':'eligible_under_policy','architectural_completion':not architectural_open,'remaining_architectural_obligations':architectural_open,'applied':False}


INVALIDATING_FIELDS=('source','claim','evaluator','profile','dependency','artifact','configuration','trust_binding','target','policy')


def maintain(current, evidence, exceptions, counterexamples, *, now):
    decisions=[]
    for record in evidence:
        changed=[k for k in INVALIDATING_FIELDS if record.get('identities',{}).get(k)!=current.get(k)]
        expired=now>=record['expires_at']
        state='stale' if changed or expired else record['result']
        decisions.append({'evidence_id':record['id'],'result':state,'invalidated_by':changed+(['expiry'] if expired else []),'action':'reassess' if state=='stale' else 'retain'})
    expired=[e for e in exceptions if now>=e['expires_at']]
    return {'schema_version':1,'stage':'maintain','result':'violated' if any(r['result']=='violated' for r in decisions) else 'inconclusive' if any(r['result']!='satisfied_within_scope' for r in decisions) or expired else 'satisfied_within_scope',
            'evidence':decisions,'expired_exceptions':expired,'counterexamples':counterexamples,'new_variant_route':'assessment','scheduled':False,'compromise_inferred_from_expiry':False}


def benchmark(runs, protocol):
    require(protocol.get('frozen_before_runs') and protocol.get('subjects') and protocol.get('budget') and protocol.get('thresholds'), 'Predeclared experiment protocol missing')
    require(all(r['subject'] in protocol['subjects'] and r['cost']>=0 and r['result'] in ('accepted','rejected','failed','timed_out','unsupported','inconclusive') for r in runs), 'Run outside frozen experiment')
    accepted=[r for r in runs if r['result']=='accepted']
    return {'runs':len(runs),'accepted':len(accepted),'acceptance_rate':len(accepted)/len(runs) if runs else None,'total_cost':sum(r['cost'] for r in runs),'cost_per_accepted':sum(r['cost'] for r in runs)/len(accepted) if accepted else None,'results':runs,'protocol_sha256':identity(protocol)}
