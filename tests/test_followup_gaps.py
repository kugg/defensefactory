"""Regression cases for the observed admission, comparison, probe and CodeIntel gaps."""
import copy
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch
import test_evidence_flow as fixtures

SCRIPTS = fixtures.SCRIPTS
from factorycore.core import GateError,identity,sha
from factorycore.trial_controls import scope_prepare,stage_start
from factorycore.runtime_plan import declare,outcomes
from factorycore.codeintel_gate import index_observation,coverage_disposition
from factorycore.source_export import export_sources
from factorycore.handoff_bundle import verify_bundle


class FollowupGaps(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.EvidenceFlow('runTest')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def opening(self, comparisons=(), required=False, codeintel_mode=None):
        f=self.f
        codeintel = ({'mode':codeintel_mode,'reference':'Synthetic ticket policy'} if codeintel_mode else
                     {'required':required,'reference':'Synthetic ticket policy'})
        prep=scope_prepare({'case':'FIXTURE-1','attempt':'synthetic-evidence','stage':'verify','subject':f.subject,
            'performed_by':'synthetic-agent','package':str(f.package),'authorization_reference':'Synthetic operator',
            'boundaries':'Offline fixtures only','comparisons':list(comparisons),
            'codeintel_requirement':codeintel})
        pub={'id':'fixture-comment','body':prep['scope_body'],'createdAt':prep['prepared_at']}
        f.opening=stage_start(prep,pub,{**pub,'operation':'retrieval','retrieved_at':prep['prepared_at']})
        (f.root/'opening.json').write_text(json.dumps(f.opening))
        return f.opening

    def cli(self, name, *args, env=None):
        f=self.f
        argv=[sys.executable,str(f.package/'scripts/stage-exec.py'),'--opening',str(f.root/'opening.json'),
              '--id',name,'--cwd',str(f.root),'--output',str(f.evidence/name),*args]
        result=subprocess.run(argv,env={**os.environ,**(env or {})},capture_output=True,text=True)
        f.event('bash',{'command':shlex.join(argv)})
        return result

    def test_baseline_setup_no_longer_needs_a_nonexistent_mutation_declaration(self):
        marker=self.f.root/'setup'
        result=self.cli('setup','--support','--purpose','Create isolated fixture','--',
                        sys.executable,'-c',f'open({str(marker)!r},"w").write("created")')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue(marker.exists())

    def test_low_level_capture_is_refused_in_registered_trial_before_side_effect(self):
        f=self.f;marker=f.root/'not-created';source=f.root/'input.json'
        source.write_text(json.dumps({'specification':{'id':'bypass','subject':f.subject,
            'performed_by':'fixture','argv':[sys.executable,'-c',f'open({str(marker)!r},"w").close()'],
            'cwd':str(f.root),'timeout_seconds':10,'execution':{'format':'command','reason':'fixture','success_criteria':'exit zero'}},
            'evidence_directory':str(f.evidence/'bypass')}))
        result=subprocess.run([sys.executable,str(SCRIPTS/'stage.py'),'command-record','--input',str(source),
            '--output',str(f.evidence/'refusal.json')],env={**os.environ,'DEFENSEFACTORY_STAGE_OPENING':str(f.root/'opening.json')},
            capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(marker.exists())
        self.assertIn('not an admission fallback',(f.evidence/'refusal.json').read_text())

    def test_incomplete_command_criteria_stop_before_launch_and_are_preserved(self):
        f=self.f;marker=f.root/'not-created'
        result=f.command('bad-criteria',[sys.executable,'-c',f'open({str(marker)!r},"w").close()'],
            execution={'format':'command','reason':'missing success criterion'})
        self.assertEqual(result['execution_state'],'preparation_failed')
        self.assertFalse(marker.exists())
        self.assertTrue((f.evidence/'bad-criteria/specification.json').exists())

    def test_rejected_cli_has_a_durable_correlated_admission_receipt(self):
        f=self.f
        result=self.cli('undeclared','--comparison','not-in-opening','--',sys.executable,'-c','pass')
        self.assertNotEqual(result.returncode,0)
        receipt=f.evidence/'undeclared/admission-failure.json'
        self.assertTrue(receipt.exists())
        saved=json.loads(receipt.read_text())
        self.assertEqual(saved['requested_options']['comparison'],'not-in-opening')
        self.assertIn('opening',[d['name'] for d in saved['evidence_dependencies']])
        audit=f.audit()
        self.assertIn('guarded_rejection',[t['classification'] for t in audit['observed_tools']])
        self.assertTrue(audit['whole_attempt_handoff_ready'],audit['problems'])

    def test_admitted_base_build_and_use_are_correctly_bound_and_survive_archive(self):
        f=self.f;repo,builder=f.source_repo();base=copy.deepcopy(f.subject)
        (repo/'extra').write_text('candidate')
        subprocess.run(['git','-C',str(repo),'add','.'],check=True)
        subprocess.run(['git','-C',str(repo),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
            '-c','commit.gpgsign=false','commit','-qm','Candidate'],check=True)
        f.subject={**f.subject,'revision':subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD']).decode().strip()}
        self.opening([{'id':'base','subject':base,'purpose':'Changed control','reference':'Synthetic scope'}])
        f.command('switch-base',['git','-C',str(repo),'checkout','--detach',base['revision']])
        output=f.root/'base-output'
        built=self.cli('base-build','--comparison','base','--source-repo',str(repo),
            '--produces','base='+str(output),'--',sys.executable,str(builder),str(output))
        self.assertEqual(built.returncode,0,built.stderr)
        binding=f.evidence/'base-build/artifacts/base/binding.json'
        self.assertEqual(json.loads(binding.read_text())['subject'],base)
        wrong=self.cli('mislabeled','--use-artifact','base='+str(binding),'--',sys.executable,'{artifact:base}','0')
        self.assertNotEqual(wrong.returncode,0)
        self.assertIn('Consumed artifact source differs',(f.evidence/'mislabeled/execution.json').read_text())
        declaration=declare(f.opening,[{'id':'base-runtime','purpose':'Changed-control acceptance',
            'comparison_id':'base','artifacts':['base'],'argv':[sys.executable,'{artifact:base}','0'],
            'assertions':[{'name':'control-accepts','exit_code':0,'stdout_contains':['fixture']}]}],'Synthetic runtime policy')
        plan=f.evidence/'control-runtime-plan.json';plan.write_text(json.dumps(declaration))
        correct=self.cli('base-runtime','--comparison','base','--runtime-plan',str(plan),'--use-artifact','base='+str(binding))
        self.assertEqual(correct.returncode,0,correct.stderr)
        audit=f.audit();bundle=f.bundle(audit);raw=Path(bundle['file']).read_bytes()
        shutil.rmtree(repo);shutil.rmtree(f.evidence)
        self.assertTrue(verify_bundle(raw,bundle['requirements'])['whole_attempt_handoff_ready'])

    def make_probe(self):
        f=self.f;repo,build,binding,payload=f.build()
        declaration=declare(f.opening,[{'id':'refusal','purpose':'Fixture refusal','artifacts':['gateway'],
            'argv':[sys.executable,'{artifact:gateway}','2'],
            'assertions':[{'name':'refused','exit_code':2,'stdout_contains':['fixture']}]},
            {'id':'legitimate','purpose':'Legitimate fixture path','artifacts':['gateway'],
             'argv':[sys.executable,'{artifact:gateway}','0'],
             'assertions':[{'name':'accepted','exit_code':0,'stdout_contains':['fixture']}]}],'Synthetic runtime contract')
        plan=f.evidence/'runtime-plan.json';plan.write_text(json.dumps(declaration))
        return declaration,plan,binding

    def test_direct_runtime_plan_asserts_actual_nonzero_and_offline_replays(self):
        f=self.f;declaration,plan,binding=self.make_probe()
        result=self.cli('refusal','--runtime-plan',str(plan),'--use-artifact','gateway='+str(binding))
        self.assertEqual(result.returncode,0,result.stderr)
        receipt=json.loads((f.evidence/'refusal/execution.json').read_text())
        self.assertEqual(receipt['exit_code'],2)
        positive=self.cli('legitimate','--runtime-plan',str(plan),'--use-artifact','gateway='+str(binding))
        self.assertEqual(positive.returncode,0,positive.stderr)
        positive_receipt=json.loads((f.evidence/'legitimate/execution.json').read_text())
        verdict=outcomes(declaration,f.opening,[receipt,positive_receipt],lambda p:Path(p).read_bytes())
        self.assertEqual(verdict['result'],'satisfied_within_scope')
        mislabeled=copy.deepcopy(receipt);mislabeled['subject']={'revision':'b'*40}
        rejected=outcomes(declaration,f.opening,[mislabeled,positive_receipt],lambda p:Path(p).read_bytes())
        self.assertEqual(rejected['result'],'inconclusive')
        audit=f.audit();self.assertTrue(audit['whole_attempt_handoff_ready'],audit['problems'])
        bundle=f.bundle(audit);raw=Path(bundle['file']).read_bytes();shutil.rmtree(f.evidence)
        self.assertTrue(verify_bundle(raw,bundle['requirements'])['whole_attempt_handoff_ready'])

    def test_dropping_runtime_protocol_or_missing_probe_cannot_earn_readiness(self):
        f=self.f;declaration,plan,binding=self.make_probe()
        # Generic exit-zero is not this declaration's refusal check.
        f.command('refusal',[sys.executable,'-c','print("fixture")'])
        audit=f.audit()
        self.assertFalse(audit['whole_attempt_handoff_ready'])
        self.assertTrue(any('Probe ID/declaration' in p for p in audit['problems']),audit['problems'])

    def test_shell_wrapper_is_rejected_at_runtime_declaration_not_rewritten_as_success(self):
        with self.assertRaisesRegex(GateError,'Separate fixture setup'):
            declare(self.f.opening,[{'id':'bad','purpose':'fixture','artifacts':['binary'],
                'argv':['docker','run','image','sh','-c','{artifact:binary}; echo $?'],
                'assertions':[{'name':'refused','exit_code':2}]}],'Synthetic contract')

    def codeintel(self, scope_required=True, query_ref='candidate', error=False):
        f=self.f;self.opening(required=scope_required)
        status=f.evidence/'status.json';status.write_text(json.dumps({'body':{'id':17,'manifests':[{
            'branch':'refs/heads/candidate','commitHash':f.subject['revision'],'active':True}]}}))
        record=index_observation(f.subject,'refs/heads/candidate',f.subject['repository'],status,'/body/manifests')
        observed=f.evidence/'index-observation.json';observed.write_text(json.dumps(record))
        coverage=coverage_disposition(f.subject,record,{'occurrences':1,'query_succeeded':not error,
            'source_reads':1 if not error else 0,'warnings':[]})
        coverage_path=f.evidence/'coverage.json';coverage_path.write_text(json.dumps(coverage))
        f.events.append({'type':'tool_use','part':{'id':'actual-native-query','tool':'factory_codeintel_grep',
            'state':{'status':'completed','input':{'repo_id':17,'ref':query_ref,'query':'entry'},
                     'output':json.dumps({'error':'offline'} if error else {'matches':[{'path':'component.go','line':1}]} )}}})
        return {'disposition':'required','reason':'Exact-source query obligation','reference':'Synthetic contract',
            'index_observation':str(observed),'query_event_ids':['actual-native-query'],
            'repository_argument':'repo_id','repository_value':17,'ref_argument':'ref',
            'coverage_receipt':str(coverage_path),'coverage_disposition':coverage['coverage_disposition'],
            'coverage_limitations':['Lexical search only; no semantic completeness claim']}

    def test_skipped_codeintel_or_discovery_only_or_error_cannot_earn_readiness(self):
        f=self.f;requirement=self.codeintel()
        f.events=[]
        missing=f.audit({'codeintel':requirement},name='missing')
        self.assertFalse(missing['whole_attempt_handoff_ready'])
        f.events=[{'type':'tool_use','part':{'id':'actual-native-query','tool':'factory_codeintel_list_repos',
            'state':{'status':'completed','input':{},'output':'{}'}}}]
        discovery=f.audit({'codeintel':requirement},name='discovery')
        self.assertFalse(discovery['whole_attempt_handoff_ready'])
        f.events=[]
        requirement=self.codeintel(error=True)
        failed=f.audit({'codeintel':requirement},name='failed-query')
        self.assertFalse(failed['whole_attempt_handoff_ready'])

    def test_codeintel_requires_raw_exact_manifest_and_scoped_actual_query_in_archived_replay(self):
        f=self.f;requirement=self.codeintel()
        audit=f.audit({'codeintel':requirement})
        self.assertTrue(audit['whole_attempt_handoff_ready'],audit['problems'])
        bundle=f.bundle(audit);raw=Path(bundle['file']).read_bytes();shutil.rmtree(f.evidence)
        self.assertTrue(verify_bundle(raw,bundle['requirements'])['whole_attempt_handoff_ready'])

    def test_stale_index_or_wrong_ref_or_relabeling_policy_is_incomplete(self):
        f=self.f;req=self.codeintel(query_ref='base')
        bad=f.audit({'codeintel':req},name='wrong-ref');self.assertFalse(bad['whole_attempt_handoff_ready'])
        raw=f.evidence/'status.json';status=json.loads(raw.read_text());status['body']['manifests'][0]['commitHash']='b'*40
        raw.write_text(json.dumps(status))
        changed=f.audit({'codeintel':req},name='changed')
        self.assertFalse(changed['whole_attempt_handoff_ready'])
        self.assertTrue(any('raw status changed' in p for p in changed['problems']))
        renamed=f.audit({'codeintel':{'disposition':'not_needed','reason':'Skipped','reference':'Synthetic policy'}},name='renamed')
        self.assertFalse(renamed['whole_attempt_handoff_ready'])
        self.assertTrue(any('downgraded' in p for p in renamed['problems']))

    def test_unavailable_codeintel_requires_actual_attempt_not_a_prose_assertion(self):
        f=self.f
        policy={'disposition':'unavailable','reason':'Transport unavailable','reference':'Synthetic scope'}
        empty=f.audit({'codeintel':policy},name='none')
        self.assertFalse(empty['whole_attempt_handoff_ready'])
        f.events.append({'type':'tool_use','part':{'id':'failed-query','tool':'factory_codeintel_grep',
            'state':{'status':'completed','input':{},'output':'{"error":"transport unavailable"}'}}})
        policy['attempt_event_ids']=['failed-query']
        supported=f.audit({'codeintel':policy},name='attempted')
        self.assertTrue(supported['whole_attempt_handoff_ready'],supported['problems'])

    def test_attempt_required_can_finish_with_a_retained_coverage_limitation(self):
        f=self.f
        self.opening(codeintel_mode='attempt_or_limitation')
        f.events.append({'type':'tool_use','part':{'id':'limited-query','tool':'factory_codeintel_grep',
            'state':{'status':'completed','input':{'ref':'candidate'},'output':'{"matches":[]}'}}})
        policy={'disposition':'limited','reason':'Exact subject indexed but text and SCIP recall are unusable',
            'reference':'Synthetic scope','attempt_event_ids':['limited-query'],
            'coverage_limitations':['SCIP occurrences are zero; known source term was not returned']}
        audit=f.audit({'codeintel':policy},name='limited')
        self.assertTrue(audit['whole_attempt_handoff_ready'],audit['problems'])

    def test_strict_coverage_scope_rejects_the_same_limitation(self):
        f=self.f
        self.opening(codeintel_mode='coverage_required')
        f.events.append({'type':'tool_use','part':{'id':'limited-query','tool':'factory_codeintel_grep',
            'state':{'status':'completed','input':{'ref':'candidate'},'output':'{"matches":[]}'}}})
        policy={'disposition':'limited','reason':'Known source term was not returned',
            'reference':'Synthetic scope','attempt_event_ids':['limited-query'],
            'coverage_limitations':['Text recall is incomplete']}
        audit=f.audit({'codeintel':policy},name='limited-strict')
        self.assertFalse(audit['whole_attempt_handoff_ready'])
        self.assertTrue(any('downgraded' in problem for problem in audit['problems']))


    def test_truncated_codeintel_error_is_checked_from_retained_full_response(self):
        f=self.f;req=self.codeintel()
        cache=f.root/'native-response.json';cache.write_text('{"isError":true,"error":"backend failed"}')
        f.events[0]['part']['state'].update(output='truncated',metadata={'truncated':True,'outputPath':str(cache)})
        audit=f.audit({'codeintel':req})
        self.assertFalse(audit['whole_attempt_handoff_ready'])
        self.assertTrue(any('returned an error' in p for p in audit['problems']),audit['problems'])

    def test_exact_source_objects_survive_loss_of_the_original_repository(self):
        f=self.f;repo,builder=f.source_repo();revision=f.subject['revision']
        result=export_sources(repo,{'variant':revision},f.evidence/'export')
        self.assertEqual(result['result'],'recorded')
        audit=f.audit({'source_revisions':[revision]});self.assertTrue(audit['whole_attempt_handoff_ready'],audit['problems'])
        bundle=f.bundle(audit);raw=Path(bundle['file']).read_bytes()
        import tarfile
        with tarfile.open(bundle['file']) as archive:
            manifest=json.load(archive.extractfile('bundle-manifest.json'))
            entry=next(e for e in manifest['resources'] if e['kind']=='source_bundle')
            source=archive.extractfile(entry['archive_path']).read()
        shutil.rmtree(repo);shutil.rmtree(f.evidence)
        self.assertTrue(verify_bundle(raw,bundle['requirements'])['whole_attempt_handoff_ready'])
        received=f.root/'received.bundle';received.write_bytes(source)
        subprocess.run(['git','clone','--bare',str(received),str(f.root/'receiver.git')],check=True,capture_output=True)
        actual=subprocess.check_output(['git','--git-dir',str(f.root/'receiver.git'),'rev-parse','refs/heads/variant']).decode().strip()
        self.assertEqual(actual,revision)

    def test_missing_source_objects_and_export_failure_are_preserved_not_excused(self):
        f=self.f;repo,builder=f.source_repo()
        failed=export_sources(repo,{'missing':'b'*40},f.evidence/'failed-export')
        self.assertEqual(failed['result'],'inconclusive')
        self.assertTrue((f.evidence/'failed-export/commands.json').exists())
        audit=f.audit({'source_revisions':['b'*40]})
        self.assertFalse(audit['whole_attempt_handoff_ready'])
        self.assertTrue(any('source objects not exported' in p for p in audit['problems']))
        bundle=f.bundle(audit)
        self.assertTrue(bundle['bundle_complete'])

    def test_removing_assertions_after_inline_shell_rejection_is_detected(self):
        f=self.f;criteria=f.evidence/'assertions.json'
        criteria.write_text('[{"name":"refused","exit_code":2}]')
        rejected=self.cli('runtime-case','--assertions',str(criteria),'--','docker','run','image','sh','-c','echo done')
        self.assertNotEqual(rejected.returncode,0)
        argv=[sys.executable,str(f.package/'scripts/stage-exec.py'),'--opening',str(f.root/'opening.json'),
              '--id','runtime-case','--cwd',str(f.root),'--output',str(f.evidence/'fallback'),
              '--',sys.executable,'-c','print("done")']
        proc=subprocess.run(argv,capture_output=True,text=True)
        self.assertEqual(proc.returncode,0,proc.stderr)
        f.event('bash',{'command':shlex.join(argv)})
        audit=f.audit()
        self.assertFalse(audit['whole_attempt_handoff_ready'])
        self.assertTrue(any('assertions dropped' in p for p in audit['problems']),audit['problems'])

    def test_deployed_style_current_manifest_activation_is_derived_from_raw_fields(self):
        f=self.f;raw=f.evidence/'deployed-status.json';subject=f.subject
        manifest={'branch':'refs/heads/candidate','commitHash':subject['revision'],'status':'READY',
                  'activatedAt':'2026-01-01T00:00:00Z','supersededAt':None,'failedAt':None}
        status={'body':{'id':17,'activeIndexUsable':True,'currentIndexManifests':[manifest]}}
        raw.write_text(json.dumps(status))
        activation={'mode':'activated_current','usable_pointer':'/body/activeIndexUsable'}
        result=index_observation(subject,'refs/heads/candidate',subject['repository'],raw,
            '/body/currentIndexManifests',activation=activation)
        self.assertTrue(result['exact_index_available'])
        manifest['supersededAt']='2026-01-02T00:00:00Z';raw.write_text(json.dumps(status))
        superseded=index_observation(subject,'refs/heads/candidate',subject['repository'],raw,
            '/body/currentIndexManifests',activation=activation)
        self.assertFalse(superseded['exact_index_available'])
        manifest['supersededAt']=None;status['body']['activeIndexUsable']=False;raw.write_text(json.dumps(status))
        unusable=index_observation(subject,'refs/heads/candidate',subject['repository'],raw,
            '/body/currentIndexManifests',activation=activation)
        self.assertFalse(unusable['exact_index_available'])

    def test_same_commit_and_branch_in_another_repository_cannot_qualify_query(self):
        f=self.f;req=self.codeintel();req['repository_value']=99
        f.events[0]['part']['state']['input']['repo_id']=99
        audit=f.audit({'codeintel':req})
        self.assertFalse(audit['whole_attempt_handoff_ready'])
        self.assertTrue(any('manifest repository differs' in p for p in audit['problems']))

    def test_source_export_timeout_keeps_partial_diagnostics(self):
        f=self.f;repo,builder=f.source_repo()
        with patch('factorycore.source_export.subprocess.run',side_effect=subprocess.TimeoutExpired(
                ['git'],1,output=b'partial source output',stderr=b'partial diagnostic')):
            result=export_sources(repo,{'candidate':f.subject['revision']},f.evidence/'timed-export',timeout=1)
        self.assertEqual(result['result'],'inconclusive')
        log=json.loads((f.evidence/'timed-export/commands.json').read_text())['commands'][0]
        self.assertEqual(log['stdout'],'partial source output')
        self.assertEqual(log['stderr'],'partial diagnostic')
        self.assertEqual(log['error'],'TimeoutExpired')
