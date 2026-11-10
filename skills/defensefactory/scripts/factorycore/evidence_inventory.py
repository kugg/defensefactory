"""Inventory declared evidence roots and observable tool calls; never infer working memory."""
import json
from pathlib import Path
import shlex
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from .core import canonical, identity, require, sha
from .evidence_records import dependency, now, replay_comparison, write_json


def public_value(value):
    """Remove common protocol credentials; caller still reviews project-specific secrets."""
    sensitive={'authorization','cookie','password','token','secret','apikey','api_key'}
    if isinstance(value,dict):
        if str(value.get('name','')).lower() in sensitive and 'value' in value:
            return {**value,'value':'[REDACTED]'}
        return {k:'[REDACTED]' if k.lower() in sensitive else public_value(v) for k,v in value.items()}
    if isinstance(value,list):return [public_value(v) for v in value]
    if isinstance(value,str):
        try:
            parsed=json.loads(value)
        except ValueError:parsed=None
        if isinstance(parsed,(dict,list)):
            clean=public_value(parsed)
            if clean!=parsed:return json.dumps(clean)
        def url(match):
            original=match.group(0)
            try:
                p=urlsplit(original);items=parse_qsl(p.query,keep_blank_values=True)
                clean=[(k,'REDACTED' if any(s in k.lower() for s in ('signature','token','credential')) else v) for k,v in items]
                return original if clean==items else urlunsplit((p.scheme,p.netloc,p.path,urlencode(clean),p.fragment))
            except ValueError:return original
        cleaned=re.sub(r'https?://[^\s\"\x27<>]+',url,value)
        return re.sub(r'\b([A-Z_]*(?:TOKEN|SECRET|PASSWORD|API_KEY))=([^\s]+)',r'\1=[REDACTED]',cleaned)
    return value


def record_kind(raw):
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError):
        return 'evidence_file', None
    if not isinstance(value, dict):
        return 'evidence_file', value
    if 'execution_state' in value and 'specification_sha256' in value:
        return ('execution_receipt' if value['execution_state'] == 'finished' else 'execution_attempt'), value
    return {'saved_comparison': 'comparison_receipt', 'artifact_binding': 'artifact_binding',
            'bundle_artifact_reference':'artifact_binding_reference',
            'saved_observation': 'observation_receipt'}.get(value.get('record_type'), 'evidence_file'), value


def scan_roots(roots):
    roots = [Path(r).resolve() for r in roots]
    require(roots and all(r.is_dir() for r in roots), 'Existing evidence roots required')
    require(all(a != b and a not in b.parents and b not in a.parents for i,a in enumerate(roots) for b in roots[i+1:]), 'Evidence roots must not overlap')
    result = []
    for root in roots:
        for path in sorted(root.rglob('*')):
            require(not path.is_symlink(), 'Evidence symlink requires an explicit byte snapshot: ' + str(path))
            if path.is_file():
                raw = path.read_bytes()
                kind, _ = record_kind(raw)
                result.append({'path': str(path), 'sha256': sha(raw), 'bytes': len(raw), 'kind': kind})
    require(len(result) <= 10000, 'Evidence inventory exceeds bounded file count; use a narrower evidence root')
    return result


