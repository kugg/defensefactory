"""Compact component-owned definitions; identities, observations and hashes live in receipts."""
import copy
import json
import os
from pathlib import Path,PurePosixPath
import re
import subprocess
import tarfile
import tempfile
import time
from .core import require,identity,sha,GateError
from .registry import source_blob
from .verification import git,command,evaluator_guard
from .check_results import qualify_execution


RULES_START='<!-- defensefactory-claims:start -->'
RULES_END='<!-- defensefactory-claims:end -->'


def _keys(value,allowed,required=()):
    require(isinstance(value,dict) and set(value)<=set(allowed) and set(required)<=set(value),'Unknown/missing definition fields; computed hashes and execution history belong in receipts')


def _ids(rows):
    require(all(isinstance(r,dict) for r in rows),'Definitions must be objects')
    ids=[r.get('id') for r in rows];require(all(isinstance(i,str) and i for i in ids) and len(ids)==len(set(ids)),'Missing/duplicate canonical identity')


def _path(value):
    require(isinstance(value,str) and value,'Nonempty path required')
    p=PurePosixPath(value);require(not p.is_absolute() and '..' not in p.parts and str(p)==value and '\\' not in value,'Unsafe component-relative path');return p


def validate_catalog(catalog):
    _keys(catalog,('schema_version','component','claims','fences','bug_classes'),('schema_version','component','claims','fences','bug_classes'))
    require(catalog['schema_version']==2 and isinstance(catalog['component'],str) and catalog['component'],'Component identity/schema required')
    for group in ('claims','fences','bug_classes'):require(isinstance(catalog[group],list),'Definition collection must be an array');_ids(catalog[group])
    for c in catalog['claims']:
        _keys(c,('id','statement','preserves','bug_classes','fences'),('id','statement','preserves','bug_classes','fences'))
        require(isinstance(c['statement'],str) and c['statement'] and c['preserves'] and c['bug_classes'] and c['fences'],'Atomic statement, legitimate behavior, class mapping and fence references required')
        for k in ('preserves','bug_classes','fences'):require(isinstance(c[k],list) and all(isinstance(x,str) and x for x in c[k]) and len(set(c[k]))==len(c[k]),'Duplicate/empty claim list')
    for b in catalog['bug_classes']:
        _keys(b,('id','definition','cwe'),('id','definition'));require(b['definition'],'Bug-class definition required')
    for f in catalog['fences']:
        _keys(f,('id','kind','mechanism','controls','check'),('id','kind','mechanism','controls'))
        allowed={'test','lint','type'} if f['kind']=='hard' else {'guidance','review_policy'} if f['kind']=='soft' else set()
        require(f['mechanism'] in allowed and f['controls'],'Explicit hard/static or complementary soft fence required')
        if f['kind']=='hard':require(isinstance(f.get('check'),str) and f['check'],'Hard fence needs a deterministic check identity')
        for c in f['controls']:
            _keys(c,('path','selector','introduced'),('path','selector','introduced'));_path(c['path']);require(isinstance(c['selector'],str) and c['selector'],'Control selector required')
            i=c['introduced'];_keys(i,('repository','ref','path','selector'),('repository','ref','path'));_path(i['path'])
            require(i['repository'] and re.fullmatch('[a-f0-9]{40}',i['ref']),'Original repository and immutable introduction commit required')
    return catalog


