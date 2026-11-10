"""Check downloaded machine requirements against the frozen bundle preparation."""
import json
from .core import require, sha


def evaluate(expected, bundle, requirements, depth=0):
    from .handoff_bundle import verify_bundle
    require(sha(bundle) == expected['sha256'], 'Downloaded bundle differs from prepared bytes')
    actual = json.loads(requirements)
    require(actual == expected['requirements'], 'Downloaded machine requirements differ; narrative summaries are not external requirements')
    if expected.get('external_requirements_sha256'):
        require(sha(requirements) == expected['external_requirements_sha256'], 'Machine requirements byte digest differs')
    return verify_bundle(bundle, actual, _depth=depth+1)


def replay(record, read_dep, depth=0):
    if record.get('phase') != 'verified': return
    data = {d['name']:read_dep(d) for d in record['evidence_dependencies']}
    result = evaluate(json.loads(data['expected']),data['bundle'],data['requirements'],depth)
    require(result == record['verification'], 'Handoff verification differs from replay')
