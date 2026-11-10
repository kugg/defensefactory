"""Claim identity, preservation, assessment and code-evidence qualification."""
import copy
import re
from .core import require, identity
from .assessment import exposure_graph
from .e2e import guidance_gate
from .assessment_resolution import decision_plan, impact_review


def validate_claim(claim):
    require(claim.get('schema_version') == 1 and claim.get('id') and claim.get('owner'), 'Claim identity/owner required')
    require(claim.get('version', 0) > 0 and claim.get('property'), 'Versioned property required')
    obligations = claim.get('obligations', [])
    ids = [o['id'] for o in obligations]
    require(len(ids) == len(set(ids)) and bool(ids), 'Duplicate/missing obligation identity')
    require({'security','business','architecture'} <= {o['kind'] for o in obligations}, 'Security, business and architecture obligations required')
    for o in obligations:
        require(o.get('predicate') and o.get('checks'), 'Executable predicate/check bindings required')
    require(claim.get('bindings'), 'Implementation binding missing')
    require(all(e.get('owner') and e.get('expires_at') and e.get('reason') for e in claim.get('exceptions', [])), 'Unowned/unbounded exception')
    require(not set(claim.get('required_behaviors', [])) & set(claim.get('prohibited_behaviors', [])), 'Contradictory requirements')
    return identity(claim)


def delegate(claim, obligations, proposed_claim=None):
    validate_claim(claim)
    require(set(obligations) == {o['id'] for o in claim['obligations']}, 'Delegation loses an obligation')
    require(proposed_claim is None or identity(proposed_claim) == identity(claim), 'Claim amendment requires separate approval')
    return {'claim_id':claim['id'], 'claim_version':claim['version'], 'specification_sha256':identity(claim), 'obligations':sorted(obligations)}


def membership(property_id, candidates, *, occurrence=None, variant=None):
    # Retrieval candidates are proposals; only exact reviewed property identity establishes membership.
    same = [c for c in candidates if c['property'] == property_id]
    if not same:
        return {'classification':'new_property' if property_id else 'unresolved', 'candidate_claims':[]}
    require(len({c['id'] for c in same}) == 1, 'Conflicting claim lineage requires review')
    c = same[0]
    return {'claim_id':c['id'], 'classification':'covered_occurrence' if occurrence in c.get('covered_occurrences', []) else 'uncovered_variant' if variant else 'unresolved', 'closure_permitted':False}


def assess(claim, finding, alternatives, code_evidence, eligibility=None):
    if eligibility is None:
        return {'stage':'assess','result':'inconclusive','disposition':'hold','closure_permitted':False,
                'execution_result':'completed','handoff_readiness':'incomplete','question_required':False,
                'missing_assessment_inputs':['early_applicability_review'],
                'next_action':'Inspect current applicability and recover scope/evidence through the ticket before repair assessment.'}
    from .eligibility import evaluate
    disposition = evaluate(eligibility["packet"], eligibility["policy"], eligibility["actor"])
    if disposition["disposition"] != "continue":
        return disposition
    digest = validate_claim(claim)
    diagram=exposure_graph(finding['exposure_graph'])
    require(finding.get('premise') in ('supported','disputed','unresolved'), 'Premise evidence required')
    require(finding.get('evidence') and finding.get('exposure') and finding.get('complexity'), 'Premise/exposure/complexity evidence required')
    require(any(a['boundary']=='local' for a in alternatives) and any(a['boundary']=='shared' for a in alternatives), 'Compare local and shared enforcement')
    for a in alternatives:
        require(all(k in a for k in ('bypasses','migration','cost_basis')), 'Incomplete enforcement comparison')
    required=('subject','classification','target_scope','requirement_authority','handoff_contract')
    missing=[field for field in required if not finding.get(field)]
    if finding.get('classification')=='unresolved':missing.append('classification_resolution')
    contract=finding.get('handoff_contract') or {}
    for field in ('version','obligations','scope','bypasses','migration','unknowns','checks','authorized_actions','budgets'):
        # Explicit empty arrays are legitimate for bypasses/migration/unknowns; missing keys are not.
        if field not in contract:missing.append('handoff_contract.'+field)
    for field in ('obligations','scope','checks','authorized_actions','budgets'):
        if field in contract and not contract[field]:missing.append('handoff_contract.'+field)
    if contract.get('obligations'):
        declared={x if isinstance(x,str) else x.get('id') for x in contract['obligations']}
        if declared!={o['id'] for o in claim['obligations']}:missing.append('handoff_contract.obligation_correspondence')
    if contract.get('checks'):
        declared_checks={x if isinstance(x,str) else x.get('id') for x in contract['checks']}
        if not {c for o in claim['obligations'] for c in o['checks']} <= declared_checks:missing.append('handoff_contract.required_check_correspondence')
    legacy=[dict(d, blocks_stages=d.get('blocks_stages',['repair'])) for d in finding.get('decisions',[]) if d.get('blocks_handoff') or d.get('blocks_stages')]
    planning=decision_plan(legacy, 'repair')
    open_decisions=planning['blocking_decisions']
    open_decisions+=copy.deepcopy(disposition.get('repair_contract_blockers',[]))
    impact=impact_review(finding['impact_assertions']) if finding.get('impact_assertions') else None
    if impact is None or impact['result']=='inconclusive':missing.append('impact_evidence_review')
    e2e=guidance_gate(finding.get('end_to_end_guidance'))
    if not e2e['guidance_bound']:missing.append('end_to_end_guidance')
    ready=finding['premise']=='supported' and not missing and not open_decisions
    return {'schema_version':1, 'stage':'assess', 'claim_sha256':digest, 'premise':finding['premise'],
            'execution_result':'completed', 'premise_result':finding['premise'],
            'handoff_readiness':'complete_for_review' if ready else 'incomplete',
            'missing_assessment_inputs':sorted(set(missing)), 'open_decisions':open_decisions,'deferred_decisions':planning['deferred_decisions']+disposition.get('decision_plan',{}).get('deferred_decisions',[]),'impact_review':impact,'end_to_end_guidance':e2e,'question_required':e2e['question_required'] or bool(open_decisions),
            'next_action':e2e['next_action'] if e2e['question_required'] else 'Review the versioned assessment contract; this result grants no repair permission.' if ready else 'Complete the listed assessment inputs and resolve or scope each blocking decision, then rerun assessment.',
            'result':'premise_disputed' if finding['premise']=='disputed' else 'satisfied_within_scope' if ready else 'inconclusive',
            'eligibility':disposition,'exposure_diagram':diagram,'finding':copy.deepcopy(finding), 'alternatives':copy.deepcopy(alternatives), 'code_evidence':code_evidence,
            'verification_brief':delegate(claim,[o['id'] for o in claim['obligations']]), 'approval':'not_granted_by_assessment'}