def render_rules(catalog):
    """Render the developer-facing companion without creating another authority."""
    validate_catalog(catalog)
    definition=json.dumps(catalog,indent=2,sort_keys=True)
    return f"""# Component security rules

This file is owned with this component, like its source, dependencies and
CODEOWNERS rules. Developers and agents may amend it through normal repository
review. It is not a security-team lock file.

The reserved block below is the human review surface for the adjacent
`claims.json`. It must contain exactly the same schema-2 object. Edit the claim,
bug-class, fence and control definitions together; run `claim-rules.py --check`
before review. The factory refuses divergent definitions. Computed hashes,
execution verdicts, model output and ticket journals belong in receipts, not in
this file.

## Exact claim shape

| Object | Required fields | Meaning |
| --- | --- | --- |
| Catalog | `schema_version`, `component`, `claims`, `fences`, `bug_classes` | One portable definition at the owning component root. |
| Claim | `id`, `statement`, `preserves`, `bug_classes`, `fences` | The security property, legitimate behavior, mapped failure classes and enforcing fences. |
| Bug class | `id`, `definition` | A recurring failure mechanism; optional `cwe` is descriptive, not coverage proof. |
| Fence | `id`, `kind`, `mechanism`, `controls` | A hard deterministic check or complementary soft intent. Hard fences also require `check`. |
| Control | `path`, `selector`, `introduced` | Current component-relative control and its stable selector. |
| Introduction | `repository`, `ref`, `path` | Original repository, full introducing commit and original path; optional `selector` records a reviewed rename. |

{RULES_START}
```json
{definition}
```
{RULES_END}
"""


def validate_rules(raw,catalog):
    require(isinstance(raw,(bytes,str)),'RULES.md bytes required')
    text=raw.decode() if isinstance(raw,bytes) else raw
    require(text.count(RULES_START)==1 and text.count(RULES_END)==1,'RULES.md needs exactly one reserved claim-definition block')
    before,tail=text.split(RULES_START,1);block,after=tail.split(RULES_END,1)
    match=re.fullmatch(r'\s*```json\s*\n(.*?)\n```\s*',block,flags=re.DOTALL)
    require(match is not None,'RULES.md reserved block must be one JSON fence')
    try:definition=json.loads(match.group(1))
    except json.JSONDecodeError as error:raise GateError('RULES.md claim definition is invalid JSON: '+str(error))
    validate_catalog(definition)
    require(definition==catalog,'RULES.md claim definition differs from adjacent claims.json')
    require('Exact claim shape' in before,'RULES.md must describe the exact claim shape before its reserved definition')
    return definition


def _inspect_control(repo,repository,revision,catalog_path,control,origins):
    current=(PurePosixPath(catalog_path).parent/_path(control['path'])).as_posix()
    result={'path':current,'selector':control['selector'],'introduced':copy.deepcopy(control['introduced'])}
    try:body=source_blob(repo,revision,current)
    except GateError:result.update(state='missing',reason='Current control is absent or nonregular');return result
    result['sha256']=sha(body)
    if control['selector'].encode() not in body:result.update(state='selector_missing',reason='Declared selector text absent; resolve rename or replacement');return result
    intro=control['introduced'];origin=repo if intro['repository']==repository else origins.get(intro['repository'])
    if not origin:result.update(state='history_unavailable',reason='Original repository capability missing; portability does not require ancestry in the destination');return result
    try:
        git(origin,'cat-file','-e',intro['ref']+'^{commit}');old=source_blob(origin,intro['ref'],intro['path'])
        original_selector=intro.get('selector',control['selector']);require(isinstance(original_selector,str) and original_selector,'Original selector required')
        require(original_selector.encode() in old,'Control selector absent at introduction')
        parents=git(origin,'show','-s','--format=%P',intro['ref']).decode().split()
        for parent in parents:
            try:prior=source_blob(origin,parent,intro['path'])
            except GateError:continue
            require(original_selector.encode() not in prior,'Referenced commit already inherited this selector; find its introduction or explain a replacement')
    except (GateError,subprocess.CalledProcessError) as error:result.update(state='introduction_unresolved',reason=str(error));return result
    result.update(state='located',introduction_blob_sha256=sha(old),limitation='Git path and selector-text provenance only; deterministic execution must establish control behavior.')
    return result


