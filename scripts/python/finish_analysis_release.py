"""Publish a local search selection after the independent full audit passes."""
import argparse
import json
from pathlib import Path
import sys
import time

import analysis_release as releases

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/variation_review'))
from build_release_data import build


def finish(args):
    deadline = time.monotonic() + args.max_wait_seconds
    while not args.audit.exists():
        if time.monotonic() >= deadline:
            raise TimeoutError('Independent audit did not finish within the wait window')
        time.sleep(15)
    if not args.catalog.exists():
        releases.register(args.catalog, args.version, args.root, args.audit,
                          args.dictionary, args.dictionary_receipt)
    else:
        release = releases.read(args.catalog)['releases'][args.version]
        if (Path(release['root']) != args.root.resolve()
                or release['audit_sha256'] != releases.sha(args.audit)):
            raise ValueError('Existing search selection belongs to another release')
    if not args.review_dataset.exists():
        build(args.source_dataset, args.catalog, args.version, args.review_dataset)
    dataset = releases.read(args.review_dataset)
    if (dataset['parent_dataset_sha256'] != releases.sha(args.source_dataset)
            or dataset['analysis_catalog_sha256'] != releases.sha(args.catalog)):
        raise ValueError('Existing review dataset belongs to different inputs')
    release = releases.read(args.catalog)['releases'][args.version]
    checks = {}
    for corpus in ('seoul', 'modu'):
        source = sorted(release['sources'][corpus])[0]
        _, documents = releases.selected_source(args.catalog, args.version, corpus, source)
        uid = documents[0]['utterances'][0]['utterance_id']
        result = releases.context(args.catalog, args.version, corpus, source, uid)
        checks[corpus] = result['target_utterance_id'] == uid
    groups = releases.dictionary_groups(release, '다리', 'NNG')
    if len(groups['candidate_groups']) < 2 or not all(checks.values()):
        raise ValueError('Live release smoke checks failed')
    report = dict(
        status='passed_local_search_and_review_binding', analysis_version=args.version,
        source_counts={c:len(release['sources'][c]) for c in ('seoul', 'modu')},
        dictionary_release=release['dictionary_release'], semantic_unit='urimalsaem_group_id',
        review_cards=len(dataset['cards']), mapping_counts=dataset['mapping_counts'],
        context_checks=checks, catalog_sha256=releases.sha(args.catalog),
        review_dataset_sha256=releases.sha(args.review_dataset),
        model_calls=0, training_started=False, textgrid_writes=0,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('root','audit','catalog','dictionary','dictionary-receipt',
                 'source-dataset','review-dataset','report'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--version',required=True)
    parser.add_argument('--max-wait-seconds',type=int,default=0)
    args=parser.parse_args()
    finish(args)