def observed_tools(raw, workspace, opening=None, cache_directory=None, capture_loader=None, evidence_root=None):
    """Conservative shell classification. Compound commands never earn guarded credit."""
    prefix = raw[:raw.rfind(b'\n')+1] if raw and not raw.endswith(b'\n') else raw
    tools, problems, records = [], [], []
    seen_captures=set()
    package = Path(opening['scope']['package']) if opening else None
    for number, line in enumerate(prefix.splitlines()):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError:
            problems.append('Non-JSON log line ' + str(number+1))
            continue
        if not isinstance(event, dict) or event.get('type') != 'tool_use':
            continue  # Private reasoning and narrative are not exported.
        part = event.get('part', {}); state = part.get('state', {})
        item = public_value({'event_index': number, 'event_id':part.get('id', 'line:'+str(number)), 'timestamp': event.get('timestamp'), 'tool': part.get('tool'),
                'status': state.get('status'), 'input': state.get('input', {}),
                'output': state.get('output'), 'error': state.get('error')})
        metadata = state.get('metadata', {})
        if metadata.get('truncated'):
            item['response_truncated'] = True
            cache = metadata.get('outputPath')
            if cache_directory is not None and isinstance(cache,str) and Path(cache).is_file() and not Path(cache).is_symlink():
                snapshot = Path(cache_directory) / ('tool-'+str(number)+'.response')
                original=Path(cache).read_bytes()
                try:
                    parsed=json.loads(original);clean=public_value(parsed)
                    snapshot.write_bytes(original if clean==parsed else canonical(clean))
                except (ValueError,UnicodeError):snapshot.write_bytes(public_value(original.decode(errors='replace')).encode())
                snapshot.chmod(0o600)
                dep = dependency('full-response', snapshot, 'tool_response')
                dep['source_path'] = cache
                dep['original_sha256'] = sha(original)
                dep['redacted'] = snapshot.read_bytes()!=original
                item['evidence_dependencies'] = [dep]
            else:
                problems.append('Truncated tool response is missing its cache snapshot: '+str(number))
        classification = 'native_tool_snapshot'
        if item['tool'] in ('bash', 'shell', 'exec_command'):
            command = item['input'].get('command', item['input'].get('cmd', ''))
            try:
                lexer = shlex.shlex(command, posix=True, punctuation_chars=';&|<>')
                lexer.whitespace_split = True
                argv = list(lexer)
            except ValueError:
                argv = []
            compound = any(a in (';', '&&', '||', '|', '>', '>>', '<', '&') for a in argv)
            script_index = 1 if argv and Path(argv[0]).name.startswith('python') else 0
            script = Path(argv[script_index]) if len(argv)>script_index else None
            expected = package / 'scripts/stage-exec.py' if package else None
            if (not compound and script is not None and package and script.is_absolute()
                    and script.resolve().parent==(package/'scripts').resolve() and '--help' in argv):
                classification='prerequisite_read_snapshot'
            elif (not compound and script is not None and expected is not None
                    and script.is_absolute() and script.resolve() == expected.resolve()):
                classification = 'guarded_command'
                try:
                    output_arg = argv[argv.index('--output')+1]
                    if evidence_root:
                        output_arg = output_arg.replace('${DEFENSEFACTORY_EVIDENCE_ROOT}', str(evidence_root)).replace('$DEFENSEFACTORY_EVIDENCE_ROOT', str(evidence_root))
                    output = Path(output_arg)
                    if not output.is_absolute():
                        output = Path(workspace) / output
                    receipt = output.resolve() / 'execution.json'
                    try:
                        value = json.loads(capture_loader(str(receipt)) if capture_loader else receipt.read_bytes())
                    except (OSError,ValueError):
                        receipt = output.resolve() / 'admission-failure.json'
                        value = json.loads(capture_loader(str(receipt)) if capture_loader else receipt.read_bytes())
                        require(value.get('record_type')=='stage_admission_failure', 'No saved admission rejection')
                        classification = 'guarded_rejection'
                    require(value.get('stage_start_sha256') == identity(opening), 'Opening differs')
                    require(argv[argv.index('--id')+1]==value.get('check_id'), 'Capture check ID differs')
                    if '--' in argv and classification != 'guarded_rejection':
                        spec_path=value['specification_reference']
                        spec=json.loads(capture_loader(spec_path) if capture_loader else Path(spec_path).read_bytes())
                        require(argv[argv.index('--')+1:]==spec.get('invoker_argv',spec['argv']), 'Captured producer differs from observed argv')
                    require(str(receipt) not in seen_captures, 'Capture reused by multiple tool calls')
                    seen_captures.add(str(receipt))
                    item['capture_reference'] = str(receipt)
                except (ValueError, OSError, IndexError, KeyError):
                    classification = 'capture_missing_or_unbound'
            elif not compound and argv and Path(argv[0]).name in ('cat','ls','pwd','rg','find','head','tail'):
                classification = 'prerequisite_read_snapshot'
            elif (not compound and script is not None and package and script.is_absolute()
                    and script.resolve().parent == (package / 'scripts').resolve()
                    and script.name in ('evidence-compare.py','handoff-audit.py','codeintel-api.py','ticket-transfer.py','restore-artifact.py')):
                classification = 'evidence_helper'
            elif (not compound and script is not None and package and script.is_absolute()
                    and script.resolve()==(package/'scripts/stage.py').resolve()
                    and len(argv)>script_index+1 and argv[script_index+1] in
                    ('--describe','stage-scope','stage-start','mutation-plan','mutation-result','codeintel-index-subject',
                     'evidence-record','ticket-snapshot','source-resolve','publication-verify','bundle-prepare','bundle-verify',
                     'runtime-plan','runtime-result','codeintel-index-observation','source-export',
                     'ledger-parse','ledger-prepare','ledger-check','ledger-reconcile')):
                classification = 'evidence_helper'
            else:
                classification = 'unreviewed_shell_command'
        item['classification'] = classification
        if classification in ('unreviewed_shell_command','capture_missing_or_unbound'):
            problems.append('Unbound/unreviewed tool event ' + str(number))
        tools.append({'event_index':number,'tool':item['tool'],'classification':classification,
                      **({'capture_reference':item['capture_reference']} if item.get('capture_reference') else {})})
        records.append(item)
    return {'record_type':'tool_observations','captured_at':now(),'raw_prefix_sha256':sha(prefix),
            'raw_prefix_bytes':len(prefix),'private_reasoning_exported':False,'share_review_required':True,'events':records,
            'parse_problems':[p for p in problems if not p.startswith('Unbound/unreviewed')]}, tools, problems


