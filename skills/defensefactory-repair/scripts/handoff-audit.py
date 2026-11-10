#!/usr/bin/env python3
"""Snapshot a handoff inventory and observable tool results, excluding private reasoning."""
import argparse
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from factorycore.evidence_inventory import inventory
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
    a = p.parse_args()
    try:
        registered=os.environ.get('DEFENSEFACTORY_HANDOFF_ROOT')
        if registered and Path(registered).resolve() not in a.output.resolve().parents:
            raise ValueError('Save worker handoff generations inside DEFENSEFACTORY_HANDOFF_ROOT')
        roots = a.root or ([Path(os.environ['DEFENSEFACTORY_EVIDENCE_ROOT'])] if os.environ.get('DEFENSEFACTORY_EVIDENCE_ROOT') else [])
        result = inventory(roots, a.output, events=a.events, workspace=a.workspace,
            opening=json.loads(a.opening.read_text()) if a.opening else None,
            requirements=json.loads(a.requirements.read_text()) if a.requirements else None)
        summary={'inventory':str(a.output/'inventory.json'),'inventory_sha256':sha((a.output/'inventory.json').read_bytes()),
                 'snapshot_handoff_ready':result['snapshot_handoff_ready'],
                 'whole_attempt_handoff_ready':result['whole_attempt_handoff_ready'],'problems':result['problems']}
        if a.bundle:
            from factorycore.handoff_bundle import prepare_bundle
            from factorycore.evidence_records import write_json
            if not result.get('opening'):raise ValueError('Bundle needs the ticket-backed stage opening')
            scope=result['opening']['scope']
            prepared=prepare_bundle({'case':scope['case'],'attempt':scope['attempt'],'subject':scope['subject'],
                'scope':'whole_attempt','inventory_reference':str(a.output/'inventory.json'),
                'inventory_sha256':summary['inventory_sha256']},a.output/'evidence.tar.gz')
            write_json(a.output/'bundle-prepared.json',prepared)
            write_json(a.output/'bundle-requirements.json',prepared['requirements'])
            summary.update(bundle=prepared['file'],external_requirements=str(a.output/'bundle-requirements.json'))
        print(json.dumps(summary))
        return 0 if result['snapshot_handoff_ready'] else 1
    except (OSError,ValueError,KeyError,TypeError) as error:
        p.error(str(error))


if __name__ == '__main__':
    raise SystemExit(main())
