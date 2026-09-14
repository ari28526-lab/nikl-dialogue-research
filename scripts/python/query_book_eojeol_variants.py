"""Explicit opt-in lookup through the additive book spelling-variant index."""
import argparse, json
from pathlib import Path
from build_book_eojeol_index import lookup

def main():
    ap=argparse.ArgumentParser()
    for name in ['surface','analysis','lemma','pos']: ap.add_argument('--'+name,required=True)
    ap.add_argument('--numeric-template',action='store_true')
    ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args()
    result={'schema':'book_variant_lookup.v1','sources':{dataset:lookup(a.surface,a.analysis,a.lemma,a.pos,dataset,numeric=a.numeric_template) for dataset in ['05.txt','12.txt']},'datasets_summed':False,'selected_group':None,'api_called':False}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':'queried','selected_group':None,'api_called':False,'source_counts':{d:sum(v.get('native_distribution',{}).values()) for d,v in result['sources'].items()}},ensure_ascii=False))

if __name__=='__main__':main()