def qualify_query(result, expected_subject, required_files=()):
    require(result['subject'] == expected_subject, 'Index/source identity mismatch')
    require(result.get('producer') and result.get('query_sha256') and result.get('raw_sha256'), 'Evidence provenance missing')
    diagnostics = list(result.get('diagnostics', []))
    if result.get('truncated'):
        diagnostics.append('truncated')
    missing = set(required_files) - set(result.get('covered_files', []))
    if missing:
        diagnostics.append('missing_files:' + ','.join(sorted(missing)))
    if not result.get('semantic_available'):
        diagnostics.append('semantic_layer_unavailable')
    for edge in result.get('edges', []):
        require(edge.get('kind') in ('syntax','semantic_reference','possible_dispatch','configuration','proposal','runtime'), 'Undeclared evidence layer')
        require(edge.get('producer') and edge.get('evidence'), 'Edge provenance missing')
        if edge['kind'] == 'proposal':
            require(edge.get('state') in ('unresolved','rejected','validated'), 'Unadjudicated proposed edge')
    return {'result':'inconclusive' if diagnostics else 'satisfied_within_scope','diagnostics':diagnostics,'complete':not diagnostics and result.get('coverage')=='declared_fixture','raw_sha256':result['raw_sha256']}


def compare_queries(base, head, mapping):
    require(base['query_sha256'] == head['query_sha256'] and base['extractor'] == head['extractor'] and base.get('configuration') == head.get('configuration'), 'Incomparable query/extractor/configuration')
    names = {e['symbol'] for e in base.get('symbols', [])}
    current = {e['symbol'] for e in head.get('symbols', [])}
    unresolved = names - current - set(mapping)
    require(set(mapping.values()) <= current, 'Symbol mapping targets missing')
    return {'result':'inconclusive' if unresolved else 'satisfied_within_scope','unmapped':sorted(unresolved),'mapping':mapping,'note':'Symbol disappearance does not establish remediation.'}


class EvidenceCache:
    """Immutable retained query results with authorization checked on EVERY retrieval."""
    def __init__(self):
        self.objects = {}

    def put(self, result):
        key = identity(result)
        self.objects[key] = copy.deepcopy(result)
        return key

    def get(self, key, allowed_repositories):
        value = self.objects[key]
        require(value['subject']['repository'] in allowed_repositories, 'Repository access denied')
        return copy.deepcopy(value)

    def export(self):
        return copy.deepcopy(self.objects)

    @classmethod
    def restore(cls, objects):
        cache = cls()
        for key, obj in objects.items():
            require(identity(obj) == key, 'Cached evidence corrupted')
            cache.objects[key] = copy.deepcopy(obj)
        return cache
