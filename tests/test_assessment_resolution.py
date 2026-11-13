import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/defensefactory/scripts'))

from factorycore.assessment_resolution import decision_plan
from factorycore.core import GateError


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
            'id': 'recovery-safety', 'state': 'unresolved', 'blocks_stages': ['repair'],
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


if __name__ == '__main__':
    unittest.main()
