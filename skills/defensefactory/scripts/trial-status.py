#!/usr/bin/env python3
"""Read the current invocation scope, paths and measured elapsed time after context loss."""
import argparse
import datetime
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from factorycore.evidence_records import write_json


def status(opening_file, invocation, *, at=None):
    opening=json.loads(Path(opening_file).read_text()); invocation=Path(invocation)
    scope=opening['scope']; start=json.loads((invocation/'invocation-start.json').read_text())
    end=invocation/'invocation-result.json'
    finish=json.loads(end.read_text())['finished_at'] if end.exists() else at or datetime.datetime.now(datetime.timezone.utc).isoformat()
    parse=lambda s:datetime.datetime.fromisoformat(s.replace('Z','+00:00'))
    elapsed=(parse(finish)-parse(start['started_at'])).total_seconds()
    if elapsed<0:raise ValueError('Invocation clock precedes captured start')
    return {'record_type':'trial_status','case':scope['case'],'attempt':scope['attempt'],
            'subject':scope['subject'],'scope_comment_id':opening['scope_comment_id'],
            'comparisons':scope.get('comparisons',[]),'runtime_requirement':scope.get('runtime_requirement'),
            'codeintel_requirement':scope.get('codeintel_requirement'),
            'package':scope['package'],'scripts':str(Path(scope['package'])/'scripts'),
            'opening_file':str(Path(opening_file).resolve()),'started_at':start['started_at'],
            'observed_until':finish,'elapsed_seconds':elapsed,'worker_exited':end.exists(),
            'paths':{k:str(invocation/v) for k,v in [('evidence','evidence'),('handoffs','handoffs'),('publication','publication')]},
            'next_action':'Fetch live ticket and latest approval/input checkpoints; reconcile them with these frozen inputs before further work. Compaction summaries and this local status are not current ticket authority.',
            'scope':'Invocation timing only. Do not infer whole-attempt duration or reset a continuation budget.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--opening',type=Path,default=os.environ.get('DEFENSEFACTORY_STAGE_OPENING'))
    p.add_argument('--invocation',type=Path)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    try:
        if not a.opening:raise ValueError('Current stage opening required')
        invocation=a.invocation or a.opening.parent
        r=status(a.opening,invocation)
        if a.output:write_json(a.output,r)
        print(json.dumps(r,indent=2))
    except (OSError,ValueError,KeyError,TypeError) as error:p.error(str(error))


if __name__=='__main__':main()
