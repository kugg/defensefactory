"""Exact-source check execution, frozen evaluator guards and deterministic architecture checks."""
import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import tarfile
import tempfile
import time
from .core import require, sha, identity
from .claims import validate_claim
from .check_results import qualify_execution


def git(repo, *args):
    return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.PIPE)


def tree_files(repo, revision):
    names=git(repo,'ls-tree','-rz','--name-only',revision).split(b'\0')
    return {n.decode():sha(git(repo,'show',revision+':'+n.decode())) for n in names if n}


def evaluator_guard(repo, revision, expected):
    require(bool(expected), 'Frozen evaluator manifest missing')
    files=tree_files(repo,revision)
    changed=[name for name,digest in expected.items() if files.get(name)!=digest]
    return {'result':'violated' if changed else 'satisfied_within_scope','changed_evaluator_files':changed,'manifest_sha256':identity(expected)}


def command(argv, cwd, timeout, *, environment=None):
    require(bool(argv) and 0<timeout<=600, 'Invalid command/budget')
    started=time.time();started_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
    with tempfile.TemporaryFile() as log:
        proc=subprocess.Popen(argv,cwd=cwd,env=environment,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        timed_out=False
        try:
            code=proc.wait(timeout=timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
            timed_out=True
            os.killpg(proc.pid,signal.SIGTERM)
            try:proc.wait(timeout=2)
            except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
            if isinstance(exc,KeyboardInterrupt):raise
            code=proc.returncode
        log.seek(0);raw=log.read()
    return {'argv':argv,'started_at':started_at,'finished_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'exit_code':code,'timed_out':timed_out,'seconds':time.time()-started,
            'result':'inconclusive' if timed_out else 'satisfied_within_scope' if code==0 else 'violated',
            'log':raw.decode(errors='replace'),'log_sha256':sha(raw)}


def verify(repo, revision, claim, checks, evaluator_manifest, *, max_seconds=300, formal_evidence=None, implementation_evidence=None):
    validate_claim(claim)
    require(git(repo,'rev-parse',revision).decode().strip()==revision, 'Use a full exact revision')
    require(claim.get('evaluator_manifest_sha256')==identity(evaluator_manifest), 'Evaluator manifest differs from versioned claim')
    guard=evaluator_guard(repo,revision,evaluator_manifest)
    require(claim.get('check_specs_sha256')==identity(checks), 'Check commands differ from versioned claim')
    required={x for o in claim['obligations'] for x in o['checks']}
    require({c['id'] for c in checks}==required and len(checks)==len(required), 'Required checks missing, duplicated or changed')
    results=[];start=time.time()
    if guard['result']!='satisfied_within_scope':
        return {'stage':'verify','candidate':revision,'claim_sha256':identity(claim),'check_specs_sha256':identity(checks),'result':'violated','evaluator_guard':guard,'checks':[], 'reason':'Evaluator changed; do not execute/accept weakened candidate checks.'}
    with tempfile.TemporaryDirectory(prefix='factory-verifier-') as temp:
        root=Path(temp);archive=root/'source.tar';archive.write_bytes(git(repo,'archive',revision));source=root/'source';source.mkdir()
        with tarfile.open(archive) as tar:tar.extractall(source,filter='data')
        before={str(p.relative_to(source)):sha(p.read_bytes()) for p in source.rglob('*') if p.is_file()}
        for check in checks:
            remaining=max_seconds-(time.time()-start)
            if remaining<=0:
                results.append({'id':check['id'],'result':'inconclusive','reason':'Parent check budget exhausted'})
                continue
            rel=Path(check.get('cwd','.'))
            require(not rel.is_absolute() and '..' not in rel.parts, 'Check working directory escapes subject')
            try:
                env={k:v for k,v in os.environ.items() if k in ('PATH','HOME','TMPDIR','GOPATH','GOCACHE','GOMODCACHE','GOTOOLCHAIN','JAVA_HOME','LANG','LC_ALL')}
                env.update({'PYTHONDONTWRITEBYTECODE':'1','GOWORK':'off','GOFLAGS':'','FACTORY_CANDIDATE_REVISION':revision,'FACTORY_CHECK_ID':check['id']})
                r=command(check['argv'],source/rel,min(check.get('timeout',60),remaining),environment=env)
                qualified=qualify_execution(check,r,revision)
                r={**r,'execution_result':r['result'],'result':qualified['result'],'test_evidence':qualified}
            except OSError as e:
                r={'result':'unsupported','reason':str(e)}
            results.append({'id':check['id'],'cwd':str(rel),**r})
        changed=[name for name,digest in before.items() if not (source/name).is_file() or sha((source/name).read_bytes())!=digest]
        added=[str(p.relative_to(source)) for p in source.rglob('*') if p.is_file() and str(p.relative_to(source)) not in before]
    obligations=[]
    for o in claim['obligations']:
        records=[r for r in results if r['id'] in o['checks']]
        result='violated' if any(r['result']=='violated' for r in records) else 'satisfied_within_scope' if all(r['result']=='satisfied_within_scope' for r in records) else 'inconclusive'
        obligations.append({'id':o['id'],'result':result,'checks':[r['id'] for r in records]})
    formal_required=claim.get('formal',{}).get('required',False)
    formal_model_ok=(formal_evidence is not None and formal_evidence.get('result')=='satisfied_within_scope' and formal_evidence.get('profile_sha256')==claim.get('formal',{}).get('profile_sha256') and formal_evidence.get('source_sha256')==claim.get('formal',{}).get('source_sha256') and formal_evidence.get('legitimate_behavior_reachable') is True and formal_evidence.get('safety',{}).get('result')=='satisfied_within_scope')
    files=tree_files(repo,revision)
    binding_manifest={p:files.get(p) for p in claim['bindings']}
    correspondence_ok=(implementation_evidence is not None and implementation_evidence.get('candidate')==revision and implementation_evidence.get('claim_sha256')==identity(claim) and implementation_evidence.get('bindings')==binding_manifest and all(binding_manifest.values()) and set(implementation_evidence.get('check_ids',[]))==required and all(r['result']=='satisfied_within_scope' for r in results))
    formal_ok=formal_model_ok and correspondence_ok
    overall='violated' if any(o['result']=='violated' for o in obligations) else 'inconclusive' if changed or added else 'satisfied_within_scope' if all(o['result']=='satisfied_within_scope' for o in obligations) else 'inconclusive'
    if (not all(binding_manifest.values()) or (formal_required and not formal_ok)) and overall=='satisfied_within_scope':overall='inconclusive'
    return {'schema_version':1,'stage':'verify','candidate':revision,'claim_sha256':identity(claim),'evaluator_guard':guard,'check_specs_sha256':identity(checks),'binding_manifest':binding_manifest,'definition_source':claim.get('source_definition'),'formal_required':formal_required,'formal_evidence':formal_evidence,'formal_model_satisfied':formal_model_ok,'implementation_evidence':implementation_evidence,'implementation_correspondence_satisfied':bool(correspondence_ok),'formal_satisfied':bool(formal_ok),
            'result':overall,'obligations':obligations,'checks':results,'changed_inputs':changed,'added_inputs':added,
            'independence':'same_host_rehearsal','acceptance':'not_granted_by_runner','toolchain':{'python':os.sys.version},'seconds':time.time()-start}


def architecture_scan(repo, helper, policy):
    p=command(['go','run',str(Path(helper).resolve()),str(Path(repo).resolve())],Path(helper).resolve().parent,60)
    if p['result']!='satisfied_within_scope':
        return {'result':'inconclusive','extraction':p}
    facts=json.loads(p['log']);violations=[]
    for f in facts:
        if policy.get('scope') and f['file'] not in policy['scope']:
            continue
        if f['kind']=='import' and f['value'] in policy.get('forbidden_imports',[]):violations.append(f)
        if f['kind']=='call_syntax' and f['value'] in policy.get('forbidden_calls',[]):violations.append(f)
        if f['kind']=='function' and f['value'] in policy.get('forbidden_functions',[]):violations.append(f)
        if f['kind']=='field:InsecureSkipVerify' and f['value']=='true':violations.append(f)
        if f['kind']=='field:BaseURL' and f['value'].startswith('"http://'):violations.append(f)
    return {'result':'violated' if violations else 'satisfied_within_scope','violations':violations,'facts':facts,
            'policy_sha256':identity(policy),'extractor_sha256':sha(Path(helper).read_bytes()),
            'limits':'Go AST syntax/explicit policy only; semantic dispatch, new parallel mechanisms and nonliteral configuration require semantic/runtime review.'}
