#!/usr/bin/env python3
"""Snapshot an explicitly supplied foreground Bash runner before optionally running it.

The invoker must authorize the script and each resource. No scheduler or retry
worker is installed. A snapshot prevents accidental edits to a shared runner
from changing what a long-running shell reads later.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess


def prepare(script, resources, destination):
    script=Path(script);paths=[script,*map(Path,resources)]
    if len({p.name for p in paths})!=len(paths):
        raise ValueError('Snapshot resource basenames must be unique')
    if any(not p.is_file() or p.is_symlink() for p in paths):
        raise ValueError('Explicit regular script/resource files required')
    if any(p.name in ('manifest.json','invocation-start.json','invocation-result.json') for p in paths):
        raise ValueError('Reserved snapshot filename')
    captured={p.name:p.read_bytes() for p in paths}
    target=Path(destination);target.mkdir(parents=True,exist_ok=False,mode=0o700)
    for name,raw in captured.items():
        with (target/name).open('xb') as f:f.write(raw)
        (target/name).chmod(0o400)
    check=subprocess.run(['bash','-n',str(target/script.name)],capture_output=True,text=True)
    manifest={'script':script.name,'files':{name:{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()} for name,raw in captured.items()},
              'syntax_exit_code':check.returncode,'syntax_diagnostics':check.stderr,
              'limitation':'Captured bytes and syntax only, not authorization or security/behavioral acceptance. Explicit resources must include files the runner needs relative to its own path.'}
    with (target/'manifest.json').open('x') as f:json.dump(manifest,f,indent=2)
    (target/'manifest.json').chmod(0o400)
    return target,manifest


def execute(target, manifest):
    target=Path(target)
    if manifest['syntax_exit_code']:
        raise ValueError('Snapshot failed Bash syntax validation; preserve it and do not launch')
    for name,entry in manifest['files'].items():
        if hashlib.sha256((target/name).read_bytes()).hexdigest()!=entry['sha256']:
            raise ValueError('Snapshot bytes changed before launch')
    now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
    with (target/'invocation-start.json').open('x') as f:json.dump({'started_at':now(),'script':manifest['script']},f)
    # Bash reads the private captured copy, never the changing original path.
    code=subprocess.call(['bash',str(target/manifest['script'])])
    result={'finished_at':now(),'exit_code':code,'factory_acceptance':'not_evaluated',
            'snapshot_unchanged':all(hashlib.sha256((target/n).read_bytes()).hexdigest()==v['sha256'] for n,v in manifest['files'].items())}
    with (target/'invocation-result.json').open('x') as f:json.dump(result,f,indent=2)
    return code


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--script',required=True);p.add_argument('--resource',action='append',default=[])
    p.add_argument('--destination',required=True);p.add_argument('--run',action='store_true')
    a=p.parse_args()
    try:target,manifest=prepare(a.script,a.resource,a.destination)
    except (OSError,ValueError) as e:p.error(str(e))
    print(json.dumps({'snapshot':str(target),'syntax_exit_code':manifest['syntax_exit_code']}),flush=True)
    if a.run:
        try:return execute(target,manifest)
        except (OSError,ValueError) as e:p.error(str(e))
    return 0 if manifest['syntax_exit_code']==0 else 1


if __name__=='__main__':raise SystemExit(main())
