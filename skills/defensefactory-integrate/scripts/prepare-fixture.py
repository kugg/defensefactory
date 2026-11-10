#!/usr/bin/env python3
"""Assemble approved source archives offline; retain the recipe and failed preparations."""
import argparse
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from factorycore.fixtures import prepare


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--opening', type=Path, default=os.environ.get('DEFENSEFACTORY_STAGE_OPENING'))
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    try:
        registered = os.environ.get('DEFENSEFACTORY_EVIDENCE_ROOT')
        if registered and Path(registered).resolve() not in a.output.resolve().parents:
            raise ValueError('Save fixture preparation in DEFENSEFACTORY_EVIDENCE_ROOT')
        if not a.opening: raise ValueError('Ticket opening required')
        r = prepare(a.plan, a.opening, a.output)
        print(json.dumps({'receipt':str(a.output/'fixture.json'), 'result':r['result'], 'error':r.get('error')}))
        return 0 if r['result'] == 'recorded' else 1
    except (OSError, ValueError, KeyError, TypeError) as e: p.error(str(e))


if __name__ == '__main__': raise SystemExit(main())
