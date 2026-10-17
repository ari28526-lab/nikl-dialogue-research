"""Bounded, read-only gzip-level comparison on receipt-bound completed outputs.

No source text is printed. Timings cover in-memory compression, not the entire
producer or disk I/O. Existing inputs and producer code remain unchanged.
"""
import argparse
import ctypes
import gc
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import statistics
import time


def sha(data):
    return hashlib.sha256(data).hexdigest()


def available_memory():
    if os.name != 'nt':
        return None
    class Memory(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong),
                    ('total_phys', ctypes.c_ulonglong), ('avail_phys', ctypes.c_ulonglong),
                    ('total_page', ctypes.c_ulonglong), ('avail_page', ctypes.c_ulonglong),
                    ('total_virtual', ctypes.c_ulonglong), ('avail_virtual', ctypes.c_ulonglong),
                    ('avail_extended', ctypes.c_ulonglong)]
    state = Memory()
    state.length = ctypes.sizeof(state)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)):
        raise OSError('memory_status_unavailable')
    return state.avail_phys


def benchmark(receipt_path, limit_mib=32, seconds=60):
    if os.name == 'nt':
        kernel = ctypes.windll.kernel32
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        kernel.SetPriorityClass.restype = ctypes.c_int
        if not kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x4000):
            raise OSError('below_normal_priority_unavailable')
    receipt_bytes = receipt_path.read_bytes()
    receipt = json.loads(receipt_bytes)
    if receipt['status'] != 'complete_with_reviews':
        raise ValueError('completed_source_required')
    started = time.perf_counter()
    results = []
    limit = limit_mib * 2**20
    for name, expected in receipt['outputs'].items():
        if not name.endswith('.json.gz') or Path(name).name != name:
            raise ValueError('plain_gzip_basename_required')
        free = available_memory()
        if free is not None and free < 700 * 2**20:
            raise MemoryError('preserve_active_worker_memory_floor')
        source = receipt_path.parent / name
        source_bytes = source.read_bytes()
        source_sha = sha(source_bytes)
        if source_sha != expected['sha256'] or len(source_bytes) != expected['bytes']:
            raise ValueError('source_receipt_binding')
        with gzip.GzipFile(fileobj=io.BytesIO(source_bytes)) as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise ValueError('bounded_sample_limit_exceeded')
        raw_sha = sha(raw)
        timings = {n: [] for n in (1, 3, 6, 9)}
        sizes = {}
        exact = {}
        for order in ((9, 1, 3, 6), (6, 3, 1, 9)):
            for level in order:
                if time.perf_counter() - started > seconds:
                    raise TimeoutError('bounded_benchmark_time_limit')
                sink = io.BytesIO()
                begin = time.perf_counter()
                with gzip.GzipFile(fileobj=sink, mode='wb', filename='', mtime=0,
                                   compresslevel=level) as compressed:
                    compressed.write(raw)
                elapsed = time.perf_counter() - begin
                payload = sink.getvalue()
                restored = gzip.decompress(payload)
                if restored != raw or sha(restored) != raw_sha:
                    raise ValueError('lossless_roundtrip_failed')
                timings[level].append(elapsed)
                sizes[level] = len(payload)
                exact[level] = payload == source_bytes
                del payload, restored, sink
        if sha(source.read_bytes()) != source_sha:
            raise ValueError('source_changed_during_benchmark')
        results.append(dict(output_kind=name, uncompressed_bytes=len(raw),
            source_bytes=len(source_bytes), source_sha256=source_sha,
            uncompressed_sha256=raw_sha, all_roundtrips_byte_identical=True,
            levels={str(n): dict(seconds=timings[n], median_seconds=statistics.median(timings[n]),
                compressed_bytes=sizes[n], source_compressed_bytes_identical=exact[n]) for n in timings}))
        del source_bytes, raw
        gc.collect()
    if receipt_path.read_bytes() != receipt_bytes:
        raise ValueError('receipt_changed_during_benchmark')
    summary = {str(n): dict(compression_seconds=sum(r['levels'][str(n)]['median_seconds'] for r in results),
        compressed_bytes=sum(r['levels'][str(n)]['compressed_bytes'] for r in results)) for n in (1, 3, 6, 9)}
    return dict(schema='bounded_lossless_gzip_benchmark.v1', status='passed',
        receipt_sha256=sha(receipt_bytes), input_files_unchanged=True,
        producer_modified=False, production_outputs_modified=False,
        samples=results, totals=summary, elapsed_seconds=time.perf_counter()-started,
        limits='One bounded completed source, two alternating-order measurements per level. '
               'In-memory compression only; excludes serialization, dictionary application, hashes, disk I/O '
               'and final audit. Concurrent producer and small-sample variability prevent end-to-end speed claims.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise ValueError('new_report_required')
    report = benchmark(args.receipt)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=True, indent=2)
        stream.write('\n')
    print(json.dumps({k: report[k] for k in ('status','totals','elapsed_seconds')}, ensure_ascii=True))


if __name__ == '__main__':
    main()
