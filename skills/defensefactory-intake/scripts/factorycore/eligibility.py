"""Early, scoped assessment dispositions. Trusted policy is supplied by the invoker."""
import re
import subprocess
from .core import authorize, identity, require, GateError, sha
from .registry import source_blob
from .check_results import qualify_execution
from .assessment_resolution import decision_plan


def _attested_reviews(reviews, policy):
    verified=policy.get('verified_scope_reviews',{})
    return [r for r in reviews if r.get('performed_by')==r.get('reviewer') and
            (a:=verified.get(identity(r),{})).get('performed_by')==r.get('performed_by') and
            a.get('authorized_by') and a.get('authorization_reference') and a.get('review_reference')]


def observe(packet, actor):
    """Record applicability evidence without inventing support policy or closure authority."""
    require(packet.get('case') and actor, 'Case and actual performing actor required')
    rows=packet.get('targets',[])
    require(len({r['id'] for r in rows})==len(rows), 'Duplicate observation target')
    evidence={e['id']:e for e in packet.get('evidence',[])}
    require(len(evidence)==len(packet.get('evidence',[])), 'Duplicate evidence')
    for e in evidence.values():require(identity(e['record'])==e['sha256'], 'Corrupt observation evidence')
    results=[]
    for row in rows:
        require(row.get('role') in ('reported_revision','trial_target','comparison_revision','supported_release','deployed_artifact'), 'Explicit revision role required')
        require(row.get('subject') and row.get('reason') in ('active','already_fixed','removed','retired','unknown'), 'Subject and observation required')
        refs=row.get('evidence',[])
        require(refs and all(ref in evidence for ref in refs), 'Observation evidence missing')
        for ref in refs:
            record=evidence[ref]['record']
            require(record.get('target')==row['id'] and record.get('subject')==row['subject'], 'Observation subject mismatch')
            require(record.get('performed_by')==actor and record.get('rationale') and record.get('source_reference'), 'Observation must name its actual performer and source')
        results.append({k:row[k] for k in ('id','subject','role','reason','evidence')})
    return {'schema_version':2,'stage':'assess','case':packet['case'],'performed_by':actor,
            'result':'recorded','observations':results,'closure_permitted':False,
            'disposition_authorized':False,'packet_sha256':identity(packet),
            'next_action':'Recover declared trial/support scope; authorize disposition separately. Continue only already-authorized source investigation.',
            'limitation':'Observations are evidence proposals, not a supported-target inventory or independent review.'}


def _hold(packet, policy, missing):
    return {'schema_version':2,'stage':'assess','case':packet.get('case'),'result':'inconclusive',
            'disposition':'hold','closure_permitted':False,'disposition_authorized':False,
            'missing_inputs':missing,'problems':missing,'continue_targets':[],
            'question_required':True,'question_kind':'target_scope_or_authority','handoff_readiness':'incomplete',
            'allowed_next_actions':['recover_scope_authority','publish_observations','continue_already_authorized_source_investigation'],
            'packet_sha256':identity(packet),'policy_sha256':identity(policy),
            'next_action':'Ask once for the missing scope/authority reference; do not invent a reviewer or promote a comparison ref.'}


def inspect_component(repo, before, after, path):
    """Inspect immutable Git trees; absence is not inferred from a failed read/search."""
    original = source_blob(repo, before, path)
    require(bool(re.fullmatch('[a-f0-9]{40}', after)), 'Full current Git revision required')
    subprocess.check_output(['git','-C',str(repo),'cat-file','-e',after+'^{commit}'], stderr=subprocess.PIPE)
    listing = subprocess.check_output(['git','-C',str(repo),'ls-tree','-r','-z',after], stderr=subprocess.PIPE)
    base = subprocess.check_output(['git','-C',str(repo),'rev-parse',before+':'+path], stderr=subprocess.PIPE).decode().strip()
    entries = [x.split(b'\t',1) for x in listing.split(b'\0') if x]
    paths = [p.decode() for _,p in entries]
    copies = [p.decode() for meta,p in entries if meta.decode().split()[-1] == base and p.decode()!=path]
    diff = subprocess.check_output(['git','-C',str(repo),'diff','--name-status','-z','--find-renames',before,after], stderr=subprocess.PIPE)
    fields = diff.decode().split('\0'); renames=[]; i=0
    while i < len(fields)-1:
        status=fields[i]; i+=1
        if status.startswith(('R','C')):
            old,new=fields[i:i+2]; i+=2
            if old==path:renames.append(new)
        else:i+=1
    return {'before':before,'after':after,'path':path,'original_sha256':sha(original),
            'state':'present' if path in paths else 'relocated' if copies or renames else 'removed',
            'possible_replacements':sorted(set(copies+renames)),
            'limitation':'Git absence does not establish retirement of replacements or deployed releases.'}


