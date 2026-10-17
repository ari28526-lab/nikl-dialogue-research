"""Experimental bounded batching and result cache; no production integration."""
from collections import OrderedDict
import copy
import hashlib
import json
import re


def fetch_by_keys(connection, table, key_column, columns, keys, batch_size=300):
    """Read unique native-typed keys; retain NULL payloads and omit missing keys."""
    if not columns:
        raise ValueError('nonempty_payload_columns_required')
    identifiers = (table, key_column, *columns)
    if any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name) for name in identifiers):
        raise ValueError('invalid_sql_identifier')
    if not 1 <= batch_size <= 300:
        raise ValueError('bounded_batch_size_required')
    unique = list(dict.fromkeys(keys))
    if len(unique) > 10000:
        raise ValueError('bounded_key_count_exceeded')
    results = {}
    for start in range(0, len(unique), batch_size):
        chunk = unique[start:start + batch_size]
        query = (f'SELECT {key_column},' + ','.join(columns) + f' FROM {table} '
                 f'WHERE {key_column} IN (' + ','.join('?' for _ in chunk) + ')')
        for row in connection.execute(query, chunk):
            if row[0] in results:
                raise ValueError('nonunique_batch_lookup_key')
            results[row[0]] = tuple(row[1:])
    return results


class BoundedResultCache:
    """Per-snapshot cache with complete caller-supplied keys and copy isolation."""
    def __init__(self, snapshot, max_entries=512, max_value_bytes=65536):
        if max_entries < 1 or max_value_bytes < 1:
            raise ValueError('positive_cache_bounds_required')
        self.scope = hashlib.sha256(self.encode(snapshot)).hexdigest()
        self.max_entries = max_entries
        self.max_value_bytes = max_value_bytes
        self.values = OrderedDict()
        self.hits = self.misses = self.evictions = self.oversized = 0

    @staticmethod
    def encode(value):
        return json.dumps(value, sort_keys=True, ensure_ascii=True,
                          separators=(',', ':'), allow_nan=False).encode()

    def call(self, key, compute):
        payload = self.encode(key)
        identity = (self.scope, hashlib.sha256(payload).digest())
        if identity in self.values:
            self.hits += 1
            self.values.move_to_end(identity)
            return copy.deepcopy(self.values[identity])
        self.misses += 1
        value = compute()
        if len(payload) > self.max_value_bytes or len(self.encode(value)) > self.max_value_bytes:
            self.oversized += 1
            return value
        self.values[identity] = copy.deepcopy(value)
        if len(self.values) > self.max_entries:
            self.values.popitem(last=False)
            self.evictions += 1
        return value

    def stats(self):
        return dict(hits=self.hits, misses=self.misses, evictions=self.evictions,
                    oversized=self.oversized, entries=len(self.values))
