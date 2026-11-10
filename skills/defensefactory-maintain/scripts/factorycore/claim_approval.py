"""Authenticate contract approval and derive an obligation-preserving verifier handoff."""
import copy
from .core import require,identity,sha
from .claims import validate_claim
from .registry import validate_registry
from .signatures import verify_signed


def propose_contract(registry,claim_id,evaluator,producer,context,actions,budget):
    validate_registry(registry)
    row=next((r for r in registry['claims'] if r['claim']['id']==claim_id),None)
    require(row is not None,'Claim absent from product registry')
    claim=row['claim']
    if registry.get('schema_version')==2:
        from .component_claims import execution_contract
        claim=execution_contract(registry,claim_id,evaluator['checks'],evaluator['files'],evaluator.get('formal'))
    validate_claim(claim)
    required={c for o in claim['obligations'] for c in o['checks']}
    require(required=={c['id'] for c in evaluator['checks']} and len(required)==len(evaluator['checks']),'Evaluator drops or duplicates a required check')
    require(evaluator.get('files') and all(len(d)==64 for d in evaluator['files'].values()),'Evaluator file digests required')
    require(context and all(r.get('reference') and len(r.get('sha256',''))==64 for r in context),'Pinned handoff context required')
    require(producer.get('actor') and len(producer.get('public_key_sha256',''))==64,'Producing identity/key binding required')
    require(actions and budget,'Handoff action/budget contract required')
    proposal={'schema_version':1,'subject':registry['subject'],'registry_sha256':registry['registry_sha256'],'claim_location':row['path'],'claim':copy.deepcopy(claim),'claim_sha256':identity(claim),'evaluator':copy.deepcopy(evaluator),'evaluator_sha256':identity(evaluator),'producer':copy.deepcopy(producer),'context':copy.deepcopy(context),'permitted_actions':list(actions),'budget':copy.deepcopy(budget),'disagreement_route':'Return a proposed versioned amendment with evidence; preserve original requirements until separately authorized.'}
    return proposal


def approve_contract(proposal,envelope,policy,now):
    require(policy.get('schema_version')==1 and policy.get('id') and policy.get('version'),'Trusted policy identity missing')
    require(policy.get('mode') in ('local_rehearsal','protected'),'Unknown approval trust mode')
    require(proposal['claim_sha256']==validate_claim(proposal['claim']) and proposal['evaluator_sha256']==identity(proposal['evaluator']),'Proposal specification/evaluator integrity mismatch')
    receipt=envelope['receipt'];actor=receipt.get('actor');principal=policy.get('principals',{}).get(actor)
    require(principal is not None and not principal.get('revoked'),'Untrusted/revoked contract approver')
    require('contract-reviewer' in principal.get('roles',[]) and proposal['subject']['repository'] in principal.get('repositories',[]),'Approver role/repository denied')
    producer=proposal['producer'];producer_principal=policy.get('principals',{}).get(producer['actor'])
    require(producer_principal and not producer_principal.get('revoked') and 'contract-producer' in producer_principal.get('roles',[]) and proposal['subject']['repository'] in producer_principal.get('repositories',[]),'Untrusted contract producer')
    require(sha(producer_principal['public_key'].encode())==producer['public_key_sha256'],'Producer key differs from trusted policy')
    producer_envelope=envelope.get('producer_attestation')
    require(producer_envelope is not None,'Authenticated producer attestation required')
    signed_producer=verify_signed(producer_envelope,producer_principal['public_key'],expected_actor=producer['actor'],expected_subject=proposal['subject'])['receipt']
    require(signed_producer.get('action')=='propose_contract' and signed_producer.get('proposal_sha256')==identity(proposal) and signed_producer.get('policy_sha256')==identity(policy),'Producer attestation does not bind current proposal/policy')
    require(isinstance(signed_producer.get('issued_at'),int) and isinstance(signed_producer.get('expires_at'),int) and signed_producer['issued_at']<=now<signed_producer['expires_at'],'Producer attestation expired/future')
    require(receipt.get('producer_attestation_sha256')==identity(producer_envelope),'Review does not bind producer attestation')
    require(actor!=proposal['producer']['actor'] and sha(principal['public_key'].encode())!=proposal['producer']['public_key_sha256'],'Producer cannot approve its own contract, including a key alias')
    authenticated=verify_signed(envelope,principal['public_key'],expected_actor=actor,expected_subject=proposal['subject'])
    require(receipt.get('action')=='approve_contract' and receipt.get('decision')=='approved','Contract approval action missing')
    require(receipt.get('proposal_sha256')==identity(proposal) and receipt.get('policy_sha256')==identity(policy),'Approval does not bind current proposal/policy')
    issued,expires=receipt.get('issued_at'),receipt.get('expires_at')
    require(isinstance(issued,int) and isinstance(expires,int) and issued<=now<expires and expires-issued<=policy['max_approval_age_seconds'],'Expired/future/out-of-policy approval')
    return {'result':'satisfied_within_scope','proposal_sha256':identity(proposal),'actor':actor,'policy_sha256':identity(policy),'public_key_sha256':authenticated['public_key_sha256'],'mode':policy['mode'],'independence':'not_established_by_signature','authority':'Configured-key admission only; trust of policy distribution and OS/repository isolation needs separate evidence.','closure_permitted':False}


def verification_handoff(proposal,envelope,policy,now):
    admission=approve_contract(proposal,envelope,policy,now)
    require(all(c.get('argv') or (c.get('adapter_reference') and c.get('adapter_sha256')) for c in proposal['evaluator']['checks']),'Evaluator is not executable; complete required checks before verification handoff')
    claim=copy.deepcopy(proposal['claim']);required={c for o in claim['obligations'] for c in o['checks']}
    require({c['id'] for c in proposal['evaluator']['checks']}==required,'Required checks changed')
    return {'schema_version':1,'stage':'verify','subject':proposal['subject'],'claim_location':proposal['claim_location'],'specification_sha256':proposal['claim_sha256'],'claim':claim,'obligations':copy.deepcopy(claim['obligations']),'evaluator':copy.deepcopy(proposal['evaluator']),'evaluator_sha256':proposal['evaluator_sha256'],'context':copy.deepcopy(proposal['context']),'permitted_actions':proposal['permitted_actions'],'budget':proposal['budget'],'disagreement_route':proposal['disagreement_route'],'approval':admission,'result':'ready_for_declared_verification','acceptance':'No repaired-source acceptance is implied by contract approval.'}


def check_handoff(expected,received):
    fields=('subject','claim_location','specification_sha256','claim','obligations','evaluator','evaluator_sha256','context','permitted_actions','budget','disagreement_route','approval')
    changed=[f for f in fields if received.get(f)!=expected.get(f)]
    return {'result':'violated' if changed else 'satisfied_within_scope','changed_fields':changed,'note':'Transport preservation check, not an execution or runtime result.'}
