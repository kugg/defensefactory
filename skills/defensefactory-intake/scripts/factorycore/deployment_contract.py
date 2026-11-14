"""Project-agnostic cross-component deployment alignment contracts."""
import copy
import re
from .core import identity, require


RULES={'all_equal','all_present','allowed_values'}


def validate_contract(contract):
    require(isinstance(contract,dict) and contract.get('schema')=='defensefactory/deployment-contract/v1'
            and contract.get('id') and contract.get('subject'), 'Deployment contract identity and subject required')
    points=contract.get('points')
    require(isinstance(points,list) and points and len({p.get('id') for p in points})==len(points),
            'Unique deployment alignment points required')
    for point in points:
        require(point.get('id') and point.get('description') and point.get('rule') in RULES,
                'Alignment point needs id, description and supported rule')
        sources=point.get('sources')
        require(isinstance(sources,list) and sources and len(set(sources))==len(sources)
                and all(isinstance(s,str) and s and not any(ch.isspace() for ch in s) for s in sources),
                'Alignment sources must be unique opaque identifiers')
        if point['rule']=='all_equal':require(len(sources)>=2,'all_equal needs at least two sources')
        allowed=point.get('allowed_values')
        require((point['rule']=='allowed_values') == bool(allowed),
                'allowed_values rule needs a nonempty allow-list and other rules must omit it')
        if allowed:require(isinstance(allowed,list) and all(isinstance(value,str) for value in allowed)
                           and len(set(allowed))==len(allowed),'Allowed values must be unique strings')
    return contract


def evaluate(contract, observations):
    """Return per-point status without serializing observed values."""
    validate_contract(contract)
    require(isinstance(observations,dict), 'Deployment observations object required')
    declared={source for point in contract['points'] for source in point['sources']}
    require(set(observations)<=declared,'Observation names outside the deployment contract')
    rows=[]
    for point in contract['points']:
        available=[];unknown=[];references=[]
        for source in point['sources']:
            item=observations.get(source)
            if not isinstance(item,dict) or item.get('state')!='observed' or 'value' not in item:
                unknown.append(source);continue
            require(item.get('reference') and not item['reference'].startswith('file://'),
                    'Observed deployment value needs a durable evidence reference')
            require(re.fullmatch(r'[0-9a-f]{64}',item.get('capture_sha256','')),
                    'Observed deployment value needs its protected capture digest')
            available.append((source,item['value']));references.append({'source':source,
                'reference':item['reference'],'capture_sha256':item['capture_sha256']})
        status='unknown'
        if not unknown:
            values=[value for _,value in available]
            if point['rule']=='all_present':ok=all(value not in ('',None) for value in values)
            elif point['rule']=='all_equal':ok=all(value==values[0] for value in values[1:])
            else:ok=all(value in point['allowed_values'] for value in values)
            status='satisfied' if ok else 'violated'
        rows.append({'id':point['id'],'status':status,'sources':point['sources'],
                     'unknown_sources':unknown,'evidence':references})
    ready=all(row['status']=='satisfied' for row in rows)
    violated=any(row['status']=='violated' for row in rows)
    body={'record_type':'deployment_binding','schema_version':1,'contract_id':contract['id'],
          'contract_sha256':identity(contract),'subject':copy.deepcopy(contract['subject']),
          'points':rows,'deployment_binding_ready':ready,
          'result':'satisfied_within_scope' if ready else 'violated' if violated else 'inconclusive',
          'values_retained':False,
          'next_action':'Deployment binding gate satisfied.' if ready else
                        'Correct violated alignment points before deployment.' if violated else
                        'Capture every unknown alignment source before deployment.',
          'limitation':'Values are compared in memory and omitted from this shareable receipt. Evidence references must preserve protected raw observations where replay is required.'}
    body['deployment_binding_sha256']=identity(body)
    return body


def validate_binding(receipt, subject):
    require(receipt.get('record_type')=='deployment_binding' and receipt.get('deployment_binding_ready') is True
            and receipt.get('result')=='satisfied_within_scope','Satisfied deployment-binding receipt required')
    require(receipt.get('subject')==subject,'Deployment binding is for another subject')
    require(receipt.get('deployment_binding_sha256')==
            identity({k:v for k,v in receipt.items() if k!='deployment_binding_sha256'}),
            'Deployment-binding receipt changed')
    return receipt
