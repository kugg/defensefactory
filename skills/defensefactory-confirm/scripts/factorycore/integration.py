"""Read actual GitHub PR/protection state and calculate the local merge tree without merging."""
import json
import re
import time
from urllib.parse import quote
import subprocess
from .core import require, identity
from .verification import git


def github_subject(repository, number):
    require(re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository) and re.fullmatch(r'[1-9][0-9]*',str(number)),'Explicit repository/PR required')
    p=subprocess.run(['gh','pr','view',str(number),'--repo',repository,'--json','url,state,isDraft,headRefOid,baseRefOid,headRefName,baseRefName,statusCheckRollup,mergeCommit,mergedAt,reviewDecision,mergeStateStatus'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
    require(p.returncode==0,'GitHub PR state unavailable')
    data=json.loads(p.stdout)
    branch=quote(data['baseRefName'],safe='')
    protection=subprocess.run(['gh','api','repos/'+repository+'/branches/'+branch+'/protection'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
    protection_data=json.loads(protection.stdout) if protection.returncode==0 else None
    rules=subprocess.run(['gh','api','repos/'+repository+'/rules/branches/'+branch],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
    rule_data=json.loads(rules.stdout) if rules.returncode==0 else None
    runs=subprocess.run(['gh','api','--paginate','--slurp','repos/'+repository+'/commits/'+data['headRefOid']+'/check-runs?per_page=100'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
    statuses=subprocess.run(['gh','api','--paginate','--slurp','repos/'+repository+'/commits/'+data['headRefOid']+'/statuses?per_page=100'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
    observations=[]
    if runs.returncode==0:
        for page in json.loads(runs.stdout):
            for r in page.get('check_runs',[]):observations.append({'id':r['id'],'name':r['name'],'revision':r['head_sha'],'app_id':r.get('app',{}).get('id'),'status':r['status'],'conclusion':r.get('conclusion'),'started_at':r.get('started_at') or r.get('created_at')})
    if statuses.returncode==0:
        for page in json.loads(statuses.stdout):
            for r in page:observations.append({'id':r['id'],'name':r['context'],'revision':data['headRefOid'],'app_id':None,'status':'in_progress' if r['state']=='pending' else 'completed','conclusion':'success' if r['state']=='success' else 'failure','started_at':r.get('created_at')})
    checks=list(((protection_data or {}).get('required_status_checks') or {}).get('contexts',[]))
    for rule in rule_data or []:
        if rule.get('type')=='required_status_checks':checks.extend(x['context'] for x in rule.get('parameters',{}).get('required_status_checks',[]))
    return {'schema_version':1,'repository':repository,'number':int(number),'observed_at':time.time(),'pr':data,'check_observations':observations,'api_observation':{'protection_available':protection.returncode==0,'rules_available':rules.returncode==0,'check_runs_available':runs.returncode==0,'statuses_available':statuses.returncode==0},'protection':protection_data,'rules':rule_data,
            'protection_observation':{'required_checks':sorted(set(checks)),'enforced':bool(checks),'bypass_allowed':None},
            'limits':['Read-only observed GitHub state; bypass permissions require separate policy evidence.','No merge or protection settings were changed.']}


def merge_tree(repo, base, head):
    require(len(base)==40 and len(head)==40,'Exact base/head required')
    require(git(repo,'rev-parse',base).decode().strip()==base and git(repo,'rev-parse',head).decode().strip()==head,'Unavailable merge inputs')
    p=subprocess.run(['git','-C',str(repo),'merge-tree','--write-tree',base,head],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
    if p.returncode!=0:return {'result':'inconclusive','base':base,'head':head,'reason':'merge_conflict','raw':p.stdout.decode(errors='replace')}
    tree=p.stdout.decode().splitlines()[0]
    verified_tree=git(repo,'rev-parse',head+'^{tree}').decode().strip()
    return {'result':'satisfied_within_scope','base':base,'head':head,'merge_tree':tree,'candidate_tree':verified_tree,'tree_matches_candidate':tree==verified_tree,'requires_reevaluation':tree!=verified_tree,'merge_performed':False}
