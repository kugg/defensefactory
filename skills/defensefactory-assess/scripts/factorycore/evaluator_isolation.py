"""Run explicit evaluator adapters in separate clean process contexts and compare them."""
import json
import os
from pathlib import Path
import subprocess

from .core import identity, require
from .evidence_records import now, write_json


def _validate(spec):
    require(isinstance(spec, dict) and spec.get('subject') and isinstance(spec.get('contract'), dict),
            'Exact subject and evaluation contract required')
    obligations=spec['contract'].get('obligations')
    require(isinstance(obligations,list) and obligations and len(set(obligations))==len(obligations),
            'Unique contract obligations required')
    evaluators=spec.get('evaluators')
    require(isinstance(evaluators,list) and len(evaluators)==2, 'Exactly primary and independent evaluator adapters required')
    require({item.get('role') for item in evaluators}=={'primary','independent'},
            'One primary and one independent evaluator required')
    require(len({item.get('identity') for item in evaluators})==2,
            'Independent evaluator must declare a different identity')
    for item in evaluators:
        require(item.get('identity') and isinstance(item.get('argv'),list) and item['argv']
                and all(isinstance(part,str) and part for part in item['argv']),
                'Evaluator identity and direct argv required')
        require(isinstance(item.get('environment',{}),dict) and
                all(isinstance(k,str) and isinstance(v,str) and k and v for k,v in item.get('environment',{}).items()),
                'Evaluator environment must contain explicit nonempty string values')
    require(type(spec.get('timeout_seconds',120)) is int and 1 <= spec.get('timeout_seconds',120) <= 3600,
            'Bounded evaluator timeout required')
    return obligations,evaluators


def _result(raw, obligations):
    value=json.loads(raw)
    require(isinstance(value,dict) and isinstance(value.get('obligations'),dict),
            'Evaluator output needs an obligations object')
    require(set(value['obligations'])==set(obligations), 'Evaluator output differs from frozen obligation inventory')
    for name,row in value['obligations'].items():
        require(isinstance(row,dict) and row.get('result') in
                ('satisfied_within_scope','violated','inconclusive','unsupported')
                and isinstance(row.get('evidence'),list), 'Every obligation needs a result and evidence list')
    return value


def run_isolated(spec, destination):
    """Execute adapters without shell/history/shared cwd and retain agreement/divergence."""
    obligations,evaluators=_validate(spec)
    root=Path(destination).resolve();root.mkdir(parents=True,exist_ok=False,mode=0o700)
    frozen={'subject':spec['subject'],'contract':spec['contract']}
    write_json(root/'evaluation-input.json',frozen)
    records={};problems=[]
    for item in evaluators:
        role=item['role'];work=root/role;work.mkdir(mode=0o700)
        home=work/'home';home.mkdir(mode=0o700)
        environment={'PATH':os.environ.get('PATH','/usr/bin:/bin'),'LANG':'C.UTF-8','LC_ALL':'C.UTF-8',
                     **item.get('environment',{}),'HOME':str(home),
                     'DEFENSEFACTORY_EVALUATION_INPUT':str(root/'evaluation-input.json')}
        started=now()
        try:
            completed=subprocess.run(item['argv'],input=json.dumps(frozen),text=True,cwd=work,
                env=environment,capture_output=True,timeout=spec.get('timeout_seconds',120),check=False)
            (work/'stdout').write_text(completed.stdout);(work/'stderr').write_text(completed.stderr)
            for path in (work/'stdout',work/'stderr'):path.chmod(0o600)
            parsed=_result(completed.stdout,obligations) if completed.returncode==0 else None
            if parsed is None:problems.append(role+': evaluator exited '+str(completed.returncode))
            records[role]={'identity':item['identity'],'argv':item['argv'],'started_at':started,'finished_at':now(),
                'exit_code':completed.returncode,'result':parsed,
                'stdout_reference':str(work/'stdout'),'stderr_reference':str(work/'stderr')}
        except (OSError,subprocess.TimeoutExpired,ValueError,TypeError,json.JSONDecodeError) as error:
            problems.append(role+': '+str(error));records[role]={'identity':item['identity'],'argv':item['argv'],
                'started_at':started,'finished_at':now(),'exit_code':None,'result':None,'error':str(error)}
    comparisons=[]
    if not problems:
        for name in obligations:
            left=records['primary']['result']['obligations'][name]
            right=records['independent']['result']['obligations'][name]
            agreement=left['result']==right['result']
            comparisons.append({'obligation':name,'primary_result':left['result'],
                'independent_result':right['result'],'agreement':agreement,
                'primary_evidence':left['evidence'],'independent_evidence':right['evidence']})
    diverged=any(not row['agreement'] for row in comparisons)
    receipt={'record_type':'isolated_evaluator_comparison','schema_version':1,
        'subject':spec['subject'],'contract_sha256':identity(spec['contract']),
        'evaluators':records,'comparisons':comparisons,'problems':problems,
        'result':'inconclusive' if problems else 'diverged' if diverged else 'agreed',
        'fresh_process_context':True,'shared_chat_history_supplied':False,
        'independence_authenticated':False,
        'next_action':'Investigate every divergent obligation before acceptance.' if diverged else
                      'Repair evaluator execution and preserve this failed attempt.' if problems else
                      'Review evidence adequacy; agreement alone is not independent acceptance.',
        'limitation':'Fresh clean processes and separate working directories; not a protected sandbox, authenticated organizational independence, or proof adapters ignored external state.'}
    receipt['comparison_sha256']=identity(receipt)
    write_json(root/'comparison.json',receipt)
    return receipt
