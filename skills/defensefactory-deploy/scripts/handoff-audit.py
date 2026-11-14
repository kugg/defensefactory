#!/usr/bin/env python3
"""Snapshot a handoff inventory and observable tool results, excluding private reasoning."""
import argparse
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from factorycore.evidence_inventory import inventory, publication_gate
from factorycore.core import sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', action='append', type=Path)
    p.add_argument('--events', type=Path, default=os.environ.get('DEFENSEFACTORY_EVENT_LOG'))
    p.add_argument('--workspace', type=Path, default=Path.cwd())
    p.add_argument('--opening', type=Path, default=os.environ.get('DEFENSEFACTORY_STAGE_OPENING'))
    p.add_argument('--requirements', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--bundle',action='store_true',help='Also prepare the whole snapshot archive and distinct external requirements')
    p.add_argument('--override',type=Path,help='Structured operator override to publish incomplete evidence without claiming readiness')
    a = p.parse_args()
    try:
        registered=os.environ.get('DEFENSEFACTORY_HANDOFF_ROOT')
        if registered and Path(registered).resolve() not in a.output.resolve().parents:
            raise ValueError('Save worker handoff generations inside DEFENSEFACTORY_HANDOFF_ROOT')
        roots = a.root or ([Path(os.environ['DEFENSEFACTORY_EVIDENCE_ROOT'])] if os.environ.get('DEFENSEFACTORY_EVIDENCE_ROOT') else [])
        requirements=a.requirements
        if requirements is None and os.environ.get('DEFENSEFACTORY_EVIDENCE_ROOT'):
            candidate=Path(os.environ['DEFENSEFACTORY_EVIDENCE_ROOT'])/'handoff-requirements.json'
            if candidate.is_file():requirements=candidate
        result = inventory(roots, a.output, events=a.events, workspace=a.workspace,
            opening=json.loads(a.opening.read_text()) if a.opening else None,
            requirements=json.loads(requirements.read_text()) if requirements else None)
        gate=publication_gate(result,lambda path:Path(path).read_bytes(),
            json.loads(a.override.read_text()) if a.override else None)
        summary={'inventory':str(a.output/'inventory.json'),'inventory_sha256':sha((a.output/'inventory.json').read_bytes()),
                 'snapshot_handoff_ready':result['snapshot_handoff_ready'],
                 'whole_attempt_handoff_ready':result['whole_attempt_handoff_ready'],
                 'whole_attempt_handoff_reason':result['whole_attempt_handoff_reason'],
                 'publication_gate':gate,'problems':result['problems']}
        if a.bundle:
            from factorycore.handoff_bundle import prepare_bundle
            from factorycore.evidence_records import write_json
            if not result.get('opening'):raise ValueError('Bundle needs the ticket-backed stage opening')
            if not gate['publish_permitted']:raise ValueError('Handoff publication gate blocked: '+'; '.join(gate['problems']))
            scope=result['opening']['scope']
            prepared=prepare_bundle({'case':scope['case'],'attempt':scope['attempt'],'subject':scope['subject'],
                'scope':'whole_attempt','inventory_reference':str(a.output/'inventory.json'),
                'inventory_sha256':summary['inventory_sha256']},a.output/'evidence.tar.gz')
            write_json(a.output/'bundle-prepared.json',prepared)
            summary.update(bundle=prepared['file'],external_requirements=prepared['external_requirements_file'],
                external_requirements_sha256=prepared['external_requirements_sha256'],
                next_action='Publish these exact two files as distinct native resources; verify both with verify-handoff.py using native event IDs.')
        print(json.dumps(summary))
        return 0 if gate['publish_permitted'] else 1
    except (OSError,ValueError,KeyError,TypeError) as error:
        p.error(str(error))


if __name__ == '__main__':
    raise SystemExit(main())
