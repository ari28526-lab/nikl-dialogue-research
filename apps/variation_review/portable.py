"""Portable review packets; immutable response exchange and atomic local import.

Build and dry-run read the production DB through a consistent SQLite backup.
Only --apply writes judgments, using the same Store validation as the local app.
"""
import argparse
import copy
import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path
from server import Store, Problem, ROOT, DATA, LEDGER, STATIC, digest, now

APP = Path(__file__).resolve().parent
OUT = ROOT / 'outputs/reviews/portable_review_v1'
WORK = ROOT / 'work/portable_review'
SCHEMA = 'variation_portable_responses.v1'

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def write_new(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        f.write(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, indent=2))

def snapshot(database, destination):
    """Never copy an open DB/WAL as raw files."""
    src = sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro', uri=True)
    dst = sqlite3.connect(destination)
    try:
        src.backup(dst)
    finally:
        dst.close(); src.close()

def make_packet(store):
    catalog = store.catalog()
    # Browsing preferences are not part of the immutable evidence/answer baseline.
    catalog['preferences'] = {}
    states = store.states()
    legacy, lh, _ = store.legacy()
    if catalog['legacy_hash'] != lh:
        raise ValueError('기존 판단 장부가 갱신 중입니다. 잠시 후 묶음을 다시 생성하세요.')
    details = {}
    for oid, card in store.cards.items():
        annotation = store.annotation_input(oid)
        details[oid] = dict(card=card, candidates=list(store.candidates(card).values()),
            legacy=legacy.get(oid, []), state=store.effective(card, states, legacy), legacy_hash=lh,
            annotation_request=annotation, annotation_request_sha256=digest(annotation))
    payload = dict(schema='variation_portable_packet.v1', catalog=catalog, details=details,
        base_states={oid: states.get(oid, dict(revision=0, decision=None)) for oid in store.cards},
        dataset_hash=store.dataset_hash, legacy_hash=lh)
    payload['packet_id'] = digest(payload)
    return payload

def render(packet):
    html = (STATIC/'index.html').read_text(encoding='utf-8')
    import re
    html = re.sub(r'<link[^>]+>', '', html)
    html = re.sub(r'<script src="/app.js" defer></script>', '', html)
    html = html.replace('href="/"', 'href="#"')
    html = html.replace('결 · 한국어 변이 검토', '결 · 휴대용 검토')
    html = html.replace('id="proposalRecordBtn"', 'id="proposalRecordBtn" disabled title="모델 제안 기록은 주 PC 서버에서 저장합니다."')
    html = html.replace('기록 내보내기</button>', '답변 파일 저장</button>')
    html = html.replace('저장한 판단은 PC와 휴대폰에서 이어집니다.', '답변 파일을 저장한 뒤 다른 PC에서 불러올 수 있습니다.')
    toolbar = '''<section class="portable-bar"><div><strong>휴대용 검토 · 설치 없이 사용</strong>
<p id="portableStatus" role="status">답변 파일을 불러오거나 검토를 시작하세요.</p></div>
<button id="portableImport" class="secondary">답변 파일 불러오기</button>
<input id="portableFile" type="file" accept=".json,application/json" hidden>
<span id="portableCount"></span></section>'''
    html = html.replace('<div id="banner"', toolbar+'<div id="banner"')
    css = (STATIC/'style.css').read_text(encoding='utf-8') + '''
.portable-bar{display:flex;gap:16px;align-items:center;padding:14px 28px;background:#e9f2eb;border-bottom:1px solid #b5cabb;flex-wrap:wrap}.portable-bar p{margin:5px 0;font-size:14px}.portable-bar div{flex:1;min-width:240px}.portable-bar.unsaved{background:#fff1d6}.portable-bar button{white-space:nowrap}
'''
    html = html.replace('</head>', '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'unsafe-inline\'; style-src \'unsafe-inline\'; img-src data:; connect-src \'none\'; base-uri \'none\'; form-action \'none\'"><style>'+css+'</style></head>')
    app = (STATIC/'app.js').read_text(encoding='utf-8')
    app = app.replace("'PC에 연결됨'", "'오프라인 파일'")
    app = app.replace("'PC에 저장 중…'", "'답변에 기록 중…'")
    app = app.replace('건 저장했습니다.', '건 답변에 기록했습니다. 상단에서 답변 파일을 저장하세요.')
    app = app.replace('async function exportRecords(){', 'async function originalExportRecords(){')
    # UI handlers now use the bridge's explicit file export, not the legacy DB export.
    packet_json = json.dumps(packet, ensure_ascii=False, separators=(',', ':')).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    scripts = '<script type="application/json" id="portableData">'+packet_json+'</script>'
    for content in [(APP/'portable_core.js').read_text(encoding='utf-8'),
                    (APP/'portable_bridge.js').read_text(encoding='utf-8'), app,
                    'installPortableUI();']:
        scripts += '<script>'+content.replace('</script', '<\\/script')+'</script>'
    return html.replace('</body>', scripts+'</body>')

