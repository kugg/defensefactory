"""Portable evidence bundles: validate transitive execution dependencies, not just tar hashes."""
import gzip
import io
import json
from pathlib import Path,PurePosixPath
import re
import tarfile
from .core import canonical,identity,sha,require,GateError
from .check_results import qualify_execution


def _path(name):
    p=PurePosixPath(name)
    require(name and not p.is_absolute() and '..' not in p.parts and str(p)==name, 'Unsafe archive member path')
    return name


def _resource_type(raw, kind):
    """A finished capture cannot evade dependency verification by changing its label."""
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError):
        return
    if isinstance(value, dict) and value.get('execution_state') == 'finished' and all(
            key in value for key in ('raw_log_reference', 'specification_reference', 'specification_sha256')):
        require(kind == 'execution_receipt',
                'Finished execution must use execution_receipt, including failed/inconclusive runs; '
                'a diagnostic label cannot omit its raw log, specification or evaluator dependencies')


def prepare_bundle(plan, output):
    require(plan.get('case') and plan.get('attempt') and plan.get('subject'), 'Case/attempt/exact subject required')
    resources=plan.get('resources',[]);require(resources,'Explicit required resource inventory missing')
    payloads={};entries={};executions={}
    def add(identifier, path, kind, digest=None):
        require(identifier not in entries, 'Duplicate resource identity')
        p=Path(path);require(p.is_file() and not p.is_symlink(), 'Required resource bytes missing/nonregular: '+identifier)
        raw=p.read_bytes();require(digest is None or sha(raw)==digest,'Required resource changed: '+identifier)
        name='resources/'+str(len(entries)).zfill(4)+'/'+re.sub('[^A-Za-z0-9_.-]','_',p.name)[:70]
        payloads[name]=raw;entries[identifier]={'id':identifier,'kind':kind,'archive_path':name,'sha256':sha(raw),'bytes':len(raw),'original_path':str(p)}
        return raw
    for resource in resources:
        raw = add(resource['id'],resource['path'],resource['kind'],resource.get('sha256'))
        _resource_type(raw, resource['kind'])
    expected_executions={}
    for resource in resources:
        if resource['kind']!='execution_receipt':continue
        identifier=resource['id'];record=json.loads(payloads[entries[identifier]['archive_path']])
        require(record.get('execution_state')=='finished', 'Execution receipt is incomplete')
        expected_subject=resource.get('subject',plan['subject']);require(record['subject']==expected_subject,'Execution subject differs from declared requirement for '+identifier+'; use resource.subject for explicitly historical/comparison evidence, or select the correct receipt. Never relabel an execution.')
        expected_executions[identifier]=expected_subject
        log_id=identifier+':raw-log';add(log_id,record['raw_log_reference'],'raw_log',record['raw_log_sha256'])
        spec_id=identifier+':specification';spec_path=resource.get('specification_path') or record.get('specification_reference')
        require(spec_path,'Exact command specification bytes missing')
        spec_raw=add(spec_id,spec_path,'command_specification');spec=json.loads(spec_raw)
        require(identity(spec)==record['specification_sha256'],'Command specification differs from captured execution')
        evaluators={}
        for number,(original,digest) in enumerate(sorted(record.get('evaluator_files',{}).items())):
            source=record.get('captured_evaluator_files',{}).get(original,{}).get('path',original)
            key=identifier+':evaluator:'+str(number);add(key,source,'evaluator',digest);evaluators[original]=key
        context={}
        for name,captured in record.get('captured_context_files',{}).items():
            key=identifier+':context:'+name;add(key,captured['path'],'execution_context',captured['sha256']);context[name]=key
        for name in ('stage_start','challenge_plan'):
            require((name+'_sha256' in spec)==(name in context), 'Execution context bytes missing: '+name)
        executions[identifier]={'receipt':identifier,'log':log_id,'specification':spec_id,'evaluators':evaluators,'context':context}
    requirements={'case':plan['case'],'attempt':plan['attempt'],'subject':plan['subject'],
                  'required_resources':list(entries),'executions':expected_executions}
    manifest={**{k:plan[k] for k in ('case','attempt','subject')},'schema_version':1,'resources':list(entries.values()),'executions':executions}
    payloads['bundle-manifest.json']=canonical(manifest)
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w',format=tarfile.USTAR_FORMAT) as archive:
        for name,raw in sorted(payloads.items()):
            info=tarfile.TarInfo(name);info.size=len(raw);info.mode=0o600;archive.addfile(info,io.BytesIO(raw))
    raw=gzip.compress(stream.getvalue(),mtime=0)
    checked=verify_bundle(raw,requirements);require(checked['bundle_complete'], 'Prepared bundle is incomplete: '+str(checked['problems']))
    target=Path(output);target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb') as out:out.write(raw)
    target.chmod(0o600)
    return {'result':'recorded','file':str(target),'bytes':len(raw),'sha256':sha(raw),'requirements':requirements,
            'bundle_complete':True,'stage_readiness':'not_evaluated','closure_permitted':False,
            'next_action':'Review/redact for sharing, attach bundle and external requirements through ticket, then retrieve and verify both.'}