def catalog_receipt(repo,repository,revision,paths=None,origins=None):
    require(re.fullmatch('[a-f0-9]{40}',revision),'Full immutable subject required');git(repo,'cat-file','-e',revision+'^{commit}')
    if paths is None:
        names=git(repo,'ls-tree','-r','--name-only',revision).decode().splitlines();paths=[p for p in names if PurePosixPath(p).name=='claims.json']
    catalogs=[];claims=[];fences=[];classes=[];components=set()
    for path in paths:
        _path(path);require(PurePosixPath(path).name=='claims.json','One claims.json per owning component root')
        raw=source_blob(repo,revision,path);data=validate_catalog(json.loads(raw));require(data['component'] not in components,'Duplicate component definition');components.add(data['component'])
        rules_path=(PurePosixPath(path).parent/'RULES.md').as_posix()
        try:
            rules_raw=source_blob(repo,revision,rules_path);rules_definition=validate_rules(rules_raw,data)
            rules={'path':rules_path,'state':'synchronized','sha256':sha(rules_raw),'definition':rules_definition}
        except GateError as error:
            if 'Product resource missing or not a regular Git blob' not in str(error):raise
            rules={'path':rules_path,'state':'missing_legacy','reason':'Existing claims.json has no adjacent RULES.md; unchanged legacy definitions remain readable, but any semantic amendment must add the synchronized developer review surface.'}
        catalogs.append({'path':path,'definition':data,'sha256':sha(raw),'rules':rules})
        for b in data['bug_classes']:classes.append({**b,'component':data['component'],'catalog':path})
        for f in data['fences']:
            controls=[_inspect_control(repo,repository,revision,path,c,origins or {}) for c in f['controls']]
            fences.append({'fence':copy.deepcopy(f),'component':data['component'],'catalog':path,'controls':controls})
        for c in data['claims']:claims.append({'claim':copy.deepcopy(c),'component':data['component'],'path':path,'claim_sha256':identity(c)})
    _ids([r['claim'] for r in claims]);_ids([r['fence'] for r in fences]);_ids(classes)
    fs={f['fence']['id']:f for f in fences};bs={b['id'] for b in classes}
    for row in claims:
        c=row['claim'];require(set(c['fences'])<=set(fs) and set(c['bug_classes'])<=bs,'Unresolved fence/bug-class dependency; retrieve its owning catalog')
        row['bindings']=[{'path':control['path'],'state':'present' if control.get('sha256') else 'missing','control_state':control['state'],'sha256':control.get('sha256')} for fid in c['fences'] for control in fs[fid]['controls']]
    result={'schema_version':2,'subject':{'repository':repository,'revision':revision},'catalogs':catalogs,'claims':claims,'fences':fences,'bug_classes':classes,'authority':'Canonical component Git definitions; this generated receipt is not a second editable registry.'}
    result['registry_sha256']=identity(result);return result


def validate_receipt(receipt):
    require(receipt.get('schema_version')==2 and receipt.get('registry_sha256')==identity({k:v for k,v in receipt.items() if k!='registry_sha256'}),'Component receipt integrity mismatch')
    for c in receipt['catalogs']:
        validate_catalog(c['definition']);rules=c.get('rules',{})
        require(rules.get('state') in ('synchronized','missing_legacy'),'Unknown RULES.md state')
        if rules['state']=='synchronized':require(rules.get('definition')==c['definition'] and re.fullmatch('[a-f0-9]{64}',rules.get('sha256','')),'RULES.md receipt binding differs from claims.json')
    return receipt


def map_bug_classes(receipt,classes):
    validate_receipt(receipt);known={b['id'] for b in receipt['bug_classes']};unknown=sorted(set(classes)-known)
    matches=[{'claim_id':r['claim']['id'],'component':r['component'],'fences':r['claim']['fences']} for r in receipt['claims'] if set(classes)&set(r['claim']['bug_classes'])]
    return {'subject':receipt['subject'],'registry_sha256':receipt['registry_sha256'],'unknown_bug_classes':unknown,'candidates':matches,'classification':'unresolved' if unknown or not classes else 'mapped_candidates','coverage_verified':False,'closure_permitted':False}


