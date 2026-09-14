"""Query the original dictionary together with the completed Sejong supplement."""
import argparse,json
from pathlib import Path
from sejong_supplement import supplemented_dictionary

def main():
    p=argparse.ArgumentParser();p.add_argument('--lemma',required=True);p.add_argument('--pos',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    d=supplemented_dictionary()
    try:r=d.lookup(a.lemma,a.pos)
    finally:d.close()
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':'combined_dictionary_queried','api_called':False,'sejong_contexts':len(r['sejong_sense_supplement']['annotated_contexts']),'base_sources':len(r['sources'])}))
if __name__=='__main__':main()
