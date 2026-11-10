"""Portable evidence bundles: validate transitive execution dependencies, not just tar hashes."""
import gzip
import io
import json
from pathlib import Path,PurePosixPath
import re
import tarfile
from .core import canonical,identity,sha,require,GateError
from .check_results import qualify_execution
from .evidence_records import replay_comparison
from .artifact_binding import validate_binding, validate_use


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
    resources=list(plan.get('resources',[]));inventory=None
    if plan.get('inventory_reference'):
        inventory_raw=Path(plan['inventory_reference']).read_bytes()
        require(sha(inventory_raw)==plan.get('inventory_sha256'), 'Inventory bytes differ from the pinned handoff snapshot')
        inventory=json.loads(inventory_raw)
        require(inventory.get('record_type')=='handoff_inventory', 'Use a generated handoff inventory')
        from .evidence_inventory import scan_roots
        observed={f['path']:(f['sha256'],f['bytes']) for f in scan_roots(inventory['roots'])}
        frozen={f['path']:(f['sha256'],f['bytes']) for f in inventory['files'] if any(Path(r) in Path(f['path']).parents for r in inventory['roots'])}
        require(observed==frozen, 'Evidence roots changed after inventory; retain it and create a new generation')
        existing={str(Path(r['path']).resolve()) for r in resources}
        for number,entry in enumerate(inventory['files']):
            if entry['path'] in existing:continue
            resource={'id':'inventory-file-'+str(number),'path':entry['path'],'sha256':entry['sha256'],'kind':entry['kind']}
            if entry['kind']=='execution_receipt':resource['subject']=json.loads(Path(entry['path']).read_text())['subject']
            resources.append(resource)
        resources.append({'id':'handoff-inventory','path':plan['inventory_reference'],'sha256':plan['inventory_sha256'],'kind':'handoff_inventory'})
    require(plan.get('scope','declared_subset')!='whole_attempt' or inventory is not None, 'Whole-attempt handoff needs a pinned generated inventory')
    require(resources,'Explicit required resource inventory missing')
    payloads={};entries={};executions={};dependency_graph={};pending=[];expected_executions={}
    expected_subjects={r['id']:r.get('subject',plan['subject']) for r in resources}
    def add(identifier,path,kind,digest=None):
        require(identifier not in entries,'Duplicate resource identity')
        p=Path(path);require(p.is_file() and not p.is_symlink(),'Required resource bytes missing/nonregular: '+identifier)
        raw=p.read_bytes();require(digest is None or sha(raw)==digest,'Required resource changed: '+identifier)
        _resource_type(raw,kind)
        name='resources/'+str(len(entries)).zfill(4)+'/'+re.sub('[^A-Za-z0-9_.-]','_',p.name)[:70]
        payloads[name]=raw;entries[identifier]={'id':identifier,'kind':kind,'archive_path':name,'sha256':sha(raw),'bytes':len(raw),'original_path':str(p.resolve())}
        pending.append(identifier)
        return identifier
    def linked(identifier,path,kind,digest=None):
        resolved=str(Path(path).resolve())
        for e in entries.values():
            if e['original_path']==resolved and (digest is None or e['sha256']==digest):
                # A scanned arbitrary file can acquire its stronger dependency role.
                if e['kind']=='evidence_file':e['kind']=kind
                return e['id']
        return add(identifier,path,kind,digest)
    for resource in resources:add(resource['id'],resource['path'],resource['kind'],resource.get('sha256'))
    for identifier in pending:
        raw=payloads[entries[identifier]['archive_path']]
        try:value=json.loads(raw)
        except (ValueError,UnicodeError):continue
        if not isinstance(value,dict):continue
        if entries[identifier]['kind']=='execution_receipt':
            record=value;require(record.get('execution_state')=='finished','Execution receipt is incomplete')
            expected=expected_subjects.get(identifier,record['subject'])
            require(record['subject']==expected,'Execution subject differs from declared requirement for '+identifier)
            expected_executions[identifier]=expected
            log=linked(identifier+':raw-log',record['raw_log_reference'],'raw_log',record['raw_log_sha256'])
            specification=linked(identifier+':specification',record['specification_reference'],'command_specification')
            spec=json.loads(payloads[entries[specification]['archive_path']])
            require(identity(spec)==record['specification_sha256'],'Command specification differs from captured execution')
            evaluators={}
            for n,(original,digest) in enumerate(sorted(record.get('evaluator_files',{}).items())):
                source=record.get('captured_evaluator_files',{}).get(original,{}).get('path',original)
                evaluators[original]=linked(identifier+':evaluator:'+str(n),source,'evaluator',digest)
            context={}
            for name,captured in record.get('captured_context_files',{}).items():
                context[name]=linked(identifier+':context:'+name,captured['path'],'execution_context',captured['sha256'])
            for name in ('stage_start','challenge_plan','runtime_plan'):
                require((name+'_sha256' in spec)==(name in context),'Execution context bytes missing: '+name)
            produced={}
            for name,artifact in record.get('artifact_evidence',{}).get('produced',{}).items():
                if not artifact.get('binding'):continue
                binding=json.loads(Path(artifact['binding']).read_text())
                produced[name]=linked(identifier+':artifact:'+name,artifact['binding'],binding['record_type'])
            executions[identifier]={'receipt':identifier,'log':log,'specification':specification,
                                   'evaluators':evaluators,'context':context,'produced_artifacts':produced}
        declared=value.get('evidence_dependencies',[])
        require(isinstance(declared,list) and len({d['name'] for d in declared})==len(declared),'Duplicate/malformed evidence dependency')
        if declared:dependency_graph[identifier]={}
        for dep in declared:
            key=linked(identifier+':dependency:'+dep['name'],dep['path'],dep.get('kind','evidence_input'),dep['sha256'])
            require(entries[key]['bytes']==dep['bytes'],'Dependency length differs')
            dependency_graph[identifier][dep['name']]=key
        if value.get('execution_state') not in (None,'finished'):
            for label,path in [('specification',value.get('specification_reference')),
                               *[(k,v['path']) for k,v in value.get('captured_context_files',{}).items()]]:
                if path and Path(path).is_file():linked(identifier+':partial:'+label,path,'preparation_dependency')
    requirements={'case':plan['case'],'attempt':plan['attempt'],'subject':plan['subject'],
                  'required_resources':list(entries),'executions':expected_executions}
    if inventory is not None:requirements['inventory']={'resource':'handoff-inventory','sha256':plan['inventory_sha256']}
    manifest={**{k:plan[k] for k in ('case','attempt','subject')},'schema_version':2,
              'resources':list(entries.values()),'executions':executions,'dependencies':dependency_graph}
    payloads['bundle-manifest.json']=canonical(manifest)
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w',format=tarfile.USTAR_FORMAT) as archive:
        for name,raw in sorted(payloads.items()):
            info=tarfile.TarInfo(name);info.size=len(raw);info.mode=0o600;archive.addfile(info,io.BytesIO(raw))
    raw=gzip.compress(stream.getvalue(),mtime=0)
    checked=verify_bundle(raw,requirements);require(checked['bundle_complete'],'Prepared bundle is incomplete: '+str(checked['problems']))
    target=Path(output);external=target.with_name(target.name+'.requirements.json')
    require(not target.exists() and not external.exists(), 'Use new bundle AND machine-requirements paths')
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb') as out:out.write(raw)
    target.chmod(0o600)
    with external.open('xb') as out:out.write(canonical(requirements))
    external.chmod(0o600)
    return {'result':'recorded','file':str(target),'bytes':len(raw),'sha256':sha(raw),'requirements':requirements,
            'external_requirements_file':str(external),'external_requirements_sha256':sha(external.read_bytes()),
            'bundle_complete':True,'stage_readiness':'not_evaluated','closure_permitted':False,
            'whole_attempt_handoff_ready':checked.get('whole_attempt_handoff_ready',False),
            'snapshot_handoff_ready':checked.get('snapshot_handoff_ready',False),
            'handoff_scope':'whole_attempt_snapshot' if inventory is not None else 'declared_subset_only',
            'next_action':'Review/redact for sharing, attach bundle and external requirements through ticket, then retrieve and verify both.'}