def fence_health(receipt,execution):
    validate_receipt(receipt);require(execution.get('subject')==receipt['subject'] and execution.get('registry_sha256')==receipt['registry_sha256'],'Fence execution subject/catalog changed')
    records=execution.get('checks',[]);require(len({r['id'] for r in records})==len(records),'Duplicate fence check result')
    checks={r['id']:r for r in records};fences={r['fence']['id']:r for r in receipt['fences']};results=[]
    for row in receipt['claims']:
        hard=[fences[f] for f in row['claim']['fences'] if fences[f]['fence']['kind']=='hard'];states=[]
        if execution.get('evaluator_guard',{}).get('result')=='violated':states.append('violated')
        for f in hard:
            states += ['violated' if c['state'] in ('missing','selector_missing') else 'inconclusive' if c['state']!='located' else 'satisfied_within_scope' for c in f['controls']]
            states.append(checks.get(f['fence']['check'],{}).get('result','inconclusive'))
        result='violated' if 'violated' in states else 'satisfied_within_scope' if hard and states and all(s=='satisfied_within_scope' for s in states) and execution.get('result')=='satisfied_within_scope' else 'inconclusive'
        results.append({'claim_id':row['claim']['id'],'result':result,'hard_fences':[f['fence']['id'] for f in hard],'soft_fences':[fid for fid in row['claim']['fences'] if fences[fid]['fence']['kind']=='soft']})
    result={'subject':receipt['subject'],'registry_sha256':receipt['registry_sha256'],'execution_sha256':identity(execution),'claims':results,'result':'violated' if any(r['result']=='violated' for r in results) else 'satisfied_within_scope' if all(r['result']=='satisfied_within_scope' for r in results) else 'inconclusive','coverage':'Within executed fence scope; no universal bug-class coverage or lifecycle closure.'}
    result['health_sha256']=identity(result);return result


def execute_fences(repo,receipt,checks,expected_checks_sha256,evaluator_manifest,max_seconds=120):
    validate_receipt(receipt);require(identity(checks)==expected_checks_sha256,'Check plan changed from trusted receipt')
    needed={f['fence']['check'] for f in receipt['fences'] if f['fence']['kind']=='hard' and any(f['fence']['id'] in c['claim']['fences'] for c in receipt['claims'])}
    require({c['id'] for c in checks}==needed and len(checks)==len(needed),'Required fence checks missing/duplicated')
    require(evaluator_manifest,'Trusted evaluator receipt required');revision=receipt['subject']['revision'];guard=evaluator_guard(repo,revision,evaluator_manifest)
    output={'subject':receipt['subject'],'registry_sha256':receipt['registry_sha256'],'check_plan_sha256':identity(checks),'evaluator_guard':guard,'checks':[],'result':'inconclusive'}
    if guard['result']!='satisfied_within_scope':output['result']='violated';return output
    with tempfile.TemporaryDirectory(prefix='factory-fences-') as temp:
        root=Path(temp);archive=root/'source.tar';archive.write_bytes(git(repo,'archive',revision));source=root/'source';source.mkdir()
        with tarfile.open(archive) as tar:tar.extractall(source,filter='data')
        snapshot=lambda:{str(p.relative_to(source)):sha(p.read_bytes()) for p in source.rglob('*') if p.is_file()}
        before=snapshot();started=time.monotonic()
        for check in checks:
            remaining=max_seconds-(time.monotonic()-started)
            if remaining<=0:output['checks'].append({'id':check['id'],'result':'inconclusive','reason':'Fence budget exhausted'});continue
            cwd=source/_path(check.get('cwd','.'))
            env={k:v for k,v in os.environ.items() if k in ('PATH','HOME','TMPDIR','GOPATH','GOCACHE','GOMODCACHE','GOTOOLCHAIN','JAVA_HOME','LANG','LC_ALL')};env.update({'PYTHONDONTWRITEBYTECODE':'1','GOWORK':'off','FACTORY_CANDIDATE_REVISION':revision,'FACTORY_CHECK_ID':check['id']})
            try:r=command(check['argv'],cwd,min(check.get('timeout',60),remaining),environment=env)
            except OSError as error:
                output['checks'].append({'id':check['id'],'argv':check['argv'],'result':'unsupported','reason':str(error)});continue
            q=qualify_execution(check,r,revision)
            test_fence=any(f['fence']['mechanism']=='test' and f['fence'].get('check')==check['id'] for f in receipt['fences'])
            if test_fence and check.get('execution',{}).get('format')=='command':q={**q,'result':'inconclusive','reason':'A QA fence needs named-test evidence, not exit status alone.'}
            output['checks'].append({**r,'id':check['id'],'execution_result':r['result'],'test_evidence':q,'result':q['result']})
        output['inputs_changed']=before!=snapshot()
    output['result']='violated' if any(c['result']=='violated' for c in output['checks']) else 'inconclusive' if output['inputs_changed'] or any(c['result']!='satisfied_within_scope' for c in output['checks']) else 'satisfied_within_scope';return output


