#!/usr/bin/env python3
"""One classifier request. Environment profile supplies endpoint/model/secret capability."""
import argparse,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(next(p for p in (HERE,HERE.parent,HERE.parent.parent) if (p/'factorycore').is_dir())))
from factorycore.classifier_provider import classify
p=argparse.ArgumentParser();p.add_argument('--profile',required=True);p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args();out=Path(a.output)
if out.exists():p.error('Use a new receipt path')
data=json.loads(Path(a.input).read_text());result=classify(json.loads(Path(a.profile).read_text()),data['finding'],data['candidates']);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'result':result['result'],'elapsed_seconds':result['elapsed_seconds'],'receipt':str(out)}));sys.exit(0 if result['result']=='proposal_recorded' else 1)
