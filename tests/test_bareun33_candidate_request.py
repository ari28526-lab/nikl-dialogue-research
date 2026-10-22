import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts/python'))
from bareun33_candidate_request import prepare, digest


class CandidateRequestTests(unittest.TestCase):
    def setUp(self):
        self.job = dict(request_id='context-a', text='  synthetic context  ',
                        mappings=[{'begin': 2, 'end': 19}], options={'with_sense': True},
                        target_ids=['candidate', 'conflict', 'dialect'],
                        target_priorities={'candidate': 'primary', 'conflict': 'primary',
                                           'dialect': 'dialect_later'})
        self.targets = [dict(target_id=k, lemma=k, pos='NNG', priority=v)
                        for k, v in self.job['target_priorities'].items()]

    def run_prepare(self, ids=None, states=None, frequency=None, sha=None):
        return prepare(self.job, ids or ['candidate', 'dialect'], self.targets,
                       sha or digest(self.job), frequency or (lambda lemma, pos: 10),
                       states or {})

    def test_context_preserved_conflict_excluded_no_mutation(self):
        before = copy.deepcopy((self.job, self.targets))
        result = self.run_prepare()
        for key in ['text', 'mappings', 'options']:
            self.assertEqual(result['job'][key], self.job[key])
        self.assertEqual(result['job']['target_ids'], ['candidate', 'dialect'])
        self.assertNotIn('conflict', result['job']['target_priorities'])
        self.assertEqual((self.job, self.targets), before)
        self.assertFalse(result['transport_authorized'])

    def test_parent_id_quarantine_survives_derived_id(self):
        result = self.run_prepare(states={'context-a': 'uncertain_no_retry'})
        self.assertNotEqual(result['job']['request_id'], 'context-a')
        self.assertEqual(result['disposition'], 'quarantine_no_retry')

    def test_success_reused_without_resending(self):
        self.assertEqual(self.run_prepare(states={'context-a': 'response_verified'})
                         ['disposition'], 'reuse_saved_response')

    def test_order_canonical_and_frequency_then_dialect(self):
        a = self.run_prepare(ids=['dialect', 'candidate'])
        b = self.run_prepare(ids=['candidate', 'dialect'])
        self.assertEqual(a, b)
        rare = self.run_prepare(frequency=lambda lemma, pos: 1)
        dialect = self.run_prepare(ids=['dialect'])
        self.assertLess(a['sort_key'], rare['sort_key'])
        self.assertLess(rare['sort_key'], dialect['sort_key'])

    def test_changed_parent_rejected(self):
        sha = digest(self.job)
        self.job['text'] += ' changed'
        with self.assertRaisesRegex(ValueError, 'parent_request_changed'):
            self.run_prepare(sha=sha)

    def test_duplicate_or_foreign_targets_rejected(self):
        for ids in [['candidate', 'candidate'], ['foreign']]:
            with self.assertRaisesRegex(ValueError, 'ownership'):
                self.run_prepare(ids=ids)

    def test_unknown_history_and_missing_frequency_fail_closed(self):
        with self.assertRaisesRegex(ValueError, 'prior_context_state'):
            self.run_prepare(states={'context-a': 'intent'})
        for n in [0, -1, True, None]:
            with self.assertRaisesRegex(ValueError, 'global_candidate_frequency'):
                self.run_prepare(frequency=lambda lemma, pos: n)

    def test_priority_change_rejected(self):
        self.targets[0]['priority'] = 'dialect_later'
        with self.assertRaisesRegex(ValueError, 'parent_priority_changed'):
            self.run_prepare()


if __name__ == '__main__':
    unittest.main()
