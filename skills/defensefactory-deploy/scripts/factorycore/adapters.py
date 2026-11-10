"""Explicit task-supplied adapter protocol; no built-in application defaults."""
import json
import datetime
import os
import uuid
from pathlib import Path
import subprocess
from .core import require, sha, canonical


def invoke_adapter(manifest, inputs):
    entry=Path(manifest['entrypoint']).resolve()
    require(entry.is_file() and not Path(manifest['entrypoint']).is_symlink(),'Adapter source must be a regular retrieved resource')
    require(sha(entry.read_bytes())==manifest['sha256'],'Adapter source digest mismatch')
    argv=[str(entry) if part=='{entrypoint}' else part for part in manifest['argv']]
    require(str(entry) in argv,'Adapter invocation must name the verified source')
    require(0<manifest.get('timeout_seconds',0)<=600,'Adapter timeout missing/out of bounds')
    require(manifest.get('evidence_directory'), 'Adapter evidence directory required before execution')
    evidence=Path(manifest['evidence_directory']).resolve()
    evidence.mkdir(mode=0o700,parents=True,exist_ok=True)
    require(evidence.stat().st_uid==os.getuid() and evidence.stat().st_mode & 0o777==0o700, 'Adapter evidence directory must be owner-private')
    attempt=evidence/uuid.uuid4().hex;attempt.mkdir(mode=0o700)
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    def retain(stdout,stderr,code,timed_out):
        files={}
        for name,raw in [('stdout.raw',stdout),('stderr.raw',stderr)]:
            path=attempt/name
            with path.open('xb') as stream:
                os.chmod(path,0o600);stream.write(raw)
            files[name]={'path':str(path),'sha256':sha(raw),'size':len(raw),'privacy':'Private raw evidence; review/redact and attach before downstream handoff'}
        record={'argv':argv,'adapter_sha256':manifest['sha256'],'input_sha256':sha(canonical(inputs)),'started_at':started,'finished_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'exit_code':code,'timed_out':timed_out,'files':files}
        path=attempt/'execution.json';path.write_bytes(canonical(record));os.chmod(path,0o600)
        return record
    try:
        process=subprocess.run(argv,input=canonical(inputs),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=manifest['timeout_seconds'],cwd=manifest.get('cwd'))
    except OSError as exc:
        return {'result':'unsupported','reason':'adapter_start_failed','execution':retain(b'',str(exc).encode(),None,False)}
    except subprocess.TimeoutExpired as exc:
        return {'result':'inconclusive','reason':'adapter_timeout','execution':retain(exc.stdout or b'',exc.stderr or b'',None,True)}
    execution=retain(process.stdout,process.stderr,process.returncode,False)
    require(len(process.stdout)<=2*1024*1024,'Adapter output exceeds declared protocol limit')
    try:output=json.loads(process.stdout)
    except (ValueError,UnicodeError):
        return {'result':'inconclusive','reason':'adapter_did_not_return_JSON','execution':execution,'exit_code':process.returncode,'stdout_sha256':sha(process.stdout),'stderr_sha256':sha(process.stderr)}
    return {'result':output.get('result','inconclusive') if process.returncode==0 else 'inconclusive','adapter_sha256':manifest['sha256'],'execution':execution,'exit_code':process.returncode,'output':output,'stderr_sha256':sha(process.stderr),'authority':'Environment/tool permissions remain external; adapter inputs do not grant powers.'}
