"""Export selected local Git objects without changing source refs or copying unrelated refs."""
import json
from pathlib import Path
import re
import subprocess
import tempfile
from .core import require, sha
from .evidence_records import now, dependency, write_json


def export_sources(repo, revisions, output, timeout=60):
    repo=Path(repo).resolve()
    require(repo.is_dir() and revisions and len(revisions)<=32, 'Local repository and bounded exact revision map required')
    require(all(re.fullmatch('[A-Za-z0-9_-]+',k) and re.fullmatch('[0-9a-f]{40}',v) for k,v in revisions.items()),
            'Safe unique source names and full commit hashes required')
    require(type(timeout) is int and 0<timeout<=120, 'Bounded source-export timeout required')
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False,mode=0o700)
    log=root/'commands.json';bundle=root/'source.bundle'
    result={'record_type':'source_export','schema_version':1,'revisions':revisions,'repository_path':str(repo),
            'started_at':now(),'result':'inconclusive','commands':[]}
    write_json(root/'preparation.json',result)
    def save_log():
        temporary=root/'commands.tmp'
        temporary.write_text(json.dumps({'commands':result['commands']},indent=2)+'\n')
        temporary.chmod(0o600);temporary.replace(log)
    def run(argv):
        started=now()
        record={'argv':argv,'started_at':started,'exit_code':None,'state':'running'}
        result['commands'].append(record);save_log()
        try:
            p=subprocess.run(argv,capture_output=True,text=True,timeout=timeout)
            record.update(finished_at=now(),exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr,state='finished')
        except (OSError,subprocess.TimeoutExpired) as error:
            record.update(finished_at=now(),exit_code=None,error=type(error).__name__,state='failed')
            for name in ('stdout','stderr'):
                value=getattr(error,name,None)
                if value is not None:record[name]=value.decode(errors='replace') if isinstance(value,bytes) else value
        save_log()
        require(record['exit_code']==0, 'Source export producer failed; retain commands and partial bytes')
        return record.get('stdout','')
    try:
        with tempfile.TemporaryDirectory(prefix='factory-source-export-') as temp:
            bare=Path(temp)/'objects.git'
            run(['git','init','--bare',str(bare)])
            git=['git','-c','protocol.allow=never','-c','protocol.file.allow=always','--git-dir',str(bare)]
            run([*git,'fetch','--no-tags','--no-recurse-submodules',str(repo),
                 *[v+':refs/heads/'+k for k,v in revisions.items()]])
            run([*git,'bundle','create',str(bundle),'--all'])
            run([*git,'bundle','verify',str(bundle)])
            heads=run([*git,'bundle','list-heads',str(bundle)])
            observed={ref.removeprefix('refs/heads/'):rev for rev,ref in (line.split() for line in heads.splitlines())}
            require(observed==revisions, 'Exported Git refs differ from selected source inventory')
            result['result']='recorded'
    except (ValueError,OSError) as error:result['error']=str(error)
    save_log();result.pop('commands')
    result.update(finished_at=now(),evidence_dependencies=[dependency('commands',log,'source_export_log')],
                  limitation='Observed local Git export and exact named refs, not a protected build or source authorization.')
    if bundle.is_file():result['evidence_dependencies'].append(dependency('source',bundle,'source_bundle'))
    write_json(root/'source-export.json',result)
    return result
