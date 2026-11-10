"""Real disposable processes/Git/files; synthetic connector events, never a live agent pass."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/defensefactory/scripts'
sys.path.insert(0,str(SCRIPTS))
from factorycore.core import GateError, identity, sha
from factorycore.evidence_records import compare_files, replay_comparison, saved_observation
from factorycore.evidence_inventory import inventory
from factorycore.handoff_bundle import prepare_bundle, verify_bundle
from factorycore.trial_controls import scope_prepare, stage_start, stage_command
from factorycore.artifact_binding import restore_artifact


class EvidenceFlow(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name).resolve();self.evidence=self.root/'evidence';self.evidence.mkdir()
        self.subject={'repository':'fixture/component','revision':'a'*40}
        self.package=ROOT/'skills/defensefactory-verify'
        self.events=[]
        self.opening=self.open(self.subject)

    def open(self,subject):
        prep=scope_prepare({'case':'FIXTURE-1','attempt':'synthetic-evidence','stage':'verify','subject':subject,
            'performed_by':'synthetic-agent','package':str(self.package),
            'authorization_reference':'synthetic scope decision','boundaries':'Disposable local fixtures only'})
        pub={'id':'synthetic-native-record','body':prep['scope_body'],'createdAt':prep['prepared_at']}
        opening=stage_start(prep,pub,{**pub,'operation':'retrieval','retrieved_at':prep['prepared_at']})
        (self.root/'opening.json').write_text(json.dumps(opening))
        return opening

    def command(self,identifier,argv,**extra):
        spec={'id':identifier,'subject':self.subject,'performed_by':'synthetic-agent','argv':argv,
              'cwd':str(self.root),'timeout_seconds':10,
              'execution':{'format':'command','reason':'Synthetic producer','success_criteria':'exits zero'},
              'stage_start_reference':str(self.root/'opening.json'),'stage_start_sha256':identity(self.opening),**extra}
        capture=self.evidence/identifier
        result=stage_command(self.opening,spec,capture)
        args=[sys.executable,str(self.package/'scripts/stage-exec.py'),'--opening',str(self.root/'opening.json'),
              '--id',identifier,'--cwd',str(self.root),'--output',str(capture),'--',*argv]
        self.event('bash',{'command':__import__('shlex').join(args)})
        return result

    def event(self,name,inputs,output='',metadata=None):
        self.events.append({'type':'tool_use','timestamp':1,'part':{'tool':name,'state':{
            'status':'completed','input':inputs,'output':output,'metadata':metadata or {}}}})

    def audit(self,requirements=None,name='handoff',finalized=True):
        events=self.root/'events.jsonl'
        private={'type':'reasoning','part':{'text':'PRIVATE_THOUGHT_MUST_NOT_BE_EXPORTED'}}
        events.write_text('\n'.join(json.dumps(x) for x in [private,*self.events])+'\n')
        req={'scope_reference':'synthetic-source-only policy','comparison_ids':[], 'assertion_checks':{},'artifact_subjects':{},
             'codeintel':{'disposition':'not_needed','reason':'Offline helper fixture without a service','reference':'Synthetic test scope'}}
        if requirements:req.update(requirements)
        return inventory([self.evidence],self.root/name,events=events,workspace=self.root,
                         opening=self.opening,requirements=req,finalized=finalized)

    def bundle(self,audit,name='bundle.tar.gz'):
        file=self.root/'handoff/inventory.json'
        return prepare_bundle({'case':'FIXTURE-1','attempt':'synthetic-evidence','subject':self.subject,
            'scope':'whole_attempt','inventory_reference':str(file),'inventory_sha256':sha(file.read_bytes())},self.root/name)

    def test_comparison_survives_relocation_and_loss_of_original_inputs(self):
        left,right=self.root/'left.json',self.root/'right.json'
        left.write_text('{"payload":{"answer":true},"irrelevant":1}')
        right.write_text('{"value":true}')
        out=self.evidence/'compare'
        record=compare_files('opening-body',left,right,out,mode='json',left_pointer='/payload/answer',right_pointer='/value')
        self.assertEqual(record['result'],'satisfied_within_scope')
        left.unlink();right.unlink();relocated=self.root/'relocated'
        shutil.copytree(out,relocated);shutil.rmtree(out)
        result=subprocess.run([sys.executable,str(SCRIPTS/'evidence-compare.py'),'--replay',str(relocated/'comparison.json'),
            '--output',str(self.root/'replayed')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        changed=copy.deepcopy(record);changed['observed_equal']=False
        with self.assertRaisesRegex(GateError,'differs from replay'):
            replay_comparison(changed,{'left':(relocated/'left.input').read_bytes(),'right':(relocated/'right.input').read_bytes()})

    def test_comparison_preserves_negative_and_ambiguous_json(self):
        a,b=self.root/'a',self.root/'b';a.write_text('one');b.write_text('two')
        failed=compare_files('mismatch',a,b,self.evidence/'negative')
        self.assertEqual(failed['result'],'violated')
        self.assertTrue((self.evidence/'negative/left.input').exists())
        a.write_text('{"a":1,"a":2}');b.write_text('{"a":2}')
        ambiguous=compare_files('ambiguous',a,b,self.evidence/'ambiguous',mode='json')
        self.assertEqual(ambiguous['result'],'inconclusive')
        with self.assertRaises(FileExistsError):compare_files('again',a,b,self.evidence/'negative')

    def test_actual_nonzero_exit_can_satisfy_refusal_but_printed_exit_cannot(self):
        protocol={'format':'process-assertions-v1','required_tests':['root-refused'],
                  'assertions':[{'name':'root-refused','exit_code':2,'stdout_contains':['refused']} ]}
        actual=self.command('real-refusal',[sys.executable,'-c','print("refused");raise SystemExit(2)'],execution=protocol)
        masked=self.command('masked-refusal',[sys.executable,'-c','print("refused LEG_EXIT=2")'],execution=protocol)
        self.assertEqual(actual['exit_code'],2)
        self.assertEqual(actual['result'],'satisfied_within_scope')
        self.assertEqual(masked['exit_code'],0)
        self.assertEqual(masked['result'],'violated')

    def test_inline_container_shell_cannot_earn_runtime_assertion_credit(self):
        with self.assertRaisesRegex(GateError,'inline container shell'):
            self.command('shell',['docker','run','fixture','sh','-c','false; echo LEG_EXIT=2'],
                execution={'format':'process-assertions-v1','required_tests':['refuse'],
                           'assertions':[{'name':'refuse','exit_code':2}]})

    def source_repo(self):
        repo=self.root/'source';repo.mkdir()
        subprocess.run(['git','init','-q',str(repo)],check=True)
        builder=repo/'builder.py'
        builder.write_text('import pathlib,sys\np=pathlib.Path(sys.argv[1])\np.write_text("import sys\\nprint(\\\"fixture\\\")\\nraise SystemExit(int(sys.argv[1]))\\n")\n')
        subprocess.run(['git','-C',str(repo),'add','.'],check=True)
        subprocess.run(['git','-C',str(repo),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
                        '-c','commit.gpgsign=false','commit','-qm','Synthetic artifact source'],check=True)
        revision=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD']).decode().strip()
        self.subject={**self.subject,'revision':revision};self.opening=self.open(self.subject)
        return repo,builder

    def build(self):
        repo,builder=self.source_repo();produced=self.root/'new-binary'
        record=self.command('build',[sys.executable,str(builder),str(produced)],source_repository=str(repo),
                            produces_artifacts={'gateway':str(produced)})
        binding=Path(record['artifact_evidence']['produced']['gateway']['binding'])
        value=json.loads(binding.read_text());payload=next(d['path'] for d in value['evidence_dependencies'] if d['name']=='payload')
        return repo,record,binding,Path(payload)

    def test_artifact_binding_rejects_wrong_source_changed_payload_and_unused_artifact(self):
        repo,build,binding,payload=self.build()
        self.assertEqual(build['result'],'satisfied_within_scope')
        valid=self.command('run',[sys.executable,str(payload),'0'],uses_artifacts={'gateway':str(binding)})
        self.assertEqual(valid['result'],'satisfied_within_scope')
        marker=self.root/'should-not-run'
        unused=self.command('unused',[sys.executable,'-c',f'open({str(marker)!r},"w").close()'],uses_artifacts={'gateway':str(binding)})
        self.assertEqual(unused['execution_state'],'preparation_failed');self.assertFalse(marker.exists())
        payload.write_text('changed')
        changed=self.command('changed',[sys.executable,str(payload),'0'],uses_artifacts={'gateway':str(binding)})
        self.assertEqual(changed['execution_state'],'preparation_failed')
        builder=repo/'builder.py';builder.write_text(builder.read_text()+'\n# source drift\n')
        wrong=self.command('wrong-build',[sys.executable,'-c',f'open({str(marker)!r},"w").close()'],
            source_repository=str(repo),produces_artifacts={'fresh':str(self.root/'fresh')})
        self.assertEqual(wrong['execution_state'],'preparation_failed');self.assertFalse(marker.exists())

    def test_whole_inventory_includes_omitted_failed_capture_and_api_bytes(self):
        self.command('checkout',[sys.executable,'-c','print("checkout fixture")'])
        self.command('failed-check',[sys.executable,'-c','raise SystemExit(42)'])
        api=self.evidence/'api.json';api.write_text('{"method":"GET","status":409,"body":{"error":"active job"}}')
        audit=self.audit();self.assertTrue(audit['whole_attempt_handoff_ready'],audit['problems'])
        result=self.bundle(audit);raw=Path(result['file']).read_bytes()
        with tarfile.open(result['file']) as archive:
            manifest=json.load(archive.extractfile('bundle-manifest.json'))
            self.assertEqual(len(manifest['executions']),2)
            self.assertTrue(any(e['sha256']==sha(api.read_bytes()) for e in manifest['resources']))
            self.assertNotIn(b'PRIVATE_THOUGHT_MUST_NOT_BE_EXPORTED',b''.join(archive.extractfile(m).read() for m in archive.getmembers()))
        shutil.rmtree(self.evidence);shutil.rmtree(self.root/'handoff')
        verified=verify_bundle(raw,result['requirements'])
        self.assertTrue(verified['bundle_complete'],verified['problems'])
        self.assertTrue(verified['whole_attempt_handoff_ready'])

    def test_artifact_graph_replays_without_the_build_host_or_original_files(self):
        repo,build,binding,payload=self.build()
        self.command('runtime',[sys.executable,str(payload),'0'],uses_artifacts={'gateway':str(binding)})
        audit=self.audit({'artifact_subjects':{'gateway':self.subject}})
        self.assertTrue(audit['whole_attempt_handoff_ready'],audit['problems'])
        result=self.bundle(audit);raw=Path(result['file']).read_bytes()
        shutil.rmtree(repo);shutil.rmtree(self.evidence);shutil.rmtree(self.root/'handoff')
        verified=verify_bundle(raw,result['requirements'])
        self.assertTrue(verified['bundle_complete'],verified['problems'])
        self.assertTrue(verified['whole_attempt_handoff_ready'])

    def test_changed_git_head_and_comparison_binary_cannot_claim_candidate_subject(self):
        repo,build,binding,payload=self.build()
        (repo/'builder.py').write_text((repo/'builder.py').read_text()+'\n# changed source\n')
        subprocess.run(['git','-C',str(repo),'add','.'],check=True)
        subprocess.run(['git','-C',str(repo),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
                        '-c','commit.gpgsign=false','commit','-qm','New fixture source'],check=True)
        failed=self.command('wrong-head',[sys.executable,'-c','pass'],source_repository=str(repo),
                            produces_artifacts={'new':str(self.root/'new')})
        self.assertIn('HEAD differs',failed['reason'])
        self.subject={**self.subject,'revision':'b'*40};self.opening=self.open(self.subject)
        wrong=self.command('wrong-subject',[sys.executable,str(payload),'0'],uses_artifacts={'gateway':str(binding)})
        self.assertIn('Consumed artifact source differs',wrong['reason'])

    def test_cli_build_and_runtime_assertion_use_the_sealed_payload(self):
        repo,builder=self.source_repo()
        capture=self.evidence/'cli-build'
        args=[sys.executable,str(SCRIPTS/'stage-exec.py'),'--opening',str(self.root/'opening.json'),
              '--id','cli-build','--cwd',str(self.root),'--output',str(capture),'--source-repo',str(repo),
              '--produces','cli='+str(self.root/'binary'),'--',sys.executable,str(builder),str(self.root/'binary')]
        r=subprocess.run(args,capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
        binding=capture/'artifacts/cli/binding.json'
        criteria=self.evidence/'criteria.json';criteria.write_text('[{"name":"refusal","exit_code":2,"stdout_contains":["fixture"]}]')
        run=[sys.executable,str(SCRIPTS/'stage-exec.py'),'--opening',str(self.root/'opening.json'),
             '--id','cli-runtime','--cwd',str(self.root),'--output',str(self.evidence/'cli-runtime'),
             '--assertions',str(criteria),'--use-artifact','gateway='+str(binding),'--',sys.executable,'{artifact:gateway}','2']
        r=subprocess.run(run,capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
        record=json.loads((self.evidence/'cli-runtime/execution.json').read_text())
        self.assertEqual(record['exit_code'],2);self.assertEqual(record['result'],'satisfied_within_scope')

    def test_required_comparison_uses_stored_inputs_in_archived_replay(self):
        a,b=self.root/'expected',self.root/'actual';a.write_text('same');b.write_text('same')
        compare_files('opening-bytes',a,b,self.evidence/'comparison')
        self.event('bash',{'command':__import__('shlex').join([sys.executable,str(self.package/'scripts/evidence-compare.py'),
            '--id','opening-bytes','--left',str(a),'--right',str(b),'--output',str(self.evidence/'comparison')])})
        audit=self.audit({'comparison_ids':['opening-bytes']});result=self.bundle(audit)
        self.assertTrue(result['whole_attempt_handoff_ready'])
        raw=Path(result['file']).read_bytes();a.unlink();b.unlink();shutil.rmtree(self.evidence)
        self.assertTrue(verify_bundle(raw,result['requirements'])['whole_attempt_handoff_ready'])

    def test_unwrapped_build_and_console_comparison_block_ready_handoff(self):
        self.event('bash',{'command':'go build ./... | tail -3; echo exit=$?'},'exit=0')
        self.event('bash',{'command':'python3 -c "print(left == right)"'},'True')
        audit=self.audit({'comparison_ids':['opening-bytes']})
        self.assertFalse(audit['whole_attempt_handoff_ready'])
        result=self.bundle(audit)
        self.assertTrue(result['bundle_complete'])
        self.assertFalse(result['whole_attempt_handoff_ready'])

    def test_changed_root_requires_new_inventory_and_subset_cannot_claim_whole(self):
        self.command('observed',[sys.executable,'-c','pass'])
        audit=self.audit();(self.evidence/'later.json').write_text('{}')
        with self.assertRaisesRegex(GateError,'changed after inventory'):self.bundle(audit)
        with self.assertRaisesRegex(GateError,'pinned generated inventory'):
            prepare_bundle({'case':'F','attempt':'a','subject':self.subject,'scope':'whole_attempt','resources':[]},self.root/'no.tar')
        subset=prepare_bundle({'case':'F','attempt':'a','subject':self.subject,'resources':[
            {'id':'one','path':str(self.evidence/'later.json'),'kind':'diagnostic'}]},self.root/'subset.tar')
        self.assertFalse(subset['whole_attempt_handoff_ready'])

    def test_truncated_native_response_cache_is_snapshotted_and_closed(self):
        cache=self.root/'host-cache.json';cache.write_text('{"body":"full native response","token":"synthetic-secret"}')
        self.event('linear_list_comments',{'issueId':'FIXTURE-1'},'truncated',{'truncated':True,'outputPath':str(cache)})
        audit=self.audit();result=self.bundle(audit)
        cache.unlink()
        with tarfile.open(result['file']) as archive:
            data=b''.join(archive.extractfile(m).read() for m in archive.getmembers())
            self.assertIn(b'full native response',data);self.assertNotIn(b'synthetic-secret',data)
        self.assertTrue(verify_bundle(Path(result['file']).read_bytes(),result['requirements'])['whole_attempt_handoff_ready'])

    def test_missing_cache_and_missing_comparison_stay_incomplete(self):
        self.event('linear_list_comments',{},'truncated',{'truncated':True,'outputPath':str(self.root/'gone')})
        audit=self.audit({'comparison_ids':['missing']})
        self.assertFalse(audit['whole_attempt_handoff_ready'])
        self.assertTrue(any('cache' in s for s in audit['problems']))
        self.assertTrue(any('comparison' in s.lower() for s in audit['problems']))

    def test_live_prefix_cannot_certify_the_finished_attempt(self):
        self.command('captured',[sys.executable,'-c','pass'])
        audit=self.audit(finalized=False)
        self.assertTrue(audit['snapshot_handoff_ready'])
        self.assertFalse(audit['whole_attempt_handoff_ready'])
        result=self.bundle(audit)
        self.assertTrue(result['snapshot_handoff_ready'])
        self.assertFalse(result['whole_attempt_handoff_ready'])

    def test_editing_a_readiness_field_cannot_replace_missing_capture(self):
        self.event('bash',{'command':'go build ./...'},'')
        audit=self.audit();audit['whole_attempt_handoff_ready']=True;audit['snapshot_handoff_ready']=True;audit['problems']=[]
        (self.root/'handoff/inventory.json').write_text(json.dumps(audit))
        with self.assertRaisesRegex(GateError,'readiness differs'):self.bundle(audit)

    def test_failed_build_payload_is_preserved_but_cannot_be_consumed(self):
        repo,_=self.source_repo();output=self.root/'failed-output'
        failed=self.command('failed-build',[sys.executable,'-c',f'open({str(output)!r},"w").write("partial");raise SystemExit(42)'],
            source_repository=str(repo),produces_artifacts={'broken':str(output)})
        self.assertEqual(failed['exit_code'],42)
        binding=Path(failed['artifact_evidence']['produced']['broken']['binding'])
        bad=json.loads(binding.read_text());self.assertEqual(bad['record_type'],'failed_artifact_observation')
        path=next(d['path'] for d in bad['evidence_dependencies'] if d['name']=='payload')
        blocked=self.command('not-consumable',[sys.executable,path],uses_artifacts={'broken':str(binding)})
        self.assertEqual(blocked['execution_state'],'preparation_failed')
        audit=self.audit();result=self.bundle(audit)
        self.assertTrue(result['bundle_complete'])
        self.assertEqual(Path(path).read_text(),'partial')

    def test_nonexecution_observation_imports_its_raw_dependency(self):
        source=self.root/'native-api.json';source.write_text('{"status":200,"body":{"active":true}}')
        record=saved_observation('api',source,self.evidence/'observation')
        result=prepare_bundle({'case':'FIXTURE-1','attempt':'synthetic-evidence','subject':self.subject,
            'resources':[{'id':'api-record','kind':'observation_receipt','path':str(self.evidence/'observation/observation.json')}]},
            self.root/'observation.tar.gz')
        self.assertTrue(result['bundle_complete'])
        with tarfile.open(result['file']) as archive:
            manifest=json.load(archive.extractfile('bundle-manifest.json'))
            self.assertEqual(len(manifest['resources']),2)
        source.unlink()
        self.assertTrue(verify_bundle(Path(result['file']).read_bytes(),result['requirements'])['bundle_complete'])

    def test_next_stage_runs_archived_artifact_after_original_host_paths_are_gone(self):
        repo,build,binding,payload=self.build()
        source=prepare_bundle({'case':'FIXTURE-1','attempt':'synthetic-build','subject':self.subject,'resources':[
            {'id':'build','kind':'execution_receipt','path':str(self.evidence/'build/execution.json')}]},self.root/'origin.tar.gz')
        req=self.root/'origin-requirements.json';req.write_text(json.dumps(source['requirements']))
        original_bytes=binding.read_bytes()
        shutil.rmtree(repo);shutil.rmtree(self.evidence);self.evidence.mkdir()
        self.events=[];self.opening=self.open(self.subject)
        restored=self.evidence/'restored'
        result=restore_artifact(self.root/'origin.tar.gz',req,restored,name='gateway')
        self.assertEqual(result['subject'],self.subject)
        restored_payload=next(d['path'] for d in result['evidence_dependencies'] if d['name']=='payload')
        self.event('bash',{'command':__import__('shlex').join([sys.executable,str(self.package/'scripts/restore-artifact.py'),
            '--bundle',str(self.root/'origin.tar.gz'),'--requirements',str(req),'--name','gateway','--output',str(restored)])})
        run=self.command('next-stage-runtime',[sys.executable,restored_payload,'0'],
                         uses_artifacts={'gateway':str(restored/'binding-reference.json')})
        self.assertEqual(run['result'],'satisfied_within_scope')
        audit=self.audit({'artifact_subjects':{'gateway':self.subject}});bundle=self.bundle(audit)
        self.assertTrue(bundle['whole_attempt_handoff_ready'])
        current_req=self.root/'current-requirements.json';current_req.write_text(json.dumps(bundle['requirements']))
        second=restore_artifact(Path(bundle['file']),current_req,self.root/'next-receiver',name='gateway')
        origin=next(d for d in second['evidence_dependencies'] if d['name']=='source-bundle')
        self.assertEqual(origin['sha256'],source['sha256'])  # no ever-growing stage archive chain
        with tarfile.open(self.root/'origin.tar.gz') as archive:
            manifest=json.load(archive.extractfile('bundle-manifest.json'))
            binding_entry=next(e for e in manifest['resources'] if e['kind']=='artifact_binding')
            self.assertEqual(archive.extractfile(binding_entry['archive_path']).read(),original_bytes)
