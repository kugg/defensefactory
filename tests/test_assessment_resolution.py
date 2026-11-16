import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/defensefactory/scripts'))

from factorycore.assessment_resolution import decision_plan
from factorycore.core import GateError
from factorycore.eligibility import fixed_decision_satisfaction


class DecisionAuthorityTests(unittest.TestCase):
    def review(self, records=None):
        return {
            'ticket': 'FIXTURE-1',
            'ticket_updated_at': '2026-01-01T10:00:00Z',
            'retrieved_at': '2026-01-01T10:01:00Z',
            'snapshot_reference': 'fixture/current-ticket.json',
            'surfaces': [
                {'kind': kind, 'state': 'reviewed', 'reference': 'fixture/' + kind + '.json'}
                for kind in ('description', 'status', 'comments', 'documents', 'attachments', 'relations')
            ],
            'authority_records': records or [],
        }

    def unresolved(self):
        return {
            'id': 'recovery-safety', 'kind': 'owner_policy', 'state': 'unresolved', 'blocks_stages': ['repair'],
            'owner': 'component owner', 'reference': 'fixture/report',
            'authority_review': 'no_applicable_resolution',
            'authority_rationale': 'No applicable owner decision was found in the complete current ticket.',
            'applied_authority_references': [],
            'question': 'Which recovery condition governs reuse?',
            'alternatives': [
                {'choice': 'verified cleanup', 'consequence': 'fail closed until cleanup is verified'},
                {'choice': 'elapsed time', 'consequence': 'reuse after a timeout'},
            ],
        }

    def resolution(self, effect='resolves'):
        return {
            'id': 'owner-recovery-direction', 'decision_id': 'recovery-safety',
            'effect': effect, 'reference': 'ticket-comment:owner-recovery-direction',
            'owner': 'component owner', 'recorded_at': '2026-01-01T09:00:00Z',
            'directive': 'Require verified cleanup before reuse.',
        }

    def test_unresolved_question_requires_complete_current_review(self):
        result = decision_plan([self.unresolved()], authority_review=self.review())
        self.assertTrue(result['blocked'])
        self.assertEqual(result['questions'][0]['id'], 'recovery-safety')
        self.assertTrue(result['authority_review_sha256'])

    def test_reviewed_owner_resolution_cannot_be_reopened(self):
        with self.assertRaisesRegex(GateError, 'do not reopen'):
            decision_plan([self.unresolved()], authority_review=self.review([self.resolution()]))

    def test_current_owner_resolution_cannot_disappear_from_early_gate(self):
        with self.assertRaisesRegex(GateError, 'not mapped'):
            decision_plan([], authority_review=self.review([self.resolution()]))

    def test_resolved_decision_binds_exact_owner_record(self):
        decision = self.unresolved()
        decision.update({
            'state': 'resolved',
            'decision_reference': 'ticket-comment:owner-recovery-direction',
            'choice': 'Require verified cleanup before reuse.',
        })
        decision.pop('authority_review')
        decision.pop('authority_rationale')
        result = decision_plan([decision], authority_review=self.review([self.resolution()]))
        self.assertFalse(result['blocked'])
        self.assertEqual(result['resolved_decisions'][0]['decision_reference'],
                         'ticket-comment:owner-recovery-direction')

    def test_already_fixed_cannot_contradict_recovery_owner_decision(self):
        decision = self.unresolved()
        decision.update(state='resolved', decision_reference='ticket-comment:owner-recovery-direction',
                        choice='Require verified cleanup before reuse.')
        decision.pop('authority_review'); decision.pop('authority_rationale')
        plan = decision_plan([decision], authority_review=self.review([self.resolution()]))
        ttl_only = {'decision_satisfaction': [{
            'decision_id': 'recovery-safety', 'outcome': 'violated',
            'evidence_reference': 'ticket-attachment:ttl-recovery-test',
            'rationale': 'The observed test permits elapsed-time reuse without verified cleanup.',
        }]}
        with self.assertRaisesRegex(GateError, 'conflicts with a retained owner decision'):
            fixed_decision_satisfaction(ttl_only, plan)
        reconciled = {'decision_satisfaction': [{
            'decision_id': 'recovery-safety', 'outcome': 'satisfied',
            'evidence_reference': 'ticket-attachment:journal-reconciliation-test',
            'rationale': 'The prior call is terminated and durable state reconciled before reuse.',
        }]}
        self.assertEqual(fixed_decision_satisfaction(reconciled, plan)[0]['outcome'], 'satisfied')

    def test_current_constraint_must_be_applied(self):
        constrained = self.unresolved()
        with self.assertRaisesRegex(GateError, 'omitted a current owner constraint'):
            decision_plan([constrained], authority_review=self.review([self.resolution('constrains')]))
        constrained['applied_authority_references'] = ['ticket-comment:owner-recovery-direction']
        self.assertTrue(decision_plan([constrained], authority_review=self.review([self.resolution('constrains')]))['blocked'])

    def test_conflicting_resolutions_need_explicit_supersession(self):
        first = self.resolution()
        second = dict(first, id='owner-recovery-change', reference='ticket-comment:owner-recovery-change',
                      recorded_at='2026-01-01T09:30:00Z', directive='Permit reuse after timeout.')
        decision = self.unresolved()
        decision.update({'state': 'resolved', 'choice': second['directive'],
                         'decision_reference': second['reference']})
        decision.pop('authority_review')
        decision.pop('authority_rationale')
        with self.assertRaisesRegex(GateError, 'Conflicting owner resolutions'):
            decision_plan([decision], authority_review=self.review([first, second]))
        second['supersedes'] = [first['id']]
        result = decision_plan([decision], authority_review=self.review([first, second]))
        self.assertEqual(result['resolved_decisions'][0]['choice'], 'Permit reuse after timeout.')

    def test_incomplete_or_stale_ticket_review_is_rejected(self):
        incomplete = self.review()
        incomplete['surfaces'][2]['state'] = 'truncated'
        with self.assertRaisesRegex(GateError, 'completely reviewed'):
            decision_plan([self.unresolved()], authority_review=incomplete)
        stale = self.review()
        stale['retrieved_at'] = '2026-01-01T09:59:59Z'
        with self.assertRaisesRegex(GateError, 'predates'):
            decision_plan([self.unresolved()], authority_review=stale)

    def test_observable_fact_routes_to_factory_evidence_not_owner(self):
        blocker = {
            'id': 'provider-profile', 'kind': 'observable_fact', 'state': 'unresolved',
            'blocks_stages': ['repair'], 'reference': 'ticket:provider-requirement',
            'question': 'Which authenticated media profile does the provider negotiate?',
            'authority_review': 'no_applicable_resolution',
            'authority_rationale': 'Ticket review settles fail-closed policy but contains no measurement.',
            'applied_authority_references': [],
            'evidence_plan': {
                'executor': 'factory', 'method': 'bounded sanitized capability probe',
                'authorization_reference': 'ticket:probe-scope',
                'success_criteria': ['answer transport and keying method recorded'],
                'redactions': ['credentials', 'key material'],
                'inference_boundary': {
                    'measurement_unit': 'one exact endpoint/client/profile attempt',
                    'allowed_conclusions': ['negotiation result for the exact attempt'],
                    'prohibited_conclusions': ['provider-wide capability absence'],
                    'legitimate_behavior': ['provider calling remains available'],
                },
            },
        }
        result = decision_plan([blocker], authority_review=self.review())
        self.assertTrue(result['blocked'])
        self.assertTrue(result['factory_evidence_required'])
        self.assertFalse(result['owner_action_required'])
        self.assertEqual(result['questions'], [])
        self.assertEqual(result['evidence_tasks'][0]['next_action_owner'], 'factory')

    def test_observable_fact_cannot_be_disguised_as_owner_choice(self):
        blocker = self.unresolved()
        blocker['kind'] = 'observable_fact'
        blocker['evidence_plan'] = {
            'executor': 'factory', 'method': 'probe', 'authorization_reference': 'ticket:scope',
            'success_criteria': ['result'], 'redactions': [],
            'inference_boundary': {
                'measurement_unit': 'attempt', 'allowed_conclusions': ['attempt result'],
                'prohibited_conclusions': ['universal absence'],
                'legitimate_behavior': ['call succeeds'],
            },
        }
        with self.assertRaisesRegex(GateError, 'cannot be presented as owner alternatives'):
            decision_plan([blocker], authority_review=self.review())

    def test_resolved_observable_fact_requires_durable_measurement(self):
        blocker = {
            'id': 'provider-profile', 'kind': 'observable_fact', 'state': 'resolved',
            'blocks_stages': ['repair'], 'applied_authority_references': [],
            'finding': 'SDES-SRTP accepted; plaintext downgrade rejected',
            'evidence_references': ['ticket-attachment:provider-capability-receipt'],
            'measurement_scope': {
                'subject': 'repository@commit', 'target': 'provider endpoint',
                'client_or_evaluator': 'probe@digest', 'attempts': ['attempt-1'],
            },
            'inference': {
                'status': 'observed', 'claim': 'SDES succeeded for this exact attempt',
                'limitations': ['Does not establish all provider endpoints'],
            },
            'legitimate_behavior': ['Provider calling remains available'],
        }
        result = decision_plan([blocker], authority_review=self.review())
        self.assertFalse(result['blocked'])
        self.assertEqual(result['resolved_decisions'][0]['finding'], blocker['finding'])

    def test_negative_probe_cannot_claim_capability_absence_without_coverage(self):
        blocker = {
            'id': 'provider-profile', 'kind': 'observable_fact', 'state': 'resolved',
            'blocks_stages': ['repair'], 'applied_authority_references': [],
            'finding': 'The exact offer did not establish authenticated media',
            'evidence_references': ['ticket-attachment:probe-result'],
            'measurement_scope': {
                'subject': 'repository@commit', 'target': 'one provider endpoint',
                'client_or_evaluator': 'probe@digest', 'attempts': ['attempt-1'],
            },
            'inference': {
                'status': 'absent_within_declared_scope',
                'claim': 'Provider capability is absent',
                'limitations': ['One suite was recognized by the parser'],
            },
            'legitimate_behavior': ['Provider calling remains available'],
        }
        with self.assertRaisesRegex(GateError, 'Capability absence needs exhaustive'):
            decision_plan([blocker], authority_review=self.review())

    def test_failed_exact_attempt_is_retained_as_not_observed(self):
        blocker = {
            'id': 'provider-profile', 'kind': 'observable_fact', 'state': 'resolved',
            'blocks_stages': ['repair'], 'applied_authority_references': [],
            'finding': 'The exact DTLS offer received plaintext RTP',
            'evidence_references': ['ticket-attachment:probe-result'],
            'measurement_scope': {
                'subject': 'repository@commit', 'target': 'one provider endpoint',
                'client_or_evaluator': 'probe@digest', 'attempts': ['attempt-1'],
            },
            'inference': {
                'status': 'not_observed',
                'claim': 'Authenticated media was not observed in this attempt',
                'limitations': ['Does not distinguish provider capability from client incompatibility'],
            },
            'legitimate_behavior': ['Provider calling remains available'],
        }
        result = decision_plan([blocker], authority_review=self.review())
        self.assertEqual(result['resolved_decisions'][0]['inference']['status'], 'not_observed')


if __name__ == '__main__':
    unittest.main()
