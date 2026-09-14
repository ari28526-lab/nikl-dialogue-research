"""Replay existing 103-utterance reference through the resumable runner."""
import json,sqlite3,time,uuid
from pathlib import Path
import apply_context_dictionary_full as app

def main():
    cfg=app.read(app.DEFAULT_CONFIG)
    source='NIKL_DIALOGUE_2025_v1.0/SARW2500000001.csv'
    bindings=[json.loads(line) for line in (app.ROOT/cfg['json_bindings']).read_text(encoding='utf-8').splitlines()]
    binding=next(b for b in bindings if b['source_file']==source)
    parent=(Path(cfg['input_root'])/binding['bareun_receipt_relative']).parent
    ref={'source_file':source,'receipt_sha256':binding['bareun_receipt_sha256'],'json_binding':binding}
    output=app.ROOT/'work/context_dictionary_application_20260906'/('technical_check_'+uuid.uuid4().hex)
    d=app.Dictionary();started=time.monotonic()
    for n,c in list(d.units.items()):d.units[n]=app.QueryCache(c,cfg['query_cache_entries_per_source'])
    paused=[False]
    def hook(stage,ordinal,row):
        if stage=='committed' and not paused[0]:paused[0]=True;raise KeyboardInterrupt()
    try:
        try:app.apply_one(parent,output,ref,'technical_equivalence',d,checkpoint=25,hook=hook,json_path=Path(cfg['json_root'])/binding['json_relative'])
        except KeyboardInterrupt:pass
        c=sqlite3.connect(output/'APPLICATION.building.sqlite')
        try:checkpoint=app.unit_counts(c)['utterances'];assert checkpoint==25,checkpoint
        finally:c.close()
        r,_=app.apply_one(parent,output,ref,'technical_equivalence',d,checkpoint=25,json_path=Path(cfg['json_root'])/binding['json_relative'])
        c=sqlite3.connect(output/'APPLICATION.sqlite')
        try:actual=[app.unpacked(p) for p, in c.execute('SELECT payload FROM morphemes ORDER BY utterance_ordinal,row_ordinal')]
        finally:c.close()
        reference=app.ROOT/'work/context_dictionary_full_20260906/BAREUN_APPLICATION.jsonl'
        expected=[json.loads(line) for line in reference.read_text(encoding='utf-8').splitlines()]
        assert actual==expected,'resumed full consumer differs from frozen reference'
        report={'status':'passed','errors':[],'scope':'runner technical equivalence, not a new linguistic pilot or accuracy estimate','forced_pause_after_utterances':checkpoint,'counts':r['counts'],'decoded_payloads_exactly_equal':len(actual),'reference_sha256':app.sha(reference),'runner_sha256':app.sha(Path(app.__file__)),'validator_sha256':app.sha(Path(__file__)),'output':output.relative_to(app.ROOT).as_posix(),'elapsed_seconds':round(time.monotonic()-started,2),'api_called':False}
        app.atomic_json(app.ROOT/'outputs/reports/VALIDATION_context_dictionary_application_20260906.json',report)
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    finally:d.close()

if __name__=='__main__':main()
