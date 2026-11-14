"""Explicit host release, deployed confirmation and invoked maintenance contracts."""
import copy
from .core import require,identity,authorize
from .lifecycle import deployment_event,confirm,maintain


def admit_release(case,actor,policy,integration,build,units,claims,fences,deployment_binding):
    authorize(policy,actor,'build',case);authorize(policy,actor,'deploy',case)
    cfg=policy['release_cases'][case]
    require(cfg['mode']=='demo','Protected/production platform qualification is a separate capability; no fallback to demo')
    require(integration.get('result')=='satisfied_within_scope' and integration.get('integrated_revision')==build.get('source'),'Accepted integrated source/build correspondence missing')
    require(build.get('artifact_sha256') and build.get('build',{}).get('result')=='satisfied_within_scope','Identified successful artifact build required')
    from .deployment_contract import validate_binding
    validate_binding(deployment_binding,build['source'])
    require(units and set(units)==set(cfg['units']),'Declared rollout units differ from authority')
    require(claims and fences,'Claim/fence identities must follow the artifact')
    for name,unit in units.items():require(unit.get('configuration_sha256') and unit.get('binding') and unit.get('evidence_reference'),'Configuration/binding/evidence locator required for '+name)
    r={'schema_version':1,'stage':'deploy','case':case,'mode':'demo','source':build['source'],'artifact_sha256':build['artifact_sha256'],'integration_sha256':identity(integration),'build_sha256':identity(build),'deployment_binding_sha256':deployment_binding['deployment_binding_sha256'],'units':copy.deepcopy(units),'claim_ids':list(claims),'fence_ids':list(fences),'policy_sha256':identity(policy),'rollout_performed':False,'result':'satisfied_within_scope','closure_permitted':False}
    r['release_sha256']=identity(r);return r


def validate_release(release):
    require(release.get('release_sha256')==identity({k:v for k,v in release.items() if k!='release_sha256'}),'Release contract changed');return release


def record_rollout(release,current,event,rollback_release=None):
    validate_release(release);require(event.get('unit') in release['units'],'Unit outside declared rollout scope')
    target=release
    if rollback_release is not None:
        validate_release(rollback_release);require(event.get('kind')=='rolled_back' and rollback_release['case']==release['case'] and event['unit'] in rollback_release['units'],'Rollback outside admitted scope');target=rollback_release
    expected=target['units'][event['unit']]
    require(event.get('artifact_sha256')==target['artifact_sha256'] and event.get('configuration_sha256')==expected['configuration_sha256'],'Artifact/configuration substitution; a different rollback subject requires its own admitted release')
    return deployment_event(current,event)


def confirm_release(release,rollout,observations,now,max_age):
    validate_release(release);require(max_age>0,'Confirmation freshness policy missing');rows=[]
    for unit,expected in release['units'].items():
        observation=observations.get(unit);reasons=[]
        if observation:
            if observation.get('source')!=release['source']:reasons.append('source_mismatch')
            if not observation.get('evidence'):reasons.append('raw_observation_evidence_missing')
        accepted={'artifact_sha256':release['artifact_sha256'],'configuration_sha256':expected['configuration_sha256'],'claim_sha256':identity({'claims':release['claim_ids'],'fences':release['fence_ids'],'source':release['source']}),'binding':expected['binding']}
        result=confirm(accepted,rollout,{unit:observation} if observation else {},[unit],now=now,max_age=max_age)['units'][0]
        if reasons:result={**result,'result':'violated' if 'source_mismatch' in reasons else 'inconclusive','reasons':reasons}
        rows.append(result)
    complete=bool(rows) and all(r['result']=='satisfied_within_scope' for r in rows)
    r={'schema_version':1,'stage':'confirm','case':release['case'],'release_sha256':release['release_sha256'],'source':release['source'],'artifact_sha256':release['artifact_sha256'],'units':rows,'complete':complete,'result':'satisfied_within_scope' if complete else 'violated' if any(x['result']=='violated' for x in rows) else 'inconclusive','confirmed_units':[x['unit'] for x in rows if x['result']=='satisfied_within_scope'],'observed_at':now,'observations_sha256':identity(observations),'closure_permitted':False,'scope':'Declared demo rollout units only; a finding transition remains a separate authorized native operation.'}
    r['confirmation_sha256']=identity(r);return r


def release_identities(release):
    return {'source':release['source'],'artifact':release['artifact_sha256'],'configuration':identity(release['units']),'claim':identity(release['claim_ids']),'fence':identity(release['fence_ids']),'policy':release['policy_sha256']}


def maintain_release(release,rollout,current,records,exceptions,counterexamples,now,existing_actions=None):
    validate_release(release);require(records,'No retained evidence; maintenance cannot infer green from an empty ledger')
    expected=release_identities(release);freshness=maintain(current,records,exceptions,[],now=now);actions=[]
    if current!=expected:actions.append({'action':'reverify','reason':'Release identities drifted; retain old evidence.'})
    for name in release['units']:
        if rollout.get('units',{}).get(name,{}).get('status')!='deployed':actions.append({'action':'reverify','unit':name,'reason':'Unit missing, stopped or rolled back; prior confirmation is not current.'})
    covered={unit for r in records for unit in r.get('units',[])}
    for unit in set(release['units'])-covered:actions.append({'action':'reverify','unit':unit,'reason':'No retained confirmation for declared unit.'})
    for record in records:
        if record.get('identities')!=current:actions.append({'action':'reverify','evidence_id':record.get('id'),'reason':'Full source/artifact/configuration/claim/fence/policy identities differ.'})
    for r in freshness['evidence']:
        if r['result']!='satisfied_within_scope':actions.append({'action':'reverify','evidence_id':r['evidence_id'],'reason':r['result'],'invalidated_by':r['invalidated_by']})
    existing_actions=existing_actions or {}
    for c in counterexamples:
        require(c.get('claim_id') in release['claim_ids'] and c.get('fence_id') in release['fence_ids'] and c.get('evidence'),'Counterexample lacks scoped claim/fence/evidence')
        key=release['case']+':'+c['claim_id']+':'+c['fence_id']
        if not any(a.get('effect_key')==key for a in actions):actions.append({'action':'reuse_corrective_work' if key in existing_actions else 'create_corrective_work','effect_key':key,'existing':existing_actions.get(key),'evidence':c['evidence'],'route':'Finding intake/repair under normal developer ownership; source only from the ticket, no unsupervised scan.'})
    result='violated' if counterexamples or freshness['result']=='violated' else 'inconclusive' if actions or freshness['result']!='satisfied_within_scope' else 'satisfied_within_scope'
    return {'schema_version':1,'stage':'maintain','case':release['case'],'release_sha256':release['release_sha256'],'result':result,'freshness':freshness,'actions':actions,'counterexamples':counterexamples,'scheduled':False,'compromise_inferred_from_expiry':False,'authority':'Action plan only. The invoked agent reconciles native tickets/PRs and verifies action receipts; fixtures do not create real security findings.'}