def _semantic(value):
    if isinstance(value,dict):return {k:_semantic(v) for k,v in value.items()}
    if isinstance(value,list):return sorted((_semantic(v) for v in value),key=lambda x:json.dumps(x,sort_keys=True))
    return value


def compare_definitions(base,head,health,policy,reviews):
    validate_receipt(base);validate_receipt(head)
    require(health.get('registry_sha256')==head['registry_sha256'] and health.get('subject')==head['subject'] and health.get('health_sha256')==identity({k:v for k,v in health.items() if k!='health_sha256'}),'Health does not bind current catalog')
    require(base['subject']['repository']==head['subject']['repository'] or policy.get('authorized_component_transfer'),'Cross-repository comparison needs an explicit transfer scope')
    b={r['claim']['id']:r['claim'] for r in base['claims']};h={r['claim']['id']:r['claim'] for r in head['claims']}
    bf={r['fence']['id']:r['fence'] for r in base['fences']};hf={r['fence']['id']:r['fence'] for r in head['fences']}
    changed_claims=sorted(k for k in b.keys()|h.keys() if _semantic(b.get(k))!=_semantic(h.get(k)));changed_fences=sorted(k for k in bf.keys()|hf.keys() if _semantic(bf.get(k))!=_semantic(hf.get(k)))
    bc={r['id']:{k:v for k,v in r.items() if k not in ('component','catalog')} for r in base['bug_classes']};hc={r['id']:{k:v for k,v in r.items() if k not in ('component','catalog')} for r in head['bug_classes']}
    taxonomy_changed=bc!=hc
    br={c['definition']['component']:{'state':c.get('rules',{}).get('state'),'sha256':c.get('rules',{}).get('sha256')} for c in base['catalogs']}
    hr={c['definition']['component']:{'state':c.get('rules',{}).get('state'),'sha256':c.get('rules',{}).get('sha256')} for c in head['catalogs']}
    changed_rules=sorted(k for k in br.keys()|hr.keys() if br.get(k)!=hr.get(k))
    old_components={kind+':'+r[key]['id']:r['component'] for kind,key,rows in [('claim','claim',base['claims']),('fence','fence',base['fences'])] for r in rows}
    new_components={kind+':'+r[key]['id']:r['component'] for kind,key,rows in [('claim','claim',head['claims']),('fence','fence',head['fences'])] for r in rows}
    old_components.update({'bug_class:'+r['id']:r['component'] for r in base['bug_classes']})
    new_components.update({'bug_class:'+r['id']:r['component'] for r in head['bug_classes']})
    changed_components=sorted(k for k in old_components.keys()&new_components.keys() if old_components[k]!=new_components[k])
    changed=bool(changed_claims or changed_fences or taxonomy_changed or changed_components or changed_rules or policy.get('ownership_changed'))
    owner_map=policy.get('component_owners')
    known=set(policy.get('owners',[]))|{o for owners in (owner_map or {}).values() for o in owners}
    approved=[r for r in reviews if r.get('reviewer') in known and r.get('state')=='APPROVED' and r.get('base')==base['subject']['revision'] and r.get('head')==head['subject']['revision'] and r.get('reference')]
    affected={r['component'] for view in (base,head) for r in view['claims'] if r['claim']['id'] in changed_claims}|{r['component'] for view in (base,head) for r in view['fences'] if r['fence']['id'] in changed_fences}
    affected|=set(changed_rules)
    if taxonomy_changed or changed_components or policy.get('ownership_changed'):affected|={c['definition']['component'] for view in (base,head) for c in view['catalogs']}
    covered=bool(approved) if owner_map is None else bool(affected) and all(any(r['reviewer'] in owner_map.get(c,[]) for r in approved) for c in affected)
    blockers=[]
    missing_rules=sorted(c['definition']['component'] for c in head['catalogs'] if c.get('rules',{}).get('state')!='synchronized')
    semantic_change=bool(changed_claims or changed_fences or taxonomy_changed or changed_components)
    if missing_rules and (semantic_change or changed_rules):blockers.append('Changed component claims need an adjacent synchronized RULES.md with the exact claim shape: '+', '.join(missing_rules))
    review_required=policy.get('definition_review_required',False)
    if changed and review_required and not covered:blockers.append('Definition/fence/class amendment needs current code-owner review for every affected component.')
    removed=sorted(b.keys()-h.keys());retired=policy.get('retired_claims',{})
    if any(not retired.get(k) for k in removed):blockers.append('Removed claims need an explicit owner-authorized retirement/transfer decision; deleting the catalog cannot disable the gate.')
    if health['result']!='satisfied_within_scope':blockers.append('Required hard fences are missing, failing or unverified; soft review cannot override them.')
    result={'base':base['subject'],'subject':head['subject'],'changed_claims':changed_claims,'changed_fences':changed_fences,'changed_rules':changed_rules,'missing_rules':missing_rules,'bug_class_definitions_changed':taxonomy_changed,'changed_component_ownership':changed_components,'removed_claims':removed,'result':'violated' if health['result']=='violated' else 'inconclusive' if blockers else 'satisfied_within_scope','blockers':blockers,'pr_blocked':bool(blockers),'definition_changes_allowed':changed and (not review_required or covered),'review_policy':'native_repository','additional_security_approval':False,'health_sha256':health['health_sha256'],'policy_sha256':identity(policy),'review_receipts_sha256':identity(reviews),'next_action':'Block the PR and reconcile the listed requirements; on an already integrated branch, create/reuse a Linear corrective finding keyed by claim/fence and open a bounded corrective PR under existing authority.' if blockers else 'Normal integration gates still apply; ordinary source refactors do not require digest edits.','authority':'Reviews/policy must be retrieved from trusted native owner/repository controls; this helper does not authenticate caller-supplied review assertions or install CI.'}
    result['change_gate_sha256']=identity(result);return result