def build(database=DATA/'reviews.sqlite', output=OUT, dataset=DATA/'dataset.json', ledger=LEDGER):
    WORK.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=WORK) as tmp:
        db = Path(tmp)/'snapshot.sqlite'; snapshot(database, db)
        packet = make_packet(Store(dataset, db, ledger))
    dest = Path(output)/packet['packet_id'][:16]
    dest.mkdir(parents=True, exist_ok=True)
    manifest = dest/'packet.json'
    if manifest.exists():
        if read_json(manifest) != packet: raise ValueError('Packet ID collision')
    else: write_new(manifest, packet)
    # Rebuild the view without overwriting a user's response file.
    (dest/'검토하기.html').write_text(render(packet), encoding='utf-8')
    guide=(APP/'portable_guide.html').read_text(encoding='utf-8').replace('__PACKET_LINK__',dest.name+'/검토하기.html').replace('__PACKET_SHORT__',dest.name).replace('__CARD_COUNT__',str(len(packet['details'])))
    (Path(output)/'시작하기.html').write_text(guide,encoding='utf-8')
    (Path(output)/'LATEST.json').write_text(json.dumps(dict(packet_id=packet['packet_id'],html=dest.name+'/검토하기.html',cards=len(packet['details'])),ensure_ascii=False,indent=2),encoding='utf-8')
    return dict(packet_id=packet['packet_id'], cards=len(packet['details']),
        html=str(dest/'검토하기.html'), manifest=str(manifest))

def ordered_events(events):
    if not isinstance(events,list) or len(events)>20000: raise ValueError('답변 이벤트 개수/형식 오류')
    by_id={}
    for e in events:
        eid=e.get('id') if isinstance(e,dict) else None
        if not isinstance(eid,str) or not 8<=len(eid)<=100: raise ValueError('이벤트 ID 오류')
        if eid in by_id and by_id[eid]!=e: raise ValueError('같은 이벤트 ID에 다른 내용이 있습니다.')
        if e.get('request',{}).get('request_id')!=eid: raise ValueError('요청 ID 불일치')
        by_id[eid]=e
    pending=dict(by_id); done=set(); result=[]
    while pending:
        ready=[]
        for eid,e in pending.items():
            parents=e.get('parents')
            if not isinstance(parents,dict): raise ValueError('부모 판단 정보 누락')
            deps={v for v in parents.values() if v!='base'}
            if not deps.issubset(by_id): raise ValueError('선행 답변이 빠졌습니다. 전체 답변 파일을 사용하세요.')
            if deps.issubset(done): ready.append(eid)
        if not ready: raise ValueError('판단 이력이 순환합니다.')
        for eid in sorted(ready):
            result.append(pending.pop(eid)); done.add(eid)
    return result

