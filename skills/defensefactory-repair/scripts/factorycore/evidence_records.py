"""Saved observations and replayable comparisons; never serialize private reasoning."""
import datetime
import json
from pathlib import Path
from .core import canonical, identity, require, sha


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def dependency(name, path, kind='evidence_input'):
    path = Path(path).resolve()
    require(path.is_file() and not path.is_symlink(), 'Missing/nonregular dependency: ' + name)
    raw = path.read_bytes()
    return {'name': name, 'path': str(path), 'kind': kind, 'sha256': sha(raw), 'bytes': len(raw)}


def write_json(path, value):
    path = Path(path)
    with path.open('x') as out:
        json.dump(value, out, indent=2)
        out.write('\n')
    path.chmod(0o600)


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('Non-finite JSON number')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def select(value, pointer):
    require(not pointer or pointer.startswith('/'), 'Use a JSON Pointer, or empty string for the whole value')
    if pointer:
        for token in pointer[1:].split('/'):
            token = token.replace('~1', '/').replace('~0', '~')
            if isinstance(value, list):
                require(token.isdigit() and str(int(token)) == token, 'Invalid array selector')
                value = value[int(token)]
            else:
                require(isinstance(value, dict), 'Pointer does not select a container')
                value = value[token]
    return value


def comparison_outcome(recipe, left, right):
    require(recipe['mode'] in ('bytes', 'json') and recipe['expected'] in ('equal', 'different'), 'Unsupported comparison recipe')
    try:
        if recipe['mode'] == 'json':
            left = canonical(select(strict_json(left), recipe.get('left_pointer', '')))
            right = canonical(select(strict_json(right), recipe.get('right_pointer', '')))
        equal = left == right
        return {'result': 'satisfied_within_scope' if equal == (recipe['expected'] == 'equal') else 'violated',
                'observed_equal': equal}
    except (ValueError, KeyError, IndexError, TypeError, UnicodeError):
        return {'result': 'inconclusive', 'observed_equal': None,
                'error': 'Inputs are not unambiguous JSON at the declared selectors'}


def compare_files(identifier, left, right, output, *, mode='bytes', expected='equal',
                  left_pointer='', right_pointer='', replays=None):
    """Snapshot both inputs BEFORE comparing; preserve negative/invalid outcomes."""
    require(identifier and mode in ('bytes', 'json') and expected in ('equal', 'different'), 'Comparison ID/mode/expectation required')
    require(mode == 'json' or not (left_pointer or right_pointer), 'Pointers require JSON mode')
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=False, mode=0o700)
    recipe = {'mode': mode, 'expected': expected, 'left_pointer': left_pointer, 'right_pointer': right_pointer}
    preparation={'record_type':'comparison_preparation','id':identifier,'recipe':recipe,
                 'requested_inputs':{'left':str(Path(left).resolve()),'right':str(Path(right).resolve())},'started_at':now()}
    write_json(root/'preparation.json',preparation)
    inputs, deps = {}, []
    for name, source in [('left', left), ('right', right)]:
        source = Path(source).resolve()
        try:
            raw = source.read_bytes()
        except OSError as error:
            failed={**preparation,'record_type':'comparison_preparation_failure','result':'inconclusive',
                    'missing_input':name,'error':type(error).__name__,'evidence_dependencies':deps,'finished_at':now()}
            write_json(root/'comparison.json',failed)
            return failed
        snapshot = root / (name + '.input')
        snapshot.write_bytes(raw)
        snapshot.chmod(0o600)
        inputs[name] = raw
        dep = dependency(name, snapshot)
        dep['relative_path'] = snapshot.name
        dep['source_path'] = str(source)
        deps.append(dep)
    record = {'record_type': 'saved_comparison', 'schema_version': 1, 'id': identifier,
              'started_at': preparation['started_at'], 'recipe': recipe, 'evidence_dependencies': deps,
              'replay': 'evidence-compare.py --replay RECEIPT --output NEW_DIRECTORY',
              'scope': 'Declared file comparison only; not semantic correctness or authenticated publication.'}
    record.update(comparison_outcome(recipe, inputs['left'], inputs['right']), finished_at=now())
    if replays:
        record['replays_sha256'] = replays
    write_json(root / 'comparison.json', record)
    return record


def replay_comparison(record, inputs):
    require(record.get('record_type') == 'saved_comparison', 'Not a saved comparison')
    require({d['name'] for d in record['evidence_dependencies']} == {'left', 'right'}, 'Comparison input inventory differs')
    for dep in record['evidence_dependencies']:
        raw = inputs[dep['name']]
        require(sha(raw) == dep['sha256'] and len(raw) == dep['bytes'], 'Comparison input changed: ' + dep['name'])
    actual = comparison_outcome(record['recipe'], inputs['left'], inputs['right'])
    require(all(record.get(k) == v for k, v in actual.items()), 'Saved comparison outcome differs from replay')
    return actual


def saved_observation(identifier, source, output, dependencies=()):
    """Persist exact nonsecret connector bytes and explicit dependency edges."""
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=False, mode=0o700)
    snapshot = root / 'observation.input'
    snapshot.write_bytes(Path(source).read_bytes())
    snapshot.chmod(0o600)
    deps = [dependency('observation', snapshot)]
    deps.extend(dependency('input-' + str(i), f) for i, f in enumerate(dependencies))
    result = {'record_type': 'saved_observation', 'schema_version': 1, 'id': identifier,
              'captured_at': now(), 'evidence_dependencies': deps,
              'result': 'recorded', 'scope': 'Transport snapshot, not an inference or gate pass.'}
    write_json(root / 'observation.json', result)
    return result