def inventory(roots, output, *, events=None, workspace=None, opening=None, requirements=None, finalized=False):
    root = Path(output).resolve()
    require(all(root != Path(r).resolve() and Path(r).resolve() not in root.parents for r in roots),
            'Write the handoff snapshot OUTSIDE its evidence roots')
    root.mkdir(parents=True, exist_ok=False, mode=0o700)
    files = scan_roots(roots)
    observations, tools, problems = None, [], []
    if events is None:
        problems.append('Observable tool-event stream not supplied')
    else:
        observations, tools, problems = observed_tools(Path(events).read_bytes(), workspace, opening, root, evidence_root=roots[0])
        # Dependency edges belong on the snapshot itself, not hidden inside event prose.
        observations['evidence_dependencies'] = [{**d,'name':'full-response-'+str(i)} for i,d in enumerate(
            d for event in observations['events'] for d in event.get('evidence_dependencies',[]))]
        write_json(root / 'tool-observations.json', observations)
        files.append({**dependency('tool-observations', root / 'tool-observations.json'), 'kind':'tool_observations'})
    comparisons = {}
    for file in files:
        _,value=record_kind(Path(file['path']).read_bytes())
        if isinstance(value,dict) and value.get('record_type')=='saved_comparison':
            comparisons[value['id']]={'path':file['path'],'result':value['result']}
    requirements = requirements or {}
    result = {'record_type':'handoff_inventory','schema_version':2,'captured_at':now(),
              'roots':[str(Path(r).resolve()) for r in roots], 'files':files,
              'observed_tools':tools,'comparisons':comparisons,'requirements':requirements,
              'opening':opening,'workspace':str(Path(workspace or '.').resolve()),
              'evidence_roots_complete':True,'capture_adherence':'incomplete' if problems else 'satisfied_within_observed_prefix',
              'trace_finalized':finalized,'snapshot_handoff_ready':not problems,
              'whole_attempt_handoff_ready':not problems and finalized,'problems':problems,
              'limitation':'Declared roots and observed event prefix only. Undisclosed files, arbitrary external tools and private working memory are not observable. No authenticated isolation/acceptance.'}
    checked=verify_inventory(result, lambda p:Path(p).read_bytes(), check_saved=False)
    result.update(checked, capture_adherence='incomplete' if checked['problems'] else 'satisfied_within_observed_prefix')
    write_json(root / 'inventory.json', result)
    return result


