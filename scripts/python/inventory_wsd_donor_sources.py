"""Read existing LS tables once; report coverage/schema, never emit source text.

This is a donor inventory, not sense adoption or an exact-context match run.
"""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import time


def inventory(source_root, references):
    files = sorted(source_root.glob('*LS*.csv'))
    if not files:
        raise ValueError('no_LS_tables')
    targets = {Path(r['relative']).parent.name for r in references}
    results = []
    started = time.monotonic()
    csv.field_size_limit(10_000_000)
    for path in files:
        before = path.stat()
        sentences = set()
        matched = set()
        nonempty_sense_sentences = set()
        pos = Counter()
        counts = Counter()
        required = {'doc_id', 'sent_id', 'sent_form', 'word', 'pos', 'sense_id', 'begin', 'end', 'word_id'}
        with path.open(encoding='utf-8-sig', newline='') as handle:
            reader = csv.DictReader(handle)
            if not required.issubset(reader.fieldnames or []):
                raise ValueError('missing_context_columns_' + path.name)
            for row in reader:
                uid = row['sent_id']
                sentences.add(uid)
                counts['annotation_rows'] += 1
                pos[row['pos']] += 1
                if uid.split('.')[0] in targets:
                    matched.add(uid)
                if row['sense_id'] and row['sense_id'] not in {'[]', 'None', 'NA'}:
                    counts['rows_with_nonempty_sense_field'] += 1
                    nonempty_sense_sentences.add(uid)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise RuntimeError('source_changed_during_inventory')
        results.append({'file': path.name, 'bytes': before.st_size, 'counts': dict(counts),
                        'unique_sentence_ids_within_file': len(sentences),
                        'sentences_with_nonempty_sense_field': len(nonempty_sense_sentences),
                        'sentence_ids_in_target_conversations': len(matched),
                        'POS_counts': dict(pos), 'has_sentence_text_and_offsets': True,
                        'size_and_mtime_unchanged': True})
        print(json.dumps({'file': path.name, 'done': True, 'sentences': len(sentences)}), flush=True)
    return {'schema': 'wsd_LS_context_source_inventory.v1', 'status': 'read_only_inventory_complete',
            'elapsed_seconds': round(time.monotonic() - started, 2), 'files': results,
            'sentence_counts_are_per_file_not_global_deduplicated': True,
            'sense_number_namespace_and_zero_codes_verified': False,
            'exact_text_or_context_matching_performed': False,
            'source_content_sha_verified': False, 'sense_adoption_performed': False,
            'API_called': False, 'raw_text_exported': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--references', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    refs = json.loads(args.references.read_text(encoding='utf-8'))['sources']
    result = inventory(args.source_root, refs)
    with args.report.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=True, indent=2)
        handle.write('\n')
    print(json.dumps({'status': result['status'], 'elapsed_seconds': result['elapsed_seconds']}))
