"""Bind produced/consumed artifact bytes to an observed clean Git source."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import io
import tarfile
from .core import canonical, identity, require, sha
from .evidence_records import dependency, write_json


def source_snapshot(spec):
    repo = Path(spec['source_repository']).resolve()
    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.PIPE).decode().strip()
    revision = git('rev-parse', 'HEAD')
    require(revision == spec['subject'].get('revision'), 'Build/runtime worktree HEAD differs from the declared subject')
    require(not git('status', '--porcelain', '--untracked-files=no'), 'Tracked source is dirty; create a declared candidate revision first')
    untracked = git('ls-files', '--others', '--exclude-standard').splitlines()
    allowed = {str(Path(p).resolve()) for p in spec.get('evaluator_files', {})}
    require(all(str((repo / p).resolve()) in allowed for p in untracked),
            'Untracked source inputs must be frozen evaluators or committed before building')
    return {'repository_path': str(repo), 'revision': revision, 'tree': git('rev-parse', 'HEAD^{tree}'),
            'tracked_clean': True, 'untracked_inputs': {p: sha((repo / p).read_bytes()) for p in untracked},
            'limitation': 'Observed Git inputs, not a hermetic build: ignored files, external dependencies/toolchain still need declared evidence.'}


def validate_binding(record, read_bytes):
    require(record.get('record_type') == 'artifact_binding' and record.get('build_exit_code') == 0,
            'Successful artifact build binding required')
    require(record['source_before'] == record['source_after'] and
            record['source_before']['revision'] == record['subject'].get('revision'), 'Artifact source changed during build')
    deps = record['evidence_dependencies']
    require({d['name'] for d in deps} == {'payload', 'build_specification', 'build_log', 'build_execution'}, 'Artifact dependency inventory differs')
    data = {}
    for dep in deps:
        raw = read_bytes(dep)
        require(sha(raw) == dep['sha256'] and len(raw) == dep['bytes'], 'Artifact dependency changed: ' + dep['name'])
        data[dep['name']] = raw
    spec = json.loads(data['build_specification'])
    require(identity(spec) == record['build_specification_sha256'] and spec['subject'] == record['subject'],
            'Artifact build specification subject differs')
    require(sha(data['payload']) == record['artifact']['sha256'], 'Artifact payload differs')
    execution=json.loads(data['build_execution'])
    require(execution['specification_sha256']==record['build_specification_sha256']
            and execution['subject']==record['subject'] and execution['exit_code']==record['build_exit_code']
            and execution['result']=='satisfied_within_scope' and execution['raw_log_sha256']==sha(data['build_log']),
            'Artifact differs from actual build execution receipt')
    name=record['artifact']['name']
    require(spec.get('produces_artifacts',{}).get(name)==record['artifact']['produced_path'], 'Artifact output differs from build specification')
    return data


def bundle_artifact(bundle, requirements, *, resource=None, name=None, depth=0):
    """Resolve an artifact from verified archive bytes, never the previous host's paths."""
    from .handoff_bundle import verify_bundle
    checked=verify_bundle(bundle,requirements,_depth=depth+1)
    require(checked['bundle_complete'],'Artifact source bundle does not verify: '+str(checked['problems']))
    with tarfile.open(fileobj=io.BytesIO(bundle),mode='r:*') as archive:
        manifest=json.load(archive.extractfile('bundle-manifest.json'));index={e['id']:e for e in manifest['resources']}
        matches=[]
        for key,entry in index.items():
            if entry['kind'] not in ('artifact_binding','artifact_binding_reference'):continue
            record=json.load(archive.extractfile(entry['archive_path']))
            if (resource is None or key==resource) and (name is None or record['artifact']['name']==name):matches.append((key,entry,record))
        require(len(matches)==1,'Select one unambiguous artifact binding resource/name')
        key,entry,record=matches[0]
        payload_key=manifest['dependencies'][key]['payload']
        payload=archive.extractfile(index[payload_key]['archive_path']).read()
        return key,entry,record,payload


def validate_use(record, read_bytes, depth=0):
    if record.get('record_type')!='bundle_artifact_reference':
        validate_binding(record,read_bytes)
        return record
    deps={d['name']:d for d in record['evidence_dependencies']}
    require(set(deps)=={'source-bundle','external-requirements','payload'},'Bundle artifact dependency inventory differs')
    data={}
    for name,dep in deps.items():
        data[name]=read_bytes(dep)
        require(sha(data[name])==dep['sha256'] and len(data[name])==dep['bytes'],'Restored artifact input changed: '+name)
    key,entry,original,payload=bundle_artifact(data['source-bundle'],json.loads(data['external-requirements']),
        resource=record['source_binding_resource'],depth=depth)
    require(entry['sha256']==record['source_binding_sha256'] and original['subject']==record['subject']
            and original['artifact']==record['artifact'] and payload==data['payload'], 'Restored artifact differs from immutable origin')
    return original


