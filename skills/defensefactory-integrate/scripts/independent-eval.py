#!/usr/bin/env python3
"""Run two explicit evaluator adapters in fresh process contexts and compare obligations."""
import argparse
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE if (HERE/'factorycore').exists() else HERE.parent))
from factorycore.evaluator_isolation import run_isolated


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True,help='New evidence directory')
    args=parser.parse_args()
    try:
        result=run_isolated(json.loads(args.spec.read_text()),args.output)
        print(json.dumps({'receipt':str(args.output.resolve()/'comparison.json'),'result':result['result']}))
        return 0 if result['result']=='agreed' else 1
    except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError) as error:
        parser.error(str(error))


if __name__=='__main__':raise SystemExit(main())