def execution_contract(receipt,claim_id,checks,evaluator_manifest,formal=None):
    """Generated legacy-stage compatibility view, never another authored claim file."""
    validate_receipt(receipt);row=next((r for r in receipt['claims'] if r['claim']['id']==claim_id),None);require(row is not None,'Unknown canonical claim')
    authored=row['claim'];fences=[f for f in receipt['fences'] if f['fence']['id'] in authored['fences'] and f['fence']['kind']=='hard'];needed={f['fence']['check'] for f in fences}
    require(needed and {c['id'] for c in checks}==needed and len(checks)==len(needed),'Executable hard fences required; soft fences cannot replace them')
    bindings=sorted({c['path'] for f in fences for c in f['controls']})
    generated={'schema_version':1,'id':authored['id'],'version':1,'owner':'CODEOWNERS for '+row['path'],'property':authored['statement'],'bindings':bindings,
               'obligations':[{'id':authored['id']+':'+kind,'kind':kind,'predicate':predicate,'checks':sorted(needed)} for kind,predicate in [('security',authored['statement']),('business','; '.join(authored['preserves'])),('architecture','Required fences remain active for component '+row['component'])]],
               'required_behaviors':authored['preserves'],'prohibited_behaviors':[],'check_specs_sha256':identity(checks),'evaluator_manifest_sha256':identity(evaluator_manifest),
               'source_definition':{'component':row['component'],'path':row['path'],'subject':receipt['subject'],'claim_id':authored['id'],'fence_ids':authored['fences'],'bug_classes':authored['bug_classes']},'generation_note':'Legacy execution view only; version is adapter format, canonical definition version is its Git subject.'}
    if formal is not None:generated['formal']=copy.deepcopy(formal)
    return generated
