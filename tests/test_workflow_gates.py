"""Offline regressions for the JER-40 through JER-46 workflow gates."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'skills/defensefactory/scripts'
sys.path.insert(0,str(SCRIPTS))
from factorycore.codeintel_gate import coverage_disposition,coverage_publish_gate
from factorycore.core import identity
from factorycore.deployment_contract import evaluate as deployment_evaluate,validate_binding
from factorycore.evaluator_isolation import run_isolated
from factorycore.evidence_inventory import inventory,publication_gate
from factorycore.trial_controls import scope_prepare
from factorycore.workflow_gates import (decision_gate,decision_request,issue_eligibility,
    record_decision,repair_admission,stalled_findings)


class WorkflowGateTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name).resolve()
        self.subject={'repository':'fixture/repository','revision':'a'*40}
        self.assessment={'stage':'assess','result':'satisfied_within_scope','disposition':'continue',
            'target_decisions':[{'id':'target','reason':'active','subject':self.subject}],
            'repair_contract_blockers':[]}
        self.counterexample={'id':'fixture-counterexample','result':'reproduced',
            'evidence':['https://linear.invalid/attachment/counterexample']}
        self.contract={'id':'fixture-contract','version':'1','reference':'https://linear.invalid/contract',
            'requirements_sha256':'b'*64}
        self.scope={'authorized_by':'fixture-owner','reference':'https://linear.invalid/authorization',
            'operations':['repair'],'paths':['component/']}

    def eligibility(self):
        return issue_eligibility(self.assessment,self.subject,self.counterexample,self.contract,self.scope)

    def test_repair_refuses_missing_and_stale_eligibility_and_scope_admits_exact_receipt(self):
        self.assertFalse(repair_admission(None,self.subject)['repair_permitted'])
        receipt=self.eligibility()
        stale={**self.subject,'revision':'c'*40}
        self.assertFalse(repair_admission(receipt,stale)['repair_permitted'])
        prepared=scope_prepare({'case':'FIXTURE-1','attempt':'fixture','stage':'repair','subject':self.subject,
            'performed_by':'fixture','package':str(ROOT/'skills/defensefactory-repair'),
            'authorization_reference':'fixture scope','boundaries':'offline fixture',
            'eligibility_receipt':receipt})
        self.assertEqual(prepared['scope']['eligibility_sha256'],receipt['eligibility_sha256'])
        bad=dict(receipt);bad['contract']={**bad['contract'],'version':'changed'}
        with self.assertRaisesRegex(ValueError,'Repair admission refused'):
            scope_prepare({'case':'FIXTURE-1','attempt':'fixture','stage':'repair','subject':self.subject,
                'performed_by':'fixture','package':str(ROOT/'skills/defensefactory-repair'),
                'authorization_reference':'fixture scope','boundaries':'offline fixture',
                'eligibility_receipt':bad})

    def test_structured_decision_blocks_then_resumes_and_can_admit_eligibility(self):
        request=decision_request({'id':'owner-choice','question':'Which boundary?','blocking_stage':'repair',
            'requested_by':'fixture','created_at':'2026-01-01T00:00:00+00:00',
            'scope_reference':'https://linear.invalid/request','subject':self.subject,
            'options':[{'id':'a','consequence':'Use A'},{'id':'b','consequence':'Use B'}]})
        self.assertFalse(decision_gate(request)['resume_permitted'])
        decision=record_decision(request,'a','fixture-owner','2026-01-01T01:00:00+00:00',
            'https://linear.invalid/decision','this exact subject')
        gate=decision_gate(request,decision);self.assertTrue(gate['resume_permitted'])
        assessment={**self.assessment,'repair_contract_blockers':[{'id':'owner-choice'}]}
        receipt=issue_eligibility(assessment,self.subject,self.counterexample,self.contract,self.scope,[gate])
        self.assertTrue(receipt['repair_permitted'])

    def test_zero_occurrence_is_explicit_and_needs_operator_scope_decision(self):
        index={'subject':self.subject,'exact_index_available':True}
        coverage=coverage_disposition(self.subject,index,{'occurrences':0,'query_succeeded':True,
            'source_reads':2,'warnings':[]})
        self.assertEqual(coverage['coverage_disposition'],'coverage_zero_occurrence')
        self.assertFalse(coverage_publish_gate(coverage)['publish_permitted'])
        decided=coverage_publish_gate(coverage,{'scope':'non_semantic','decided_by':'fixture-owner',
            'reference':'https://linear.invalid/decision','reason':'Only exact file reading is required'})
        self.assertTrue(decided['publish_permitted']);self.assertFalse(decided['semantic_claim_permitted'])
        strict=coverage_publish_gate(coverage,{'scope':'semantic_required','decided_by':'fixture-owner',
            'reference':'https://linear.invalid/decision','reason':'Caller analysis is required'})
        self.assertFalse(strict['publish_permitted'])

    def test_unguarded_capture_blocks_publication_unless_explicitly_overridden(self):
        evidence=self.root/'evidence';evidence.mkdir();events=self.root/'events.jsonl'
        events.write_text(json.dumps({'type':'tool_use','part':{'id':'unsafe','tool':'bash','state':{
            'status':'completed','input':{'command':'go test ./...'},'output':'ok'}}})+'\n')
        opening={'scope':{'subject':self.subject,'package':str(ROOT/'skills/defensefactory'),
            'codeintel_requirement':{'mode':'not_required','reference':'fixture'}}}
        requirements={'scope_reference':'https://linear.invalid/scope','comparison_ids':[],
            'assertion_checks':{},'artifact_subjects':{},'codeintel':{'disposition':'not_needed',
            'reason':'offline fixture','reference':'https://linear.invalid/scope'}}
        audit=inventory([evidence],self.root/'handoff',events=events,workspace=self.root,
            opening=opening,requirements=requirements,finalized=True)
        self.assertFalse(audit['whole_attempt_handoff_ready'])
        blocked=publication_gate(audit,lambda path:Path(path).read_bytes());self.assertFalse(blocked['publish_permitted'])
        override={'decision_id':'publish-fixture','decided_by':'fixture-owner',
            'decided_at':'2026-01-01T00:00:00+00:00','reference':'https://linear.invalid/override',
            'reason':'Preserve failed evidence','scope':'publish_incomplete_evidence'}
        allowed=publication_gate(audit,lambda path:Path(path).read_bytes(),override)
        self.assertTrue(allowed['publish_permitted']);self.assertFalse(allowed['handoff_ready'])

    def test_isolated_evaluator_reports_agreement_and_divergence(self):
        def command(result):
            payload={'obligations':{'boundary':{'result':result,'evidence':['fixture']}}}
            return [sys.executable,'-c','import json;print(json.dumps('+repr(payload)+'))']
        spec={'subject':self.subject,'contract':{'obligations':['boundary']},'timeout_seconds':10,
            'evaluators':[{'role':'primary','identity':'fixture-primary','argv':command('satisfied_within_scope')},
                          {'role':'independent','identity':'fixture-independent','argv':command('satisfied_within_scope')}]}
        agreed=run_isolated(spec,self.root/'agree');self.assertEqual(agreed['result'],'agreed')
        spec['evaluators'][1]['argv']=command('violated')
        diverged=run_isolated(spec,self.root/'diverge');self.assertEqual(diverged['result'],'diverged')
        self.assertFalse(diverged['comparisons'][0]['agreement'])

    def test_intake_only_is_stalled_but_explicit_park_is_not(self):
        intake={'record_type':'intake_receipt','subject':self.subject,'reference':'https://linear.invalid/intake'}
        findings=[{'id':'FIX-1','subject':self.subject,'receipts':[intake]},
            {'id':'FIX-2','subject':self.subject,'receipts':[intake],
             'park_receipt':{'record_type':'finding_park','finding':'FIX-2','subject':self.subject,
                 'reason':'Owner-scheduled','decided_by':'fixture-owner','reference':'https://linear.invalid/park',
                 'parked_at':'2026-01-01T00:00:00+00:00'}}]
        report=stalled_findings(findings)
        self.assertEqual([row['finding'] for row in report['stalled']],['FIX-1'])
        self.assertEqual(report['stalled'][0]['required_stage'],'assess')

    def test_deployment_contract_reports_alignment_without_values(self):
        contract={'schema':'defensefactory/deployment-contract/v1','id':'fixture-deployment',
            'subject':self.subject,'points':[{'id':'upstream-host','description':'Host and TLS name agree',
                'rule':'all_equal','sources':['client.host','tls.server_name']},
                {'id':'pin-policy','description':'Selected trust policy is allowed','rule':'allowed_values',
                 'sources':['client.trust_policy'],'allowed_values':['ca_validation','user_pin']} ]}
        observations={'client.host':{'state':'observed','value':'example.invalid','reference':'https://linear.invalid/a','capture_sha256':'1'*64},
            'tls.server_name':{'state':'observed','value':'example.invalid','reference':'https://linear.invalid/b','capture_sha256':'2'*64},
            'client.trust_policy':{'state':'observed','value':'ca_validation','reference':'https://linear.invalid/c','capture_sha256':'3'*64}}
        receipt=deployment_evaluate(contract,observations)
        self.assertTrue(receipt['deployment_binding_ready']);validate_binding(receipt,self.subject)
        encoded=json.dumps(receipt);self.assertNotIn('example.invalid',encoded);self.assertNotIn('ca_validation',encoded)
        observations['tls.server_name']['value']='other.invalid'
        violated=deployment_evaluate(contract,observations)
        self.assertEqual(violated['result'],'violated')


if __name__=='__main__':unittest.main()
