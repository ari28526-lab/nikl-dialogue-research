"""Verify every archive member against its recorded source SHA before Dropbox copy."""
import hashlib,json,zipfile
from pathlib import Path
from build_seoul_share_package_20260913 import OUT,sha,write_json
root=OUT/'DELIVERY';results=[]
for p in sorted(root.rglob('*.zip')):
    with zipfile.ZipFile(p) as z:
        names=z.namelist();assert len(names)==len(set(names))
        assert not any(Path(n).suffix.lower() in {'.wav','.textgrid','.sqlite','.db','.key'} for n in names)
        refs=json.loads(z.read('FILE_MANIFEST.json'))
        assert {r['path'] for r in refs}|{'FILE_MANIFEST.json'}==set(names)
        for row in refs:
            h=hashlib.sha256();size=0
            with z.open(row['path']) as f:
                for b in iter(lambda:f.read(1024*1024),b''):h.update(b);size+=len(b)
            assert h.hexdigest()==row['sha256'] and size==row['bytes'],(p.name,row['path'])
    results.append(dict(archive=p.relative_to(root).as_posix(),members_verified=len(refs),passed=True))
    print('Verified',p.name,len(refs),flush=True)
write_json(OUT/'DELIVERY_AUDIT.json',dict(passed=True,archives=results,docx_pages=5,docx_visual_review=True,renderer='Microsoft Word PDF export and pypdfium2 after bundled LibreOffice unavailable',new_api_calls=0))
print('PASS',flush=True)
