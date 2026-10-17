import sqlite3
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/python'))
from sqlite_readonly_experiments import fetch_by_keys, BoundedResultCache


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(':memory:')
        self.addCleanup(self.connection.close)
        self.connection.execute('CREATE TABLE records (id INTEGER PRIMARY KEY, payload TEXT)')
        self.connection.executemany('INSERT INTO records VALUES (?,?)', [(1,'one'),(2,None),(3,'three')])

    def test_missing_null_duplicates_and_chunk_boundary_match_scalar_reads(self):
        keys = [3,2,99,1,3]
        expected = {}
        for key in keys:
            row = self.connection.execute('SELECT payload FROM records WHERE id=?',(key,)).fetchone()
            if row is not None:
                expected[key] = row
        self.assertEqual(fetch_by_keys(self.connection,'records','id',('payload',),keys,2),expected)
        self.assertEqual(fetch_by_keys(self.connection,'records','id',('payload',),[]),{})

    def test_sql_identifiers_and_bounds_fail_closed(self):
        for table in ('records; DROP TABLE records', 'records WHERE 1=1'):
            with self.assertRaisesRegex(ValueError,'identifier'):
                fetch_by_keys(self.connection,table,'id',('payload',),[1])
        for size in (0,301):
            with self.assertRaisesRegex(ValueError,'batch_size'):
                fetch_by_keys(self.connection,'records','id',('payload',),[1],size)
        with self.assertRaisesRegex(ValueError,'key_count'):
            fetch_by_keys(self.connection,'records','id',('payload',),range(10001))

    def test_nonunique_database_key_is_rejected(self):
        self.connection.execute('CREATE TABLE duplicate (id INTEGER, payload TEXT)')
        self.connection.executemany('INSERT INTO duplicate VALUES (?,?)',[(1,'one'),(1,'two')])
        with self.assertRaisesRegex(ValueError,'nonunique'):
            fetch_by_keys(self.connection,'duplicate','id',('payload',),[1])


class CacheTests(unittest.TestCase):
    def test_current_target_mutation_cannot_leak_into_next_result(self):
        cache = BoundedResultCache({'resource':'snapshot-one'})
        compute = lambda: {'selected_group':'g','evidence':[{'proof':1}]}
        first = cache.call(['lemma','POS','context'],compute)
        first['current_target_id'] = 'synthetic-a'
        first['evidence'][0]['proof'] = 99
        second = cache.call(['lemma','POS','context'],lambda: self.fail('cache miss'))
        self.assertNotIn('current_target_id',second)
        self.assertEqual(second['evidence'][0]['proof'],1)
        second['evidence'].clear()
        self.assertEqual(len(cache.call(['lemma','POS','context'],compute)['evidence']),1)

    def test_changed_context_or_snapshot_cannot_reuse_old_decision(self):
        first = BoundedResultCache({'resource':'snapshot-one'})
        second = BoundedResultCache({'resource':'snapshot-two'})
        self.assertNotEqual(first.scope,second.scope)
        self.assertEqual(first.call(['lemma','NNG','context-a'],lambda: 1),1)
        self.assertEqual(first.call(['lemma','VV','context-a'],lambda: 2),2)
        self.assertEqual(first.call(['lemma','NNG','context-b'],lambda: 3),3)
        self.assertEqual(second.call(['lemma','NNG','context-a'],lambda: 4),4)
        self.assertEqual(first.stats()['hits'],0)

    def test_lru_is_bounded_and_recent_hit_is_retained(self):
        cache = BoundedResultCache('scope',max_entries=2)
        cache.call('a',lambda: 1)
        cache.call('b',lambda: 2)
        cache.call('a',lambda: self.fail('miss'))
        cache.call('c',lambda: 3)
        self.assertEqual(cache.stats()['entries'],2)
        self.assertEqual(cache.stats()['evictions'],1)
        self.assertEqual(cache.call('b',lambda: 22),22)

    def test_oversized_result_is_not_retained(self):
        cache = BoundedResultCache('scope',max_value_bytes=10)
        self.assertEqual(cache.call('a',lambda: 'x'*20),'x'*20)
        self.assertEqual(cache.stats()['entries'],0)
        self.assertEqual(cache.stats()['oversized'],1)


if __name__ == '__main__':
    unittest.main()