def restore_artifact(bundle_file, requirements_file, output, *, resource=None, name=None):
    bundle=Path(bundle_file).read_bytes();requirements_raw=Path(requirements_file).read_bytes()
    retrieved_sha256=sha(bundle)
    # Keep the immutable direct build origin instead of nesting each stage's whole history.
    for level in range(4):
        key,entry,original,payload=bundle_artifact(bundle,json.loads(requirements_raw),resource=resource,name=name)
        if original.get('record_type')=='artifact_binding':break
        with tarfile.open(fileobj=io.BytesIO(bundle),mode='r:*') as archive:
            manifest=json.load(archive.extractfile('bundle-manifest.json'));index={e['id']:e for e in manifest['resources']}
            graph=manifest['dependencies'][key]
            bundle=archive.extractfile(index[graph['source-bundle']]['archive_path']).read()
            requirements_raw=archive.extractfile(index[graph['external-requirements']]['archive_path']).read()
        resource=original['source_binding_resource'];name=None
    else:raise ValueError('Artifact origin chain exceeds bounded restoration depth')
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False,mode=0o700)
    (root/'source-bundle.tar.gz').write_bytes(bundle)
    (root/'source-requirements.json').write_bytes(requirements_raw)
    (root/'payload').write_bytes(payload);(root/'payload').chmod(original['artifact']['mode'])
    record={'record_type':'bundle_artifact_reference','schema_version':1,'subject':original['subject'],
            'artifact':original['artifact'],'source_binding_resource':key,'source_binding_sha256':entry['sha256'],
            'retrieved_bundle_sha256':retrieved_sha256,
            'scope':'Restored bytes from verified immutable receipts; not a new build or execution.',
            'evidence_dependencies':[dependency('source-bundle',root/'source-bundle.tar.gz','source_evidence_archive'),
                dependency('external-requirements',root/'source-requirements.json','external_requirements'),
                dependency('payload',root/'payload','artifact_payload')]}
    write_json(root/'binding-reference.json',record)
    return record


def prepare_artifacts(spec):
    produced = spec.get('produces_artifacts', {})
    require(not produced or spec.get('source_repository'), 'Artifact production requires --source-repo')
    for name, path in produced.items():
        require(re.fullmatch(r'[A-Za-z0-9_-]+', name) and not Path(path).exists(),
                'Use a safe artifact name and a NEW output file; preserve old builds')
    before = source_snapshot(spec) if spec.get('source_repository') else None
    bindings = {}
    for name, path in spec.get('uses_artifacts', {}).items():
        raw = Path(path).read_bytes()
        binding = json.loads(raw)
        validate_use(binding, lambda d: Path(d['path']).read_bytes())
        require(binding['subject'] == spec['subject'], 'Consumed artifact source differs from command subject; select the comparison/variant scope')
        payload = next(d['path'] for d in binding['evidence_dependencies'] if d['name'] == 'payload')
        require(any(payload == arg or (payload + ':') in arg or ('source=' + payload + ',') in arg for arg in spec['argv']),
                'Bound artifact is not used by the actual producer argv')
        bindings[name] = {'path': str(Path(path).resolve()), 'sha256': sha(raw), 'record': binding}
    return {'source_before': before, 'uses': bindings}


def finish_artifacts(spec, preparation, root, record):
    """Return dependencies; preserve produced bytes even when post-build validation fails."""
    result = {'source_before': preparation['source_before'], 'uses': {}, 'produced': {}}
    deps, pending = [], []
    for name, item in preparation['uses'].items():
        require(sha(Path(item['path']).read_bytes()) == item['sha256'], 'Consumed artifact binding changed during execution')
        validate_use(item['record'], lambda d: Path(d['path']).read_bytes())
        result['uses'][name] = {'binding_sha256': item['sha256'], 'subject': item['record']['subject']}
        deps.append(dependency('used-artifact-' + name, item['path'], 'artifact_binding'))
    retained = []
    for name, path in spec.get('produces_artifacts', {}).items():
        source = Path(path)
        if not source.exists() and record['exit_code'] != 0:
            result['produced'][name] = {'unavailable':'Producer failed without this output'}
            continue
        require(source.is_file() and not source.is_symlink(), 'Declared build output missing/nonregular: ' + name)
        directory = root / 'artifacts' / name
        directory.mkdir(parents=True, exist_ok=False)
        payload = directory / 'payload'
        shutil.copy2(source, payload)
        artifact = {'name': name, 'sha256': sha(payload.read_bytes()), 'bytes': payload.stat().st_size,
                    'mode': payload.stat().st_mode & 0o777, 'produced_path': str(source.resolve())}
        retained.append((name, directory, payload, artifact))
    after = source_snapshot(spec) if spec.get('source_repository') else None
    result['source_after'] = after
    require(after == preparation['source_before'], 'Source changed while producer ran')
    for name,directory,payload,artifact in retained:
        binding = {'record_type': 'artifact_binding', 'schema_version': 1, 'subject': spec['subject'],
                   'source_before': preparation['source_before'], 'source_after': after,
                   'build_exit_code': record['exit_code'], 'build_specification_sha256': identity(spec),
                   'artifact': artifact, 'evidence_dependencies': [dependency('payload', payload, 'artifact_payload'),
                       dependency('build_specification', record['specification_reference'], 'command_specification'),
                       dependency('build_log', record['raw_log_reference'], 'raw_log')]}
        if record['exit_code'] != 0 or record.get('timed_out') or record.get('start_error'):
            binding['record_type'] = 'failed_artifact_observation'
        path = directory / 'binding.json'
        pending.append((path,binding))
        result['produced'][name] = {'binding': str(path), **artifact}
    return result, deps, pending


def seal_artifacts(pending, execution_path):
    """The finished build receipt hashes no binding receipt, avoiding a hash cycle."""
    for path,binding in pending:
        binding['evidence_dependencies'].append(dependency('build_execution',execution_path,'execution_receipt'))
        write_json(path,binding)


def expand_artifacts(argv, bindings):
    result = list(argv)
    for name, file in bindings.items():
        record = json.loads(Path(file).read_text())
        payload = next(d['path'] for d in record['evidence_dependencies'] if d['name'] == 'payload')
        result = [arg.replace('{artifact:' + name + '}', payload) for arg in result]
    return result
