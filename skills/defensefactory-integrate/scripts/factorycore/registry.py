"""Read-only claim registry derived from an immutable product Git tree."""
import json
import re
import subprocess
from pathlib import PurePosixPath
from .core import require,identity,sha
from .claims import validate_claim


def source_blob(repo,revision,path):
    require(bool(re.fullmatch('[a-f0-9]{40}',revision)), 'Full immutable Git revision required')
    p=PurePosixPath(path)
    require(not p.is_absolute() and '..' not in p.parts and str(p)==path and '\\' not in path, 'Unsafe product resource path')
    mode=subprocess.check_output(['git','-C',str(repo),'ls-tree',revision,'--',path],stderr=subprocess.PIPE).decode()
    require(mode.startswith('100644 blob ') or mode.startswith('100755 blob '), 'Product resource missing or not a regular Git blob')
    return subprocess.check_output(['git','-C',str(repo),'show',revision+':'+path],stderr=subprocess.PIPE)


def registry_view(repo,repository,revision,manifest_path):
    raw=source_blob(repo,revision,manifest_path);manifest=json.loads(raw)
    if manifest.get('schema_version')==2:
        from .component_claims import catalog_receipt
        return catalog_receipt(repo,repository,revision)
    require(manifest.get('schema_version')==1 and bool(manifest.get('claims')), 'Empty/unsupported claim registry')
    claims=[];seen=set()
    for item in manifest['claims']:
        data=source_blob(repo,revision,item['path']);claim=json.loads(data);digest=validate_claim(claim)
        require(claim['id'] not in seen, 'Duplicate claim identity in product registry');seen.add(claim['id'])
        bindings=[]
        for path in claim['bindings']:
            try:body=source_blob(repo,revision,path)
            except (ValueError,subprocess.CalledProcessError):bindings.append({'path':path,'state':'missing'});continue
            bindings.append({'path':path,'state':'present','sha256':sha(body)})
        resources=[]
        for path in item.get('resources',[]):resources.append({'path':path,'sha256':sha(source_blob(repo,revision,path))})
        claims.append({'claim':claim,'claim_sha256':digest,'blob_sha256':sha(data),'path':item['path'],'bindings':bindings,'resources':resources,'coverage':'bindings_present_only; not control enforcement'})
    result={'schema_version':1,'subject':{'repository':repository,'revision':revision},'manifest_path':manifest_path,'manifest_sha256':sha(raw),'claims':claims,'authority':'Product Git blobs; this is a derived view, not a second editable claim registry.'}
    result['registry_sha256']=identity(result);return result


def validate_lineage(child,parent,relation,evidence):
    require(relation in ('variant_of','supersedes','split_from','merged_from','related_boundary'), 'Unknown claim relation')
    require(bool(evidence), 'Claim lineage evidence missing')
    validate_claim(child);validate_claim(parent)
    if relation in ('variant_of','supersedes'):
        require(child['id']==parent['id'] and child['version']>parent['version'] and child['property']==parent['property'], 'Property identity/version lost across variant lineage')
    return {'relation':relation,'parent':{'id':parent['id'],'version':parent['version'],'sha256':identity(parent)},'child':{'id':child['id'],'version':child['version'],'sha256':identity(child)},'evidence':evidence,'approval':'requires governing policy; lineage validation is not approval'}


def validate_registry(view):
    if view.get('schema_version')==2:
        from .component_claims import validate_receipt
        return validate_receipt(view)
    require(view.get('registry_sha256')==identity({k:v for k,v in view.items() if k!='registry_sha256'}),'Registry view integrity mismatch')
    for row in view['claims']:
        require(row['claim_sha256']==validate_claim(row['claim']),'Claim differs from product view digest')
    return view
