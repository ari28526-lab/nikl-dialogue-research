"""Offline recovery: verify all pieces, reconstruct ZIPs, extract to a new folder."""
import argparse,hashlib,json,shutil,zipfile
from pathlib import Path,PurePosixPath

def safe(n):
    p=PurePosixPath(n)
    if p.is_absolute() or '..' in p.parts or '\\' in n or ':' in n:raise ValueError('Unsafe path')
    return p

def main():
    ap=argparse.ArgumentParser();ap.add_argument('catalog',type=Path);ap.add_argument('parts',type=Path);ap.add_argument('output',type=Path);a=ap.parse_args()
    c=json.loads(a.catalog.read_text(encoding='utf-8-sig'))
    if not c['complete_handoff'] or len(c['archives'])!=c['expected_archives']:raise ValueError('Incomplete handoff catalog')
    a.output.mkdir(parents=True,exist_ok=False)
    assembled=a.output/'_assembled';assembled.mkdir()
    for ar in c['archives']:
        dest=assembled/safe(ar['name']);h=hashlib.sha256()
        with dest.open('xb') as out:
            for part in ar['parts']:
                hp=hashlib.sha256();n=0
                with (a.parts/safe(part['name'])).open('rb') as f:
                    for b in iter(lambda:f.read(4*1024**2),b''):out.write(b);hp.update(b);h.update(b);n+=len(b)
                if hp.hexdigest()!=part['sha256'] or n!=part['bytes']:raise ValueError('Part mismatch')
        if h.hexdigest()!=ar['sha256'] or dest.stat().st_size!=ar['bytes']:raise ValueError('ZIP mismatch')
        with zipfile.ZipFile(dest) as z:
            records=json.loads(z.read('_BACKUP_MEMBERS.json'))
            if len(z.namelist())!=len(records)+1:raise ValueError('Membership mismatch')
            for r in records:
                p=a.output/'research_start_v1_20260914'/safe(r['relative']);p.parent.mkdir(parents=True,exist_ok=True)
                h=hashlib.sha256();n=0
                with z.open(r['relative']) as src,p.open('xb') as out:
                    for b in iter(lambda:src.read(4*1024**2),b''):out.write(b);h.update(b);n+=len(b)
                if h.hexdigest()!=r['sha256'] or n!=r['bytes']:raise ValueError('Member mismatch')
    print('Restored and SHA verified. Read the package README before joining morphology and alignment coordinates.')

if __name__=='__main__':main()