def verify_inventory(inv, read_file, check_saved=True, depth=0):
    """Recheck saved requirements from archived bytes, without consulting the old host."""
    require(inv.get('record_type')=='handoff_inventory', 'Not a handoff inventory')
    problems=[];values=[];observations=None
    for file in inv['files']:
        raw=read_file(file['path'])
        require(sha(raw)==file['sha256'] and len(raw)==file['bytes'], 'Inventoried evidence changed')
        _,value=record_kind(raw)
        if isinstance(value,dict):
            values.append((file,value))
            if value.get('record_type')=='tool_observations':observations=value
    if observations is None:
        problems.append('Observable tool-event stream not supplied')
        tools=[]
    else:
        synthetic=[]
        for event in observations['events']:
            synthetic.append({'type':'tool_use','timestamp':event.get('timestamp'),
                'part':{'id':event.get('event_id'),'tool':event['tool'],'state':{'input':event['input'],'output':event.get('output'),
                                                 'status':event.get('status'),'error':event.get('error')}}})
        _,tools,tool_problems=observed_tools(b''.join(canonical(e) for e in synthetic), inv['workspace'],
            inv.get('opening'), capture_loader=read_file, evidence_root=inv['roots'][0])
        problems.extend(tool_problems)
        problems.extend(observations.get('parse_problems',[]))
        require([t['classification'] for t in tools]==[t['classification'] for t in inv['observed_tools']],
                'Saved tool classifications differ from command replay')
    refs={t.get('capture_reference') for t in tools}
    comparisons={};executions={};artifacts={}
    for file,value in values:
        if value.get('execution_state') and file['path'] not in refs:
            problems.append('Uncorrelated capture: '+file['path'])
        if value.get('record_type')=='saved_comparison':
            require(value['id'] not in comparisons, 'Ambiguous comparison ID')
            actual=replay_comparison(value,{d['name']:read_file(d['path']) for d in value['evidence_dependencies']})
            comparisons[value['id']]=actual
        if value.get('execution_state')=='finished':executions.setdefault(value['check_id'],[]).append(value)
        if value.get('record_type') in ('artifact_binding','bundle_artifact_reference'):
            from .artifact_binding import validate_use
            validate_use(value, lambda d:read_file(d['path']),depth)
            artifacts.setdefault(value['artifact']['name'],[]).append(value)
    requirements=inv.get('requirements',{})
    if not requirements.get('scope_reference') or not all(k in requirements for k in ('comparison_ids','assertion_checks','artifact_subjects')):
        problems.append('Ticket-backed handoff requirements not supplied')
    for name in requirements.get('comparison_ids',[]):
        if comparisons.get(name,{}).get('result')!='satisfied_within_scope':problems.append('Missing comparison: '+name)
    for name,names in requirements.get('assertion_checks',{}).items():
        candidates=executions.get(name,[])
        if len(candidates)!=1:
            problems.append('Missing/ambiguous assertion check: '+name);continue
        record=candidates[0];spec=json.loads(read_file(record['specification_reference']))
        if (spec.get('execution',{}).get('format')!='process-assertions-v1' or record['result']!='satisfied_within_scope'
                or not set(names)<=set(spec['execution'].get('required_tests',[]))):problems.append('Unsatisfied process assertion: '+name)
    for name,subject in requirements.get('artifact_subjects',{}).items():
        matches=artifacts.get(name,[])
        if len(matches)!=1 or matches[0]['subject']!=subject:problems.append('Artifact subject/binding missing: '+name)
    if inv.get('schema_version',1) >= 2:
        from .codeintel_gate import check as check_codeintel
        scoped = inv.get('opening',{}).get('scope',{}).get('codeintel_requirement',{})
        if scoped.get('required') and requirements.get('codeintel',{}).get('disposition') != 'required':
            problems.append('Required CodeIntel work from the published scope was downgraded/skipped')
        problems.extend(check_codeintel(requirements.get('codeintel'),observations or {},
            [(f['path'],v) for f,v in values],read_file,inv.get('opening',{}).get('scope',{}).get('subject')))
        from .runtime_plan import outcomes
        for f,v in values:
            if v.get('record_type')=='stage_admission_failure' and any(d['name']=='requested-assertions' for d in v.get('evidence_dependencies',[])):
                for execution in executions.get(v['check_id'],[]):
                    spec=json.loads(read_file(execution['specification_reference']))
                    if spec['execution'].get('format') != 'process-assertions-v1':
                        problems.append('Runtime assertions dropped after a preserved rejection: '+v['check_id'])
        declarations={identity(v):v for f,v in values if v.get('record_type')=='runtime_plan'}
        for declaration in declarations.values():
            verdict=outcomes(declaration,inv['opening'],[v for f,v in values if v.get('execution_state')],read_file)
            problems.extend(verdict['problems'])
        exported=set()
        for f,v in values:
            if v.get('record_type')=='source_export' and v.get('result')=='recorded':
                for dep in v.get('evidence_dependencies',[]):
                    raw=read_file(dep['path'])
                    require(sha(raw)==dep['sha256'] and len(raw)==dep['bytes'], 'Exported source dependency changed')
                exported.update(v['revisions'].values())
        expected=set(requirements.get('source_revisions',[]))
        for f,v in values:
            if v.get('record_type')=='mutation_plan':
                expected.update(p['subject']['revision'] for p in v['plan']['variants'] if p['subject'].get('revision'))
        for revision in sorted(expected-exported):
            problems.append('Local challenge source objects not exported: '+revision)
    ready=not problems
    whole=ready and inv.get('trace_finalized') is True
    if check_saved:
        require(inv.get('snapshot_handoff_ready')==ready and inv.get('whole_attempt_handoff_ready')==whole,
                'Saved handoff readiness differs from replayed evidence')
    return {'snapshot_handoff_ready':ready,'whole_attempt_handoff_ready':whole,'problems':problems}
