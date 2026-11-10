"""Bounded retrieval and coverage adjudication; model output never grants coverage."""
import re
from .core import identity,require
from .registry import validate_registry


def _words(text):return set(re.findall(r'[a-z0-9]+',text.lower()))

def retrieve(finding,registry,limit=8):
    validate_registry(registry)
    require(0<limit<=50,'Retrieval limit out of bounds')
    words=_words(finding.get('description',''));ranked=[]
    for row in registry['claims']:
        c=row['claim'];overlap=sorted(words & _words(c.get('property',c.get('statement',''))+' '+' '.join(b['path'] for b in row.get('bindings',[]))+' '+' '.join(c.get('bug_classes',[]))))
        exact=finding.get('property_hint')==c.get('property',c.get('statement')) or bool(set(finding.get('bug_classes',[])) & set(c.get('bug_classes',[])))
        ranked.append({'claim_id':c['id'],'claim_sha256':row['claim_sha256'],'property_hint_matches':exact,'matched_terms':overlap,'rank_basis':'declared bug-class links and lexical/property hints; not verified coverage'})
    ranked.sort(key=lambda r:(-r['property_hint_matches'],-len(r['matched_terms']),r['claim_id']))
    return {'registry_sha256':registry['registry_sha256'],'subject':registry['subject'],'candidates':ranked[:limit],'truncated':len(ranked)>limit,'searched_claims':len(ranked),'limit':limit,'finding_sha256':identity(finding),'proposal_only':True}


def adjudicate(finding,registry,retrieval,comparisons):
    validate_registry(registry)
    require(retrieval['registry_sha256']==registry['registry_sha256'] and retrieval['subject']==registry['subject'] and retrieval['finding_sha256']==identity(finding),'Classification inputs changed after retrieval')
    by_id={r['claim']['id']:r for r in registry['claims']};ids=[r['claim_id'] for r in retrieval['candidates']]
    require(len(ids)==len(set(ids)) and all(x in by_id for x in ids),'Invalid retrieval candidates')
    require(len({c['claim_id'] for c in comparisons})==len(comparisons),'Duplicate coverage comparison')
    valid=[];gaps=[]
    for cid in ids:
        row=by_id[cid];c=next((x for x in comparisons if x['claim_id']==cid),None)
        if c is None:gaps.append(cid+':missing_comparison');continue
        require(c.get('claim_sha256')==row['claim_sha256'] and c.get('subject')==registry['subject'],'Coverage evidence subject/claim mismatch')
        require(c.get('relation') in ('same_property','different_property','unresolved'),'Unknown property relationship')
        evidence=c.get('evidence',[])
        bound=bool(evidence) and all(e.get('reference') and re.fullmatch('[a-f0-9]{64}',e.get('sha256','')) for e in evidence)
        if c.get('producer_kind')!='bounded_review' or not bound or not c.get('reviewer'):
            gaps.append(cid+':proposal_or_unbound_evidence');continue
        if c['relation']=='unresolved':gaps.append(cid+':unresolved_property');continue
        if c['relation']=='same_property':valid.append((row,c))
    result={'classification':'unresolved','closure_permitted':False,'finding_sha256':identity(finding),'registry_sha256':registry['registry_sha256'],'comparisons_sha256':identity(comparisons),'gaps':gaps,'limits':'Records a bounded reviewer decision with pinned evidence; does not independently prove its semantic correctness or reviewer independence.'}
    if len(valid)>1:result['gaps'].append('conflicting_claim_lineage');return result
    if gaps or retrieval['truncated']:result['gaps']+=['retrieval_truncated'] if retrieval['truncated'] else [];return result
    if valid:
        row,c=valid[0];claim=row['claim']
        missing=[b['path'] for b in row['bindings'] if b['state']!='present']
        if missing:result['gaps'].append('missing_implementation_bindings');return result
        occurrence=finding.get('occurrence')
        covered=bool(occurrence) and occurrence in claim.get('covered_occurrences',[]) and c.get('binding_coverage')=='verified'
        result.update(classification='covered_occurrence' if covered else 'uncovered_variant',claim_id=claim['id'],claim_sha256=row['claim_sha256'],enforcement_result='not_established_by_membership')
    elif len(comparisons)==len(ids) and not retrieval['truncated']:
        result.update(classification='new_property',basis='All candidates in the declared registry compared as different; not a global taxonomy claim')
    return result


def model_proposal(response,allowed_claim_ids):
    require(response.get('classification') in ('covered_occurrence','uncovered_variant','new_property','unresolved'),'Invalid classifier response')
    require(all(c in allowed_claim_ids for c in response.get('candidate_claim_ids',[])),'Model invented a claim identity')
    return {'response':response,'state':'proposal_only','coverage_verified':False,'closure_permitted':False,'required_next_step':'Retrieve candidates and perform evidence-bound comparisons; model label/confidence is not approval.'}
