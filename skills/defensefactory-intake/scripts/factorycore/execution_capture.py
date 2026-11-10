"""Capture commands before launch with durable raw output and explicit test protocols."""
import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from .core import require,identity,sha,canonical
from .evidence_records import dependency
from .check_results import qualify_execution, validate_protocol, validate_discovery
from .artifact_binding import prepare_artifacts, finish_artifacts, seal_artifacts


def capture(spec, evidence_directory):
    argv=spec.get('argv');require(isinstance(argv,list) and argv and all(isinstance(x,str) and x for x in argv), 'Direct argv required')
    require(spec.get('subject') and spec.get('id') and spec.get('performed_by'), 'Subject/check/actual performer required')
    require(0<spec.get('timeout_seconds',0)<=600, 'Bounded timeout required')
    require(isinstance(spec.get('environment',{}),dict), 'Environment overrides must be explicit')
    root=Path(evidence_directory).resolve();root.mkdir(parents=True,exist_ok=False,mode=0o700)
    # A new directory is mandatory: failures, partial output and retries cannot overwrite each other.
    def persist(value):
        p=root/'execution.json';tmp=root/'execution.tmp';tmp.write_text(json.dumps(value,indent=2)+'\n');os.chmod(tmp,0o600);tmp.replace(p)
    record={'schema_version':2,'check_id':spec['id'],'subject':spec['subject'],'performed_by':spec['performed_by'],
            'command':argv,'cwd':str(Path(spec['cwd']).resolve()),'specification_sha256':identity(spec),
            'environment_override_sha256':identity(spec.get('environment',{})),
            'evaluator_files':{},'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'timestamp_basis':'captured_at_execution','execution_state':'prepared','exit_code':None,'timed_out':False}
    persist(record)
    specification_path=root/'specification.json';specification_path.write_bytes(canonical(spec));os.chmod(specification_path,0o600)
    record['specification_reference']=str(specification_path)
    record['captured_context_files']={}
    for key in ('stage_start', 'challenge_plan', 'runtime_plan'):
        if key+'_sha256' not in spec:
            continue
        source=Path(spec[key+'_reference'])
        value=json.loads(source.read_text())
        require(identity(value)==spec[key+'_sha256'], 'Changed '+key+' receipt')
        destination=root/(key+'.json');destination.write_bytes(canonical(value));destination.chmod(0o600)
        record[key+'_sha256']=identity(value)
        record['captured_context_files'][key]={'path':str(destination),'sha256':sha(destination.read_bytes())}
    record['captured_evaluator_files']={}
    for name,digest in spec.get('evaluator_files',{}).items():
        p=Path(name)
        if not p.is_file() or sha(p.read_bytes())!=digest:
            record.update(execution_state='preparation_failed',result='violated',reason='Frozen evaluator file mismatch',finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
            persist(record);return record
        record['evaluator_files'][name]=digest
        snapshot=root/'evaluators'/str(len(record['captured_evaluator_files']))/p.name
        snapshot.parent.mkdir(parents=True,mode=0o700);snapshot.write_bytes(p.read_bytes());os.chmod(snapshot,0o600)
        require(sha(snapshot.read_bytes())==digest, 'Evaluator changed during capture')
        record['captured_evaluator_files'][name]={'path':str(snapshot),'sha256':digest}
    try:
        validate_protocol(spec.get('execution', {}))
        validate_discovery(spec, lambda p:Path(p).read_bytes())
        provenance = prepare_artifacts(spec)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        record.update(execution_state='preparation_failed', result='inconclusive', reason=str(error),
                      finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        persist(record)
        return record
    persist(record);started=time.monotonic();proc=None
    try:
        with (root/'output.raw').open('xb') as out:
            os.chmod(root/'output.raw',0o600)
            # No shell or truncating pipe: stdout/stderr go directly to durable bytes from launch.
            proc=subprocess.Popen(argv,cwd=record['cwd'],env={**os.environ,**spec.get('environment',{})},stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
            record.update(pid=proc.pid,execution_state='running');persist(record)
            try:record['exit_code']=proc.wait(timeout=spec['timeout_seconds'])
            except subprocess.TimeoutExpired:
                record['timed_out']=True
                os.killpg(proc.pid,signal.SIGTERM)
                try:proc.wait(timeout=2)
                except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
                record['exit_code']=proc.returncode
    except OSError as exc:record['start_error']=str(exc)
    finally:
        if proc is not None and proc.poll() is None:
            os.killpg(proc.pid,signal.SIGKILL);proc.wait()
        record.update(execution_state='finished',finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-started)
        raw=(root/'output.raw').read_bytes() if (root/'output.raw').exists() else b''
        record.update(raw_log_reference=str(root/'output.raw'),raw_log_sha256=sha(raw),raw_log_bytes=len(raw))
        outcome='unsupported' if 'start_error' in record else 'inconclusive' if record['timed_out'] else 'satisfied_within_scope' if record['exit_code']==0 else 'violated'
        candidate=spec['subject'].get('revision') or identity(spec['subject'])
        qualified=qualify_execution(spec,{'result':outcome,'log':raw.decode(errors='replace'),
            'exit_code':record['exit_code'],'timed_out':record['timed_out'],'start_error':record.get('start_error')},candidate)
        pending_artifacts=[]
        try:
            if spec.get('fixture_reference'):
                from .fixtures import validate_live
                fixture = json.loads(Path(spec['fixture_reference']).read_text())
                opening = json.loads(Path(spec['stage_start_reference']).read_text())
                validate_live(fixture, opening, spec['cwd'])
            record['artifact_evidence'], record['evidence_dependencies'], pending_artifacts = finish_artifacts(spec, provenance, root, record)
        except (OSError, ValueError, subprocess.CalledProcessError) as error:
            record['artifact_error'] = str(error)
            record['evidence_dependencies'] = [dependency('retained-output-'+str(i),p,'unqualified_artifact_payload')
                for i,p in enumerate(sorted((root/'artifacts').glob('*/payload')))]
        overall = qualified['result']
        if record.get('artifact_error') and overall != 'violated':
            overall = 'inconclusive'
        record.update(result=overall,test_evidence=qualified);persist(record)
        seal_artifacts(pending_artifacts,root/'execution.json')
    return record


def assertions(subject, check_id, expectations, observations):
    """Case adapters freeze expectations before execution and retain this declared inventory."""
    require(expectations and len({e['name'] for e in expectations})==len(expectations), 'Unique predeclared assertions required')
    candidate=subject.get('revision') or identity(subject);events=[]
    for expected in expectations:
        require(expected.get('name') and expected.get('field') and 'equals' in expected, 'Explicit assertion criterion required')
        actual=observations.get(expected['field']);passed=expected['field'] in observations and type(actual) is type(expected['equals']) and actual==expected['equals']
        events.append({'candidate':candidate,'check_id':check_id,'name':expected['name'],'status':'passed' if passed else 'failed','actual':actual,'expected':expected['equals']})
    return {'result':'satisfied_within_scope' if all(e['status']=='passed' for e in events) else 'violated',
            'expectations_sha256':identity(expectations),'events':events,
            'limitation':'Adapter must establish endpoint/correlation/readiness and cleanup; observations are not authenticated by assertion formatting.'}
