"""Small read-only real-source structural pilot, explicitly not a copy audit."""
import json
from pathlib import Path
import build_delivery_semantic_links as m

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / 'outputs/reports/bareun32_reanalysis_plan_20260926'


class SourcePilot(m.Package):
    def __init__(self):
        self.roles = {x['role']:x for x in m.read(REPORT/'DELIVERY_COPY_SOURCES_20260929.json')['roots']}
        self.paths = {}; self.checked = 0

    def ref(self, role, subpath, expected=None, optional=False):
        rel=m.relative(self.roles[role]['destination']+'/'+m.relative(subpath))
        path=Path(self.roles[role]['source'])/subpath
        if not path.is_file():
            if optional:return None
            raise ValueError('Missing source pilot reference '+str(path))
        self.paths[rel]=path; self.checked+=1
        digest=expected or (m.sha(path) if path.name in ['LINK_INDEX.csv.gz','recordings.csv'] else 'not_rehashed_in_source_pilot')
        return dict(path=rel,bytes=path.stat().st_size,sha256=digest)

    def path(self, rel):
        return self.paths[rel]


if __name__=='__main__':
    pkg=SourcePilot()
    entries=m.read(Path(pkg.roles['delivery_discourse_parquet_20260928']['source'])/'INPUTS.json')
    selected=[]
    for year in ['2020','2021','2025']:
        selected.append(next(e for e in entries if e['corpus']=='modu' and e['year']==year))
    selected.extend(e for e in entries if e['path'] in ['seoul/s01m16f1/s01m16f1.json','seoul_interviews/s01m16f.json'])
    out=ROOT/'work/delivery_semantic_source_pilot_v2_20260929';out.mkdir(exist_ok=True)
    final=m.build(pkg,out,selected,sample=True)
    result=dict(status='source_structural_pilot_passed',counts=final['counts'],references_checked=pkg.checked,
                runner_sha256=m.sha(Path(m.__file__)),
                scope='Native JSON/link SHA, exact IDs/order and path existence checked. Shared large files not rehashed. Source-backed structural pilot, not independent package reopening.')
    m.save(REPORT/'DELIVERY_SEMANTIC_SOURCE_PILOT.json',result)
    print(json.dumps(result,ensure_ascii=False))
