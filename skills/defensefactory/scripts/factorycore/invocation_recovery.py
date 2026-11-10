"""Read-only recovery advice for captured foreground agent invocations."""
import json
import re
from pathlib import Path
from .core import require, sha


def recovery_receipt(data):
    require(all(data.get(k) for k in ('case','attempt','session_id','log_path')), 'Case, attempt, existing session and captured log required')
    require(type(data.get('exit_code')) is int, 'Actual producer exit code required')
    retries=data.get('retries_used',0)
    budget=data.get('retry_budget',2)
    require(type(retries) is int and retries>=0 and type(budget) is int and 0<=budget<=3, 'Recovery budget must be explicit and bounded to at most three retries')
    raw=Path(data['log_path']).read_bytes()
    require(len(raw)<=128*1024*1024, 'Invocation log exceeds bound')
    sessions=set();errors=[];parse_errors=[];last=None
    for number,line in enumerate(raw.decode('utf-8',errors='replace').splitlines(),1):
        try:event=json.loads(line)
        except ValueError:
            parse_errors.append(number);continue
        if not isinstance(event,dict):
            parse_errors.append(number);continue
        if event.get('sessionID'):sessions.add(event['sessionID'])
        if event.get('sessionID')==data['session_id']:
            last=event
            if event.get('type')=='error':errors.append(event.get('error',{}))
    same=sessions=={data['session_id']}
    error=last.get('error',{}) if last and last.get('type')=='error' else {}
    detail=error.get('data',{}) if isinstance(error,dict) else {}
    message=detail.get('message','') if isinstance(detail,dict) else ''
    # Only observed transport error families qualify. A failed tool/test is not
    # a provider transport error and cannot gain an automatic retry here.
    network=bool(isinstance(message,str) and re.search(r'\b(?:ENOTFOUND|ECONNRESET|EAI_AGAIN|ETIMEDOUT)\b',message))
    denied=bool(re.search(r'\b(?:401|403|invalid_api_key|unauthorized|forbidden)\b',message,re.I)) if isinstance(message,str) else False
    retry=bool(data['exit_code']!=0 and same and not parse_errors and network and not denied and detail.get('isRetryable') is not False and retries<budget)
    action='invocation_completed' if data['exit_code']==0 and same and not parse_errors else 'resume_existing_session' if retry else 'reconcile_and_hold'
    return {'schema_version':1,'result':'recorded','case':data['case'],'attempt':data['attempt'],
            'session_id':data['session_id'],'observed_sessions':sorted(sessions),
            'log_sha256':sha(raw),'log_bytes':len(raw),'exit_code':data['exit_code'],
            'terminal_error':error,'error_events':errors,'non_json_lines':parse_errors,
            'failure_class':'transport' if network and not denied else 'authentication_or_permission' if denied else 'none' if data['exit_code']==0 else 'unclassified',
            'next_action':action,'retry_suggested':retry,'retries_used':retries,'retry_budget':budget,
            'reconcile_external_effects_before_retry':True,'factory_acceptance':'not_evaluated',
            'closure_permitted':False,
            'limitation':'Advice from a captured log and declared retry count, not permission, a scheduler or proof of external state. Resume the named session; preserve all invocation logs and reconcile ticket/PR effects before further mutations. Never retry a failed assertion until it passes or reset a case to hide the failure.'}
