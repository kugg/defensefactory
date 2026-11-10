"""Read-only startup, source and publication correspondence; no inferred authority."""
import datetime
import json
from pathlib import Path, PurePosixPath
import subprocess
import re
from .core import require, identity, sha, GateError


ROLES={'reported_revision','trial_target','comparison_revision','supported_release','deployed_artifact'}


def preflight(packet):
    require(packet.get('case') and packet.get('performed_by') and packet.get('protocol_reference'), 'Case, actual performer and frozen protocol reference required')
    targets=packet.get('targets',[])
    require(targets and len({t['id'] for t in targets})==len(targets), 'Unique target inventory required')
    for target in targets:
        require(target.get('role') in ROLES and target.get('subject'), 'Each target needs an explicit role/subject')
    tools=packet.get('exposed_tools')
    require(isinstance(tools,list) and all(isinstance(t,str) and t for t in tools), 'Capture exposed tool names, not MCP resources')
    require(packet.get('tool_inventory_reference'), 'Tool inventory provenance required')
    codeintel=[t for t in tools if 'codeintel' in t.lower()]
    missing=[]
    if not any(t['role']=='trial_target' for t in targets):missing.append('declared_trial_target')
    if not packet.get('scope_authorization_reference'):missing.append('scope_authorization_reference')
    return {'schema_version':2,'stage':'preflight','case':packet['case'],'performed_by':packet['performed_by'],
            'result':'inconclusive' if missing else 'recorded','targets':targets,'missing_inputs':missing,
            'codeintel':{'state':'available' if codeintel else 'not_exposed','tools':codeintel,
                         'basis':'exposed tool inventory; resources do not establish tool availability'},
            'classification_and_formal':packet.get('method_dispositions',{}),
            'question_required':bool(missing),'question_kind':'trial_target_or_scope' if missing else None,
            'closure_permitted':False,'repair_permitted':False,'input_sha256':identity(packet),
            'next_action':'Recover missing scope once; continue only already-authorized investigation.' if missing else 'Resolve subjects and record applicability before repair planning.'}


def package_inventory(paths):
    records=[]
    for name,directory in sorted(paths.items()):
        root=Path(directory).resolve();require((root/'SKILL.md').is_file(), 'Consumed skill entry point missing')
        files={}
        for path in sorted(root.rglob('*')):
            if '__pycache__' in path.parts or path.suffix=='.pyc':continue
            require(not path.is_symlink(), 'Nested skill symlink must be resolved before freezing')
            if path.is_file():files[path.relative_to(root).as_posix()]=sha(path.read_bytes())
        records.append({'skill':name,'files':files,'package_sha256':identity(files)})
    return {'result':'recorded','packages':records,'basis':'Actual consumed installed files, not a Git archive assumed to match them.'}


def resolve_source(repo, ref, dependency_paths=()):
    require(isinstance(ref,str) and ref and not ref.startswith('-') and not any(c in ref for c in '\r\n\x00'), 'Invalid source ref')
    def git(*args):
        return subprocess.run(['git','-C',str(repo),*args],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20)
    observed=datetime.datetime.now(datetime.timezone.utc).isoformat()
    resolved=git('rev-parse','--verify','--end-of-options',ref+'^{commit}')
    if resolved.returncode:
        return {'result':'inconclusive','state':'unavailable_locally','ref':ref,'observed_at':observed,
                'closure_permitted':False,'next_action':'Verify repository identity and authorized fetch; local absence does not invalidate a reported commit.'}
    revision=resolved.stdout.decode().strip();tree=git('rev-parse',revision+'^{tree}')
    require(tree.returncode==0, 'Source tree unavailable')
    deps={}
    for name in dependency_paths:
        path=PurePosixPath(name);require(not path.is_absolute() and '..' not in path.parts and str(path)==name, 'Dependency path escapes source')
        content=git('show',revision+':'+name)
        require(content.returncode==0, 'Dependency input missing at exact source')
        deps[name]={'sha256':sha(content.stdout),'bytes':len(content.stdout)}
    remote=git('remote','get-url','origin')
    return {'result':'recorded','state':'resolved_locally','repository_path':str(Path(repo).resolve()),
            'ref':ref,'revision':revision,'tree':tree.stdout.decode().strip(),'observed_at':observed,
            'remote_url_sha256':sha(remote.stdout.strip()) if remote.returncode==0 else None,
            'dependency_inputs':deps,'remote_freshness':'not_established_by_local_ref_read',
            'limitation':'Record a separately captured authorized fetch and resolved dependency/toolchain manifest before live-source claims.'}


