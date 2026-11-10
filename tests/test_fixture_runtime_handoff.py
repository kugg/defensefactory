"""Observed failure regressions: offline fixtures, real child probes and native readback.

No model, service, ticket, container or production calls. Transfer responses are
explicit synthetic native events; local subprocess/Git/Go work is real.
"""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tarfile
import unittest
from unittest.mock import patch
import test_evidence_flow as fixtures

SCRIPTS=fixtures.SCRIPTS
from factorycore.core import identity,sha,GateError
from factorycore.fixtures import prepare,replay,validate_live
from factorycore.handoff_bundle import prepare_bundle,verify_bundle
from factorycore.runtime_plan import declare
from factorycore.trial_controls import scope_prepare,stage_start


def load(name):
    spec=importlib.util.spec_from_file_location(name,SCRIPTS/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class FixtureRuntimeHandoff(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.EvidenceFlow('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)

    def cli(self,identifier,*args,cwd=None):
        f=self.f
        argv=[sys.executable,str(f.package/'scripts/stage-exec.py'),'--opening',str(f.root/'opening.json'),
              '--id',identifier,'--cwd',str(cwd or f.root),'--output',str(f.evidence/identifier),*args]
        result=subprocess.run(argv,capture_output=True,text=True)
        f.event('bash',{'command':shlex.join(argv)},result.stdout+result.stderr)
        return result

    def archive(self,name,files,link=False):
        dest=self.f.root/name
        with tarfile.open(dest,'w') as t:
            for n,raw in files.items():
                info=tarfile.TarInfo(n);info.mode=0o644;info.size=len(raw)
                if link:info.type=tarfile.SYMTYPE;info.linkname='/tmp/escaped'
                t.addfile(info,io.BytesIO(raw))
        return dest

    def fixture_plan(self,complete=True):
        f=self.f
        base=self.archive('public.tar',{'lib/dependency.py':b'VALUE=7\n','adapter.py':b'old\n'})
        overlay=self.archive('approved.tar',{'integration/adapter.py':b'print("harness only")\n'})
        plan={'id':'local-harness','reference':'Synthetic ticket fixture input grant','inputs':[
            {'id':'public','path':str(base),'sha256':sha(base.read_bytes()),'reference':'Synthetic public source revision','mappings':[{'from':'','to':''}]},
            {'id':'approved','path':str(overlay),'sha256':sha(overlay.read_bytes()),'reference':'Synthetic approved archive resource','mappings':[{'from':'integration','to':''}],'replace':['adapter.py']}],
            'required_paths':['adapter.py','lib/dependency.py']}
        if not complete:plan['required_paths'].append('missing/import.py')
        path=f.root/'fixture-plan.json';path.write_text(json.dumps(plan));return plan,path

    def test_partial_package_is_retained_and_complete_assembly_replays_without_inputs(self):
        f=self.f;plan,path=self.fixture_plan(False)
        failed=prepare(path,f.root/'opening.json',f.evidence/'failed-fixture')
        self.assertEqual(failed['result'],'inconclusive');self.assertIn('missing/import.py',failed['error'])
        self.assertTrue((f.evidence/'failed-fixture/input-0.tar').exists())
        with self.assertRaises(ValueError):validate_live(failed,f.opening,f.root)
        plan['required_paths'].remove('missing/import.py');path.write_text(json.dumps(plan))
        ready=prepare(path,f.root/'opening.json',f.evidence/'ready-fixture')
        self.assertEqual(ready['result'],'recorded');self.assertNotEqual(ready['subject'],f.subject)
        base=Path(plan['inputs'][0]['path']);base.unlink();Path(plan['inputs'][1]['path']).unlink();path.unlink()
        replay(ready,lambda d:Path(d['path']).read_bytes())
        result=self.cli('harness-test','--support','--fixture',str(f.evidence/'ready-fixture/fixture.json'),
            '--',sys.executable,'-B','adapter.py',cwd=f.evidence/'ready-fixture/tree')
        self.assertEqual(result.returncode,0,result.stderr)
        receipt=json.loads((f.evidence/'harness-test/execution.json').read_text())
        self.assertEqual(receipt['subject'],ready['subject'])
        audit=f.audit();self.assertTrue(audit['whole_attempt_handoff_ready'],audit['problems'])
        bundle=f.bundle(audit);raw=Path(bundle['file']).read_bytes();requirements=bundle['requirements']
        shutil.rmtree(f.evidence)
        self.assertTrue(verify_bundle(raw,requirements)['whole_attempt_handoff_ready'])

    def test_fixture_refuses_unsafe_archives_unreviewed_overlays_and_tree_drift(self):
        f=self.f;plan,path=self.fixture_plan()
        plan['inputs'][1].pop('replace');path.write_text(json.dumps(plan))
        failure=prepare(path,f.root/'opening.json',f.evidence/'overlay-refused')
        self.assertIn('Explicit replacement',failure['error'])
        for i,(name,link) in enumerate([('../escape',False),('linked',True)]):
            malicious=self.archive('unsafe-'+str(i)+'.tar',{name:b'x'},link)
            plan['inputs']=[{'id':'unsafe','path':str(malicious),'sha256':sha(malicious.read_bytes()),'reference':'Synthetic unsafe test','mappings':[{'from':'','to':''}]}]
            path.write_text(json.dumps(plan));failed=prepare(path,f.root/'opening.json',f.evidence/('unsafe-'+str(i)))
            self.assertEqual(failed['result'],'inconclusive');self.assertFalse((f.root/'escape').exists())
        plan,path=self.fixture_plan();ready=prepare(path,f.root/'opening.json',f.evidence/'ready')
        (f.evidence/'ready/tree/adapter.py').write_text('changed')
        with self.assertRaisesRegex(ValueError,'tree changed'):validate_live(ready,f.opening,f.evidence/'ready/tree')
        with self.assertRaises(FileExistsError):prepare(path,f.root/'opening.json',f.evidence/'ready')

    def test_fixture_cannot_be_used_as_a_product_build_or_runtime_subject(self):
        f=self.f;_,path=self.fixture_plan();prepare(path,f.root/'opening.json',f.evidence/'fixture')
        marker=f.root/'not-launched'
        result=self.cli('wrong-role','--support','--fixture',str(f.evidence/'fixture/fixture.json'),
            '--produces','product='+str(marker),'--',sys.executable,'-c',f'open({str(marker)!r},"w").close()',cwd=f.evidence/'fixture/tree')
        self.assertNotEqual(result.returncode,0);self.assertFalse(marker.exists())
        self.assertTrue((f.evidence/'wrong-role/admission-failure.json').exists())

    def runtime_opening(self):
        f=self.f
        policy={'required':True,'reference':'Synthetic runtime acceptance policy','probes':[
            {'id':'refusal','artifacts':['gateway'],'assertions':['refused']},
            {'id':'legitimate','artifacts':['gateway'],'assertions':['accepted']}]}
        p=scope_prepare({'case':'FIXTURE-1','attempt':'synthetic-evidence','stage':'verify','subject':f.subject,
            'performed_by':'synthetic-agent','package':str(f.package),'authorization_reference':'Synthetic grant',
            'boundaries':'Disposable offline fixtures','runtime_requirement':policy})
        pub={'id':'runtime-scope','body':p['scope_body'],'createdAt':p['prepared_at']}
        f.opening=stage_start(p,pub,{**pub,'operation':'retrieval','retrieved_at':p['prepared_at']})
        (f.root/'opening.json').write_text(json.dumps(f.opening))

    def test_required_runtime_probes_cannot_disappear_behind_fixture_or_source_passes(self):
        f=self.f;self.runtime_opening()
        f.command('refusal',[sys.executable,'-c','print("unit tests passed")'])
        audit=f.audit()
        self.assertFalse(audit['whole_attempt_handoff_ready'])
        self.assertTrue(any('Required runtime probe missing' in p for p in audit['problems']))
        bad=[{'id':'refusal','purpose':'Wrong criteria','artifacts':['gateway'],'argv':['{artifact:gateway}'],
              'assertions':[{'name':'generic-zero','exit_code':0}]}]
        with self.assertRaisesRegex(ValueError,'published obligation'):declare(f.opening,bad,'Synthetic runtime contract')

    def test_scoped_actual_refusal_and_legitimate_probes_survive_erased_build_host(self):
        f=self.f;repo,builder=f.source_repo();self.runtime_opening();out=f.root/'built'
        f.command('build',[sys.executable,str(builder),str(out)],source_repository=str(repo),produces_artifacts={'gateway':str(out)})
        binding=f.evidence/'build/artifacts/gateway/binding.json'
        declaration=declare(f.opening,[{'id':n,'purpose':n,'artifacts':['gateway'],
            'argv':[sys.executable,'{artifact:gateway}',str(code)],'assertions':[{'name':label,'exit_code':code,'stdout_contains':['fixture']}]}
            for n,code,label in [('refusal',2,'refused'),('legitimate',0,'accepted')]],'Synthetic runtime policy')
        plan=f.evidence/'runtime-plan.json';plan.write_text(json.dumps(declaration))
        for n in ['refusal','legitimate']:
            result=self.cli(n,'--runtime-plan',str(plan),'--use-artifact','gateway='+str(binding))
            self.assertEqual(result.returncode,0,result.stderr)
        audit=f.audit();self.assertTrue(audit['whole_attempt_handoff_ready'],audit['problems'])
        bundle=f.bundle(audit);raw=Path(bundle['file']).read_bytes();shutil.rmtree(repo);shutil.rmtree(f.evidence)
        self.assertTrue(verify_bundle(raw,bundle['requirements'])['whole_attempt_handoff_ready'])

    def test_actual_go_discovery_refuses_guessed_names_before_launch(self):
        f=self.f;repo=f.root/'go-fixture';repo.mkdir()
        (repo/'go.mod').write_text('module example.invalid/discovery\n\ngo 1.22\n')
        test=repo/'sample_test.go';test.write_text('package discovery\nimport "testing"\nfunc TestPresent(t *testing.T){}\n')
        evaluators=f.root/'evaluators.json';evaluators.write_text(json.dumps({'sample_test.go':sha(test.read_bytes())}))
        env=['--env','GOWORK=off','--env','GOTOOLCHAIN=local','--env','GOPROXY=off','--env','GOCACHE='+str(f.root/'go-cache')]
        listed=self.cli('discovery','--support','--protocol','go-list-json','--evaluators',str(evaluators),*env,
            '--','go','test','-json','-list','.','./...',cwd=repo)
        self.assertEqual(listed.returncode,0,listed.stderr)
        inventory=f.evidence/'discovery/execution.json'
        marker=f.root/'should-not-execute'
        no_inventory=self.cli('undiscovered','--support','--protocol','go-test-json','--required-test','example.invalid/discovery::TestInvented',
            '--',sys.executable,'-c',f'open({str(marker)!r},"w").close()',cwd=repo)
        self.assertNotEqual(no_inventory.returncode,0);self.assertFalse(marker.exists())
        refused=self.cli('guessed','--support','--protocol','go-test-json','--required-test','example.invalid/discovery::TestInvented',
            '--discovered-tests',str(inventory),'--evaluators',str(evaluators),'--',sys.executable,'-c',f'open({str(marker)!r},"w").close()',cwd=repo)
        self.assertNotEqual(refused.returncode,0);self.assertFalse(marker.exists())
        actual=self.cli('selected','--support','--protocol','go-test-json','--required-test','example.invalid/discovery::TestPresent',
            '--discovered-tests',str(inventory),'--evaluators',str(evaluators),*env,'--','go','test','-count=1','-json','./...',cwd=repo)
        self.assertEqual(actual.returncode,0,actual.stderr)
        audit=f.audit();bundle=f.bundle(audit);raw=Path(bundle['file']).read_bytes();shutil.rmtree(repo);shutil.rmtree(f.evidence)
        self.assertTrue(verify_bundle(raw,bundle['requirements'])['bundle_complete'])

    def test_deny_all_binary_fails_the_required_legitimate_runtime_probe(self):
        f=self.f;repo,builder=f.source_repo()
        builder.write_text('import pathlib,sys\npathlib.Path(sys.argv[1]).write_text("print(\\\"fixture\\\")\\nraise SystemExit(2)\\n")\n')
        subprocess.run(['git','-C',str(repo),'add','.'],check=True)
        subprocess.run(['git','-C',str(repo),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
                        '-c','commit.gpgsign=false','commit','-qm','Synthetic deny-all implementation'],check=True)
        f.subject['revision']=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD']).decode().strip()
        self.runtime_opening();output=f.root/'deny-all'
        f.command('build',[sys.executable,str(builder),str(output)],source_repository=str(repo),produces_artifacts={'gateway':str(output)})
        binding=f.evidence/'build/artifacts/gateway/binding.json'
        probes=[{'id':n,'purpose':n,'artifacts':['gateway'],'argv':[sys.executable,'{artifact:gateway}',str(code)],
                 'assertions':[{'name':label,'exit_code':code,'stdout_contains':['fixture']}]}
                for n,code,label in [('refusal',2,'refused'),('legitimate',0,'accepted')]]
        plan=f.evidence/'runtime.json';plan.write_text(json.dumps(declare(f.opening,probes,'Synthetic deny-all challenge')))
        self.assertEqual(self.cli('refusal','--runtime-plan',str(plan),'--use-artifact','gateway='+str(binding)).returncode,0)
        self.assertNotEqual(self.cli('legitimate','--runtime-plan',str(plan),'--use-artifact','gateway='+str(binding)).returncode,0)
        receipt=json.loads((f.evidence/'legitimate/execution.json').read_text())
        self.assertEqual(receipt['exit_code'],2);self.assertEqual(receipt['result'],'violated')
        self.assertFalse(f.audit()['whole_attempt_handoff_ready'])

    def prepared(self):
        f=self.f;f.command('check',[sys.executable,'-c','print("check")']);audit=f.audit();return f.bundle(audit)

    def native_events(self,prepared,requirements):
        f=self.f;log=f.root/'native.jsonl'
        records=[{'type':'tool_use','part':{'id':name,'tool':'linear_get_attachment','state':{'status':'completed',
            'output':json.dumps({'id':name+'-resource','url':'https://example.invalid/'+name+'?signature=synthetic-private'})}}}
            for name in ['bundle','requirements']]
        log.write_text('\n'.join(json.dumps(e) for e in records)+'\n')
        payloads={'/bundle':Path(prepared['file']).read_bytes(),'/requirements':requirements}
        def curl(argv,**kwargs):
            config=Path(argv[argv.index('--config')+1]).read_text()
            key='/requirements' if '/requirements?' in config else '/bundle'
            Path(argv[argv.index('--output')+1]).write_bytes(payloads[key])
            return subprocess.CompletedProcess(argv,0,'200','')
        return log,curl

    def test_emitted_machine_requirements_download_and_verify_as_distinct_assets(self):
        f=self.f;prepared=self.prepared();external=Path(prepared['external_requirements_file'])
        self.assertEqual(json.loads(external.read_text()),prepared['requirements'])
        saved=f.root/'prepared.json';saved.write_text(json.dumps(prepared));helper=load('verify-handoff')
        log,curl=self.native_events(prepared,external.read_bytes())
        with patch('subprocess.run',side_effect=curl):
            result=helper.verify(log,'bundle','requirements',saved,f.root/'readback',f.root/'opening.json')
        self.assertEqual(result['phase'],'verified');self.assertTrue(result['verification']['whole_attempt_handoff_ready'])
        self.assertNotIn('synthetic-private',(f.root/'readback/readback.json').read_text())
        shutil.rmtree(f.evidence);external.unlink()
        from factorycore.handoff_readback import replay as replay_readback
        replay_readback(result,lambda d:Path(d['path']).read_bytes())
        with self.assertRaises(FileExistsError):helper.verify(log,'bundle','requirements',saved,f.root/'readback')

    def test_narrative_requirements_and_failed_downloads_remain_failed_generations(self):
        f=self.f;prepared=self.prepared();saved=f.root/'prepared.json';saved.write_text(json.dumps(prepared));helper=load('verify-handoff')
        log,curl=self.native_events(prepared,b'{"summary":"everything passed"}')
        with patch('subprocess.run',side_effect=curl):r=helper.verify(log,'bundle','requirements',saved,f.root/'bad-readback')
        self.assertEqual(r['phase'],'failed');self.assertTrue((f.root/'bad-readback/requirements.json').exists())
        self.assertFalse((f.root/'bad-readback/bundle.tar.gz').exists())
        self.assertNotIn('verification',r)
        before=(f.root/'bad-readback/requirements.json').read_bytes()
        with self.assertRaises(FileExistsError):helper.verify(log,'bundle','requirements',saved,f.root/'bad-readback')
        self.assertEqual((f.root/'bad-readback/requirements.json').read_bytes(),before)

    def test_status_uses_current_invocation_paths_and_measured_times(self):
        f=self.f;helper=load('trial-status');inv=f.root/'continuation';inv.mkdir()
        (inv/'invocation-start.json').write_text('{"started_at":"2026-01-01T00:00:00+00:00"}')
        r=helper.status(f.root/'opening.json',inv,at='2026-01-01T00:15:49+00:00')
        self.assertEqual(r['elapsed_seconds'],949);self.assertEqual(r['paths']['evidence'],str(inv/'evidence'))
        (inv/'invocation-result.json').write_text('{"finished_at":"2026-01-01T00:16:00+00:00"}')
        self.assertEqual(helper.status(f.root/'opening.json',inv)['elapsed_seconds'],960)
        self.assertFalse('approved' in r)


if __name__=='__main__':unittest.main()
