#!/usr/bin/env python3
"""Save and replay a bounded comparison; never rely on a printed Boolean."""
import argparse
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from factorycore.core import identity
from factorycore.evidence_records import compare_files, replay_comparison


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--id')
    p.add_argument('--left', type=Path)
    p.add_argument('--right', type=Path)
    p.add_argument('--mode', choices=('bytes', 'json'), default='bytes')
    p.add_argument('--expected', choices=('equal', 'different'), default='equal')
    p.add_argument('--left-pointer', default='')
    p.add_argument('--right-pointer', default='')
    p.add_argument('--replay', type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    try:
        roots=[Path(os.environ[k]).resolve() for k in ('DEFENSEFACTORY_EVIDENCE_ROOT','DEFENSEFACTORY_PUBLICATION_ROOT') if os.environ.get(k)]
        if roots and not any(r in a.output.resolve().parents for r in roots):
            raise ValueError('Save comparisons in the registered evidence/publication root')
        if a.replay:
            record = json.loads(a.replay.read_text())
            inputs, paths = {}, {}
            for dep in record['evidence_dependencies']:
                relative = Path(dep['relative_path'])
                if relative.is_absolute() or '..' in relative.parts:
                    raise ValueError('Replay inputs must stay beside the receipt')
                path = a.replay.resolve().parent / relative
                inputs[dep['name']], paths[dep['name']] = path.read_bytes(), path
            replay_comparison(record, inputs)
            result = compare_files(record['id'], paths['left'], paths['right'], a.output,
                                   **record['recipe'], replays=identity(record))
        else:
            if not (a.id and a.left and a.right):
                p.error('--id, --left and --right required for a new comparison')
            result = compare_files(a.id, a.left, a.right, a.output, mode=a.mode, expected=a.expected,
                                   left_pointer=a.left_pointer, right_pointer=a.right_pointer)
        print(json.dumps({'receipt': str(a.output / 'comparison.json'), 'result': result['result']}))
        return 0 if result['result'] == 'satisfied_within_scope' else 1
    except (OSError, ValueError, KeyError, TypeError) as error:
        p.error(str(error))


if __name__ == '__main__':
    raise SystemExit(main())
