#!/usr/bin/env python3
"""Download both native assets and verify the emitted machine requirements; no retry."""
import argparse
import json
import os
from pathlib import Path
import runpy
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from factorycore.core import require
from factorycore.evidence_records import write_json, dependency, now
from factorycore.handoff_readback import evaluate

transfer = runpy.run_path(str(Path(__file__).with_name('ticket-transfer.py')))['transfer']


def verify(events, bundle_event, requirements_event, expected_file, output, opening_file=None):
    output = Path(output).resolve()
    registered = os.environ.get('DEFENSEFACTORY_PUBLICATION_ROOT')
    require(not registered or Path(registered).resolve() in output.parents, 'Use a new directory in DEFENSEFACTORY_PUBLICATION_ROOT')
    output.mkdir(parents=True,exist_ok=False,mode=0o700)
    frozen = output/'expected.json'; frozen.write_bytes(Path(expected_file).read_bytes())
    deps = [dependency('expected',frozen)]
    record = {'record_type':'handoff_verification','phase':'prepared','started_at':now(),
              'result':'inconclusive','evidence_dependencies':deps,
              'scope':'Downloaded integrity and declared snapshot completeness; not factory acceptance or native authority.'}
    write_json(output/'readback.json',record)
    try:
        expected = json.loads(frozen.read_text())
        require(expected.get('requirements',{}).get('required_resources'), 'Use bundle-prepared.json emitted by the helper')
        if opening_file:
            opening = json.loads(Path(opening_file).read_text()); scope = opening['scope']
            require(all(expected['requirements'][k] == scope[k] for k in ('case','attempt','subject')), 'Bundle preparation belongs to another scope')
        require(bundle_event != requirements_event, 'Two distinct native attachment lookups required')
        resource_ids = []
        for name,event,filename,digest in [
            ('requirements',requirements_event,'requirements.json',expected.get('external_requirements_sha256')),
            ('bundle',bundle_event,'bundle.tar.gz',expected['sha256'])]:
            dest = output/filename; receipt = output/(name+'-transfer.json')
            try:
                result = transfer(events,dest,receipt,expected=digest,event_id=event)
            finally:
                if dest.is_file():deps.append(dependency(name,dest))
                if receipt.is_file():deps.append(dependency(name+'-transfer',receipt))
            require(result['result'] == 'recorded', 'Failed '+name+' transfer; retain this generation and refresh native metadata before recovery')
            resource_ids.append(result['native_resource_id'])
        require(all(resource_ids) and len(set(resource_ids)) == 2, 'Two distinct native attachment resource IDs required')
        verdict = evaluate(expected,(output/'bundle.tar.gz').read_bytes(),(output/'requirements.json').read_bytes())
        require(verdict['bundle_complete'], 'Downloaded bundle is incomplete: '+str(verdict['problems']))
        record.update(phase='verified',result='recorded',verification=verdict)
    except (OSError,ValueError,KeyError,TypeError) as error:
        record.update(phase='failed',error=str(error))
    record['finished_at'] = now()
    (output/'readback.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--events',type=Path,default=os.environ.get('DEFENSEFACTORY_EVENT_LOG'))
    p.add_argument('--bundle-event',required=True)
    p.add_argument('--requirements-event',required=True)
    p.add_argument('--prepared',type=Path,required=True,help='Exact bundle-prepared.json, not a narrative summary')
    p.add_argument('--opening',type=Path,default=os.environ.get('DEFENSEFACTORY_STAGE_OPENING'))
    p.add_argument('--output',type=Path,required=True)
    a = p.parse_args()
    try:
        if not a.events:raise ValueError('Native event stream required')
        r = verify(a.events,a.bundle_event,a.requirements_event,a.prepared,a.output,a.opening)
        print(json.dumps({'receipt':str(a.output/'readback.json'),'result':r['result'],
                          'verification':r.get('verification'),'error':r.get('error')}))
        return 0 if r['result'] == 'recorded' else 1
    except (OSError,ValueError,KeyError,TypeError) as error:p.error(str(error))


if __name__=='__main__':raise SystemExit(main())
