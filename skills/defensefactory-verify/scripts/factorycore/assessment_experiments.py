"""Predeclared paired classification/handoff scoring; no synthetic independence claims."""
from .core import require,identity,sha
from .signatures import verify_signed

LABELS={'covered_occurrence','uncovered_variant','new_property','unresolved'}

def freeze_protocol(cases,arms,thresholds,adjudication):
    ids=[x['id'] for x in cases];require(ids and len(ids)==len(set(ids)),'Duplicate/empty evaluation corpus')
    require(len(arms)>=2 and len(set(arms))==len(arms),'Paired arms missing/duplicated')
    require(all(c['expected']['classification'] in LABELS for c in cases),'Invalid corpus label')
    require(all(k in thresholds for k in ('max_false_merges','max_false_splits','max_unresolved_fraction')),'Predeclared decision thresholds required')
    require(0<=thresholds['max_unresolved_fraction']<=1 and thresholds['max_false_merges']>=0 and thresholds['max_false_splits']>=0,'Invalid thresholds')
    require(adjudication.get('kind') in ('author_generated_synthetic','external_review'),'Unknown corpus adjudication provenance')
    body={'schema_version':1,'corpus_sha256':identity(cases),'case_ids':ids,'arms':arms,'thresholds':thresholds,'adjudication':adjudication,'evaluation_targets':['false_merges','false_splits','abstention','taxonomy_growth','tokens_through_accepted_remediation','retries_and_rework'],'security_requirements_fixed':True}
    return {**body,'protocol_sha256':identity(body)}


def _attestation(envelope,policy,role,action,subject,producer,now):
    r=envelope['receipt'];actor=r['actor'];principal=policy.get('principals',{}).get(actor)
    require(principal and not principal.get('revoked') and role in principal.get('roles',[]),'Untrusted experiment attestor')
    require(actor!=producer['actor'] and sha(principal['public_key'].encode())!=producer['public_key_sha256'],'Experiment producer cannot self-attest')
    verify_signed(envelope,principal['public_key'],expected_actor=actor,expected_subject=subject)
    require(r.get('action')==action and r.get('policy_sha256')==identity(policy),'Experiment attestation action/policy mismatch')
    require(isinstance(r.get('issued_at'),int) and isinstance(r.get('expires_at'),int) and r['issued_at']<=now<r['expires_at'],'Experiment attestation expired/future')
    return r


def score(cases,runs,protocol,*,attestations=None,trusted_policy=None,now=None):
    body={k:v for k,v in protocol.items() if k!='protocol_sha256'}
    require(identity(body)==protocol['protocol_sha256'] and identity(cases)==protocol['corpus_sha256'],'Protocol/corpus changed after freeze')
    require([c['id'] for c in cases]==protocol['case_ids'],'Evaluation denominator changed')
    expected={(arm,c['id']) for arm in protocol['arms'] for c in cases}
    actual=[(r['arm'],r['case_id']) for r in runs]
    require(len(actual)==len(set(actual)) and set(actual)==expected,'Paired runs missing/duplicated or denominator changed')
    labels_authenticated=False
    attestations=attestations or {}
    if attestations:
        require(trusted_policy is not None and now is not None,'Trusted experiment policy/time required')
        if attestations.get('labels'):
            subject={'corpus_sha256':protocol['corpus_sha256'],'protocol_sha256':protocol['protocol_sha256']}
            receipt=_attestation(attestations['labels'],trusted_policy,'labels-reviewer','adjudicate_corpus',subject,protocol['adjudication']['producer'],now)
            require(receipt.get('decision')=='labels_confirmed','Corpus labels not confirmed')
            labels_authenticated=True
    results=[]
    for arm in protocol['arms']:
        rows=[x for x in runs if x['arm']==arm];merges=splits=unresolved=correct=0;new_properties=set()
        for c in cases:
            row=next(x for x in rows if x['case_id']==c['id']);p=row['prediction'];e=c['expected'];require(p['classification'] in LABELS,'Unknown classifier output')
            require(row.get('protocol_sha256')==protocol['protocol_sha256'],'Run is not bound to predeclared protocol')
            existing=p['classification'] in ('covered_occurrence','uncovered_variant')
            if existing and (e['classification'] not in ('covered_occurrence','uncovered_variant') or p.get('claim_id')!=e.get('claim_id')):merges+=1
            if p['classification']=='new_property' and e['classification'] in ('covered_occurrence','uncovered_variant'):splits+=1
            unresolved+=p['classification']=='unresolved';correct+=not row.get('failure') and p['classification']==e['classification'] and p.get('claim_id')==e.get('claim_id')
            if p['classification']=='new_property':new_properties.add(p.get('property_id',c['id']))
        failures=sum(bool(row.get('failure')) for row in rows)
        limits=protocol['thresholds'];passed=failures==0 and merges<=limits['max_false_merges'] and splits<=limits['max_false_splits'] and unresolved/len(cases)<=limits['max_unresolved_fraction']
        usage=[row.get('usage') for row in rows];tokens=sum(u['total_tokens'] for u in usage) if all(u is not None and isinstance(u.get('total_tokens'),int) and u['total_tokens']>=0 for u in usage) else None
        reported_acceptance=all(x.get('independently_accepted_remediation') is True and x.get('acceptance_reference') for x in rows)
        costs=[]
        for row in rows:
            envelope=(attestations.get('outcomes') or {}).get(arm+':'+row['case_id'])
            if envelope:
                subject={'protocol_sha256':protocol['protocol_sha256'],'arm':arm,'case_id':row['case_id'],'source':row['subject']}
                verified=_attestation(envelope,trusted_policy,'outcome-reviewer','attest_accepted_remediation',subject,row['producer'],now)
                components=verified.get('cost_components',{})
                require(set(components)=={'classification','investigation','repair','verification','rework'} and all(isinstance(n,int) and n>=0 for n in components.values()),'Incomplete signed end-to-end token ledger')
                require(verified.get('decision')=='accepted' and verified.get('acceptance_reference') and verified.get('observation_window'),'Accepted outcome/reference/window missing')
                costs.append(sum(components.values()))
        accepted=len(costs)==len(rows)  # Unsigned caller booleans/references earn no cost credit.
        results.append({'arm':arm,'cases':len(cases),'correct':correct,'failed_requests':failures,'false_merges':merges,'false_splits':splits,'abstentions':unresolved,'unresolved_fraction':unresolved/len(cases),'taxonomy_growth':len(new_properties),'declared_local_thresholds_met':passed,'reported_classification_tokens':tokens,'tokens_through_accepted_remediation':sum(costs) if accepted else None,'accepted_remediation_measurement_available':bool(accepted),'unverified_acceptance_reports_present':bool(reported_acceptance)})
    return {'schema_version':1,'protocol_sha256':protocol['protocol_sha256'],'results':results,'qualification':'local_fixture_only' if protocol['adjudication']['kind']=='author_generated_synthetic' else 'external_label_claim_requires_signature_validation','independent_qualification':False,'labels_authenticated':labels_authenticated,'remaining':['Authenticated independent corpus adjudication','Actual independently accepted remediation/rework/cost outcomes'],'note':'Missing token or accepted-remediation observations remain null; classification labels do not prove repair success.'}
