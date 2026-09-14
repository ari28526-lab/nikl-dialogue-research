"""Verify installed client transport using synthetic inputs and an in-memory spy.

No credentials, API calls, or corpus text are needed for this diagnostic.
"""
import argparse
import hashlib
import inspect
import json
from pathlib import Path


def probe():
    from bareunpy import Tagger

    class Spy:
        def __init__(self):
            self.calls = []

        def analyze_syntax(self, content, dictionaries, **kwargs):
            self.calls.append(('AnalyzeSyntax', content, kwargs))
            return None

        def analyze_syntax_list(self, content, dictionaries, **kwargs):
            self.calls.append(('AnalyzeSyntaxList', content, kwargs))
            return None

    tagger = Tagger.__new__(Tagger)
    spy = Spy()
    tagger.client = spy
    tagger.custom_dicts = []
    tagger.tags(['synthetic one', 'synthetic two'], auto_split=False, auto_spacing=False, auto_jointing=False, with_sense=False)
    tagger.tags(['synthetic one', 'synthetic two'], auto_split=False, auto_spacing=True, auto_jointing=True, with_sense=True)
    tagger.taglist(['synthetic one', 'synthetic two'], with_sense=True)
    assert spy.calls[0][0] == spy.calls[1][0] == 'AnalyzeSyntax'
    assert spy.calls[0][1] == spy.calls[1][1] == 'synthetic one\nsynthetic two'
    assert spy.calls[2][0] == 'AnalyzeSyntaxList'
    client_source = Path(inspect.getfile(Tagger))
    return {'schema': 'bareun_processing_unit_probe.v1', 'passed': True,
            'network_calls': 0, 'synthetic_only': True,
            'installed_tagger_source_sha256': hashlib.sha256(client_source.read_bytes()).hexdigest(),
            'morph_and_wsd_input_unit': 'source_CSV_utt_id_row_form',
            'actual_tags_RPC': 'AnalyzeSyntax',
            'tags_transport': 'newline_joined_utterance_forms_in_one_document',
            'taglist_RPC': 'AnalyzeSyntaxList',
            'automatic_linguistic_sentence_reconstruction': False,
            'server_cross_line_semantic_context': 'not_established_by_client_probe',
            'probe_calls': [{'rpc': c[0], 'options': c[2]} for c in spy.calls]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = probe()
    with args.report.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')
    print(json.dumps(result))
