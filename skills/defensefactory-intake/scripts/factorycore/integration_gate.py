"""Ticket-driven merge planning/admission/reconciliation. No remote merge API calls."""
import copy
import datetime
import os
import re
import subprocess
import time
from .core import require,identity,authorize
from .integration import merge_tree
from .verification import git
from .lifecycle import integrate


def _component_definitions_present(repo, revisions):
    for revision in revisions:
        for name in git(repo,'ls-tree','-r','--name-only',revision).decode().splitlines():
            if name.rsplit('/',1)[-1]=='claims.json':
                return True
            if name.rsplit('/',1)[-1]=='RULES.md':
                try: raw=git(repo,'show',revision+':'+name)
                except subprocess.CalledProcessError: continue
                if b'Grammar: `defensefactory/rules/v1`' in raw:return True
    return False


def _commit(repo, revision):
    require(isinstance(revision,str) and re.fullmatch('[a-f0-9]{40}',revision),'Full immutable commit required')
    require(git(repo,'rev-parse',revision+'^{commit}').decode().strip()==revision,'Commit unavailable')


def prepare_merge(repo,repository,base,head,method='merge'):
    _commit(repo,base);_commit(repo,head)
    require(method in ('merge','squash'),'Unsupported merge strategy; rebase needs a separate correspondence policy')
    tree=merge_tree(repo,base,head)
    if tree['result']!='satisfied_within_scope':return {**tree,'repository':repository,'method':method,'planning_only':True}
    argv=['git','-C',str(repo),'commit-tree',tree['merge_tree'],'-p',base]
    if method=='merge':argv+=['-p',head]
    env=dict(os.environ);env.update({'GIT_AUTHOR_NAME':'Factory merge preview','GIT_AUTHOR_EMAIL':'fixture@example.invalid','GIT_COMMITTER_NAME':'Factory merge preview','GIT_COMMITTER_EMAIL':'fixture@example.invalid','GIT_AUTHOR_DATE':'2000-01-01T00:00:00Z','GIT_COMMITTER_DATE':'2000-01-01T00:00:00Z'})
    r=subprocess.run(argv,input=b'Factory evaluation subject; no branch moved\n',env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
    plan={**tree,'repository':repository,'method':method,'evaluation_revision':r.stdout.decode().strip(),
          'changed_from_candidate':git(repo,'diff','--name-status',head,tree['merge_tree']).decode(),'planning_only':True,
          'note':'Local immutable preview object only; actual integrated commit must be observed separately.'}
    plan['plan_sha256']=identity(plan);return plan


def _validate_plan(repo, plan):
    require(plan.get('plan_sha256')==identity({k:v for k,v in plan.items() if k!='plan_sha256'}),'Merge plan integrity mismatch')
    require(plan.get('method') in ('merge','squash'),'Unsupported planned strategy')
    _commit(repo,plan['base']);_commit(repo,plan['head']);_commit(repo,plan['evaluation_revision'])
    parents=git(repo,'show','-s','--format=%P',plan['evaluation_revision']).decode().split()
    require(parents==([plan['base'],plan['head']] if plan['method']=='merge' else [plan['base']]),'Preview parents mismatch')
    require(git(repo,'rev-parse',plan['evaluation_revision']+'^{tree}').decode().strip()==plan['merge_tree'],'Preview tree mismatch')
    actual=merge_tree(repo,plan['base'],plan['head'])
    require(actual.get('merge_tree')==plan['merge_tree'] and actual.get('candidate_tree')==plan['candidate_tree'],'Merge inputs do not reproduce the plan')


def _fresh(observation, policy, now):
    return isinstance(observation.get('observed_at'),(int,float)) and 0<=now-observation['observed_at']<=policy['max_observation_age_seconds']


def assess_merge(repo,case,actor,policy,plan,verification,observation,now=None,verifier_envelope=None,component_gate=None):
    now=time.time() if now is None else now;authorize(policy,actor,'evaluate_merge',case)
    cfg=policy['integration_cases'][case];require('required_checks' in cfg and (cfg['required_checks'] or cfg.get('no_platform_checks_reason')),'Explicit required platform checks/disposition missing');require(cfg['mode'] in ('demo','protected'),'Unknown integration mode')
    _validate_plan(repo,plan);reasons=[]
    pr=observation.get('pr',{})
    if observation.get('repository')!=cfg['repository'] or plan['repository']!=cfg['repository'] or str(observation.get('number'))!=str(cfg['number']):reasons.append('repository_or_pr_mismatch')
    if not _fresh(observation,policy,now):reasons.append('observation_stale_or_future')
    if pr.get('state')!='OPEN' or pr.get('isDraft') is not False:reasons.append('pr_not_open_ready')
    if pr.get('baseRefOid')!=plan['base'] or pr.get('headRefOid')!=plan['head']:reasons.append('base_or_head_moved; refresh_plan')
    if pr.get('mergeStateStatus')!='CLEAN':reasons.append('platform_mergeability_not_clean')
    if cfg.get('required_review_decision') and pr.get('reviewDecision')!=cfg['required_review_decision']:reasons.append('required_review_missing')
    if cfg['required_checks'] and not (observation.get('api_observation',{}).get('check_runs_available') is True and observation.get('api_observation',{}).get('statuses_available') is True):reasons.append('platform_check_lookup_incomplete')
    if cfg.get('method')!=plan['method']:reasons.append('merge_method_changed')
    execution=verification.get('execution',{});revision=verification.get('subject',{}).get('revision')
    reused=False
    if revision==plan['evaluation_revision']:pass
    elif revision==plan['head'] and cfg.get('reuse_mode')=='exact_tree' and cfg.get('revision_sensitive') is False and plan['merge_tree']==plan['candidate_tree']:reused=True
    else:reasons.append('merge_subject_requires_verification')
    definition_present=_component_definitions_present(repo,(plan['base'],plan['head'],plan['evaluation_revision']))
    if definition_present or cfg.get('component_claims_required') or execution.get('definition_source'):
        valid_gate=(component_gate is not None and component_gate.get('change_gate_sha256')==identity({k:v for k,v in component_gate.items() if k!='change_gate_sha256'}) and component_gate.get('result')=='satisfied_within_scope' and component_gate.get('pr_blocked') is False and component_gate.get('base',{}).get('repository')==cfg['repository'] and component_gate.get('base',{}).get('revision')==plan['base'] and component_gate.get('subject',{}).get('revision')==revision and component_gate.get('subject',{}).get('repository')==cfg['repository'])
        if not valid_gate:reasons.append('component_claim_or_fence_gate_missing_stale_or_blocked')
    if execution.get('candidate')!=revision or verification.get('subject',{}).get('repository')!=cfg['repository']:reasons.append('verification_subject_mismatch')
    for key,actual in [('claim_sha256',execution.get('claim_sha256')),('check_specs_sha256',execution.get('check_specs_sha256')),('evaluator_manifest_sha256',execution.get('evaluator_guard',{}).get('manifest_sha256'))]:
        if cfg.get(key)!=actual:reasons.append(key+'_changed')
    if verification.get('case')!=case or not cfg.get('verification_contract_sha256') or verification.get('contract_sha256')!=cfg['verification_contract_sha256']:reasons.append('verification_contract_or_case_changed')
    if execution.get('result')!='satisfied_within_scope' or execution.get('evaluator_guard',{}).get('result')!='satisfied_within_scope' or not execution.get('obligations') or not execution.get('checks') or any(r.get('result')!='satisfied_within_scope' for r in execution.get('obligations',[])+execution.get('checks',[])):reasons.append('underlying_execution_not_satisfied')
    if verification.get('result')!='satisfied_within_scope' or verification.get('handoff_readiness')!='ready_for_integration_review' or verification.get('obligation_inventory_complete') is not True:reasons.append('verification_not_complete')
    for check in cfg.get('required_checks',[]):
        matches=[r for r in observation.get('check_observations',[]) if r.get('name')==check['name'] and (check.get('app_id') is None or r.get('app_id')==check['app_id']) and r.get('revision')==plan['head']]
        if not matches:reasons.append('required_check_missing:'+check['name']);continue
        # The latest observed run wins; an old success cannot hide a newer failed/pending run.
        latest=max(matches,key=lambda r:(r.get('started_at') or '',r.get('id') or 0))
        if latest.get('status')!='completed' or latest.get('conclusion')!='success':reasons.append('required_check_not_successful:'+check['name'])
    protected=None
    if cfg['mode']=='protected':
        protected=integrate({'revision':revision},execution,policy,actor=actor,case=case,protection=observation.get('protection_observation',{}),approved_claim_sha256=cfg['claim_sha256'],verifier_envelope=verifier_envelope)
        reasons+=protected['blocked_reasons']
    result={'schema_version':1,'stage':'integrate','case':case,'mode':cfg['mode'],'plan':copy.deepcopy(plan),'plan_sha256':plan['plan_sha256'],
            'verification_sha256':identity(verification),'component_gate_sha256':identity(component_gate) if component_gate is not None else None,'observation_sha256':identity(observation),'policy_sha256':identity(policy),
            'result':'inconclusive' if reasons else 'satisfied_within_scope','blocked_reasons':reasons,'ready_for_merge_intent':not reasons,
            'evidence_reuse':'exact_tree_under_explicit_policy' if reused else 'exact_preview_revision','protected_admission':protected,
            'merge_performed':False,'closure_permitted':False,'independence':'same_host_demo' if cfg['mode']=='demo' else 'subject_to_protected_admission',
            'next_action':'Publish/read back admission and request a bound merge intent under existing authority.' if not reasons else 'Resolve listed stale/failed/missing inputs and re-evaluate; no merge.'}
    result['admission_sha256']=identity(result);return result


def merge_intent(repo,admission,verification,observation,policy,actor,authorization_reference,now=None,verifier_envelope=None,component_gate=None):
    require(admission.get('admission_sha256')==identity({k:v for k,v in admission.items() if k!='admission_sha256'}),'Admission changed')
    require(admission.get('ready_for_merge_intent') and admission.get('result')=='satisfied_within_scope','No accepted admission')
    require(admission['policy_sha256']==identity(policy) and admission['verification_sha256']==identity(verification),'Policy or accepted verification changed')
    authorize(policy,actor,'merge',admission['case']);require(authorization_reference,'Existing user/policy merge authority reference required')
    require(admission.get('component_gate_sha256')==(identity(component_gate) if component_gate is not None else None),'Component gate changed after admission')
    fresh=assess_merge(repo,admission['case'],actor,policy,admission['plan'],verification,observation,now,verifier_envelope,component_gate)
    require(fresh['ready_for_merge_intent'],'Fresh pre-merge admission blocked: '+str(fresh['blocked_reasons']))
    cfg=policy['integration_cases'][admission['case']]
    value={'case':admission['case'],'repository':cfg['repository'],'number':cfg['number'],'mode':cfg['mode'],'plan':admission['plan'],
           'admission_sha256':fresh['admission_sha256'],'policy_sha256':identity(policy),'verification_sha256':identity(verification),'authorization_reference':authorization_reference,
           'effect_key':admission['case']+':merge:'+admission['plan_sha256'],'operation':'merge_intent_only','applied':False}
    value['intent_sha256']=identity(value);return value


def reconcile_merge(repo,intent,observation,policy,now=None):
    now=time.time() if now is None else now
    require(intent.get('intent_sha256')==identity({k:v for k,v in intent.items() if k!='intent_sha256'}),'Merge intent changed')
    if intent['policy_sha256']!=identity(policy):return {'result':'inconclusive','action':'hold','reason':'Policy changed; reassess.'}
    require(observation.get('repository')==intent['repository'] and str(observation.get('number'))==str(intent['number']),'Wrong merge observation')
    if not _fresh(observation,policy,now):return {'result':'inconclusive','action':'hold','reason':'Fresh effect readback missing.'}
    pr=observation.get('pr',{});plan=intent['plan'];_validate_plan(repo,plan)
    if pr.get('state')=='MERGED':
        revision=(pr.get('mergeCommit') or {}).get('oid');_commit(repo,revision)
        tree=git(repo,'rev-parse',revision+'^{tree}').decode().strip();parents=git(repo,'show','-s','--format=%P',revision).decode().split()
        expected=[plan['base'],plan['head']] if plan['method']=='merge' else [plan['base']]
        if tree!=plan['merge_tree'] or parents!=expected:return {'result':'inconclusive','action':'hold','reason':'Observed integrated tree or parents differ; re-evaluate actual subject.','integrated_revision':revision}
        return {'schema_version':1,'stage':'integrate','case':intent['case'],'result':'satisfied_within_scope','action':'record_existing_merge','integrated_revision':revision,'integrated_tree':tree,
                'verified_subject':plan['evaluation_revision'],'intent_sha256':intent['intent_sha256'],'mode':intent['mode'],'build_ready_for_declared_policy':True,'closure_permitted':False,
                'limitation':'Exact source correspondence only; artifact build, deployment and deployed confirmation remain later stages.'}
    if pr.get('state')=='CLOSED':return {'result':'inconclusive','action':'stop','reason':'PR closed without observed merge.'}
    if pr.get('state')=='OPEN' and pr.get('headRefOid')==plan['head'] and pr.get('baseRefOid')==plan['base']:
        return {'result':'inconclusive','action':'renew_intent_before_retry','reason':'Fresh read observed no merge. Recheck gates/authority before retrying the same effect key.'}
    return {'result':'inconclusive','action':'hold','reason':'Unknown or moved merge subject; reconcile before retry.'}