def import_responses(store, packet, bundle):
    """Caller chooses a disposable snapshot for preflight or production for apply.

    Entire bundle commits or rolls back. Previously imported IDs remain idempotent.
    Local app and importer share SQLite writer locks, so revisions cannot race.
    """
    check=dict(packet); pid=check.pop('packet_id')
    if digest(check)!=pid: raise ValueError('검토 묶음 정본 해시 불일치')
    if bundle.get('schema')!=SCHEMA or bundle.get('packet_id')!=pid: raise ValueError('다른 묶음의 답변입니다.')
    if packet['dataset_hash']!=store.dataset_hash or packet['legacy_hash']!=store.legacy()[1]:
        raise ValueError('자료 또는 기존 판단 판이 달라졌습니다. 재검토가 필요합니다.')
    events=ordered_events(bundle.get('events'))
    accepted=[]; skipped=[]
    with store.lock,store.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        c.execute('CREATE TABLE IF NOT EXISTS portable_imports(event_uuid TEXT PRIMARY KEY, event_hash TEXT NOT NULL, local_event_id INTEGER NOT NULL, packet_id TEXT NOT NULL, source_event TEXT NOT NULL)')
        for event in events:
            eid=event['id']; eh=digest(event)
            old=c.execute('SELECT event_hash,local_event_id,packet_id FROM portable_imports WHERE event_uuid=?',(eid,)).fetchone()
            if old:
                if old[0]!=eh or old[2]!=pid: raise ValueError('같은 이벤트 ID의 내용 충돌')
                skipped.append(eid); continue
            req=copy.deepcopy(event['request']); ids=req.get('ids')
            if not isinstance(ids,list) or not ids or set(event['parents'])!=set(ids): raise ValueError('대상/부모 목록 오류')
            if req.get('kind') not in ('review','undo'): raise ValueError('지원하지 않는 판단 종류')
            if req.get('dataset_hash')!=packet['dataset_hash'] or req.get('legacy_hash')!=packet['legacy_hash']:
                raise ValueError('이벤트 자료 판 불일치')
            states=store.states(c)
            for oid in ids:
                if oid not in packet['details']: raise ValueError('묶음 밖의 출현')
                state=states.get(oid,dict(revision=0,decision=None))
                parent=event['parents'][oid]
                if parent=='base':
                    baseline=packet['base_states'][oid]
                    if state['revision']!=baseline['revision'] or state['decision']!=baseline['decision'] or state.get('event_id')!=baseline.get('event_id'):
                        raise ValueError('수정 충돌: '+packet['details'][oid]['card']['case_id']+' — 기존 판단과 답변 파일 모두 보존. 이번 파일은 반영하지 않았습니다.')
                else:
                    previous=c.execute('SELECT local_event_id FROM portable_imports WHERE event_uuid=? AND packet_id=?',(parent,pid)).fetchone()
                    if not previous or state.get('event_id')!=previous[0]:
                        raise ValueError('분기 충돌: '+packet['details'][oid]['card']['case_id']+' — 두 답변을 자동으로 합치지 않습니다.')
                if req.get('content_hashes',{}).get(oid)!=packet['details'][oid]['card']['content_hash']:
                    raise ValueError('출현 내용 판 불일치')
            req['revisions']={oid:states.get(oid,{}).get('revision',0) for oid in ids}
            if req['kind']=='undo':
                target=req.get('event_id')
                if any(event['parents'][oid]!=target for oid in ids): raise ValueError('후속 판단을 건너뛴 되돌리기')
                mapped=c.execute('SELECT local_event_id FROM portable_imports WHERE event_uuid=? AND packet_id=?',(target,pid)).fetchone()
                if not mapped: raise ValueError('되돌릴 이벤트가 없습니다.')
                req['event_id']=mapped[0]
            # IDs are namespaced; don't silently reuse a non-portable local request.
            req['request_id']='portable:'+eid
            if c.execute('SELECT 1 FROM events WHERE request_id=?',(req['request_id'],)).fetchone():
                raise ValueError('가져오기 영수증 없이 같은 요청이 존재합니다.')
            result=store.mutate(req,_connection=c)
            c.execute('INSERT INTO portable_imports VALUES(?,?,?,?,?)',(eid,eh,result['event_id'],pid,json.dumps(event,ensure_ascii=False)))
            accepted.append(eid)
    return dict(ok=True,accepted=len(accepted),duplicates=len(skipped),packet_id=pid)

def process_response(path, packet_path, apply=False, dataset=DATA/'dataset.json', database=DATA/'reviews.sqlite', ledger=LEDGER):
    path=Path(path)
    if path.stat().st_size>32*1024*1024: raise ValueError('답변 파일이 너무 큽니다.')
    packet=read_json(packet_path); bundle=read_json(path)
    WORK.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=WORK) as tmp:
        db=Path(tmp)/'check.sqlite'; snapshot(database,db)
        result=import_responses(Store(dataset,db,ledger),packet,bundle)
    result['applied']=False
    if apply:
        backup=ROOT/'work/portable_review_backups'/('before_'+now().replace(':','').replace('.','')+'.sqlite')
        backup.parent.mkdir(parents=True,exist_ok=True); snapshot(database,backup)
        result=import_responses(Store(dataset,database,ledger),packet,bundle);result['applied']=True
    return result

def main():
    parser=argparse.ArgumentParser(description='휴대용 검토 묶음 생성 및 답변 검증/반영')
    sub=parser.add_subparsers(dest='command',required=True)
    b=sub.add_parser('build'); b.add_argument('--output',type=Path,default=OUT)
    b.add_argument('--dataset',type=Path,default=DATA/'dataset.json')
    b.add_argument('--database',type=Path,default=DATA/'reviews.sqlite')
    i=sub.add_parser('import'); i.add_argument('responses',type=Path); i.add_argument('--packet',type=Path,required=True); i.add_argument('--apply',action='store_true')
    i.add_argument('--dataset',type=Path,default=DATA/'dataset.json')
    i.add_argument('--database',type=Path,default=DATA/'reviews.sqlite')
    args=parser.parse_args()
    if args.command=='build': print(json.dumps(build(output=args.output,dataset=args.dataset,database=args.database),ensure_ascii=False)); return
    result=process_response(args.responses,args.packet,args.apply,dataset=args.dataset,database=args.database)
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':
    try: main()
    except (ValueError,Problem,KeyError,TypeError) as e:
        raise SystemExit('답변 반영 중단: '+str(e))