def evaluate(packet, policy, actor):
    """Validate evidence correspondence, not the truth of an external reviewer's judgment.

    Evidence records must be recovered by verified ticket references before invocation.
    Authority/scope comes from the trusted invoker, never from the finding packet.
    """
    case=packet.get('case');require(case, 'Case required')
    policy=policy or {}
    if not policy.get('actors') or case not in policy.get('assessment_scopes',{}):
        return _hold(packet,policy,['invoker_scope_and_execution_authority'])
    authorize(policy,actor,'assess',case)
    scope=policy['assessment_scopes'][case]
    if not isinstance(scope,dict):return _hold(packet,policy,['declared_trial_or_supported_target_inventory'])
    required=scope.get('targets',[])
    if not required:return _hold(packet,policy,['declared_trial_or_supported_target_inventory'])
    require(len({t['id'] for t in required})==len(required), 'Duplicate trusted scope target')
    source_only=scope.get('purpose')=='source_assessment'
    declared=required
    if source_only:
        if not scope.get('reference'):return _hold(packet,policy,['authorized_source_scope_reference'])
        required=[t for t in declared if t.get('role')=='trial_target']
        if not required:return _hold(packet,policy,['authorized_trial_target'])
    evidence={}
    for e in packet.get('evidence',[]):
        require(e['id'] not in evidence and identity(e['record'])==e['sha256'], 'Duplicate/corrupt evidence')
        evidence[e['id']]=e
    rows=packet.get('targets',[])
    require(len({r['id'] for r in rows})==len(rows), 'Duplicate target disposition')
    background=[r for r in rows if r['id'] not in {t['id'] for t in required}]
    allowed_background_roles=('reported_revision','comparison_revision','supported_release','deployed_artifact') if source_only else ('reported_revision','comparison_revision')
    require(all(r['id'] in {t['id'] for t in declared} or r.get('role') in allowed_background_roles for r in background), 'Target outside trusted scope')
    if not source_only:require({r['id'] for r in rows} <= {t['id'] for t in required}, 'Target outside trusted scope')
    decisions=[]; problems=[];scope_questions=[]
    for target in required:
        row=next((r for r in rows if r['id']==target['id']),None)
        try:
            require(row is not None, 'Required target missing')
            require(row.get('subject')==target['subject'], 'Target revision/artifact/configuration mismatch')
            reason=row.get('reason'); require(reason in ('active','removed','retired','already_fixed','unknown'), 'Unknown disposition')
            require(reason!='unknown','Applicability unresolved')
            records=[]
            for ref in row.get('evidence',[]):
                require(ref in evidence,'Evidence reference missing')
                record=evidence[ref]['record']
                require(record.get('target')==target['id'] and record.get('subject')==target['subject'], 'Evidence subject mismatch')
                records.append(record)
            require(records,'No target evidence')
            reviews=[r for r in records if r.get('kind')=='scope_review' and r.get('reviewer') in policy.get('assessment_reviewers',[]) and r.get('decision')==reason and r.get('rationale') and r.get('original_report') and r.get('inventory_reference')]
            observations=[r for r in records if r.get('kind')=='applicability_observation' and r.get('performed_by')==actor and r.get('reason')==reason and r.get('rationale') and r.get('source_reference')]
            if reason=='active':
                require(reviews or observations, 'Source applicability evidence missing')
            elif source_only and reason in ('removed','already_fixed'):
                # An authorized source assessor may conclude a bounded source task.
                # This is not a review of all supported/deployed artifacts.
                reviews=observations+_attested_reviews(reviews,policy)
                require(reviews, 'Source applicability evidence missing')
            else:
                if not source_only:
                    if scope.get('complete') is not True or not scope.get('reference'):scope_questions.append('complete_declared_support_scope_reference')
                    require(scope.get('complete') is True and scope.get('reference'), 'Complete declared support scope/reference missing')
                require(target.get('role') in ('trial_target','supported_release','deployed_artifact'), 'Comparison/report revision cannot authorize disposition')
                # Names, connector account identity and delegated execution are not review attestation.
                reviews=_attested_reviews(reviews,policy)
                require(reviews, 'Verified actual-performer review binding missing; do not attribute agent review to invoker')
            if reason=='removed':
                g=row['git']; actual=inspect_component(g['repo'],g['before'],g['after'],g['path'])
                require(g['after']==target['subject']['revision'], 'Removal inspected a different current revision')
                require(actual['state']=='removed', 'Component present/renamed/copied; removal not established')
                if source_only:
                    require(any(isinstance(r.get('replacement_review'),dict) and
                                r['replacement_review'].get('revision')==g['after'] and
                                r['replacement_review'].get('reference') and
                                r['replacement_review'].get('rationale') and
                                isinstance(r['replacement_review'].get('searched_roots'),list) and
                                r['replacement_review']['searched_roots'] and
                                all(isinstance(p,str) and p and not p.startswith('/') and '..' not in p.split('/')
                                    for p in r['replacement_review']['searched_roots']) for r in reviews),
                            'Bounded source replacement review missing; inspect successors in the selected tree')
                else:
                    require(any(r.get('replacement_and_supported_release_review') for r in reviews), 'Replacement/release review missing')
            if reason=='retired':
                require(any(r.get('retirement_authority') and r.get('support_decision')=='excluded_from_scope' and r.get('remaining_risk') for r in reviews), 'Deprecation label is not a retirement decision')
            if reason=='already_fixed':
                require(any(r.get('fix_reference') and r.get('source_analysis') for r in reviews), 'Current fix/source correspondence review missing')
                checks=target.get('required_checks',[])
                require(checks and {'security','positive_behavior','regression'} <= {c['kind'] for c in checks}, 'Fixed disposition requires security/positive/regression checks')
                for check in checks:
                    matches=[r for r in records if r.get('kind')=='check' and r.get('check_id')==check['id'] and r.get('evaluator_sha256')==check['evaluator_sha256']]
                    require(check.get('required_tests'), 'Named test inventory missing from trusted evaluator')
                    require(len(matches)==1, 'Required exact evaluator evidence missing/duplicated')
                    result=matches[0]
                    require(set(check['required_tests']) <= set(result.get('executed_tests',[])) and result.get('command') and result.get('started_at') and result.get('finished_at'), 'Named execution/command/timestamps missing')
                    log=packet.get('raw_logs',{}).get(result.get('raw_log_reference'))
                    require(isinstance(log,str) and sha(log.encode())==result.get('raw_log_sha256'), 'Raw verification log missing/changed')
                    require(result.get('result')=='passed' and result.get('exit_code')==0 and result.get('tests_run',0)>0 and result.get('skipped')==0 and result.get('raw_log_reference') and re.fullmatch('[a-f0-9]{64}',result.get('raw_log_sha256','')), 'Failed/skipped/empty or unlogged verification')
                    require(result.get('timestamp_basis')=='captured_at_execution', 'Reconstructed/mtime timestamps cannot qualify execution')
                    require(check.get('argv') and result['command']==check['argv'], 'Executed command differs from frozen evaluator')
                    protocol={'id':check['id'],'execution':check.get('execution',{})}
                    require(set(check['required_tests'])==set(protocol['execution'].get('required_tests',[])), 'Frozen assertion inventory differs')
                    qualified=qualify_execution(protocol,{'result':'satisfied_within_scope','log':log},target['subject'].get('revision') or identity(target['subject']))
                    require(qualified['result']=='satisfied_within_scope', 'Raw output does not establish named assertions: '+str(qualified.get('diagnostics')))
            decisions.append({'id':target['id'],'reason':reason,'subject':target['subject'],'evidence':row['evidence']})
        except (GateError,KeyError,subprocess.CalledProcessError) as error:
            problems.append({'target':target['id'],'problem':str(error)})
    active=[d for d in decisions if d['reason']=='active']
    action='hold' if problems else 'continue' if active else 'close' if all(d['reason']=='already_fixed' for d in decisions) else 'disqualify'
    hypothetical=packet.get('evaluation_mode')=='hypothetical' or policy.get('evaluation_mode')=='hypothetical'
    proposed_action=action
    if hypothetical:action='hold'
    if source_only and action in ('close','disqualify'):action='stop_source'
    if action in ('close','disqualify'):authorize(policy,actor,action,case)
    plan=decision_plan(packet.get('repair_decisions',[]), 'repair', packet.get('authority_review'))
    repair_blockers=plan['blocking_decisions']
    result={'schema_version':2,'stage':'assess','case':case,'result':'inconclusive' if problems else 'recorded' if hypothetical else 'satisfied_within_scope',
            'disposition':action,'closure_permitted':action in ('close','disqualify'),'scope':required,'target_decisions':decisions,
            'problems':problems,'continue_targets':[d['id'] for d in active], 'packet_sha256':identity(packet),'policy_sha256':identity(policy),
            'question_required':bool(scope_questions or (repair_blockers and active)),'question_kind':'repair_requirements' if repair_blockers and active else 'supported_target_scope' if scope_questions else None,
            'missing_inputs':sorted(set(scope_questions)),
            'handoff_readiness':'incomplete' if problems or hypothetical else 'assessment_required' if active else 'source_disposition_ready_for_publication' if source_only else 'disposition_ready_for_publication',
            'evaluation_mode':'hypothetical' if hypothetical else 'actual','hypothetical_disposition':proposed_action if hypothetical else None,
            'disposition_authorized':not hypothetical and not problems and action not in ('hold','stop_source'),'performed_by':actor,
            'scope_purpose':'source_assessment' if source_only else 'lifecycle_disposition',
            'source_assessment_permitted':bool(active) and not problems and not hypothetical,
            'repair_permitted':False,'repair_contract_blockers':repair_blockers,
            'decision_plan':plan,
            'source_assessment_complete':action=='stop_source' and not problems and not hypothetical,
            'source_disposition':(decisions[0]['reason'] if len({d['reason'] for d in decisions})==1 else 'mixed_nonactive') if action=='stop_source' else None,
            'lifecycle_disposition':'deferred' if source_only else action,
            'background_observations':background if source_only else [],
            'declared_scope':declared,'deferred_lifecycle_targets':[t for t in declared if t.get('role')!='trial_target'] if source_only else [],
            'terminal_disposition_blockers':['source_only_scope_does_not_authorize_lifecycle_transition'] if source_only else [],
            'next_action':'Hypothetical comparison only; recover actual scope before disposition.' if hypothetical else 'Resolve missing/stale applicability evidence.' if problems else 'Continue source assessment; resolve named repair requirements before repair. No lifecycle transition is authorized.' if source_only and active else 'Publish and read back the completed scoped source disposition, then stop this source task. Lifecycle scope/authority is deferred; do not mutate ticket status or ask for unrelated E2E guidance.' if source_only else 'Assess the active targets.' if active else 'Publish disposition and evidence; read back, apply authorized native lifecycle status/reason, read back again, then stop.',
            'limitation':'Correspondence and configured authority checks; external scope reviews and test observations still require substantive review. No lifecycle API was called.'}
    return result
