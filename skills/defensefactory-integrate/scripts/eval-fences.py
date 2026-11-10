#!/usr/bin/env python3
"""Evaluate portable component claims with disposable Git/Go fixtures; no live effects."""
import argparse
import copy
import json
from pathlib import Path
import sys
import tempfile
import os
import shutil
import subprocess
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE if (HERE / 'factorycore').is_dir() else HERE.parents[1]))
from factorycore.component_claims import execute_fences,fence_health,compare_definitions,map_bug_classes,catalog_receipt
from factorycore.core import identity, require
from factorycore.verification import tree_files


class FenceFixture:
    """Self-contained synthetic component; never imports repository test support."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='factory-fence-eval-')
        self.repo = Path(self.tmp.name) / 'repo'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.name', 'Synthetic fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        (self.repo / 'go.mod').write_text('module example.invalid/fences\n\ngo 1.22\n')
        self.component = self.repo / 'core'
        self.component.mkdir()
        (self.component / 'control.go').write_text('package core\nfunc Allowed(peer string) bool { return peer == "trusted" }\n')
        (self.component / 'control_test.go').write_text('package core\nimport "testing"\nfunc TestNegative(t *testing.T) { if Allowed("other") { t.Fatal("untrusted peer") } }\nfunc TestPositive(t *testing.T) { if !Allowed("trusted") { t.Fatal("legitimate peer") } }\n')
        (self.component / 'AGENTS.md').write_text('Authenticate before credentials.\n')
        intro = self.commit()
        self.definition = {
            'schema_version': 2, 'component': 'peer-component',
            'bug_classes': [{'id': 'unauthenticated-peer', 'definition': 'A sensitive operation trusts an unauthenticated peer.'}],
            'claims': [{'id': 'AUTHENTICATED-PEER', 'statement': 'Only an authenticated peer is admitted.',
                        'preserves': ['The legitimate peer remains admitted.'], 'bug_classes': ['unauthenticated-peer'],
                        'fences': ['peer-tests', 'peer-intent']}],
            'fences': [
                {'id': 'peer-tests', 'kind': 'hard', 'mechanism': 'test', 'check': 'peer-check',
                 'controls': [{'path': 'control_test.go', 'selector': 'TestNegative',
                               'introduced': {'repository': 'fixture/origin', 'ref': intro, 'path': 'core/control_test.go'}}]},
                {'id': 'peer-intent', 'kind': 'soft', 'mechanism': 'guidance',
                 'controls': [{'path': 'AGENTS.md', 'selector': 'Authenticate before credentials.',
                               'introduced': {'repository': 'fixture/origin', 'ref': intro, 'path': 'core/AGENTS.md'}}]}]}
        self.save()
        self.base = self.commit()
        self.receipt = self.read(self.base)
        self.checks = [{'id': 'peer-check', 'argv': ['go', 'test', '-count=1', '-json', './core'],
                        'execution': {'format': 'go-test-json', 'required_tests': [
                            'example.invalid/fences/core::TestNegative', 'example.invalid/fences/core::TestPositive']}}]
        self.frozen = {'core/control_test.go': tree_files(self.repo, self.base)['core/control_test.go']}
        # An explicitly selected example repository policy, not a security-team veto.
        self.policy = {'owners': ['owner'], 'definition_review_required': True}

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], stderr=subprocess.PIPE).decode().strip()

    def commit(self):
        self.git('add', '-A')
        self.git('commit', '-qm', 'Synthetic fence evaluation fixture')
        return self.git('rev-parse', 'HEAD')

    def save(self):
        (self.component / 'claims.json').write_text(json.dumps(self.definition, indent=2) + '\n')

    def read(self, revision):
        return catalog_receipt(self.repo, 'fixture/origin', revision)

    def review(self, revision):
        return [{'reviewer': 'owner', 'state': 'APPROVED', 'base': self.base,
                 'head': revision, 'reference': 'synthetic-owner-review'}]

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
for tool in ('git', 'go'):
    if not shutil.which(tool): p.error('Install '+tool+' before running this evaluation')
os.environ['GOTOOLCHAIN'] = 'local'
a.output = a.output.resolve()
a.output.mkdir(parents=True,exist_ok=False)
f=FenceFixture();base_definition=copy.deepcopy(f.definition)
# Never let a shared host cache turn a fixture/provenance case into a build failure.
cache=Path(f.tmp.name)/'go-cache';cache.mkdir(mode=0o700)
os.environ['GOCACHE']=str(cache)
def save(name,value):(a.output/(name+'.json')).write_text(json.dumps(value,indent=2)+'\n');return value
def run(name,expected_blocked,reviews=None):
    revision=f.git('rev-parse','HEAD');r=f.read(revision);e=execute_fences(f.repo,r,f.checks,identity(f.checks),f.frozen);h=fence_health(r,e);gate=compare_definitions(f.receipt,r,h,f.policy,reviews or []);save(name,{'catalog_receipt':r,'execution':e,'health':h,'admission':gate});f.git('update-ref','refs/heads/evidence/'+name,revision);require(gate['pr_blocked']==expected_blocked, 'Unexpected gate outcome: '+name+'; observed '+gate['result']);return gate
def reset():f.git('checkout','--detach',f.base);f.definition=copy.deepcopy(base_definition);f.component=f.repo/'core'
try:
    save('environment',{'go_executable':shutil.which('go'),
        'go_version':subprocess.check_output(['go','version']).decode().strip(),
        'GOTOOLCHAIN':os.environ['GOTOOLCHAIN'],'GOCACHE':str(cache),
        'cache_scope':'Private disposable writable cache, removed with the fixture; never the host default cache.'})
    save('authored-component-example',f.definition);save('base-receipt',f.receipt);save('check-plan',{'checks':f.checks,'expected_checks_sha256':identity(f.checks),'evaluator_manifest':f.frozen});save('bug-class-mapping',map_bug_classes(f.receipt,['unauthenticated-peer']))
    outcomes={};outcomes['baseline']=run('baseline',False)['result']
    (f.component/'control.go').write_text('package core\n// Harmless refactor, no catalog edits\nfunc Allowed(peer string) bool { return map[string]bool{"trusted":true}[peer] }\n');f.commit();outcomes['refactor']=run('harmless-refactor',False)['result']
    reset();(f.component/'control.go').write_text('package core\nfunc Allowed(peer string) bool { return true }\n');f.commit();outcomes['bypass']=run('bypass',True)['result']
    reset();(f.component/'control.go').write_text('package core\nfunc Allowed(peer string) bool { return false }\n');f.commit();outcomes['deny_all']=run('deny-all',True)['result']
    reset();(f.component/'control_test.go').unlink();f.commit();outcomes['removed_control']=run('removed-control',True)['result']
    reset();f.definition['claims'][0]['statement']='Admit only the authenticated peer while preserving legitimate access.';f.save();rev=f.commit();outcomes['unreviewed_amendment']=run('unreviewed-amendment',True)['result'];outcomes['reviewed_amendment']=run('reviewed-amendment',False,f.review(rev))['result']
    reset();f.git('mv','core','relocated');f.commit();f.checks[0]['argv'][-1]='./relocated';f.checks[0]['execution']['required_tests']=[s.replace('/core::','/relocated::') for s in f.checks[0]['execution']['required_tests']];f.frozen={'relocated/control_test.go':f.frozen['core/control_test.go']};outcomes['component_move']=run('component-move',False)['result']
    dest=Path(f.tmp.name)/'destination';dest.mkdir();shutil.copytree(f.repo/'relocated',dest/'moved');shutil.copy2(f.repo/'go.mod',dest/'go.mod')
    def dg(*args):return subprocess.check_output(['git','-C',str(dest),*args],stderr=subprocess.PIPE).decode().strip()
    dg('init','-q');dg('add','.');dg('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','Imported portable component');rev=dg('rev-parse','HEAD')
    transferred=catalog_receipt(dest,'fixture/destination',rev,origins={'fixture/origin':str(f.repo)});checks=copy.deepcopy(f.checks);checks[0]['argv'][-1]='./moved';checks[0]['execution']['required_tests']=[s.replace('/relocated::','/moved::') for s in checks[0]['execution']['required_tests']];frozen={'moved/control_test.go':f.frozen['relocated/control_test.go']}
    e=execute_fences(dest,transferred,checks,identity(checks),frozen);h=fence_health(transferred,e);policy={**f.policy,'authorized_component_transfer':'Owner-authorized synthetic transfer'};g=compare_definitions(f.receipt,transferred,h,policy,[]);save('cross-repository-transfer',{'catalog_receipt':transferred,'execution':e,'health':h,'admission':g});require(not g['pr_blocked'], 'Component transfer unexpectedly blocked');outcomes['cross_repository_transfer']=g['result']
    missing=catalog_receipt(dest,'fixture/destination',rev);e=execute_fences(dest,missing,checks,identity(checks),frozen);h=fence_health(missing,e);save('unavailable-original-history',{'catalog_receipt':missing,'execution':e,'health':h});require(h['result']=='inconclusive', 'Missing provenance must remain inconclusive; observed '+h['result']);outcomes['unavailable_original_history']=h['result'];dg('bundle','create',str((a.output/'destination.bundle').resolve()),'--all')
    f.git('bundle','create',str((a.output/'source.bundle').resolve()),'--all');save('summary',{'outcomes':outcomes,'scope':'Actual Git/Go processes. Owner-review objects are explicit synthetic fixture decisions, not native GitHub approvals.','definition_file_count_per_component':1,'computed_hash_fields_in_authored_definition':0,'source_bundle':'source.bundle'});print(json.dumps(outcomes))
finally:
    # Preserve reachable source and mutations even if an expectation fails.
    preservation_errors = []
    for name in ('source', 'destination'):
        repo = f.repo if name == 'source' else Path(f.tmp.name) / 'destination'
        if not (repo / '.git').exists():
            continue
        try:
            subprocess.run(['git', '-C', str(repo), 'bundle', 'create',
                            str(a.output / (name + '-at-exit.bundle')), '--all'],
                           check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except (OSError, subprocess.CalledProcessError):
            # Preserve the repository itself if bundling fails; retain the original failure.
            shutil.copytree(repo, a.output / (name + '-at-exit-repository'))
            preservation_errors.append(name)
    save('preservation', {'fallback_repositories': preservation_errors})
    f.tmp.cleanup()
