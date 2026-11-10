"""Manual bounded challenge and replay. No scheduler or background worker."""
import os
from pathlib import Path
import subprocess
import tempfile
import time
from .core import require, identity, sha
from .verification import verify, git
from .lifecycle import maintain


def challenge(repo, revision, claim, checks, evaluator_manifest, patches, *, max_rounds=4, max_seconds=300):
    require(len(patches)<=max_rounds and len({p['id'] for p in patches})==len(patches), 'Challenge budget/identity invalid')
    criteria={}
    for patch in patches:
        obligation=next((o for o in claim['obligations'] if o['id']==patch['expected_obligation']),None)
        selected=[c for c in checks if obligation and c['id'] in obligation['checks']]
        named={n for c in selected for n in c.get('execution',{}).get('required_tests',[])}
        intended=set(patch.get('expected_tests',named))
        require(intended and intended<=named, 'Declare named security/positive failures in the expected obligation')
        criteria[patch['id']]=(selected,named,intended)
    start=time.time();results=[]
    baseline=verify(repo,revision,claim,checks,evaluator_manifest,max_seconds=max_seconds)
    if baseline['result']!='satisfied_within_scope':
        return {'stage':'bounded-challenge','result':'inconclusive','baseline':baseline,'rounds':[],
                'reason':'Untouched candidate must pass before interpreting mutants','seconds':time.time()-start}
    for patch in patches:
        remaining=max_seconds-(time.time()-start)
        if remaining<=0:
            results.append({'id':patch['id'],'result':'inconclusive','detected':False,'reason':'Parent budget exhausted'});continue
        with tempfile.TemporaryDirectory(prefix='factory-challenge-') as tmp:
            clone=Path(tmp)/'candidate';subprocess.run(['git','clone','--no-hardlinks','--quiet',str(Path(repo).resolve()),str(clone)],check=True,stderr=subprocess.PIPE)
            subprocess.run(['git','-C',str(clone),'checkout','--detach','--quiet',revision],check=True,stderr=subprocess.PIPE)
            subprocess.run(['git','-C',str(clone),'apply','--check','-'],input=patch['patch'].encode(),check=True,stderr=subprocess.PIPE)
            subprocess.run(['git','-C',str(clone),'apply','-'],input=patch['patch'].encode(),check=True,stderr=subprocess.PIPE)
            subprocess.run(['git','-C',str(clone),'add','--all'],check=True)
            env=dict(os.environ);env.update({'GIT_AUTHOR_DATE':'2000-01-01T00:00:00Z','GIT_COMMITTER_DATE':'2000-01-01T00:00:00Z'})
            subprocess.run(['git','-C',str(clone),'-c','user.name=Factory challenge fixture','-c','user.email=factory-fixture@example.invalid','commit','--quiet','-m','Challenge '+patch['id']],env=env,check=True,stderr=subprocess.PIPE)
            candidate=git(clone,'rev-parse','HEAD').decode().strip()
            report=verify(clone,candidate,claim,checks,evaluator_manifest,max_seconds=remaining)
            # Detection requires the intended obligation to fail, not an unrelated baseline failure.
            expected=patch['expected_obligation']
            selected,named,intended=criteria[patch['id']]
            observed=[t for c in report.get('checks',[]) if c['id'] in {s['id'] for s in selected} for t in c.get('test_evidence',{}).get('tests',[])]
            failed={t['name'] for t in observed if t['status']=='failed'}
            executed={t['name'] for t in observed if t['status'] in ('passed','failed')}
            detected=bool(intended & failed) and named<=executed and report['evaluator_guard']['result']=='satisfied_within_scope'
            results.append({'id':patch['id'],'base':revision,'candidate':candidate,'patch_sha256':sha(patch['patch'].encode()),'patch':patch['patch'],'expected_obligation':expected,'expected_tests':sorted(intended),'intended_failures':sorted(intended & failed),'detected':detected,'result':'satisfied_within_scope' if detected else 'inconclusive','verification':report})
    return {'schema_version':2,'stage':'bounded-challenge','result':'satisfied_within_scope' if results and all(r['detected'] for r in results) else 'inconclusive','baseline':baseline,'rounds':results,'seconds':time.time()-start,'retained_counterexamples':[r['id'] for r in results if r['detected']],'independence':'same_host_rehearsal'}


def maintenance_pass(current, evidence, exceptions, counterexamples, *, now, repo, revision, claim, checks, evaluator_manifest, max_seconds=300):
    freshness=maintain(current,evidence,exceptions,counterexamples,now=now)
    replay=verify(repo,revision,claim,checks,evaluator_manifest,max_seconds=max_seconds)
    return {'stage':'maintain','freshness':freshness,'replay':replay,'result':replay['result'] if freshness['result']=='satisfied_within_scope' else 'inconclusive' if freshness['result']=='inconclusive' else 'violated','counterexamples':counterexamples,'scheduled':False}
