"""Evidence of actual CodeIntel work, separate from index/semantic coverage claims."""
import json
from pathlib import Path
from .core import require, identity, sha
from .evidence_records import dependency, select, now, strict_json
from .trial_controls import index_subject


def index_observation(subject, branch, request_repository, source_file, pointer, fields=None, activation=None, repository_pointer='/body/id'):
    raw = Path(source_file).read_bytes()
    mapping = fields or ({'branch':'/branch','commitHash':'/commitHash'} if activation else
                        {'branch':'/branch','commitHash':'/commitHash','active':'/active'})
    record = {'record_type':'codeintel_index_observation', 'schema_version':1,
              'subject':subject,'branch':branch,'request_repository':request_repository,
              'manifest_pointer':pointer,'fields':mapping,'captured_at':now(),
              'repository_pointer':repository_pointer,
              'evidence_dependencies':[dependency('status',source_file,'api_observation')]}
    if activation:record['activation']=activation
    result = replay_index(record,raw,check_saved=False)
    record.update(result)
    return record


def replay_index(record, raw, check_saved=True):
    dep = record['evidence_dependencies'][0]
    require(dep['name']=='status' and sha(raw)==dep['sha256'] and len(raw)==dep['bytes'], 'CodeIntel raw status changed')
    status = strict_json(raw)
    values = select(status,record['manifest_pointer'])
    require(isinstance(values,list), 'Select the actual manifest array from the retained raw status')
    manifests = [{k:select(v,p) for k,p in record['fields'].items()} for v in values]
    if record.get('activation'):
        activation=record['activation']
        require(activation.get('mode')=='activated_current' and record['manifest_pointer'].endswith('/currentIndexManifests')
                and set(record['fields'])=={'branch','commitHash'}, 'Use the actual current-manifest collection and supported activation profile')
        usable=select(status,activation['usable_pointer']) is True
        for normalized,original in zip(manifests,values):
            require(all(k in original for k in ('status','activatedAt','supersededAt','failedAt')), 'Activation fields missing from current manifest')
            normalized['active']=(usable and original.get('status')=='READY' and bool(original.get('activatedAt'))
                                  and original.get('supersededAt') is None and original.get('failedAt') is None)
    else:
        require(set(record['fields'])=={'branch','commitHash','active'}, 'Manifest selectors must cover branch, full commit and actual active flag')
    result = index_subject(record['subject'],manifests,record['branch'],
        request_repository=record['request_repository'],job_active=None)
    result['repository_value']=select(status,record['repository_pointer'])
    result.update(job_state_evaluated=False,quality_evaluated=False)
    if not result['exact_index_available']:
        result['next_action']='Inspect actual job/ref/policy status before scheduling; this receipt checks index identity only.'
    if check_saved:
        require(all(record.get(k)==v for k,v in result.items()), 'CodeIntel observation differs from raw manifest replay')
    return result


def _payload(event):
    value = event.get('output')
    if isinstance(value,str):
        try:value=json.loads(value)
        except ValueError:return value
    if isinstance(value,dict) and isinstance(value.get('content'),list):
        texts=[c.get('text','') for c in value['content'] if c.get('type')=='text']
        if value.get('isError'):return {'error':'Native MCP failure'}
        if len(texts)==1:
            try:return json.loads(texts[0])
            except ValueError:return texts[0]
    return value


def check(requirement, observations, records, read_file, subject):
    if not isinstance(requirement,dict):
        return ['CodeIntel disposition missing; available tools do not count as executed work']
    if not requirement.get('reference') or not requirement.get('reason'):
        return ['CodeIntel needs the governing requirement/disposition reference and reason']
    disposition=requirement.get('disposition')
    if disposition=='not_needed':
        return []  # A declared ticket policy, never inferred from skipped work.
    events={e.get('event_id'):e for e in observations.get('events',[]) if 'codeintel' in str(e.get('tool','')).lower()}
    if disposition=='unavailable':
        attempts=[events[k] for k in requirement.get('attempt_event_ids',[]) if k in events]
        apis=[r for path,r in records if path in requirement.get('api_observations',[]) and r.get('record_type')=='api_observation']
        return [] if attempts or apis else ['CodeIntel unavailable is unsupported: no retained discovery/query/API attempt']
    if disposition=='limited':
        attempts=[events[k] for k in requirement.get('attempt_event_ids',[]) if k in events]
        apis=[r for path,r in records if path in requirement.get('api_observations',[]) and r.get('record_type')=='api_observation']
        problems=[]
        if not attempts and not apis:
            problems.append('CodeIntel limitation is unsupported: no retained discovery/query/API attempt')
        if not requirement.get('coverage_limitations'):
            problems.append('CodeIntel limitation needs explicit search/index/SCIP coverage limitations')
        if requirement.get('index_observation'):
            try:
                record=json.loads(read_file(requirement['index_observation']))
                require(record.get('record_type')=='codeintel_index_observation' and record['subject']==subject,
                        'Limited CodeIntel index observation is not bound to the current subject')
                replay_index(record,read_file(record['evidence_dependencies'][0]['path']))
            except (ValueError,OSError,KeyError,TypeError) as error:
                problems.append('CodeIntel limitation index evidence: '+str(error))
        return problems
    if disposition!='required':
        return ['Unknown CodeIntel disposition']
    problems=[]
    try:
        index_path=requirement['index_observation']
        record=json.loads(read_file(index_path))
        require(record.get('record_type')=='codeintel_index_observation' and record['subject']==subject,
                'Exact-current-subject CodeIntel observation required')
        replay_index(record,read_file(record['evidence_dependencies'][0]['path']))
        require(record['exact_index_available'], 'No active exact-source index')
        branch=record['branch']
        require(record['repository_value']==requirement['repository_value'], 'CodeIntel manifest repository differs from actual query repository')
        ids=requirement.get('query_event_ids',[])
        require(ids and len(set(ids))==len(ids), 'Actual scoped CodeIntel query event IDs required')
        for key in ids:
            e=events.get(key)
            require(e and e.get('status')=='completed' and not e.get('error'), 'CodeIntel query missing/failed: '+key)
            # Tool discovery alone cannot stand in for a source query.
            tool=str(e['tool']).lower()
            require(any(n in tool for n in ('grep','search','read_file','definition','reference','caller')), 'CodeIntel event is discovery, not a source query')
            args=e['input']
            require(args.get(requirement['repository_argument'])==requirement['repository_value'], 'CodeIntel query repository is unscoped/different')
            query_ref=args.get(requirement['ref_argument'])
            require(isinstance(query_ref,str) and query_ref.removeprefix('refs/heads/')==branch.removeprefix('refs/heads/'), 'CodeIntel query ref differs from active exact index')
            if e.get('response_truncated'):
                dep=next((d for d in e.get('evidence_dependencies',[]) if d['name']=='full-response'),None)
                require(dep, 'Truncated CodeIntel query has no retained full response')
                full=read_file(dep['path'])
                require(sha(full)==dep['sha256'] and len(full)==dep['bytes'], 'CodeIntel full response changed')
                result=_payload({**e,'output':full.decode()})
            else:
                result=_payload(e)
            require(not (isinstance(result,dict) and (result.get('error') or result.get('isError'))), 'CodeIntel query returned an error')
        require(requirement.get('coverage_limitations') is not None, 'Retain query/SCIP coverage limitations separately')
    except (ValueError,OSError,KeyError,TypeError) as error:
        problems.append('CodeIntel: '+str(error))
    return problems