def verify_bundle(raw, requirements):
    problems=[];manifest=None
    try:
        require(isinstance(raw,bytes) and len(raw)<=128*1024*1024,'Bundle missing or exceeds compressed size budget')
        require(requirements.get('required_resources') and all(k in requirements for k in ('case','attempt','subject','executions')), 'Ticket-bound bundle requirements missing')
        with tarfile.open(fileobj=io.BytesIO(raw),mode='r:*') as archive:
            members=archive.getmembers();require(len(members)<=4096,'Archive member budget exceeded')
            require(sum(m.size for m in members)<=256*1024*1024,'Unpacked byte budget exceeded')
            require(any(m.name=='bundle-manifest.json' for m in members),'Machine bundle manifest missing; use bundle-prepare, not a hand-written tar or outer hash as a complete handoff')
            require(all(m.isfile() for m in members),'Archive links/directories/devices are not evidence bytes')
            names=[_path(m.name) for m in members];require(len(names)==len(set(names)),'Duplicate archive member')
            require('bundle-manifest.json' in names,'Machine bundle manifest missing')
            manifest=json.loads(archive.extractfile('bundle-manifest.json').read())
            for key in ('case','attempt','subject'):require(manifest.get(key)==requirements[key],'Bundle '+key+' mismatch')
            entries=manifest.get('resources',[]);require(entries and len({e['id'] for e in entries})==len(entries),'Empty/duplicate resource inventory')
            index={e['id']:e for e in entries};require(set(requirements['required_resources'])<=set(index),'Required resource omitted from bundle')
            declared=[e['archive_path'] for e in entries];require(len(declared)==len(set(declared)),'Resource aliases an archive member')
            require(set(declared)|{'bundle-manifest.json'}==set(names),'Missing or undeclared member bytes')
            contents={}
            for entry in entries:
                content=archive.extractfile(_path(entry['archive_path'])).read()
                require(len(content)==entry['bytes'] and sha(content)==entry['sha256'],'Resource byte mismatch: '+entry['id'])
                _resource_type(content, entry['kind'])
                contents[entry['id']]=content
            graphs=manifest.get('executions',{})
            execution_ids={e['id'] for e in entries if e['kind']=='execution_receipt'}
            require(execution_ids==set(graphs)==set(requirements['executions']),'Execution dependency inventory missing or changed')
            for identifier in execution_ids:
                graph=graphs[identifier];require(graph['receipt']==identifier,'Execution receipt binding changed')
                record=json.loads(contents[identifier]);require(record.get('execution_state')=='finished','Execution incomplete')
                require(record['subject']==requirements['executions'][identifier],'Execution target mismatch')
                log=contents[graph['log']];require(sha(log)==record['raw_log_sha256'] and len(log)==record['raw_log_bytes'],'Captured raw log omitted/changed')
                spec=json.loads(contents[graph['specification']]);require(identity(spec)==record['specification_sha256'],'Captured specification omitted/changed')
                require(spec['subject']==record['subject'] and spec['argv']==record['command'],'Command/source correspondence changed')
                require(spec.get('evaluator_files',{})==record.get('evaluator_files',{}),'Specification/evaluator inventory mismatch')
                if record.get('schema_version',0)>=2:
                    outcome='unsupported' if record.get('start_error') else 'inconclusive' if record.get('timed_out') else 'satisfied_within_scope' if record.get('exit_code')==0 else 'violated'
                    qualified=qualify_execution(spec,{'result':outcome,'log':log.decode(errors='replace')},record['subject'].get('revision') or identity(record['subject']))
                    require(qualified==record.get('test_evidence'),'Named assertion report differs from captured raw log/specification')
                require(set(graph['evaluators'])==set(record.get('evaluator_files',{})),'Required evaluator source omitted')
                for original,digest in record.get('evaluator_files',{}).items():
                    key=graph['evaluators'][original];require(index[key]['kind']=='evaluator' and sha(contents[key])==digest,'Evaluator source bytes missing/changed')
                context=graph.get('context',{})
                require(set(context)==set(record.get('captured_context_files',{})), 'Execution context inventory missing/changed')
                for name in ('stage_start','challenge_plan'):
                    require((name+'_sha256' in spec)==(name in context), 'Execution context omitted: '+name)
                    if name in context:
                        value=json.loads(contents[context[name]])
                        require(identity(value)==spec[name+'_sha256']==record.get(name+'_sha256'), 'Execution context binding differs: '+name)
    except (GateError,KeyError,ValueError,TypeError,OSError,tarfile.TarError,AttributeError) as error:problems.append(str(error))
    return {'result':'satisfied_within_scope' if not problems else 'inconclusive','bundle_complete':not problems,
            'problems':problems,'stage_readiness':'not_evaluated','closure_permitted':False,
            'limitation':'Completeness/correspondence for declared resources, not authenticated authority, dependency availability or an executed sandbox replay.'}
