"""Bounded, offline fixture assembly. Fixture provenance never labels a product build."""
import io
import json
from pathlib import Path, PurePosixPath
import tarfile
from .core import require, sha, identity
from .evidence_records import dependency, now, write_json


def relative(name, empty=False):
    require(isinstance(name, str) and (name or empty), 'Relative fixture path required')
    p = PurePosixPath(name)
    require(not p.is_absolute() and '..' not in p.parts and '\\' not in name
            and (not name or str(p) == name), 'Unsafe fixture path')
    return name


def assemble(plan, read_input):
    require(plan.get('id') and plan.get('reference') and plan.get('inputs')
            and plan.get('required_paths'), 'Fixture needs ID, ticket reference, inputs and required paths')
    require(len(plan['inputs']) <= 16 and len({i['id'] for i in plan['inputs']}) == len(plan['inputs']),
            'Unique bounded fixture inputs required')
    tree = {}; total = 0
    for item in plan['inputs']:
        require(item.get('reference') and item.get('mappings'), 'Each input needs its provenance reference and explicit mappings')
        raw = read_input(item['id'])
        require(len(raw) <= 128*1024*1024 and sha(raw) == item['sha256'], 'Fixture input bytes differ')
        replacements = set(item.get('replace', [])); replaced = set(); selected = set()
        for name in replacements: relative(name)
        with tarfile.open(fileobj=io.BytesIO(raw), mode='r:*') as archive:
            seen = set(); unpacked = 0
            for member in archive:
                unpacked += member.size
                require(len(seen) < 10000 and unpacked <= 256*1024*1024, 'Fixture archive exceeds bounds')
                name = member.name.rstrip('/')
                relative(name)
                require(name not in seen, 'Duplicate fixture archive member'); seen.add(name)
                require(member.isdir() or member.isfile(), 'Fixture links/devices are unsupported')
                if member.isdir(): continue
                for mapping in item['mappings']:
                    prefix = relative(mapping['from'], empty=True)
                    dest = relative(mapping['to'], empty=True)
                    if prefix and not name.startswith(prefix+'/'): continue
                    suffix = name[len(prefix)+1:] if prefix else name
                    target = relative('/'.join(x for x in (dest, suffix) if x))
                    require(target not in selected, 'Mappings alias a fixture path'); selected.add(target)
                    require(target not in tree or target in replacements, 'Explicit replacement required: '+target)
                    if target in tree: replaced.add(target)
                    content = archive.extractfile(member).read(); total += len(content)
                    require(total <= 256*1024*1024 and len(tree) < 10000, 'Assembled fixture exceeds bounds')
                    tree[target] = (content, 0o755 if member.mode & 0o111 else 0o644)
        require(selected, 'Fixture input mapping selected no files')
        require(replacements == replaced, 'Declared fixture replacement did not replace an existing file')
    for name in tree:
        require(not any(str(p) in tree for p in PurePosixPath(name).parents if str(p) != '.'),
                'Fixture file/directory collision')
    missing = [relative(p) for p in plan['required_paths'] if p not in tree]
    require(not missing, 'Fixture missing required paths: '+', '.join(missing))
    manifest = {n: {'sha256': sha(raw), 'bytes': len(raw), 'mode': mode} for n,(raw,mode) in sorted(tree.items())}
    return tree, manifest


def prepare(plan_file, opening_file, output):
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=False, mode=0o700)
    plan_file, opening_file = Path(plan_file), Path(opening_file)
    saved = output/'plan.json'; saved.write_bytes(plan_file.read_bytes())
    opening = json.loads(opening_file.read_text()); plan = json.loads(saved.read_text())
    deps = [dependency('plan', saved)]
    snapshot = output/'opening.json'; snapshot.write_bytes(opening_file.read_bytes()); deps.append(dependency('opening', snapshot))
    record = {'record_type': 'fixture_snapshot', 'schema_version': 1, 'captured_at': now(),
              'stage_start_sha256': identity(opening), 'reference': plan.get('reference'),
              'product_subject': opening['scope']['subject'], 'tree_path': str(output/'tree'),
              'evidence_dependencies': deps, 'result': 'inconclusive',
              'scope': 'Offline source fixture only; not candidate execution, image readiness or runtime acceptance.'}
    try:
        require(opening.get('stage_execution_permitted') is True, 'Opened ticket scope required')
        inputs = {}; compressed = 0
        for i,item in enumerate(plan['inputs']):
            source = Path(item['path']); require(source.is_file() and not source.is_symlink(), 'Regular fixture input archive required')
            compressed += source.stat().st_size
            require(compressed <= 128*1024*1024, 'Fixture inputs exceed bounds')
            dest = output/('input-'+str(i)+'.tar'); dest.write_bytes(source.read_bytes()); dest.chmod(0o600)
            deps.append(dependency('input:'+item['id'], dest)); inputs[item['id']] = dest.read_bytes()
        tree, manifest = assemble(plan, inputs.__getitem__)
        for name,(raw,mode) in tree.items():
            path = output/'tree'/name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw); path.chmod(mode)
        record.update(result='recorded', files=manifest,
                      subject={'kind':'fixture_snapshot', 'name':plan['id'], 'snapshot_sha256':identity(manifest)})
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError) as error:
        record['error'] = str(error)
    write_json(output/'fixture.json', record)
    return record


def replay(record, read_dep):
    inputs = {d['name']: read_dep(d) for d in record['evidence_dependencies']}
    for d in record['evidence_dependencies']:
        require(sha(inputs[d['name']]) == d['sha256'] and len(inputs[d['name']]) == d['bytes'], 'Fixture dependency changed')
    opening = json.loads(inputs['opening'])
    require(identity(opening) == record['stage_start_sha256'] and opening['scope']['subject'] == record['product_subject'], 'Fixture scope differs')
    if record['result'] != 'recorded': return  # Retained failed preparation grants no fixture use.
    plan = json.loads(inputs['plan']); _, manifest = assemble(plan, lambda n: inputs['input:'+n])
    require(manifest == record['files'] and record['subject'] ==
            {'kind':'fixture_snapshot', 'name':plan['id'], 'snapshot_sha256':identity(manifest)}, 'Fixture recipe/manifest differs')


def validate_live(record, opening, cwd):
    require(record.get('record_type') == 'fixture_snapshot' and record.get('result') == 'recorded', 'Usable fixture snapshot required')
    replay(record, lambda d: Path(d['path']).read_bytes())
    require(record['stage_start_sha256'] == identity(opening), 'Fixture belongs to another opening')
    root = Path(record['tree_path']).resolve(); cwd = Path(cwd).resolve()
    require(cwd == root or root in cwd.parents, 'Fixture command cwd must be inside its prepared tree')
    observed = {}
    for p in root.rglob('*'):
        require(not p.is_symlink(), 'Fixture tree gained a symlink')
        if p.is_file(): observed[p.relative_to(root).as_posix()] = {'sha256':sha(p.read_bytes()), 'bytes':p.stat().st_size, 'mode':0o755 if p.stat().st_mode & 0o111 else 0o644}
    require(observed == record['files'], 'Fixture tree changed; prepare a new generation')
