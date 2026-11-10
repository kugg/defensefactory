#!/usr/bin/env python3
"""Restore artifact bytes from a verified ticket bundle without rewriting old receipts."""
import argparse
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from factorycore.artifact_binding import restore_artifact


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--requirements',type=Path,required=True)
    select=p.add_mutually_exclusive_group(required=True)
    select.add_argument('--resource')
    select.add_argument('--name')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    try:
        registered=os.environ.get('DEFENSEFACTORY_EVIDENCE_ROOT')
        if registered and Path(registered).resolve() not in a.output.resolve().parents:
            raise ValueError('Restore artifacts inside DEFENSEFACTORY_EVIDENCE_ROOT')
        result=restore_artifact(a.bundle,a.requirements,a.output,resource=a.resource,name=a.name)
        print(json.dumps({'binding_reference':str(a.output/'binding-reference.json'),'subject':result['subject']}))
    except (OSError,ValueError,KeyError,TypeError) as error:p.error(str(error))


if __name__=='__main__':main()
