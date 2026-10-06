"""Bounded cross-language Parquet probe; not a corpus conversion receipt."""
import json
from pathlib import Path
import platform
import pyarrow as pa
import pyarrow.parquet as pq

root = Path(__file__).resolve().parents[2]
table = pq.read_table(root / 'work/delivery_arrow_probe.parquet')
expected = {'id': ['001', '002', '003'], 'text': ['한글', '', None], 'offset': [0, 1, None]}
assert table.to_pydict() == expected
pq.write_table(table, root / 'work/delivery_arrow_python_probe.parquet', compression='zstd')
assert pq.read_table(root / 'work/delivery_arrow_python_probe.parquet').equals(table)
result = dict(status='python_read_of_R_probe_passed', python=platform.python_version(), pyarrow=pa.__version__,
              rows=3, checks=['string IDs with leading zeros', 'Hangul', 'empty string distinct from null', 'integer coordinates with null'],
              corpus_conversion_complete=False, R_read_of_Python_probe_pending=True)
(root / 'work/delivery_arrow_environment_probe.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
