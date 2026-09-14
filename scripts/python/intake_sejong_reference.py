"""Copy an authorized reference to a new destination and verify Dropbox hash."""
import argparse,hashlib,json,os,urllib.request
from pathlib import Path

def digest(p):
    h=hashlib.sha256();d=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):
            h.update(b);d.update(hashlib.sha256(b).digest())
    return h.hexdigest(),d.hexdigest()

def main():
    a=argparse.ArgumentParser();a.add_argument('--url',required=True);a.add_argument('--output',required=True);a.add_argument('--size',type=int,required=True);a.add_argument('--hash',required=True);a=a.parse_args()
    p=Path(a.output);p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists():
        s,d=digest(p)
        if p.stat().st_size!=a.size or d!=a.hash:raise ValueError('existing_file_mismatch')
        print(json.dumps({'status':'already_verified','name':p.name,'sha256':s}));return
    part=p.with_suffix(p.suffix+'.partial')
    try:
        with urllib.request.urlopen(a.url,timeout=120) as r,part.open('xb') as f:
            while True:
                b=r.read(1024*1024)
                if not b:break
                f.write(b)
            f.flush();os.fsync(f.fileno())
        s,d=digest(part)
        if part.stat().st_size!=a.size or d!=a.hash:raise ValueError('download_integrity_mismatch')
        part.rename(p)
        p.with_suffix(p.suffix+'.receipt.json').write_text(json.dumps({'status':'verified','name':p.name,'bytes':a.size,'sha256':s,'dropbox_content_hash':d},indent=2),encoding='utf-8')
        print(json.dumps({'status':'verified','name':p.name,'bytes':a.size,'sha256':s}))
    except Exception as e:
        print(json.dumps({'status':'failed','error_type':type(e).__name__}));raise SystemExit(1)
if __name__=='__main__':main()