def verify_bundle(raw, requirements, _depth=0):
    problems=[];manifest=None;whole=False;snapshot=False
    try:
        require(_depth<4,'Nested artifact bundle depth exceeded; create a fresh direct artifact bundle')
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
                    qualified=qualify_execution(spec,{'result':outcome,'log':log.decode(errors='replace'),
                        'exit_code':record.get('exit_code'),'timed_out':record.get('timed_out'),
                        'start_error':record.get('start_error')},record['subject'].get('revision') or identity(record['subject']))
                    require(qualified==record.get('test_evidence'),'Named assertion report differs from captured raw log/specification')
                    expected_result=qualified['result']
                    if record.get('artifact_error') and expected_result!='violated':expected_result='inconclusive'
                    require(record['result']==expected_result,'Execution result differs from its assertions/artifact qualification')
                require(set(graph['evaluators'])==set(record.get('evaluator_files',{})),'Required evaluator source omitted')
                for original,digest in record.get('evaluator_files',{}).items():
                    key=graph['evaluators'][original];require(index[key]['kind']=='evaluator' and sha(contents[key])==digest,'Evaluator source bytes missing/changed')
                context=graph.get('context',{})
                require(set(context)==set(record.get('captured_context_files',{})), 'Execution context inventory missing/changed')
                for name in ('stage_start','challenge_plan','runtime_plan'):
                    require((name+'_sha256' in spec)==(name in context), 'Execution context omitted: '+name)
                    if name in context:
                        value=json.loads(contents[context[name]])
                        require(identity(value)==spec[name+'_sha256']==record.get(name+'_sha256'), 'Execution context binding differs: '+name)
                produced=record.get('artifact_evidence',{}).get('produced',{})
                if 'runtime_plan' in context:
                    from .runtime_plan import validate_probe
                    validate_probe(json.loads(contents[context['runtime_plan']]),spec,json.loads(contents[context['stage_start']]))
                expected_produced={name for name,a in produced.items() if a.get('binding')}
                require(set(graph.get('produced_artifacts',{}))==expected_produced,'Produced artifact binding omitted')
                for name,key in graph.get('produced_artifacts',{}).items():
                    artifact=json.loads(contents[key])
                    require(artifact['subject']==record['subject'] and artifact['build_specification_sha256']==record['specification_sha256']
                            and artifact['artifact']['sha256']==produced[name]['sha256'],'Produced artifact/build correspondence differs')
            deps=manifest.get('dependencies',{})
            for identifier,raw_value in contents.items():
                try:value=json.loads(raw_value)
                except (ValueError,UnicodeError):continue
                if not isinstance(value,dict):continue
                declared=value.get('evidence_dependencies',[])
                require(set(deps.get(identifier,{}))=={d['name'] for d in declared},'Non-execution evidence dependency omitted: '+identifier)
                def read_dep(dep):
                    key=deps[identifier][dep['name']]
                    data=contents[key]
                    require(sha(data)==dep['sha256'] and len(data)==dep['bytes'],'Evidence dependency changed: '+dep['name'])
                    return data
                for dep in declared:read_dep(dep)
                if value.get('record_type')=='saved_comparison':
                    replay_comparison(value,{d['name']:read_dep(d) for d in declared})
                if value.get('record_type')=='fixture_snapshot':
                    from .fixtures import replay
                    replay(value, read_dep)
                if value.get('record_type')=='handoff_verification':
                    from .handoff_readback import replay
                    replay(value, read_dep, _depth)
                if value.get('discovery_reference'):
                    from .check_results import validate_discovery
                    paths={e['original_path']:contents[e['id']] for e in entries}
                    validate_discovery(value, paths.__getitem__)
                if value.get('record_type')=='artifact_binding':validate_binding(value,read_dep)
                if value.get('record_type')=='bundle_artifact_reference':validate_use(value,read_dep,_depth)
                if value.get('record_type')=='codeintel_index_observation':
                    from .codeintel_gate import replay_index
                    replay_index(value,read_dep(value['evidence_dependencies'][0]))
            if requirements.get('inventory'):
                binding=requirements['inventory'];inventory_raw=contents[binding['resource']]
                require(sha(inventory_raw)==binding['sha256'],'Pinned handoff inventory differs')
                inv=json.loads(inventory_raw);require(inv.get('record_type')=='handoff_inventory','Missing generated handoff inventory')
                for file in inv['files']:
                    require(any(e['original_path']==file['path'] and e['sha256']==file['sha256'] and e['bytes']==file['bytes'] for e in entries),
                            'Inventoried local file omitted from archive: '+file['path'])
                def read_file(path):
                    matches={contents[e['id']] for e in entries if e['original_path']==path}
                    require(len(matches)==1,'Evidence dependency path missing/ambiguous: '+path)
                    return matches.pop()
                from .evidence_inventory import verify_inventory
                checked=verify_inventory(inv,read_file,depth=_depth)
                whole=checked['whole_attempt_handoff_ready'];snapshot=checked['snapshot_handoff_ready']
    except (GateError,KeyError,ValueError,TypeError,OSError,tarfile.TarError,AttributeError) as error:problems.append(str(error))
    return {'result':'satisfied_within_scope' if not problems else 'inconclusive','bundle_complete':not problems,
            'problems':problems,'stage_readiness':'not_evaluated','closure_permitted':False,
            'whole_attempt_handoff_ready':whole and not problems,
            'snapshot_handoff_ready':snapshot and not problems,
            'limitation':'Completeness/correspondence for declared resources, not authenticated authority, dependency availability or an executed sandbox replay.'}
