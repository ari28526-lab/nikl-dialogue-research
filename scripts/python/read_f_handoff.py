"""Read one sample from each explicitly selected F handoff input, no API/index."""
import csv, gzip, json
from pathlib import Path

def main(package):
    c=json.loads((package/'CATALOG.json').read_text(encoding='utf-8'))
    assert c['status']=='copied_sha_verified' and c['automatic_old_version_fallback'] is False
    assert c['active_morphology']['with_sense'] is False
    rows=[]
    for year in c['alignment_years']:
        root=package/'alignment'/year['year']
        t=json.loads((root/'TABLES_MANIFEST.json').read_text(encoding='utf-8-sig'))
        assert t['pronunciation_release_id']==c['active_alignment_release']
        for role in ['utterances','words','phones']:
            with gzip.open(root/t['tables'][role]['path'],'rt',encoding='utf-8-sig',newline='') as f:
                reader=csv.DictReader(f); row=next(reader)
                rows.append(dict(year=year['year'],role=role,columns=len(row),has_utt_id='utt_id' in row))
    samples=[x for x in c['files'] if x['relative'].startswith('morphology/files/') and x['relative'].endswith('/morphemes.csv.gz')]
    assert samples
    with gzip.open(package/samples[0]['relative'],'rt',encoding='utf-8-sig',newline='') as f:
        row=next(csv.DictReader(f)); morph_columns=list(row)
    drive=package.parents[1]
    assert (drive/c['raw_root']).is_dir() and (drive/c['wav_root']).is_dir()
    print(json.dumps(dict(status='offline_sample_passed',annual_alignment_samples=rows,morphology_columns=morph_columns,raw_and_wav_roots_present=True,new_index_built=False,api_called=False),ensure_ascii=False))

if __name__=='__main__': main(Path(__file__).resolve().parent)