def resolve_reference(ref, repositories):
    """Search only explicitly provisioned ticket-linked namespaces; never scan the host."""
    require(isinstance(repositories,list) and 0<len(repositories)<=16, 'Supply a bounded ticket-linked repository list')
    require(len({r['id'] for r in repositories})==len(repositories), 'Duplicate repository namespace')
    attempts=[];matches={}
    for repository in repositories:
        require(repository.get('reference') and repository.get('repo'), 'Repository identity/path and provenance reference required')
        # A short prefix can name multiple commits in one namespace. Do not hide that
        # ambiguity by finding an unrelated match in a different repository.
        if re.fullmatch('[a-fA-F0-9]{4,39}',ref):
            p=subprocess.run(['git','-C',repository['repo'],'rev-parse','--disambiguate='+ref],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20)
            commits=[]
            for oid in p.stdout.decode().splitlines():
                kind=subprocess.run(['git','-C',repository['repo'],'cat-file','-t',oid],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20)
                if kind.stdout.strip()==b'commit':commits.append(oid)
            if len(commits)>1:
                return {'result':'inconclusive','state':'ambiguous','ref':ref,'namespace':repository['id'],'candidates':commits,'closure_permitted':False}
        result=resolve_source(repository['repo'],ref,repository.get('dependency_paths',[]))
        attempts.append({'namespace':repository['id'],'reference':repository['reference'],'resolution':result})
        if result['state']=='resolved_locally':matches.setdefault(result['revision'],[]).append(attempts[-1])
    if len(matches)==1:
        revision=next(iter(matches));return {'result':'recorded','state':'resolved_locally','ref':ref,'revision':revision,'origins':matches[revision],'attempts':attempts,'closure_permitted':False}
    return {'result':'inconclusive','state':'ambiguous' if matches else 'unavailable_in_supplied_namespaces','ref':ref,'attempts':attempts,'closure_permitted':False,
            'next_action':'Recover the originating snapshot/import/source manifest through the ticket; a product import need not contain the original Git history. Do not guess a full hash.'}


def ticket_snapshot(payload, provenance):
    require(provenance.get('operation')=='retrieval' and provenance.get('reference'), 'Snapshot requires retrieval provenance')
    require(payload.get('id') and 'description' in payload, 'Ticket identity/content missing')
    require(payload['description'] is None or isinstance(payload['description'],str), 'Ticket description must be text or null')
    # Deliberate stable projection: refreshed signed URLs are not immutable evidence IDs.
    selected={k:payload.get(k) for k in ('id','title','description','status','updatedAt')}
    selected['resources']=[{k:a.get(k) for k in ('id','title')} for a in payload.get('attachments') or []]
    raw=json.dumps(selected,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    return {'result':'recorded','snapshot':selected,'snapshot_sha256':sha(raw),'snapshot_bytes':len(raw),
            'description_sha256':sha(payload['description'].encode()) if payload['description'] is not None else None,'provenance':provenance,
            'capture_basis':'Structured retrieval payload; persist this projection as bytes. Timestamp/ID alone is not content verification.',
            'limitation':'Caller must pass actual connector output mechanically; this helper does not authenticate connector provenance.'}


def publication_verify(publication, retrieval, expected, resource_bytes=None, bundle_requirements=None):
    published=bool(publication.get('resource_id') and publication.get('acknowledged_at'))
    def timestamp(value):
        parsed=datetime.datetime.fromisoformat(value.replace('Z','+00:00'))
        require(parsed.tzinfo is not None, 'Timezone required')
        return parsed.timestamp()
    try:later=timestamp(retrieval.get('retrieved_at',''))>timestamp(publication.get('acknowledged_at',''))
    except (ValueError,AttributeError,GateError):later=False
    retrieved=bool(published and retrieval.get('operation')=='retrieval' and
                   retrieval.get('resource_id')==publication['resource_id'] and
                   later)
    verified=bool(retrieved and isinstance(resource_bytes,bytes) and
                  len(resource_bytes)==expected.get('bytes') and sha(resource_bytes)==expected.get('sha256'))
    bundle=None
    if verified and bundle_requirements is not None:
        from .handoff_bundle import verify_bundle
        bundle=verify_bundle(resource_bytes,bundle_requirements)
    complete=bool(bundle and bundle['bundle_complete'])
    return {'result':'satisfied_within_scope' if verified and complete else 'recorded' if verified and bundle_requirements is None else 'inconclusive','published':published,
            'retrieved_again':retrieved,'bytes_verified':verified,'transport_verified':verified,
            'bundle_complete':complete,'bundle_validation':bundle,'evidence_handoff_ready':verified and complete,
            'handoff_ready':verified and complete,'stage_readiness':'not_evaluated',
            'resource_id':publication.get('resource_id'),
            'next_action':'Evaluate the stage contract separately; transport and bundle completeness do not authorize a stage transition.' if complete else 'Verify declared bundle contents and referenced evaluators/specifications/logs; matching download bytes alone is not a complete handoff.' if verified else 'Retrieve again and compare actual bytes; mutation echo or resource listing is not byte readback.'}
