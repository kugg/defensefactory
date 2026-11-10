"""Read-only validation of ticket checkpoints and retrieved evidence; no second store."""
import json
import re
from .core import identity, sha, require, GateError


def validate_checkpoint(checkpoint, expected, resources):
    """expected is the pointer fetched live from the ticket, not a local cached pointer."""
    problems=[]
    try:
        require(identity(checkpoint)==expected['checkpoint_sha256'], 'Checkpoint digest mismatch')
        for key in ('case','attempt','generation','subject'):
            require(checkpoint.get(key)==expected[key], 'Checkpoint '+key+' mismatch')
        require(checkpoint.get('publication')=='completed', 'Publication incomplete')
        manifest=checkpoint.get('resources',[])
        require(manifest and len({r['id'] for r in manifest})==len(manifest),'Empty/duplicate resource manifest')
        require(set(expected['required_resources']) <= {r['id'] for r in manifest}, 'Required resource unregistered')
        for r in manifest:
            require(r['id'] in resources,'Resource missing: '+r['id'])
            raw=resources[r['id']]
            require(len(raw)==r['bytes'] and sha(raw)==r['sha256'], 'Resource bytes changed: '+r['id'])
        require(checkpoint.get('receipt_sha256') in {r['sha256'] for r in manifest}, 'Stage receipt not retained')
    except (GateError,KeyError,TypeError) as error:problems.append(str(error))
    return {'result':'inconclusive' if problems else 'satisfied_within_scope','handoff_ready':not problems,'problems':problems,
            'checkpoint_sha256':identity(checkpoint),'recovery':'Fetch the live ticket pointer and required resources again. Preserve this failure; publish a new attempt/generation only after reconciling effects. Never silently change an old digest.' if problems else 'Consume only this verified snapshot; recheck the live pointer before effects.'}


def reconcile(effect_key, intended, observed, lookup_complete=False):
    """Decide whether a timed-out publish may be retried after a bounded live lookup."""
    matches=[o for o in observed if o['effect_key']==effect_key]
    if not matches and not lookup_complete:return {'action':'hold','result':'inconclusive','new_effect_permitted':False,'reason':'Live publication lookup incomplete; absence not established.'}
    if not matches:return {'action':'retry_same_key','result':'not_observed','new_effect_permitted':True}
    digests={o['payload_sha256'] for o in matches}
    if digests!={identity(intended)} or len(matches)>1:
        return {'action':'hold','result':'inconclusive','new_effect_permitted':False,'reason':'Conflicting or duplicate publication; reconcile before retry.'}
    return {'action':'reuse_existing','result':'satisfied_within_scope','new_effect_permitted':False,'resource_id':matches[0]['resource_id']}


def parse_document(content):
    """Parse exact readback; never repair Markdown-normalized evidence implicitly."""
    fenced=re.fullmatch(r'```json\n(.*)\n```',content.strip(),re.DOTALL)
    value=json.loads(fenced.group(1) if fenced else content)
    require(isinstance(value,dict), 'Checkpoint must be a JSON object')
    return value


def prepare_publication(checkpoint, expected, resources, preparation_exit_code=0):
    require(preparation_exit_code==0, 'Preparation failed; no publication payload produced')
    checked=validate_checkpoint(checkpoint,expected,resources)
    require(checked['handoff_ready'], 'Checkpoint failed validation; no publication payload produced: '+str(checked['problems']))
    value={'checkpoint':checkpoint,'expected':expected}
    return {'content':'```json\n'+json.dumps(value,indent=2)+'\n```','payload_sha256':identity(value),
            'effect_key':checkpoint['case']+':'+checkpoint['attempt']+':'+str(checkpoint['generation'])}
